import subprocess
import json
import time
import uuid
from pathlib import Path


PROJECT_PATH = Path(r"C:\myFolder\Port\projects\privat\2025-09-agent-taskmanagement")
MCP_CONFIG = PROJECT_PATH / "mcp-server-life-db" / "mcp-config.json"
INSTRUCTIONS = PROJECT_PATH / "agent-instructions" / "task-agent-v2.md"


def main():
    session_id = str(uuid.uuid4())
    instructions_text = INSTRUCTIONS.read_text(encoding="utf-8") if INSTRUCTIONS.exists() else ""
    payload = {
        "type": "user",
        "message": {
            "role": "user",
            "content": f"{instructions_text}\n\n---\n\nTestanfrage: Sag bitte knapp Hallo und bestätige, dass stream-json funktioniert."
        },
        "session_id": session_id,
    }
    cmd = [
        "claude",
        "-p",
        "--output-format",
        "stream-json",
        "--input-format",
        "stream-json",
        "--replay-user-messages",
        "--session-id",
        session_id,
        "--dangerously-skip-permissions",
    ]
    if MCP_CONFIG.exists():
        cmd += ["--mcp-config", str(MCP_CONFIG)]

    print("==> Starte:", " ".join(cmd))
    proc = subprocess.Popen(
        " ".join(cmd),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=PROJECT_PATH,
        shell=True,
    )

    try:
        proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        proc.stdin.flush()
    except Exception as exc:
        print("Fehler beim Schreiben auf stdin:", exc)

    start = time.time()
    print("==> Warte auf Antwort…")
    try:
        while time.time() - start < 20:
            line = proc.stdout.readline()
            if not line:
                time.sleep(0.2)
                continue
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                print("[stdout]", line)
                continue
            print("[json]", msg)
            if msg.get("type") == "assistant" or msg.get("message", {}).get("role") == "assistant":
                break
    finally:
        time.sleep(1)
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    stderr = proc.stderr.read()
    if stderr:
        print("==> stderr:")
        print(stderr)


if __name__ == "__main__":
    main()

