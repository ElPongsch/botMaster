from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

import requests


@dataclass
class TelegramConfig:
    token: str
    chat_id: str


class TelegramClient:
    def __init__(self, cfg: TelegramConfig):
        self.cfg = cfg
        self.base = f"https://api.telegram.org/bot{cfg.token}"
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._offset = 0

    def send_message(self, text: str, reply_markup: dict | None = None) -> None:
        url = f"{self.base}/sendMessage"
        payload = {
            "chat_id": self.cfg.chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()

    def start_polling(self, on_message: Callable[[str, dict], None], poll_interval: float = 1.5, on_callback: Optional[Callable[[str, dict, Callable[[], None]], None]] = None) -> None:
        if self._thread and self._thread.is_alive():
            return

        def _run():
            while not self._stop.is_set():
                try:
                    updates = self._get_updates()
                    for upd in updates:
                        self._offset = max(self._offset, upd.get("update_id", 0) + 1)
                        # Handle callback queries (inline keyboard)
                        if on_callback and upd.get("callback_query"):
                            cq = upd["callback_query"]
                            data = cq.get("data", "")
                            chat_id = cq.get("message", {}).get("chat", {}).get("id")
                            if str(chat_id) == str(self.cfg.chat_id):
                                def ack():
                                    try:
                                        self._answer_callback_query(cq.get("id"))
                                    except Exception:
                                        pass
                                on_callback(data, cq, ack)
                            continue

                        msg = upd.get("message") or upd.get("edited_message")
                        if msg and str(msg.get("chat", {}).get("id")) == str(self.cfg.chat_id):
                            text = msg.get("text", "")
                            on_message(text, msg)
                except Exception:
                    # keep alive, minimal error handling here
                    pass
                time.sleep(poll_interval)

        self._stop.clear()
        self._thread = threading.Thread(target=_run, name="tg-poll", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _get_updates(self):
        url = f"{self.base}/getUpdates"
        params = {"offset": self._offset, "timeout": 20}
        r = requests.get(url, params=params, timeout=35)
        r.raise_for_status()
        data = r.json()
        return data.get("result", [])

    def _answer_callback_query(self, callback_query_id: str):
        url = f"{self.base}/answerCallbackQuery"
        r = requests.post(url, json={"callback_query_id": callback_query_id}, timeout=15)
        r.raise_for_status()
