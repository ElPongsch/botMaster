#!/usr/bin/env python3
import sys, json

def main():
    try:
        data = json.loads(sys.stdin.read() or '{}')
    except Exception as e:
        print(json.dumps({"text": f"[bridge] invalid input: {e}"}), end="")
        return

    messages = data.get("messages") or []
    user_text = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user_text = m.get("content", "").strip()
            break

    # trivial echo/confirm bridge; replace with your real headless client
    reply = (
        "[headless-bridge] Received your message.\n"
        f"User: {user_text or '(empty)'}\n"
        "(Replace headless_bridge.py with your MCP/Claude-Code client and keep the stdin/stdout JSON contract.)"
    )
    print(json.dumps({"text": reply}), end="")

if __name__ == "__main__":
    main()

