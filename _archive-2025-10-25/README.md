**botMaster**

- Headless CLI LLM Orchestrator mit Telegram-Integration
- Spawnt pro Projekt spezialisierte Agenten, loggt alles und leitet Rückfragen an Telegram weiter
- Telegram: entweder Direktaufruf (`botmaster-send`) oder später via MCP-Server-Tool

Setup

- Python 3.10+
- `.env` mit `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, optional API Keys (Anthropic/OpenAI/Gemini)
- Headless ohne Keys: `BM_DEFAULT_PROVIDER=cmd` setzen und `BM_PROVIDER_CMD` auf deinen lokalen Headless‑Bridge‑Befehl zeigen lassen
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

- HTTP: Anthropic (Claude), OpenAI, Gemini
- Headless (ohne API Keys): `BM_DEFAULT_PROVIDER=cmd` mit `BM_PROVIDER_CMD`
  - botMaster schreibt JSON auf stdin: `{ system, messages, model, temperature }`
  - Dein Command gibt entweder `{ "text": "Antwort" }` (JSON) oder Plain‑Text auf stdout zurück
  - Beispiele:
    - Windows PowerShell zu Node‑Script: `BM_PROVIDER_CMD=node C:\\…\\taskagent\\cli.js`
    - PowerShell Wrapper: `BM_PROVIDER_CMD=pwsh -NoProfile -File C:\\…\\bridge.ps1`
  - Aliase: `claude-code`, `cursor`, `local` mappen ebenfalls auf den Command‑Provider

MCP

- Unter `mcp/telegram_server_stub.py` existiert ein Stub. Geplant ist ein echtes MCP-Server-Tool `telegram.send` mit dem offiziellen SDK.
  - Falls dein MCP‑Server bereits ein Completion/Respond‑Tool anbietet, kann `BM_PROVIDER_CMD` einen MCP‑Client aufrufen, der stdin‑JSON entgegennimmt und die Antwort auf stdout schreibt.

Hinweise

- Die Projektverzeichnisse sind per Env `BM_PROJECT_DIRS` konfigurierbar (Windows-Pfade sind vorbelegt).
- Logs/Ereignisse und Konversationen werden in der DB gespeichert.
