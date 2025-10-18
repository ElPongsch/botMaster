from __future__ import annotations

import os
import requests
from typing import List, Dict, Optional
import subprocess
import json
import shlex
import sys
import threading
import time


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


class CommandProvider(LLMProvider):
    """
    Executes a user-specified command and exchanges a simple JSON payload via stdin/stdout.
    - Input JSON: { system, messages, model, temperature }
    - Output: either JSON with { text } or plain text on stdout.
    """

    def __init__(self, command: str, timeout_sec: int = 90):
        self.command = command
        self.timeout_sec = timeout_sec

    def generate(self, system_prompt: str, messages: List[Dict[str, str]], model: Optional[str] = None, temperature: float = 0.2) -> str:
        payload = {
            "system": system_prompt,
            "messages": messages,
            "model": model,
            "temperature": temperature,
        }
        try:
            # Windows-friendly: use shell=True for command strings the user provides
            proc = subprocess.run(
                self.command,
                input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout_sec,
                shell=True,
            )
        except subprocess.TimeoutExpired:
            return "[CommandProvider Timeout]"
        if proc.returncode != 0:
            err = proc.stderr.decode(errors="ignore")
            return f"[CommandProvider Error {proc.returncode}] {err.strip()}"
        out = proc.stdout.decode("utf-8", errors="ignore").strip()
        # Try JSON first
        try:
            obj = json.loads(out)
            if isinstance(obj, dict) and "text" in obj:
                return str(obj["text"]) or ""
        except Exception:
            pass
        return out


class ClaudeCLIStreamProvider(LLMProvider):
    """
    Spawns `claude` CLI in stream-json mode with a persistent session.
    - Writes JSONL user messages to stdin, reads assistant messages from stdout JSONL.
    - Supports MCP via --mcp-config and working directory (project path).
    - Optionally prepends instructions on first message by sending a combined user content.
    """

    def __init__(self, claude_bin: str = "claude", mcp_config_path: Optional[str] = None, cwd: Optional[str] = None, instructions: Optional[str] = None, session_id: Optional[str] = None):
        self.claude_bin = claude_bin
        self.mcp_config_path = mcp_config_path
        self.cwd = cwd
        self.instructions = instructions
        self._proc: Optional[subprocess.Popen] = None
        self._buf_lock = threading.Lock()
        self._started = False
        self._first_message_sent = False
        self._session_id = session_id or str(int(time.time()*1000))

    def _ensure_started(self):
        if self._started and self._proc and self._proc.poll() is None:
            return
        args = [
            "-p",
            "--verbose",
            "--output-format", "stream-json",
            "--input-format", "stream-json",
            "--replay-user-messages",
            "--session-id", self._session_id,
            "--dangerously-skip-permissions",
        ]
        if self.mcp_config_path:
            args += ["--mcp-config", self.mcp_config_path]
        cmd = [self.claude_bin] + args
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.cwd or None,
            shell=True,
        )
        self._started = True

    def generate(self, system_prompt: str, messages: List[Dict[str, str]], model: Optional[str] = None, temperature: float = 0.2) -> str:
        self._ensure_started()
        if not self._proc or not self._proc.stdin or not self._proc.stdout:
            return "[claude-cli not running]"

        # Build user content; prepend instructions once if available
        user_content = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_content = m.get("content", "")
                break
        if self.instructions and not self._first_message_sent:
            content = f"{self.instructions}\n\n---\n\nUser message:\n{user_content}"
            self._first_message_sent = True
        else:
            content = user_content

        obj = {
            "type": "user",
            "message": {"role": "user", "content": content},
            "session_id": self._session_id,
        }
        line = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        self._proc.stdin.write(line)
        self._proc.stdin.flush()

        # Read lines until we get an assistant message or timeout
        start = time.time()
        timeout = 90.0
        text_parts: List[str] = []
        while time.time() - start < timeout:
            line = self._proc.stdout.readline()
            if not line:
                time.sleep(0.05)
                continue
            s = line.decode("utf-8", errors="ignore").strip()
            if not s:
                continue
            try:
                msg = json.loads(s)
            except Exception:
                continue
            typ = msg.get("type") or msg.get("message", {}).get("role")
            if typ in ("assistant",):
                content = msg.get("message", {}).get("content") or msg.get("content") or ""
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                elif isinstance(content, str):
                    text_parts.append(content)
                # We keep reading to accumulate chunks for a short period, then break
                if time.time() - start > 2.0:
                    break
        return "".join(text_parts) or ""


def make_provider(name: str, anthropic_key: Optional[str], openai_key: Optional[str], gemini_key: Optional[str], default_model: Optional[str] = None, provider_cmd: Optional[str] = None, provider_timeout_sec: int = 90, *, claude_cli_bin: Optional[str] = None, mcp_config_path: Optional[str] = None, cwd: Optional[str] = None, instructions: Optional[str] = None) -> LLMProvider:
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
    if key in ("cmd", "local", "claude-code", "cursor"):
        if not provider_cmd:
            raise ValueError("BM_PROVIDER_CMD fehlt für lokalen/headless Provider.")
        return CommandProvider(provider_cmd, timeout_sec=provider_timeout_sec)
    if key in ("claude-cli", "claude-flow"):
        return ClaudeCLIStreamProvider(claude_bin=claude_cli_bin or "claude", mcp_config_path=mcp_config_path, cwd=cwd, instructions=instructions)
    raise ValueError(f"Unbekannter Provider: {name}")
