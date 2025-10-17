"""
MCP Server Stub (Telegram Tool)

Ziel: Einen MCP-Server anbieten, der ein Tool `telegram.send` bereitstellt.

Umsetzung (Stub): Hier nur die Schnittstelle als Platzhalter, damit
die künftige Integration mit einem echten MCP-SDK (Node/TS oder Python)
geplant werden kann. Der eigentliche MCP-Server sollte am besten mit dem
offiziellen MCP SDK (z. B. TypeScript) umgesetzt werden.
"""

from __future__ import annotations

import sys
from ..botmaster.config import load_settings
from ..botmaster.telegram_client import TelegramClient, TelegramConfig


def run_stub(argv: list[str]) -> int:
    settings = load_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        print("Telegram nicht konfiguriert (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID)", file=sys.stderr)
        return 2
    tg = TelegramClient(TelegramConfig(settings.telegram_bot_token, settings.telegram_chat_id))
    # In einem echten MCP-Server würde hier die JSON-RPC/Wire-Protocol-Schleife laufen.
    # Für den Stub unterstützen wir nur: telegram_server_stub send "Nachricht"
    if len(argv) >= 3 and argv[1] == "send":
        msg = " ".join(argv[2:])
        tg.send_message(msg)
        print("OK")
        return 0
    print("Benutzung: telegram_server_stub send <Nachricht>")
    return 1


if __name__ == "__main__":
    raise SystemExit(run_stub(sys.argv))

