from __future__ import annotations

import os
import requests
from typing import List, Dict, Optional


class LLMProvider:
    def generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
    ) -> str:
        raise NotImplementedError


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, default_model: Optional[str] = None):
        self.api_key = api_key
        self.default_model = default_model or "claude-3-5-sonnet-latest"

    def generate(self, system_prompt: str, messages: List[Dict[str, str]], model: Optional[str] = None, temperature: float = 0.2) -> str:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": model or self.default_model,
            "max_tokens": 1024,
            "temperature": temperature,
            "system": system_prompt,
            "messages": messages,
        }
        r = requests.post(url, json=payload, headers=headers, timeout=60)
        r.raise_for_status()
        data = r.json()
        # Anthropic returns content list
        content = data.get("content", [])
        if content and isinstance(content, list):
            for part in content:
                if part.get("type") == "text":
                    return part.get("text", "")
        return ""


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, default_model: Optional[str] = None):
        self.api_key = api_key
        self.default_model = default_model or "gpt-4o-mini"

    def generate(self, system_prompt: str, messages: List[Dict[str, str]], model: Optional[str] = None, temperature: float = 0.2) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        oai_msgs = []
        if system_prompt:
            oai_msgs.append({"role": "system", "content": system_prompt})
        oai_msgs.extend(messages)
        payload = {
            "model": model or self.default_model,
            "temperature": temperature,
            "messages": oai_msgs,
        }
        r = requests.post(url, json=payload, headers=headers, timeout=60)
        r.raise_for_status()
        data = r.json()
        choice = (data.get("choices") or [{}])[0]
        return choice.get("message", {}).get("content", "")


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, default_model: Optional[str] = None):
        self.api_key = api_key
        self.default_model = default_model or "gemini-1.5-flash-latest"

    def generate(self, system_prompt: str, messages: List[Dict[str, str]], model: Optional[str] = None, temperature: float = 0.2) -> str:
        mdl = model or self.default_model
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent?key={self.api_key}"
        # Gemini expects a list of contents with role parts
        parts = []
        if system_prompt:
            parts.append({"text": system_prompt})
        for m in messages:
            # collapse into plain text sequence
            parts.append({"text": f"{m.get('role')}: {m.get('content')}"})
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": parts,
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 1024,
            },
        }
        r = requests.post(url, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        cands = data.get("candidates") or []
        if cands:
            parts = cands[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "")
        return ""


def make_provider(name: str, anthropic_key: Optional[str], openai_key: Optional[str], gemini_key: Optional[str], default_model: Optional[str] = None) -> LLMProvider:
    key = name.strip().lower()
    if key in ("anthropic", "claude"):
        if not anthropic_key:
            raise ValueError("ANTHROPIC_API_KEY fehlt.")
        return AnthropicProvider(anthropic_key, default_model)
    if key in ("openai", "oai"):
        if not openai_key:
            raise ValueError("OPENAI_API_KEY fehlt.")
        return OpenAIProvider(openai_key, default_model)
    if key in ("gemini", "google"):
        if not gemini_key:
            raise ValueError("GEMINI_API_KEY fehlt.")
        return GeminiProvider(gemini_key, default_model)
    raise ValueError(f"Unbekannter Provider: {name}")

