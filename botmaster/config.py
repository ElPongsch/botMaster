"""Configuration for botMaster v2.0 - Agent Orchestrator"""
import os
from dataclasses import dataclass
from pathlib import Path


def _bool(val: str | None, default: bool = False) -> bool:
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass
class Settings:
    # Telegram
    telegram_bot_token: str | None
    telegram_chat_id: str | None

    # Storage - MariaDB (primary) + OpenMemory (semantic)
    mariadb_host: str
    mariadb_port: int
    mariadb_user: str
    mariadb_password: str
    mariadb_database: str

    # OpenMemory MCP
    openmemory_url: str
    openmemory_user_id: str
    openmemory_api_key: str

    # LLM Providers (for spawned agents)
    anthropic_api_key: str | None
    openai_api_key: str | None
    gemini_api_key: str | None

    # Agent orchestration
    data_dir: Path
    project_dirs: list[Path]
    system_prompt: str
    max_context_messages: int
    enable_telegram_polling: bool

    # CLI bins for spawned agents
    claude_flow_bin: str
    gemini_bin: str
    cursor_agent_bin: str  # via WSL
    claude_cli_bin: str    # for nested claude


def load_settings() -> Settings:
    data_dir = Path(os.getenv("BM_DATA_DIR", Path.cwd() / "botMaster_data")).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    # Project discovery
    project_dirs_env = os.getenv(
        "BM_PROJECT_DIRS",
        r"C:\myFolder\Port\projects\privat;C:\myFolder\Port\projects\oel-ass;C:\myFolder\Port\myTools",
    )
    project_dirs = [Path(p.strip()) for p in project_dirs_env.split(";") if p.strip()]

    return Settings(
        # Telegram
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),

        # MariaDB
        mariadb_host=os.getenv("BM_MARIADB_HOST", "localhost"),
        mariadb_port=int(os.getenv("BM_MARIADB_PORT", "3306")),
        mariadb_user=os.getenv("BM_MARIADB_USER", "mcp_admin"),
        mariadb_password=os.getenv("BM_MARIADB_PASSWORD", "mcp_admin_password"),
        mariadb_database=os.getenv("BM_MARIADB_DATABASE", "task_log_db"),

        # OpenMemory
        openmemory_url=os.getenv("BM_OPENMEMORY_URL", "http://localhost:8765/sse"),
        openmemory_user_id=os.getenv("BM_OPENMEMORY_USER", "markus"),
        openmemory_api_key=os.getenv("BM_OPENMEMORY_API_KEY", "local-dev-key"),

        # LLM Providers
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        gemini_api_key=os.getenv("GEMINI_API_KEY"),

        # Agent orchestration
        data_dir=data_dir,
        project_dirs=project_dirs,
        system_prompt=os.getenv(
            "BM_SYSTEM_PROMPT",
            (
                "Du bist botMaster v2.0 - Agent Orchestrator. "
                "Du koordinierst claude-flow, gemini, cursor-agent und nested-claude für Arbeitsprojekte. "
                "Nutze MariaDB für State-Tracking und OpenMemory für Context-Memory. "
                "Halte Markus per Telegram auf dem Laufenden."
            ),
        ),
        max_context_messages=int(os.getenv("BM_MAX_CONTEXT_MESSAGES", "20")),
        enable_telegram_polling=_bool(os.getenv("BM_ENABLE_TELEGRAM_POLLING", "1")),

        # CLI bins
        claude_flow_bin=os.getenv("BM_CLAUDE_FLOW_BIN", "claude-flow"),
        gemini_bin=os.getenv("BM_GEMINI_BIN", "gemini"),
        cursor_agent_bin=os.getenv("BM_CURSOR_AGENT_BIN", "wsl cursor-agent"),
        claude_cli_bin=os.getenv("BM_CLAUDE_CLI_BIN", "claude"),
    )
