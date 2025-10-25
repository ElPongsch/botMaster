"""MariaDB storage client for botMaster v2.0 orchestration state"""
import pymysql
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator
import json
import logging

logger = logging.getLogger(__name__)


class MariaDBStorage:
    """MariaDB client for orchestration state tracking with connection pooling"""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        pool_size: int = 5
    ):
        self.config = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database,
            "charset": "utf8mb4",
            "cursorclass": pymysql.cursors.DictCursor,
            "autocommit": False,
        }
        self.pool_size = pool_size
        self._connections: list[pymysql.Connection] = []

    @contextmanager
    def get_connection(self) -> Iterator[pymysql.Connection]:
        """Get a connection from the pool (or create new one)"""
        conn = None
        try:
            # Try to reuse existing connection
            if self._connections:
                conn = self._connections.pop()
                # Test if connection is still alive
                try:
                    conn.ping(reconnect=True)
                except Exception:
                    conn = None

            # Create new connection if needed
            if conn is None:
                conn = pymysql.connect(**self.config)

            yield conn
            conn.commit()

            # Return to pool if not full
            if len(self._connections) < self.pool_size:
                self._connections.append(conn)
            else:
                conn.close()

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise

        finally:
            # If error occurred and conn not in pool, close it
            if conn and conn not in self._connections:
                try:
                    conn.close()
                except Exception:
                    pass

    # ========== Agent Sessions ==========

    def create_session(
        self,
        session_id: str,
        tool_name: str,
        project_path: str | None = None,
        project_name: str | None = None,
        pid: int | None = None,
        current_task: str | None = None,
    ) -> None:
        """Register a new agent session"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO agent_sessions
                (session_id, tool_name, project_path, project_name, status, pid, current_task)
                VALUES (%s, %s, %s, %s, 'running', %s, %s)
                """,
                (session_id, tool_name, project_path, project_name, pid, current_task)
            )
            logger.info(f"Created session {session_id} for {tool_name}")

    def update_session(
        self,
        session_id: str,
        status: str | None = None,
        current_task: str | None = None,
        output_log: str | None = None,
        error_message: str | None = None,
        exit_code: int | None = None,
    ) -> None:
        """Update an existing agent session"""
        updates = []
        params = []

        if status:
            updates.append("status = %s")
            params.append(status)
            if status in ("completed", "failed", "crashed"):
                updates.append("completed_at = NOW()")

        if current_task is not None:
            updates.append("current_task = %s")
            params.append(current_task)

        if output_log is not None:
            updates.append("output_log = CONCAT(COALESCE(output_log, ''), %s)")
            params.append(output_log)

        if error_message is not None:
            updates.append("error_message = %s")
            params.append(error_message)

        if exit_code is not None:
            updates.append("exit_code = %s")
            params.append(exit_code)

        if not updates:
            return

        params.append(session_id)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE agent_sessions SET {', '.join(updates)} WHERE session_id = %s",
                params
            )
            logger.debug(f"Updated session {session_id}")

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get details of a specific session"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM agent_sessions WHERE session_id = %s",
                (session_id,)
            )
            return cursor.fetchone()

    def list_active_sessions(self) -> list[dict[str, Any]]:
        """List all currently active agent sessions"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM active_agents")
            return cursor.fetchall()

    def complete_session(
        self,
        session_id: str,
        status: str = "completed",
        exit_code: int = 0,
        error_message: str | None = None
    ) -> None:
        """Mark a session as completed/failed/crashed"""
        self.update_session(
            session_id=session_id,
            status=status,
            exit_code=exit_code,
            error_message=error_message
        )

    # ========== Agent Messages ==========

    def send_message(
        self,
        from_agent: str,
        to_agent: str,
        message: str,
        message_type: str = "request",
        context_data: dict[str, Any] | None = None,
    ) -> int:
        """Send a message from one agent to another"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO agent_messages
                (from_agent, to_agent, message_type, message, context_data, status)
                VALUES (%s, %s, %s, %s, %s, 'pending')
                """,
                (
                    from_agent,
                    to_agent,
                    message_type,
                    message,
                    json.dumps(context_data) if context_data else None
                )
            )
            message_id = cursor.lastrowid
            logger.info(f"Message {message_id} sent from {from_agent} to {to_agent}")
            return message_id

    def get_pending_messages(self, to_agent: str) -> list[dict[str, Any]]:
        """Get all pending messages for a specific agent"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM agent_messages
                WHERE to_agent = %s AND status = 'pending'
                ORDER BY timestamp ASC
                """,
                (to_agent,)
            )
            messages = cursor.fetchall()

            # Parse JSON context_data
            for msg in messages:
                if msg.get("context_data"):
                    try:
                        msg["context_data"] = json.loads(msg["context_data"])
                    except Exception:
                        pass

            return messages

    def mark_message_done(
        self,
        message_id: int,
        response: str | None = None,
        status: str = "done"
    ) -> None:
        """Mark a message as processed"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE agent_messages
                SET status = %s, processed_at = NOW(), response = %s
                WHERE id = %s
                """,
                (status, response, message_id)
            )
            logger.debug(f"Message {message_id} marked as {status}")

    def update_message_response(self, message_id: int, response: str) -> None:
        """Update the response for a message"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE agent_messages SET response = %s WHERE id = %s",
                (response, message_id)
            )

    # ========== Orchestration Decisions ==========

    def log_decision(
        self,
        project: str,
        decision: str,
        decision_type: str = "other",
        reasoning: str | None = None,
        alternatives_considered: list[str] | None = None,
    ) -> int:
        """Log an orchestration decision"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO orchestration_decisions
                (project, decision_type, decision, reasoning, alternatives_considered, outcome)
                VALUES (%s, %s, %s, %s, %s, 'pending')
                """,
                (
                    project,
                    decision_type,
                    decision,
                    reasoning,
                    json.dumps(alternatives_considered) if alternatives_considered else None
                )
            )
            decision_id = cursor.lastrowid
            logger.info(f"Logged decision {decision_id} for project {project}")
            return decision_id

    def update_decision_outcome(
        self,
        decision_id: int,
        outcome: str,
        markus_feedback: str | None = None
    ) -> None:
        """Update the outcome of a decision"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if markus_feedback:
                cursor.execute(
                    """
                    UPDATE orchestration_decisions
                    SET outcome = %s, markus_feedback = %s, feedback_timestamp = NOW()
                    WHERE id = %s
                    """,
                    (outcome, markus_feedback, decision_id)
                )
            else:
                cursor.execute(
                    "UPDATE orchestration_decisions SET outcome = %s WHERE id = %s",
                    (outcome, decision_id)
                )

            logger.debug(f"Decision {decision_id} outcome updated to {outcome}")

    def get_decisions(
        self,
        project: str | None = None,
        decision_type: str | None = None,
        limit: int = 50
    ) -> list[dict[str, Any]]:
        """Get orchestration decisions with optional filtering"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            conditions = []
            params = []

            if project:
                conditions.append("project = %s")
                params.append(project)

            if decision_type:
                conditions.append("decision_type = %s")
                params.append(decision_type)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            params.append(limit)

            cursor.execute(
                f"""
                SELECT * FROM orchestration_decisions
                {where_clause}
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                params
            )

            decisions = cursor.fetchall()

            # Parse JSON alternatives_considered
            for dec in decisions:
                if dec.get("alternatives_considered"):
                    try:
                        dec["alternatives_considered"] = json.loads(dec["alternatives_considered"])
                    except Exception:
                        pass

            return decisions

    # ========== Utility ==========

    def close_all(self) -> None:
        """Close all pooled connections"""
        for conn in self._connections:
            try:
                conn.close()
            except Exception:
                pass
        self._connections.clear()
        logger.info("Closed all database connections")
