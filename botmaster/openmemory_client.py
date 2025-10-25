"""OpenMemory client for botMaster v2.0 semantic memory"""
import requests
from typing import Any
import logging

logger = logging.getLogger(__name__)


class OpenMemoryClient:
    """HTTP client for OpenMemory semantic memory storage"""

    def __init__(self, base_url: str, user_id: str, api_key: str = "local-dev-key"):
        """
        Initialize OpenMemory client

        Args:
            base_url: Base URL of OpenMemory API (e.g. http://localhost:8765)
            user_id: User ID for memory operations (e.g. "markus")
            api_key: API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.user_id = user_id
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def add_memory(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        user_message: str | None = None
    ) -> dict[str, Any] | None:
        """
        Add a new memory to OpenMemory

        Args:
            content: The memory content to store
            metadata: Optional metadata for the memory
            user_message: Optional user message context

        Returns:
            Response dict with memory ID or None on error
        """
        try:
            # OpenMemory expects messages format
            payload = {
                "messages": [
                    {"role": "user", "content": user_message or content}
                ],
                "user_id": self.user_id
            }

            if metadata:
                payload["metadata"] = metadata

            response = requests.post(
                f"{self.base_url}/api/v1/memories/",
                json=payload,
                headers=self.headers,
                timeout=10
            )

            # Handle validation errors gracefully (known OpenMemory bug)
            if response.status_code >= 400:
                logger.warning(f"Memory add failed ({response.status_code}): {response.text}")
                return None

            result = response.json()
            logger.info(f"Memory added: {result.get('id', 'unknown')}")
            return result

        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            return None

    def search_memories(
        self,
        query: str,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Search for relevant memories

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of matching memories
        """
        try:
            params = {
                "query": query,
                "user_id": self.user_id,
                "limit": limit
            }

            response = requests.get(
                f"{self.base_url}/api/v1/memories/search/",
                params=params,
                headers=self.headers,
                timeout=10
            )

            if response.status_code != 200:
                logger.warning(f"Memory search failed ({response.status_code}): {response.text}")
                return []

            result = response.json()
            memories = result.get("results", [])
            logger.debug(f"Found {len(memories)} memories for query: {query}")
            return memories

        except Exception as e:
            logger.error(f"Failed to search memories: {e}")
            return []

    def get_memories(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> list[dict[str, Any]]:
        """
        Get recent memories for user

        Args:
            limit: Maximum number of memories to retrieve
            offset: Pagination offset

        Returns:
            List of memories
        """
        try:
            params = {
                "user_id": self.user_id,
                "limit": limit,
                "offset": offset
            }

            response = requests.get(
                f"{self.base_url}/api/v1/memories/",
                params=params,
                headers=self.headers,
                timeout=10
            )

            if response.status_code != 200:
                logger.warning(f"Get memories failed ({response.status_code}): {response.text}")
                return []

            result = response.json()
            memories = result.get("results", [])
            logger.debug(f"Retrieved {len(memories)} memories")
            return memories

        except Exception as e:
            logger.error(f"Failed to get memories: {e}")
            return []

    def store_user_context(
        self,
        context_type: str,
        context_data: dict[str, Any]
    ) -> bool:
        """
        Store user context information (preferences, project info, etc.)

        Args:
            context_type: Type of context (e.g. "user_preferences", "project_config")
            context_data: Context data to store

        Returns:
            True if successful, False otherwise
        """
        try:
            # Format as user message for better semantic storage
            content = f"{context_type}: {context_data}"

            result = self.add_memory(
                content=content,
                metadata={
                    "context_type": context_type,
                    "source": "botmaster_orchestrator"
                }
            )

            return result is not None

        except Exception as e:
            logger.error(f"Failed to store user context: {e}")
            return False

    def get_relevant_context(
        self,
        task_description: str,
        limit: int = 5
    ) -> list[dict[str, Any]]:
        """
        Get relevant context for a task from semantic memory

        Args:
            task_description: Description of the task
            limit: Maximum number of context items

        Returns:
            List of relevant memories
        """
        return self.search_memories(task_description, limit=limit)

    def log_orchestration_context(
        self,
        project: str,
        decision: str,
        outcome: str
    ) -> bool:
        """
        Log orchestration decision to semantic memory for learning

        Args:
            project: Project name
            decision: Decision made
            outcome: Outcome of the decision

        Returns:
            True if successful
        """
        content = (
            f"Orchestration for {project}: {decision}. "
            f"Outcome: {outcome}"
        )

        result = self.add_memory(
            content=content,
            metadata={
                "context_type": "orchestration_learning",
                "project": project,
                "outcome": outcome
            }
        )

        return result is not None
