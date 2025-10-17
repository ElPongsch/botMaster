from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict

from .config import Settings
from .storage import Storage
from .llm_providers import LLMProvider


@dataclass
class AgentSpec:
    id: int
    name: str
    provider_name: str
    model: Optional[str]
    project_path: Optional[str]
    session_id: int


class AgentWorker(threading.Thread):
    def __init__(self, spec: AgentSpec, settings: Settings, storage: Storage, provider: LLMProvider):
        super().__init__(name=f"agent-{spec.id}", daemon=True)
        self.spec = spec
        self.settings = settings
        self.storage = storage
        self.provider = provider
        self.inbox: "queue.Queue[str]" = queue.Queue()
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def submit(self, text: str):
        self.inbox.put(text)

    def run(self):
        # Initial announce
        self.storage.add_message(self.spec.session_id, "system", f"Agent {self.spec.name} gestartet. Projekt: {self.spec.project_path or '-'}")
        while not self._stop.is_set():
            try:
                user_text = self.inbox.get(timeout=0.5)
            except queue.Empty:
                continue
            self.storage.add_message(self.spec.session_id, "user", user_text)

            # Build context
            msgs = []
            history = self.storage.get_messages(self.spec.session_id, limit=self.settings.max_context_messages)
            for m in history:
                if m.role in ("user", "assistant"):
                    msgs.append({"role": m.role, "content": m.content})

            try:
                reply = self.provider.generate(self.settings.system_prompt, msgs, model=self.spec.model)
            except Exception as e:
                reply = f"[Fehler bei LLM-Abfrage: {e}]"
            self.storage.add_message(self.spec.session_id, "assistant", reply)


class AgentManager:
    def __init__(self, settings: Settings, storage: Storage, provider: LLMProvider):
        self.settings = settings
        self.storage = storage
        self.provider = provider
        self._agents: dict[int, AgentWorker] = {}

    def spawn(self, name: str, project_path: Optional[str] = None, model: Optional[str] = None) -> AgentSpec:
        agent_id = self.storage.create_agent(name=name, provider=self.provider.__class__.__name__, model=model, project_path=project_path)
        session_id = self.storage.create_session(agent_id, title=f"Session {name}")
        spec = AgentSpec(id=agent_id, name=name, provider_name=self.provider.__class__.__name__, model=model, project_path=project_path, session_id=session_id)
        worker = AgentWorker(spec, self.settings, self.storage, self.provider)
        worker.start()
        self._agents[agent_id] = worker
        return spec

    def submit(self, agent_id: int, text: str) -> bool:
        w = self._agents.get(agent_id)
        if not w:
            return False
        w.submit(text)
        return True

    def stop(self, agent_id: int) -> bool:
        w = self._agents.pop(agent_id, None)
        if not w:
            return False
        w.stop()
        self.storage.update_agent_status(agent_id, "stopped")
        return True

    def list_agents(self) -> List[int]:
        return list(self._agents.keys())

