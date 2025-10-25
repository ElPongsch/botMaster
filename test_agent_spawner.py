"""Test agent spawner with a simple nested-claude task"""
import sys
import time
from pathlib import Path

# Add botmaster to path
sys.path.insert(0, str(Path(__file__).parent))

from botmaster.agent_spawner import AgentSpawner
from botmaster.mariadb_storage import MariaDBStorage

# Connection settings
HOST = "localhost"
PORT = 3306
USER = "mcp_admin"
PASSWORD = "mcp_admin_password"
DATABASE = "task_log_db"


def test_spawner():
    """Test spawning a simple nested-claude agent"""
    print("Testing Agent Spawner...\n")

    # Initialize storage
    storage = MariaDBStorage(
        host=HOST,
        port=PORT,
        user=USER,
        password=PASSWORD,
        database=DATABASE
    )

    # Initialize spawner
    spawner = AgentSpawner(storage)

    # Test: Spawn nested-claude for simple task
    print("[TEST] Spawning nested-claude for simple calculation...")
    try:
        session_id = spawner.spawn_agent(
            tool_name="nested-claude",
            task="What is 15 multiplied by 7? Just give the number.",
            project_name="test_spawn"
        )
        print(f"[OK] Agent spawned: {session_id}")

        # Wait a bit for completion
        print("\n[WAIT] Waiting for agent to complete (max 15 seconds)...")
        for i in range(15):
            time.sleep(1)
            session = spawner.get_session(session_id)
            if session and not session.is_running():
                print(f"[OK] Agent completed after {i+1} seconds")
                break
            print(f"   ...{i+1}s", end="\r")
        else:
            print("\n[WARN] Agent still running after 15 seconds")

        # Update status
        spawner.update_session_status(session_id)

        # Get output
        session = spawner.get_session(session_id)
        if session:
            output = session.get_output(max_lines=20)
            print(f"\n[OUTPUT] Last 20 lines:")
            print(output[:500] if output else "(no output)")

            print(f"\n[STATUS] Final status: {session.get_status()}")
            print(f"[EXIT CODE] {session.process.returncode}")

        # Cleanup
        spawner.cleanup_finished_sessions()

    except Exception as e:
        print(f"[FAIL] Spawner test failed: {e}")

    storage.close_all()
    print("\n[DONE] Agent spawner test completed!")


if __name__ == "__main__":
    test_spawner()
