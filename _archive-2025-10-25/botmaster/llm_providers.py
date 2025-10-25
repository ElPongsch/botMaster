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
import queue
import uuid


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

    def __init__(self, claude_bin: str = "claude", mcp_config_path: Optional[str] = None, cwd: Optional[str] = None, instructions: Optional[str] = None, session_id: Optional[str] = None, response_timeout: float = 120.0):
        # claude_bin may be a full command string, e.g. "wsl -e claude"
        self.claude_bin = claude_bin
        self.mcp_config_path = mcp_config_path
        self.cwd = cwd
        self.instructions = instructions
        self.response_timeout = response_timeout
        self._proc: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._started = False
        self._first_message_sent = False
        self._session_id = session_id or str(uuid.uuid4())
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._lock = threading.Lock()
        self._last_error: Optional[str] = None
        self._ready_event = threading.Event()

    def _ensure_started(self):
        if self._started and self._proc and self._proc.poll() is None:
            return
        args = [
            self.claude_bin,
            "-p",
            "--verbose",
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--session-id",
            self._session_id,
            "--dangerously-skip-permissions",
        ]
        if self.mcp_config_path:
            args += ["--mcp-config", self.mcp_config_path]

        parts = args
        command = " ".join(shlex.quote(p) for p in parts)

        self._proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.cwd or None,
            shell=True,
        )
        self._started = True
        self._reader_thread = threading.Thread(target=self._reader, name="claude-cli-reader", daemon=True)
        self._reader_thread.start()
        self._stderr_thread = threading.Thread(target=self._stderr_reader, name="claude-cli-stderr", daemon=True)
        self._stderr_thread.start()

    def _reader(self):
        while True:
            if not self._proc:
                break
            try:
                line = self._proc.stdout.readline()
            except Exception:
                break
            if not line:
                if self._proc.poll() is not None:
                    break
                time.sleep(0.05)
                continue
            text_line = line.decode("utf-8", errors="ignore").strip()
            if not text_line:
                continue
            try:
                msg = json.loads(text_line)
            except Exception:
                continue
            typ = msg.get("type") or msg.get("message", {}).get("role")
            if typ == "system" and msg.get("subtype") == "init":
                self._ready_event.set()
            if typ in ("assistant", "assistant_message"):
                content = msg.get("message", {}).get("content") or msg.get("content") or ""
                text = self._content_to_text(content)
                if text:
                    self._queue.put(text)
            elif typ == "assistant_delta":
                delta = msg.get("delta") or msg.get("message", {}).get("delta") or {}
                text = self._content_to_text(delta.get("content"))
                if text:
                    self._queue.put(text)
            elif typ == "error":
                self._last_error = str(msg.get("error") or msg)
                self._queue.put(f"[claude-cli error] {self._last_error}")

    def _stderr_reader(self):
        while True:
            if not self._proc:
                break
            try:
                line = self._proc.stderr.readline()
            except Exception:
                break
            if not line:
                if self._proc.poll() is not None:
                    break
                time.sleep(0.05)
                continue
            text = line.decode("utf-8", errors="ignore").strip()
            if text:
                self._last_error = text

    def _content_to_text(self, content) -> str:
        if not content:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(block.get("text", ""))
            return "".join(parts)
        if isinstance(content, dict) and content.get("type") == "text":
            return content.get("text", "")
        return str(content)

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
        payload = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        with self._lock:
            # Flush queue before sending new message
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
            try:
                self._proc.stdin.write(payload)
                self._proc.stdin.flush()
            except Exception as exc:
                return f"[claude-cli write error] {exc}"

        parts: List[str] = []
        deadline = time.time() + self.response_timeout
        while time.time() < deadline:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            try:
                chunk = self._queue.get(timeout=min(remaining, 5.0))
            except queue.Empty:
                continue
            parts.append(chunk)
            # Gather additional chunks briefly for smoother output
            gather_deadline = time.time() + 0.5
            while time.time() < gather_deadline:
                try:
                    more = self._queue.get(timeout=0.1)
                    parts.append(more)
                except queue.Empty:
                    break
            break

        if parts:
            return "".join(parts)
        if self._last_error:
            return f"[claude-cli stderr] {self._last_error}"
        if self._proc and self._proc.poll() is not None:
            return f"[claude-cli exited {self._proc.returncode}]"
        return "[claude-cli timeout]"


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
