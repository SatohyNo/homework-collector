"""Usage: python -m dz  [--demo] [--no-send] [--no-moodle] [--no-classroom] [--no-telegram]

Reads your homework from Moodle, Google Classroom and Telegram, prints one table in the terminal
and sends the same list to your own Telegram "Saved Messages". It creates, changes or sends
nothing else.
"""

import argparse
import asyncio
from datetime import datetime

from .config import env, load_config, read_secret
from .keystore import KeystoreError
from .merge import apply_notices, dedupe, hide_submitted, in_window, sort_tasks
from .models import DONE, Notice, Task
from .render import render, render_telegram
from .security import redact


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

    def warn(message: str) -> None:
        warnings.append(redact(message))  # error texts can contain URLs with keys
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
            try:
                token = env("MOODLE_TOKEN") or read_secret("MOODLE_TOKEN_FILE", warn)
            except KeystoreError as e:
                token = None
                warn(f"Keychain unavailable: {e}")
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
            from . import telegram_src

            try:
                client = telegram_src.make_client(warn)
                if client:
                    tg_tasks, tg_notices, submissions = asyncio.run(telegram_src.collect(client, cfg, now, warn))
                    add((tg_tasks, tg_notices))
                else:
                    warn("Telegram skipped: not set up, run `python -m dz.setup telegram`")
            except Exception as e:  # noqa: BLE001
                warn(f"Telegram unavailable: {e}")

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
    from . import telegram_src

    try:
        client = telegram_src.make_client(print)
        if not client:
            print("\nNot sent to Saved Messages: Telegram is not set up")
            return
        asyncio.run(telegram_src.send_to_saved(client, render_telegram(tasks, notice_rows, now, until)))
        print("\nSent to Telegram Saved Messages ✓")
    except Exception as e:  # noqa: BLE001
        print(f"\nNot sent to Saved Messages: {redact(str(e))}")


if __name__ == "__main__":
    main()
