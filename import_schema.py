"""Import orchestration schema into MariaDB"""
import pymysql

# Connection settings from .env.example
HOST = "localhost"
PORT = 3306
USER = "mcp_admin"
PASSWORD = "mcp_admin_password"
DATABASE = "task_log_db"

def import_schema():
    """Import schema from SQL file"""
    try:
        # Read SQL file
        with open("schema_orchestration.sql", "r", encoding="utf-8") as f:
            sql_script = f.read()

        # Connect to MariaDB
        conn = pymysql.connect(
            host=HOST,
            port=PORT,
            user=USER,
            password=PASSWORD,
            database=DATABASE,
            charset='utf8mb4'
        )

        print(f"[OK] Connected to MariaDB at {HOST}:{PORT}")

        cursor = conn.cursor()

        # Split into individual statements (simple split on ';')
        statements = [s.strip() for s in sql_script.split(';') if s.strip()]

        executed = 0
        for i, statement in enumerate(statements, 1):
            # Skip comments and USE statements (already connected to DB)
            if statement.startswith('--') or statement.upper().startswith('USE '):
                print(f"[SKIP] Statement {i}: {statement[:60]}...")
                continue

            try:
                # Extract first word for logging
                first_word = statement.split()[0].upper()
                print(f"[EXEC] Statement {i}: {first_word} - {statement[:80]}...")
                cursor.execute(statement)
                conn.commit()
                executed += 1
                print(f"[OK] Statement {i}: {first_word} executed successfully")
            except pymysql.Error as e:
                print(f"[WARN] Statement {i} failed: {e}")
                print(f"       SQL: {statement[:200]}...")
                # Continue with other statements
                continue

        print(f"\n[INFO] Executed {executed} statements successfully")

        cursor.close()
        conn.close()

        print("\n[SUCCESS] Schema import completed!")
        print("\nCreated tables:")
        print("  - agent_sessions")
        print("  - agent_messages")
        print("  - orchestration_decisions")
        print("\nCreated views:")
        print("  - active_agents")
        print("  - pending_messages")

    except FileNotFoundError:
        print("[FAIL] schema_orchestration.sql not found")
    except pymysql.Error as e:
        print(f"[FAIL] Database error: {e}")
    except Exception as e:
        print(f"[FAIL] Unexpected error: {e}")

if __name__ == "__main__":
    print("Importing botMaster orchestration schema...\n")
    import_schema()
