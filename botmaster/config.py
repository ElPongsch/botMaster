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

    # LLM providers
    anthropic_api_key: str | None
    openai_api_key: str | None
    gemini_api_key: str | None
    default_provider: str
    default_model: str | None
    provider_cmd: str | None
    provider_timeout_sec: int

    # Storage
    data_dir: Path
    db_url: str

    # Projects discovery (semicolon separated)
    project_dirs: list[Path]

    # Agent
    system_prompt: str
    max_context_messages: int
    enable_telegram_polling: bool


def load_settings() -> Settings:
    data_dir = Path(os.getenv("BM_DATA_DIR", Path.cwd() / "botMaster_data")).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    # DB: default SQLite file; allow MariaDB via URL env
    db_url = os.getenv("BM_DB_URL")
    if not db_url:
        db_file = data_dir / "botmaster.db"
        db_url = f"sqlite:///{db_file.as_posix()}"

    project_dirs_env = os.getenv(
        "BM_PROJECT_DIRS",
        # sensible Windows defaults per user description
        r"C:\myFolder\Port\projects;C:\myFolder\Port\myTools;C:\myFolder\Port\myTools\toolbox",
    )
    project_dirs = [Path(p.strip()) for p in project_dirs_env.split(";") if p.strip()]

    return Settings(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        default_provider=os.getenv("BM_DEFAULT_PROVIDER", "anthropic"),
        default_model=os.getenv("BM_DEFAULT_MODEL"),
        provider_cmd=os.getenv("BM_PROVIDER_CMD"),
        provider_timeout_sec=int(os.getenv("BM_PROVIDER_TIMEOUT", "90")),
        data_dir=data_dir,
        db_url=db_url,
        project_dirs=project_dirs,
        system_prompt=os.getenv(
            "BM_SYSTEM_PROMPT",
            (
                "Du bist ein Headless CLI LLM Orchestrator (botMaster). "
                "Starte Spezialisten-Agenten für konkrete Projekte, halte mich per Telegram auf dem Laufenden, "
                "und frage gezielt nach, wenn Entscheidungen nötig sind."
            ),
        ),
        max_context_messages=int(os.getenv("BM_MAX_CONTEXT_MESSAGES", "20")),
        enable_telegram_polling=_bool(os.getenv("BM_ENABLE_TELEGRAM_POLLING", "1")),
    )
