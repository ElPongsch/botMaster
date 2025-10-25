from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


# Minimal storage layer using sqlite3; schema supports migrating to MariaDB later.


@dataclass
class Message:
    id: int
    session_id: int
    role: str
    content: str
    created_at: str


class Storage:
    def __init__(self, db_url: str):
        # support only sqlite:/// path for now; allow MariaDB later
        if not db_url.startswith("sqlite:///"):
            raise ValueError(
                "Only sqlite is supported in v0.1 (set BM_DB_URL to sqlite). MariaDB support will be added."
            )
        self.db_path = Path(db_url.removeprefix("sqlite:///"))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._conn() as c:
            c.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS agents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT,
                    project_path TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id INTEGER NOT NULL,
                    title TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(agent_id) REFERENCES agents(id)
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(agent_id) REFERENCES agents(id)
                );
                """
            )

    # Agents
    def create_agent(self, name: str, provider: str, model: str | None, project_path: str | None) -> int:
        now = datetime.utcnow().isoformat()
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO agents(name, provider, model, project_path, status, created_at) VALUES(?,?,?,?,?,?)",
                (name, provider, model, project_path, "running", now),
            )
            return int(cur.lastrowid)

    def update_agent_status(self, agent_id: int, status: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE agents SET status=? WHERE id=?", (status, agent_id))

    def list_agents(self) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM agents ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]

    # Sessions
    def create_session(self, agent_id: int, title: str | None = None) -> int:
        now = datetime.utcnow().isoformat()
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO sessions(agent_id, title, created_at) VALUES(?,?,?)",
                (agent_id, title, now),
            )
            return int(cur.lastrowid)

    def list_sessions(self, agent_id: int) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM sessions WHERE agent_id=? ORDER BY id DESC", (agent_id,)).fetchall()
        return [dict(r) for r in rows]

    # Messages
    def add_message(self, session_id: int, role: str, content: str) -> int:
        now = datetime.utcnow().isoformat()
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO messages(session_id, role, content, created_at) VALUES(?,?,?,?)",
                (session_id, role, content, now),
            )
            return int(cur.lastrowid)

    def get_messages(self, session_id: int, limit: int | None = None) -> list[Message]:
        q = "SELECT * FROM messages WHERE session_id=? ORDER BY id ASC"
        if limit:
            q += " LIMIT ?"
            params = (session_id, limit)
        else:
            params = (session_id,)
        with self._conn() as c:
            rows = c.execute(q, params).fetchall()
        return [Message(id=r["id"], session_id=r["session_id"], role=r["role"], content=r["content"], created_at=r["created_at"]) for r in rows]

    # Events / logging
    def log_event(self, agent_id: int, kind: str, payload: dict[str, Any]) -> None:
        now = datetime.utcnow().isoformat()
        with self._conn() as c:
            c.execute(
                "INSERT INTO events(agent_id, kind, payload, created_at) VALUES(?,?,?,?)",
                (agent_id, kind, json.dumps(payload, ensure_ascii=False), now),
            )

