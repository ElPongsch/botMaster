**botMaster**

- Headless CLI LLM Orchestrator mit Telegram-Integration
- Spawnt pro Projekt spezialisierte Agenten, loggt alles und leitet Rückfragen an Telegram weiter
- Telegram: entweder Direktaufruf (`botmaster-send`) oder später via MCP-Server-Tool

Setup

- Python 3.10+
- `.env` mit `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, optional API Keys (Anthropic/OpenAI/Gemini)
- `pip install -e .`

CLI

- `botmaster projects` zeigt automatisch erkannte Projekte (aus `BM_PROJECT_DIRS`)
- `botmaster-daemon` startet den Orchestrator und Telegram-Polling
- `botmaster-send "Nachricht"` sendet eine Nachricht direkt an Telegram

Telegram Befehle

- `/agents` listet bekannte/aktive Agenten
- `/new <project_key> [name]` spawnt einen neuen Agenten
- `/to <id> <text>` sendet Text an Agent `id`
- `/stop <id>` stoppt den Agenten

Storage

- Standard: SQLite unter `botMaster_data/botmaster.db`
- MariaDB: vorbereitet über `BM_DB_URL` (Implementierung für v0.1 noch auf SQLite — Migration möglich)

Provider

- Standard: Anthropic (Claude) via HTTP API
- Optional: OpenAI, Gemini (einfaches HTTP-Interface)

MCP

- Unter `mcp/telegram_server_stub.py` existiert ein Stub. Geplant ist ein echtes MCP-Server-Tool `telegram.send` mit dem offiziellen SDK.

Hinweise

- Die Projektverzeichnisse sind per Env `BM_PROJECT_DIRS` konfigurierbar (Windows-Pfade sind vorbelegt).
- Logs/Ereignisse und Konversationen werden in der DB gespeichert.

