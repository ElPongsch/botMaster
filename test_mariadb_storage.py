"""Test MariaDB storage client"""
import sys
from pathlib import Path

# Add botmaster to path
sys.path.insert(0, str(Path(__file__).parent))

from botmaster.mariadb_storage import MariaDBStorage
from datetime import datetime

# Connection settings from .env.example
HOST = "localhost"
PORT = 3306
USER = "mcp_admin"
PASSWORD = "mcp_admin_password"
DATABASE = "task_log_db"


def test_storage():
    """Test MariaDB storage operations"""
    storage = MariaDBStorage(
        host=HOST,
        port=PORT,
        user=USER,
        password=PASSWORD,
        database=DATABASE
    )

    print("Testing MariaDB Storage Client...\n")

    # Test 1: Create session
    print("[TEST] Creating agent session...")
    session_id = f"test_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        storage.create_session(
            session_id=session_id,
            tool_name="claude-flow",
            project_name="test_project",
            current_task="Testing storage client"
        )
        print(f"[OK] Session created: {session_id}")
    except Exception as e:
        print(f"[FAIL] Session creation: {e}")
        storage.close_all()
        return

    # Test 2: Get session
    print("\n[TEST] Retrieving session...")
    try:
        session = storage.get_session(session_id)
        if session:
            print(f"[OK] Session retrieved: {session['tool_name']} - {session['status']}")
        else:
            print("[FAIL] Session not found")
    except Exception as e:
        print(f"[FAIL] Session retrieval: {e}")

    # Test 3: Update session
    print("\n[TEST] Updating session...")
    try:
        storage.update_session(
            session_id=session_id,
            current_task="Updated task",
            output_log="Test log entry\n"
        )
        print("[OK] Session updated")
    except Exception as e:
        print(f"[FAIL] Session update: {e}")

    # Test 4: List active sessions
    print("\n[TEST] Listing active sessions...")
    try:
        active = storage.list_active_sessions()
        print(f"[OK] Found {len(active)} active session(s)")
        for sess in active:
            print(f"   - {sess['session_id']}: {sess['tool_name']} ({sess['uptime_seconds']}s)")
    except Exception as e:
        print(f"[FAIL] List active: {e}")

    # Test 5: Send message
    print("\n[TEST] Sending inter-agent message...")
    try:
        msg_id = storage.send_message(
            from_agent=session_id,
            to_agent=session_id,  # Send to self for testing
            message="Test message from agent",
            message_type="notification",
            context_data={"test": True}
        )
        print(f"[OK] Message sent: ID {msg_id}")
    except Exception as e:
        print(f"[FAIL] Send message: {e}")

    # Test 6: Get pending messages
    print("\n[TEST] Getting pending messages...")
    try:
        messages = storage.get_pending_messages(session_id)
        print(f"[OK] Found {len(messages)} pending message(s)")
        for msg in messages:
            print(f"   - From {msg['from_agent']}: {msg['message'][:50]}...")
    except Exception as e:
        print(f"[FAIL] Get messages: {e}")

    # Test 7: Log decision
    print("\n[TEST] Logging orchestration decision...")
    try:
        dec_id = storage.log_decision(
            project="test_project",
            decision="Spawn claude-flow for backend work",
            decision_type="agent_spawn",
            reasoning="Project requires Python expertise",
            alternatives_considered=["gemini", "cursor-agent"]
        )
        print(f"[OK] Decision logged: ID {dec_id}")
    except Exception as e:
        print(f"[FAIL] Log decision: {e}")

    # Test 8: Update decision outcome
    print("\n[TEST] Updating decision outcome...")
    try:
        storage.update_decision_outcome(
            decision_id=dec_id,
            outcome="success"
        )
        print("[OK] Decision outcome updated")
    except Exception as e:
        print(f"[FAIL] Update decision: {e}")

    # Test 9: Get decisions
    print("\n[TEST] Retrieving decisions...")
    try:
        decisions = storage.get_decisions(project="test_project")
        print(f"[OK] Found {len(decisions)} decision(s)")
        for dec in decisions:
            print(f"   - {dec['decision_type']}: {dec['decision'][:50]}... ({dec['outcome']})")
    except Exception as e:
        print(f"[FAIL] Get decisions: {e}")

    # Test 10: Complete session
    print("\n[TEST] Completing session...")
    try:
        storage.complete_session(
            session_id=session_id,
            status="completed",
            exit_code=0
        )
        print("[OK] Session completed")
    except Exception as e:
        print(f"[FAIL] Complete session: {e}")

    # Cleanup
    print("\n[CLEANUP] Closing connections...")
    storage.close_all()

    print("\n[SUCCESS] All storage tests completed!")


if __name__ == "__main__":
    test_storage()
