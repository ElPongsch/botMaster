"""botMaster v2.0 Orchestrator - Main coordination logic"""
import logging
from typing import Callable
from datetime import datetime

from .config import Settings
from .mariadb_storage import MariaDBStorage
from .openmemory_client import OpenMemoryClient
from .agent_spawner import AgentSpawner, AgentTool
from .telegram_client import TelegramClient

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Main orchestration engine for botMaster v2.0

    Coordinates multiple CLI agents (claude-flow, gemini, cursor-agent, nested-claude)
    for work project management, with state tracking in MariaDB and semantic memory
    in OpenMemory.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

        # Initialize storage
        self.storage = MariaDBStorage(
            host=settings.mariadb_host,
            port=settings.mariadb_port,
            user=settings.mariadb_user,
            password=settings.mariadb_password,
            database=settings.mariadb_database
        )

        # Initialize OpenMemory (degraded mode acceptable)
        self.memory = OpenMemoryClient(
            base_url=settings.openmemory_url,
            user_id=settings.openmemory_user_id,
            api_key=settings.openmemory_api_key
        )

        # Initialize agent spawner
        self.spawner = AgentSpawner(
            storage=self.storage,
            claude_flow_bin=settings.claude_flow_bin,
            gemini_bin=settings.gemini_bin,
            cursor_agent_bin=settings.cursor_agent_bin,
            claude_cli_bin=settings.claude_cli_bin
        )

        # Initialize Telegram bot (optional)
        self.telegram: TelegramClient | None = None
        if settings.telegram_bot_token and settings.telegram_chat_id:
            from .telegram_client import TelegramConfig
            self.telegram = TelegramClient(
                cfg=TelegramConfig(
                    token=settings.telegram_bot_token,
                    chat_id=settings.telegram_chat_id
                )
            )

        logger.info("Orchestrator initialized")

    def process_request(self, user_input: str) -> str:
        """
        Process a user request and orchestrate appropriate agents

        Args:
            user_input: User's task/request

        Returns:
            Response message
        """
        logger.info(f"Processing request: {user_input[:60]}...")

        # Analyze request and decide which agent(s) to use
        decision = self._decide_agent_allocation(user_input)

        # Log decision
        decision_id = self.storage.log_decision(
            project="user_request",
            decision=f"Allocate to {decision['agent']} for: {user_input[:60]}",
            decision_type="agent_spawn",
            reasoning=decision["reasoning"]
        )

        # Spawn agent
        try:
            session_id = self.spawner.spawn_agent(
                tool_name=decision["agent"],
                task=user_input,
                project_name="user_request"
            )

            response = (
                f"Agent {decision['agent']} spawned for your request.\n"
                f"Session ID: {session_id}\n"
                f"Reasoning: {decision['reasoning']}"
            )

            # Update decision outcome
            self.storage.update_decision_outcome(
                decision_id=decision_id,
                outcome="success"
            )

            return response

        except Exception as e:
            logger.error(f"Failed to spawn agent: {e}")

            # Update decision outcome
            self.storage.update_decision_outcome(
                decision_id=decision_id,
                outcome="failed"
            )

            return f"Failed to spawn agent: {e}"

    def _decide_agent_allocation(self, task: str) -> dict[str, str]:
        """
        Decide which agent is best suited for a task

        Args:
            task: Task description

        Returns:
            Dict with 'agent' and 'reasoning'
        """
        task_lower = task.lower()

        # Check for relevant context from memory (degraded mode OK)
        context = self.memory.get_relevant_context(task, limit=3)
        logger.debug(f"Found {len(context)} relevant memories for task")

        # Simple rule-based allocation (can be enhanced with LLM later)
        if any(word in task_lower for word in ["python", "backend", "api", "database"]):
            return {
                "agent": "claude-flow",
                "reasoning": "Python/backend work best suited for claude-flow swarm intelligence"
            }

        elif any(word in task_lower for word in ["quick", "simple", "check", "what is"]):
            return {
                "agent": "gemini",
                "reasoning": "Quick query best handled by fast gemini CLI"
            }

        elif any(word in task_lower for word in ["cursor", "ide", "editor"]):
            return {
                "agent": "cursor-agent",
                "reasoning": "Cursor-specific task"
            }

        else:
            # Default to nested-claude for general tasks
            return {
                "agent": "nested-claude",
                "reasoning": "General task, using nested claude for analysis"
            }

    def get_status(self) -> str:
        """Get current orchestrator status"""
        active_sessions = self.storage.list_active_sessions()

        status = f"botMaster v2.0 Status ({datetime.now().strftime('%H:%M:%S')})\n"
        status += f"Active agents: {len(active_sessions)}\n\n"

        if active_sessions:
            for session in active_sessions:
                status += (
                    f"- {session['tool_name']} ({session['session_id'][:12]}...)\n"
                    f"  Task: {session['current_task'][:50] if session['current_task'] else 'N/A'}...\n"
                    f"  Uptime: {session['uptime_seconds']}s\n\n"
                )
        else:
            status += "No active agents.\n"

        return status

    def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up orchestrator...")
        self.spawner.cleanup_finished_sessions()
        self.storage.close_all()

    def start_telegram_bot(self):
        """Start Telegram bot for user interaction"""
        if not self.telegram:
            logger.warning("Telegram not configured, skipping bot start")
            return

        logger.info("Starting Telegram bot...")

        def on_message(text: str, msg: dict):
            """Handle incoming Telegram message"""
            logger.info(f"Telegram message: {text}")

            # Handle commands
            if text.startswith("/status"):
                status = self.get_status()
                self.telegram.send_message(status)

            elif text.startswith("/help"):
                help_text = (
                    "botMaster v2.0 - Agent Orchestrator\n\n"
                    "Commands:\n"
                    "/status - Show active agents\n"
                    "/help - Show this help\n\n"
                    "Just send your task and I'll orchestrate the right agent!"
                )
                self.telegram.send_message(help_text)

            else:
                # Process as regular request
                response = self.process_request(text)
                self.telegram.send_message(response)

        def on_callback(data: str, callback_query: dict):
            """Handle callback button presses"""
            logger.info(f"Callback: {data}")
            # Handle callbacks as needed

        # Start polling
        self.telegram.send_message("botMaster v2.0 Orchestrator online!")
        self.telegram.start_polling(
            on_message=on_message,
            on_callback=on_callback,
            cleanup=self.cleanup
        )
