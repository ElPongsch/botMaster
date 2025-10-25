# botMaster v2.0 - Agent Orchestrator

Multi-agent orchestration platform for coordinating claude-flow, gemini, cursor-agent, and nested-claude CLI tools for work project management.

## Architecture

- **MariaDB**: Primary state tracking (sessions, messages, decisions)
- **OpenMemory**: Semantic memory for context (degraded mode acceptable due to API bugs)
- **Telegram Bot**: User interface for orchestration
- **Agent Spawner**: CLI process management and output capture

## Components

```
botmaster/
├── config.py              # Configuration management
├── mariadb_storage.py     # Database client (CRUD operations)
├── openmemory_client.py   # Semantic memory client (HTTP API)
├── agent_spawner.py       # CLI agent process spawning
├── orchestrator.py        # Main coordination logic
├── telegram_client.py     # Telegram bot interface
└── __init__.py           # Package exports
```

## Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment** (copy `.env.example` to `.env` and edit):
   - Telegram bot token & chat ID
   - MariaDB credentials
   - OpenMemory URL
   - CLI binary paths

3. **Import database schema**:
   ```bash
   python import_schema.py
   ```

4. **Run orchestrator**:
   ```bash
   python main.py
   ```

## Usage

### Via Telegram

Once running, interact with botMaster via Telegram:

```
/status - Show active agents
/help - Show help message
```

Or just send your task:
```
"Build a REST API for user management in Python"
```

botMaster will decide which agent to spawn and track execution.

### Programmatic

```python
from botmaster import load_settings, Orchestrator

settings = load_settings()
orchestrator = Orchestrator(settings)

# Process a request
response = orchestrator.process_request("What is 2+2?")
print(response)

# Get status
status = orchestrator.get_status()
print(status)
```

## Agent Selection Logic

- **claude-flow**: Python/backend/API/database work (swarm intelligence)
- **gemini**: Quick queries and simple checks (fast, free tier)
- **cursor-agent**: Cursor IDE specific tasks (via WSL)
- **nested-claude**: General tasks and analysis (JSON output)

## Database Schema

### agent_sessions
Tracks active/completed agent sessions with status, PIDs, output logs.

### agent_messages
Cross-agent communication queue (for future multi-agent coordination).

### orchestration_decisions
Logs allocation decisions with reasoning and outcomes (for learning).

## Status

**v2.0.0** - Initial implementation

- ✅ MariaDB state tracking
- ✅ Agent spawning (all 4 CLI tools)
- ✅ Telegram bot interface
- ✅ Decision logging
- ⚠️ OpenMemory (degraded mode - API bugs)

## Development

Run tests:
```bash
python test_mariadb_storage.py
python test_openmemory_client.py
python test_agent_spawner.py
```

## Known Issues

- OpenMemory API has validation bugs (422 errors) - degraded mode acceptable
- WSL required for cursor-agent on Windows
- Some agent tools require specific auth setup (see global CLAUDE.md)

## Future Enhancements

- Multi-agent coordination (agent-to-agent messaging)
- LLM-based decision making (replace rule-based allocation)
- OpenMemory MCP SSE upgrade (when API stable)
- Web UI dashboard
- Agent conversation history
- Cost tracking per agent
