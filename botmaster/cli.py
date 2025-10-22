from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from .config import load_settings
from .storage import Storage
from .llm_providers import make_provider
from .agent_runtime import AgentManager, AgentSpec
from .telegram_client import TelegramClient, TelegramConfig


def _is_project_dir(p: Path) -> bool:
    markers = [".git", "pyproject.toml", "package.json", "requirements.txt", "Cargo.toml", ".claude", ".claude-flow"]
    try:
        names = {c.name for c in p.iterdir()}
    except Exception:
        return False
    for m in markers:
        if m in names:
            return True
    return False


def _discover_projects(paths: list[Path], max_depth: int = 3, max_results: int = 200) -> dict[str, Path]:
    result: dict[str, Path] = {}
    count = 0
    def visit(root: Path, depth: int):
        nonlocal count
        if count >= max_results or depth > max_depth:
            return
        try:
            for entry in root.iterdir():
                if count >= max_results:
                    return
                if not entry.is_dir():
                    continue
                if _is_project_dir(entry):
                    key = entry.name.lower().replace(" ", "-")
                    if key not in result:
                        result[key] = entry
                        count += 1
                # Recurse further regardless, to catch nested projects
                visit(entry, depth + 1)
        except Exception:
            return
    for base in paths:
        if base.exists():
            visit(base, 0)
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
    # Telegram client (optional)
    tg = None
    if settings.telegram_bot_token and settings.telegram_chat_id:
        tg = TelegramClient(TelegramConfig(settings.telegram_bot_token, settings.telegram_chat_id))

    def push_agent_msg(spec, text: str):
        if not tg:
            return
        header = f"Agent #{spec.id} {spec.name}"
        project = f"Projekt: {spec.project_path or '-'}"
        body = text
        # keep formatting simple/plain to avoid Telegram markdown issues
        tg.send_message(f"{header}\n{project}\n\n{body}")

    # Provider factory: per-agent customization for claude-cli
    def _detect_claude_bin() -> str:
        # Try configured value first
        bin_candidate = settings.claude_cli_bin.strip() if settings.claude_cli_bin else ""
        if bin_candidate:
            return bin_candidate
        # Fallbacks: try native 'claude', then via WSL
        try:
            import shutil, subprocess
            if shutil.which("claude"):
                # quick version check
                subprocess.run(["claude", "-V"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
                return "claude"
        except Exception:
            pass
        # Try WSL
        try:
            import shutil, subprocess
            if shutil.which("wsl"):
                subprocess.run(["wsl", "-e", "claude", "-V"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
                return "wsl -e claude"
        except Exception:
            pass
        return "claude"  # best effort

    def provider_factory(name: str, project_path: str | None, model: str | None):
        # Per-agent provider (Claude CLI or others)
        instructions_text = None
        if settings.agent_instructions_path and Path(settings.agent_instructions_path).exists():
            try:
                instructions_text = Path(settings.agent_instructions_path).read_text(encoding='utf-8')
            except Exception:
                instructions_text = None
        claude_bin = _detect_claude_bin()
        try:
            return make_provider(
                settings.default_provider,
                settings.anthropic_api_key,
                settings.openai_api_key,
                settings.gemini_api_key,
                settings.default_model,
                provider_cmd=settings.provider_cmd,
                provider_timeout_sec=settings.provider_timeout_sec,
                claude_cli_bin=claude_bin,
                mcp_config_path=settings.mcp_config_path,
                cwd=project_path,
                instructions=instructions_text,
            )
        except Exception as e:
            if tg:
                tg.send_message(f"Provider-Fehler: {e}\nBitte prüfe die Installation von 'claude' (native oder WSL).")
            raise

    # Default provider instance for non-claude-cli modes (used when factory not needed)
    default_provider = None
    if settings.default_provider.lower() not in ("claude-cli", "claude-flow"):
        default_provider = provider_factory(name="default", project_path=None, model=None)

    manager = AgentManager(settings, storage, default_provider, on_assistant_message=push_agent_msg, provider_factory=provider_factory)

    base_agent: AgentSpec | None = None

    def get_base_agent() -> AgentSpec:
        nonlocal base_agent
        if base_agent is None:
            base_agent = manager.spawn(name="botmaster-core", project_path=None)
            if tg:
                tg.send_message(
                    f"Basis-Agent #{base_agent.id} gestartet. Nachrichten ohne '/' gehen automatisch an ihn."
                )
        return base_agent

    projects = _discover_projects(settings.project_dirs)
    project_slugs = sorted(projects.keys())

    # Start Telegram polling
    if not tg:
        print("WARN: Telegram nicht konfiguriert (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID)")
    else:

        def _send_help():
            tg.send_message(
                "botMaster Hilfe\n"+
                "/help – diese Hilfe\n"+
                "/agents – aktive und bekannte Agenten\n"+
                "/new [project_key] [name] – neuen Agenten starten\n"+
                "/to <id> <text> – Nachricht an Agent\n"+
                "/stop <id> – Agent stoppen\n"+
                "\nHinweis: Standard-Provider ist Claude (headless, stream-json)."
            )

        def _send_projects(page: int = 0, page_size: int = 10):
            if not projects:
                tg.send_message("Keine Projekte gefunden. Passe BM_PROJECT_DIRS an.")
                return
            start = page * page_size
            end = min(start + page_size, len(project_slugs))
            rows = []
            row = []
            for slug in project_slugs[start:end]:
                row.append({"text": slug, "callback_data": f"proj:{slug}"})
                if len(row) == 2:
                    rows.append(row)
                    row = []
            if row:
                rows.append(row)
            nav = []
            if page > 0:
                nav.append({"text": "◀️ Zurück", "callback_data": f"projpage:{page-1}"})
            if end < len(project_slugs):
                nav.append({"text": "Weiter ▶️", "callback_data": f"projpage:{page+1}"})
            if nav:
                rows.append(nav)
            tg.send_message("Wähle ein Projekt:", reply_markup={"inline_keyboard": rows})

        def on_msg(text: str, raw: dict):
            if not text:
                return
            stripped = text.strip()
            if not stripped:
                return

            if stripped.startswith('/'):
                parts = stripped.split()
                cmd = parts[0].lower()

                if cmd in ('/start', '/help'):
                    _send_help()
                    return

                if cmd == '/projects':
                    _send_projects(0)
                    return

                if cmd == '/agents':
                    running = manager.list_agents()
                    listing = storage.list_agents()
                    lines = ["Aktive Agent-IDs: " + (", ".join(map(str, running)) or '-')]
                    for a in listing[:10]:
                        lines.append(f"#{a['id']} {a['name']} [{a['status']}] -> {a.get('project_path') or '-'}")
                    tg.send_message("
".join(lines))
                    return

                if cmd == '/new':
                    if len(parts) == 1:
                        _send_projects(0)
                        return
                    proj_key = parts[1].lower()
                    name = " ".join(parts[2:]) if len(parts) > 2 else f"agent-{proj_key}"
                    project_path = str(projects.get(proj_key)) if proj_key in projects else None
                    try:
                        spec = manager.spawn(name=name, project_path=project_path)
                    except Exception as e:
                        tg.send_message(f"Fehler beim Start: {e}")
                        return
                    tg.send_message(
                        f"Agent #{spec.id} '{name}' gestartet. Projekt: {project_path or '-'}
"
                        f"Nutze '/to {spec.id} <text>' für Nachrichten."
                    )
                    return

                if cmd == '/stop' and len(parts) >= 2:
                    try:
                        aid = int(parts[1])
                    except ValueError:
                        tg.send_message('Ungültige Agent-ID')
                        return
                    ok = manager.stop(aid)
                    tg.send_message(f"Agent #{aid} {'gestoppt' if ok else 'nicht gefunden'}.")
                    return

                if cmd == '/to' and len(parts) >= 3:
                    try:
                        aid = int(parts[1])
                    except ValueError:
                        tg.send_message('Ungültige Agent-ID')
                        return
                    msg = " ".join(parts[2:])
                    if not manager.submit(aid, msg):
                        tg.send_message('Agent nicht gefunden.')
                    else:
                        tg.send_message(f"(an #{aid}) OK")
                    return

                tg.send_message('Unbekannter Befehl. /help für Übersicht.')
                return

            spec = get_base_agent()
            if not manager.submit(spec.id, text):
                tg.send_message('Basis-Agent nicht verfügbar.')
            else:
                tg.send_message(f"(an #{spec.id}) -> gesendet")


        if settings.enable_telegram_polling:
            def on_callback(data: str, raw: dict, ack):
                handled = False
                if data.startswith('projpage:'):
                    try:
                        page = int(data.split(':', 1)[1])
                    except Exception:
                        page = 0
                    _send_projects(page)
                    handled = True
                elif data.startswith('proj:'):
                    slug = data.split(':', 1)[1]
                    project_path = str(projects.get(slug)) if slug in projects else None
                    try:
                        spec = manager.spawn(name=f'agent-{slug}', project_path=project_path)
                    except Exception as e:
                        tg.send_message(f"Start fehlgeschlagen: {e}")
                    else:
                        tg.send_message(
                            f"Agent #{spec.id} gestartet für Projekt {slug}.
"
                            f"Nutze '/to {spec.id} <text>' für Nachrichten."
                        )
                    handled = True

                ack()
                if not handled and data:
                    tg.send_message('Unbekannte Auswahl.')



            tg.start_polling(on_msg, on_callback=on_callback)
            tg.send_message("botMaster Daemon gestartet. Antworten werden hier gespiegelt.")
            _send_help()

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
