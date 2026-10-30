import json
import os
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
HOME = Path.home()

# Secrets live outside the project, in ~/.dz (created by `python -m dz.setup ...`), so they never reach git.
# Any path can be overridden with a variable in .env.
SECRETS_DIR = HOME / ".dz"
DEFAULT_PATHS = {
    "MOODLE_TOKEN_FILE": SECRETS_DIR / "moodle-token",
    "CLASSROOM_URL_FILE": SECRETS_DIR / "classroom-url",
    "CLASSROOM_CLIENT_FILE": SECRETS_DIR / "google-client.json",
    "CLASSROOM_TOKEN_FILE": SECRETS_DIR / "google-token.json",
    "TG_CONFIG_FILE": SECRETS_DIR / "telegram-api.json",
    "TG_SESSION_FILE": SECRETS_DIR / "telegram.session",
}


@dataclass
class Config:
    tz: ZoneInfo
    horizon: str  # "next_week" (until the end of next week) or a number of days, e.g. "30"
    days_back: int  # how many recent days of Telegram and announcements to read
    subjects: dict[str, list[str]]
    telegram_chats: list[dict] = field(default_factory=list)
    moodle_url: str = ""  # e.g. https://moodle.your-university.edu
    send_to_saved: bool = True  # send the list to your Telegram "Saved Messages"
    education: dict = field(default_factory=dict)  # folder with your finished work on disk

    def deadline_until(self, now: datetime) -> datetime:
        """Deadline limit: end of next week's Sunday (or now + N days)."""
        if self.horizon == "next_week":
            next_sunday = now.date() + timedelta(days=6 - now.weekday() + 7)
            return datetime.combine(next_sunday, time(23, 59, 59), tzinfo=self.tz)
        return now + timedelta(days=int(self.horizon))


def load_config() -> Config:
    load_dotenv(ROOT / ".env")
    path = ROOT / "config.json"
    if not path.exists():
        path = ROOT / "config.example.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return Config(
        tz=ZoneInfo(data.get("timezone", "Europe/Kyiv")),
        horizon=str(data.get("horizon", "next_week")),
        days_back=int(data.get("days_back", 7)),
        subjects=data.get("subjects", {}),
        telegram_chats=data.get("telegram", {}).get("chats", []),
        moodle_url=(env("MOODLE_URL") or data.get("moodle_url", "")).rstrip("/"),
        send_to_saved=bool(data.get("send_to_saved", True)),
        education=data.get("education", {}),
    )


def env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    return value or None


def secret_path(name: str) -> Path:
    return Path(os.path.expanduser(env(name) or str(DEFAULT_PATHS[name])))


def read_secret(name: str, warn=None) -> str | None:
    from .security import ensure_private

    p = secret_path(name)
    if not p.exists():
        return None
    ensure_private(p, warn)
    return p.read_text().strip()
