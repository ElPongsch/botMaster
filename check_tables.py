"""Check which tables exist in task_log_db"""
import pymysql

HOST = "localhost"
PORT = 3306
USER = "mcp_admin"
PASSWORD = "mcp_admin_password"
DATABASE = "task_log_db"

try:
    conn = pymysql.connect(
        host=HOST,
        port=PORT,
        user=USER,
        password=PASSWORD,
        database=DATABASE,
        charset='utf8mb4'
    )

    cursor = conn.cursor()
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()

    print(f"Tables in {DATABASE}:")
    for table in tables:
        print(f"  - {table[0]}")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"Error: {e}")
