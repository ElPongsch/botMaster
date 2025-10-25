"""Agent spawner for botMaster v2.0 - spawn and manage CLI agents"""
import subprocess
import threading
import uuid
from datetime import datetime
from typing import Literal
import logging

from .mariadb_storage import MariaDBStorage

logger = logging.getLogger(__name__)

AgentTool = Literal["claude-flow", "gemini", "cursor-agent", "nested-claude"]


class AgentSession:
    """Represents a running agent session"""

    def __init__(
        self,
        session_id: str,
        tool_name: AgentTool,
        process: subprocess.Popen,
        project_path: str | None = None,
        project_name: str | None = None,
        task: str | None = None
    ):
        self.session_id = session_id
        self.tool_name = tool_name
        self.process = process
        self.project_path = project_path
        self.project_name = project_name
        self.task = task
        self.output_buffer: list[str] = []
        self._output_thread: threading.Thread | None = None

    def start_output_capture(self):
        """Start capturing stdout/stderr in background thread"""
        def capture():
            try:
                if self.process.stdout:
                    for line in iter(self.process.stdout.readline, ''):
                        if not line:
                            break
                        self.output_buffer.append(line)
                        logger.debug(f"[{self.session_id[:8]}] {line.rstrip()}")
            except Exception as e:
                logger.error(f"Output capture error for {self.session_id}: {e}")

        self._output_thread = threading.Thread(target=capture, daemon=True)
        self._output_thread.start()

    def get_output(self, max_lines: int = 100) -> str:
        """Get recent output from buffer"""
        return ''.join(self.output_buffer[-max_lines:])

    def is_running(self) -> bool:
        """Check if process is still running"""
        return self.process.poll() is None

    def get_status(self) -> str:
        """Get current status"""
        if self.is_running():
            return "running"
        elif self.process.returncode == 0:
            return "completed"
        elif self.process.returncode is not None:
            return "failed"
        return "unknown"

    def terminate(self):
        """Terminate the process gracefully"""
        if self.is_running():
            logger.info(f"Terminating session {self.session_id}")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning(f"Process {self.session_id} didn't terminate, killing...")
                self.process.kill()


class AgentSpawner:
    """Spawns and manages CLI agent processes"""

    def __init__(
        self,
        storage: MariaDBStorage,
        claude_flow_bin: str = "claude-flow",
        gemini_bin: str = "gemini",
        cursor_agent_bin: str = "wsl cursor-agent",
        claude_cli_bin: str = "claude"
    ):
        self.storage = storage
        self.cli_bins = {
            "claude-flow": claude_flow_bin,
            "gemini": gemini_bin,
            "cursor-agent": cursor_agent_bin,
            "nested-claude": claude_cli_bin
        }
        self.active_sessions: dict[str, AgentSession] = {}

    def spawn_agent(
        self,
        tool_name: AgentTool,
        task: str,
        project_path: str | None = None,
        project_name: str | None = None,
        auto_approve: bool = False
    ) -> str:
        """
        Spawn a new agent for a task

        Args:
            tool_name: Which CLI tool to use
            task: Task description/prompt
            project_path: Optional project directory
            project_name: Optional project name
            auto_approve: Whether to enable auto-approval mode

        Returns:
            Session ID
        """
        session_id = f"{tool_name}_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%H%M%S')}"

        # Build command based on tool
        cmd = self._build_command(tool_name, task, project_path, auto_approve)

        logger.info(f"Spawning {tool_name} for task: {task[:60]}...")
        logger.debug(f"Command: {' '.join(cmd)}")

        try:
            # Spawn process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # Line buffered
                cwd=project_path
            )

            # Create session
            session = AgentSession(
                session_id=session_id,
                tool_name=tool_name,
                process=process,
                project_path=project_path,
                project_name=project_name,
                task=task
            )

            # Start output capture
            session.start_output_capture()

            # Store in active sessions
            self.active_sessions[session_id] = session

            # Register in database
            self.storage.create_session(
                session_id=session_id,
                tool_name=tool_name,
                project_path=project_path,
                project_name=project_name,
                pid=process.pid,
                current_task=task
            )

            logger.info(f"Agent spawned: {session_id} (PID: {process.pid})")
            return session_id

        except Exception as e:
            logger.error(f"Failed to spawn {tool_name}: {e}")
            raise

    def _build_command(
        self,
        tool_name: AgentTool,
        task: str,
        project_path: str | None,
        auto_approve: bool
    ) -> list[str]:
        """Build the command line for spawning agent"""
        bin_path = self.cli_bins[tool_name]

        if tool_name == "claude-flow":
            cmd = [bin_path, "swarm", task]
            if auto_approve:
                cmd.append("--auto-approve")

        elif tool_name == "gemini":
            cmd = [bin_path, "-p", task]
            # Note: gemini doesn't have built-in auto-approve

        elif tool_name == "cursor-agent":
            # cursor-agent via WSL
            if project_path:
                # Convert Windows path to WSL path
                wsl_path = project_path.replace("C:\\", "/mnt/c/").replace("\\", "/")
                cmd = ["wsl", "bash", "-c", f"cd {wsl_path} && cursor-agent chat '{task}'"]
            else:
                cmd = ["wsl", "cursor-agent", "chat", task]
            if auto_approve:
                cmd.append("--force")

        elif tool_name == "nested-claude":
            cmd = [bin_path, "-p", task, "--output-format", "json"]

        else:
            raise ValueError(f"Unknown tool: {tool_name}")

        return cmd

    def get_session(self, session_id: str) -> AgentSession | None:
        """Get active session by ID"""
        return self.active_sessions.get(session_id)

    def update_session_status(self, session_id: str) -> None:
        """Update session status in database"""
        session = self.active_sessions.get(session_id)
        if not session:
            return

        status = session.get_status()
        output = session.get_output(max_lines=1000)

        self.storage.update_session(
            session_id=session_id,
            status=status,
            output_log=output,
            exit_code=session.process.returncode
        )

    def list_active_sessions(self) -> list[str]:
        """List all active session IDs"""
        return list(self.active_sessions.keys())

    def terminate_session(self, session_id: str) -> None:
        """Terminate a running session"""
        session = self.active_sessions.get(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found")
            return

        session.terminate()

        # Update status
        self.storage.update_session(
            session_id=session_id,
            status="crashed" if session.process.returncode != 0 else "completed",
            exit_code=session.process.returncode,
            output_log=session.get_output()
        )

        # Remove from active sessions
        del self.active_sessions[session_id]

    def cleanup_finished_sessions(self) -> None:
        """Remove finished sessions from active list"""
        finished = [
            sid for sid, session in self.active_sessions.items()
            if not session.is_running()
        ]

        for sid in finished:
            logger.info(f"Cleaning up finished session: {sid}")
            self.update_session_status(sid)
            del self.active_sessions[sid]
