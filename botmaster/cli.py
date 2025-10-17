from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .config import load_settings
from .storage import Storage
from .llm_providers import make_provider
from .agent_runtime import AgentManager
from .telegram_client import TelegramClient, TelegramConfig


def _discover_projects(paths: list[Path]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for base in paths:
        if not base.exists():
            continue
        for p in base.iterdir():
            if p.is_dir():
                key = p.name.lower().replace(" ", "-")
                result[key] = p
    return result


def send_cli():
    parser = argparse.ArgumentParser(description="Sendet eine Nachricht an Telegram per Bot")
    parser.add_argument("message", help="Text der Nachricht")
    args = parser.parse_args()
    settings = load_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        print("Bitte TELEGRAM_BOT_TOKEN und TELEGRAM_CHAT_ID setzen.", file=sys.stderr)
        sys.exit(2)
    tg = TelegramClient(TelegramConfig(settings.telegram_bot_token, settings.telegram_chat_id))
    tg.send_message(args.message)


def daemon():
    settings = load_settings()
    storage = Storage(settings.db_url)
    provider = make_provider(
        settings.default_provider,
        settings.anthropic_api_key,
        settings.openai_api_key,
        settings.gemini_api_key,
        settings.default_model,
        provider_cmd=settings.provider_cmd,
        provider_timeout_sec=settings.provider_timeout_sec,
    )
    manager = AgentManager(settings, storage, provider)

    projects = _discover_projects(settings.project_dirs)

    # Start Telegram polling
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        print("WARN: Telegram nicht konfiguriert (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID)")
        tg = None
    else:
        tg = TelegramClient(TelegramConfig(settings.telegram_bot_token, settings.telegram_chat_id))

        def on_msg(text: str, raw: dict):
            # Commands: /new <project_key> <name...>, /agents, /stop <id>, /to <id> <text...>
            parts = text.strip().split()
            if not parts:
                return
            cmd = parts[0].lower()
            if cmd == "/agents":
                running = manager.list_agents()
                listing = storage.list_agents()
                lines = ["Aktive Agent-IDs: " + (", ".join(map(str, running)) or "-")]
                for a in listing[:10]:
                    lines.append(f"#{a['id']} {a['name']} [{a['status']}] -> {a.get('project_path') or '-'}")
                tg.send_message("\n".join(lines))
                return
            if cmd == "/new" and len(parts) >= 2:
                proj_key = parts[1].lower()
                name = " ".join(parts[2:]) if len(parts) > 2 else f"agent-{proj_key}"
                project_path = str(projects.get(proj_key)) if proj_key in projects else None
                spec = manager.spawn(name=name, project_path=project_path)
                tg.send_message(f"Agent #{spec.id} '{name}' gestartet. Projekt: {project_path or '-'}\nSende mit '/to {spec.id} ...' Nachrichten.")
                return
            if cmd == "/stop" and len(parts) >= 2:
                try:
                    aid = int(parts[1])
                except ValueError:
                    tg.send_message("Ungültige Agent-ID")
                    return
                ok = manager.stop(aid)
                tg.send_message(f"Agent #{aid} {'gestoppt' if ok else 'nicht gefunden'}.")
                return
            if cmd == "/to" and len(parts) >= 3:
                try:
                    aid = int(parts[1])
                except ValueError:
                    tg.send_message("Ungültige Agent-ID")
                    return
                msg = " ".join(parts[2:])
                if not manager.submit(aid, msg):
                    tg.send_message("Agent nicht gefunden.")
                else:
                    tg.send_message(f"(an #{aid}) OK")
                return
            # fallback: help
            tg.send_message("Befehle: /new <project_key> [name], /agents, /stop <id>, /to <id> <text>")

        if settings.enable_telegram_polling:
            tg.start_polling(on_msg)
            tg.send_message("botMaster Daemon gestartet. /agents /new /stop /to verfügbar.")

    # Keep the daemon alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def main():
    parser = argparse.ArgumentParser(description="botMaster Orchestrator CLI")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("send", help="Sendet eine Nachricht an Telegram").add_argument("message")
    sub.add_parser("daemon", help="Startet den Orchestrator und Telegram-Poller")
    sub.add_parser("projects", help="Zeigt gefundene Projekte")

    args = parser.parse_args()
    if args.cmd == "send":
        os.execvp(sys.executable, [sys.executable, "-m", "botmaster.cli", "__send__", args.message])
        return
    if args.cmd == "daemon":
        daemon()
        return
    if args.cmd == "projects":
        s = load_settings()
        pr = _discover_projects(s.project_dirs)
        if not pr:
            print("Keine Projekte gefunden.")
        else:
            for k, p in pr.items():
                print(f"{k}: {p}")
        return

    # hidden subcommand for script entry
    if len(sys.argv) >= 3 and sys.argv[1] == "__send__":
        msg = " ".join(sys.argv[2:])
        settings = load_settings()
        if not settings.telegram_bot_token or not settings.telegram_chat_id:
            print("Bitte TELEGRAM_BOT_TOKEN und TELEGRAM_CHAT_ID setzen.", file=sys.stderr)
            sys.exit(2)
        tg = TelegramClient(TelegramConfig(settings.telegram_bot_token, settings.telegram_chat_id))
        tg.send_message(msg)
        return

    parser.print_help()
