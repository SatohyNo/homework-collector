"""Usage: python -m dz  [--demo] [--no-send] [--no-moodle] [--no-classroom] [--no-telegram]

Reads your homework from Moodle, Google Classroom and Telegram, prints one table in the terminal
and sends the same list to your own Telegram "Saved Messages". It creates, changes or sends
nothing else.
"""

import argparse
import asyncio
import json
from datetime import datetime

from .config import env, load_config, read_secret, secret_path
from .merge import apply_notices, dedupe, hide_submitted, in_window, sort_tasks
from .models import DONE, Notice, Task
from .render import render, render_telegram


def main() -> None:
    ap = argparse.ArgumentParser(prog="dz", description="Collect homework from Moodle, Google Classroom and Telegram")
    ap.add_argument("--demo", action="store_true", help="sample data, no network access")
    ap.add_argument("--no-moodle", action="store_true")
    ap.add_argument("--no-classroom", action="store_true")
    ap.add_argument("--no-telegram", action="store_true")
    ap.add_argument("--no-send", action="store_true", help="do not send the list to Telegram Saved Messages")
    args = ap.parse_args()

    cfg = load_config()
    now = datetime.now(cfg.tz)
    warnings: list[str] = []
    warn = warnings.append
    tasks: list[Task] = []
    notices: list[Notice] = []
    submissions = []  # your files in chats and on disk, used to hide work that is already done

    def add(result):
        tasks.extend(result[0])
        notices.extend(result[1])

    if args.demo:
        from .demo import collect as demo_collect

        add(demo_collect(cfg, now))
    else:
        if not args.no_moodle:
            token = env("MOODLE_TOKEN") or read_secret("MOODLE_TOKEN_FILE")
            if token and not cfg.moodle_url:
                warn("Moodle skipped: set moodle_url in config.json")
            elif token:
                from . import moodle

                try:
                    add(moodle.collect(moodle.MoodleClient(cfg.moodle_url, token), cfg, now, warn))
                except Exception as e:  # noqa: BLE001
                    warn(f"Moodle unavailable: {e}")
            else:
                warn("Moodle skipped: no token, run `python -m dz.setup moodle`")

        if not args.no_classroom:
            from . import classroom

            if classroom.available():
                try:
                    add(classroom.collect(classroom.fetch_dump(), cfg, now, warn))
                except Exception as e:  # noqa: BLE001
                    warn(f"Classroom unavailable: {e}")
            else:
                warn("Classroom skipped: no access, run `python -m dz.setup classroom`")

        if not args.no_telegram:
            tg_file = secret_path("TG_CONFIG_FILE")
            if tg_file.exists():
                from . import telegram_src

                keys = json.loads(tg_file.read_text())
                session = str(secret_path("TG_SESSION_FILE").with_suffix(""))  # Telethon appends .session itself
                try:
                    tg_tasks, tg_notices, submissions = asyncio.run(
                        telegram_src.collect(int(keys["api_id"]), keys["api_hash"], session, cfg, now, warn))
                    add((tg_tasks, tg_notices))
                except Exception as e:  # noqa: BLE001
                    warn(f"Telegram unavailable: {e}")
            else:
                warn("Telegram skipped: no keys, run `python -m dz.setup telegram`")

    tasks = [t for t in tasks if in_window(t, now, cfg.deadline_until(now))]
    tasks = dedupe(tasks)
    tasks, notice_rows = apply_notices(tasks, notices)
    # submitted tasks are hidden (merging already happened, so their Telegram copies go too)
    tasks = [t for t in tasks if t.status != DONE]
    # and tasks you already sent as a file in Telegram or have finished in your Education folder
    if not args.demo:
        from .education import scan

        submissions += scan(cfg, warn)
    tasks, hidden = hide_submitted(tasks, submissions)
    tasks = sort_tasks(tasks)

    until = cfg.deadline_until(now)
    print(render(tasks, notice_rows, warnings, now, until, hidden))

    if args.demo or args.no_send or not cfg.send_to_saved:
        return
    tg_file = secret_path("TG_CONFIG_FILE")
    if not tg_file.exists():
        print(f"\nNot sent to Saved Messages: {tg_file} is missing")
        return
    from . import telegram_src

    keys = json.loads(tg_file.read_text())
    session = str(secret_path("TG_SESSION_FILE").with_suffix(""))
    try:
        asyncio.run(telegram_src.send_to_saved(int(keys["api_id"]), keys["api_hash"], session,
                                               render_telegram(tasks, notice_rows, now, until)))
        print("\nSent to Telegram Saved Messages ✓")
    except Exception as e:  # noqa: BLE001
        print(f"\nNot sent to Saved Messages: {e}")


if __name__ == "__main__":
    main()
