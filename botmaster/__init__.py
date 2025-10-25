"""botMaster v2.0 - Agent Orchestration Platform"""
__version__ = "2.0.0"

from .config import Settings, load_settings
from .orchestrator import Orchestrator
from .agent_spawner import AgentSpawner, AgentSession
from .mariadb_storage import MariaDBStorage
from .openmemory_client import OpenMemoryClient
from .telegram_client import TelegramClient, TelegramConfig

__all__ = [
    "Settings",
    "load_settings",
    "Orchestrator",
    "AgentSpawner",
    "AgentSession",
    "MariaDBStorage",
    "OpenMemoryClient",
    "TelegramClient",
    "TelegramConfig",
]
