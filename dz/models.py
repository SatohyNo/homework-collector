from dataclasses import dataclass, field
from datetime import datetime

NEW = "new"
DONE = "done"
UNCLEAR = "unclear"

MOODLE = "Moodle"
CLASSROOM = "Classroom"
TELEGRAM = "Telegram"


@dataclass
class Task:
    subject: str | None
    title: str
    deadline: datetime | None  # always timezone-aware
    source: str
    status: str = NEW
    notes: list[str] = field(default_factory=list)  # why the task is "unclear"
    url: str | None = None
    # True if the deadline comes from an API (exact), False if it was parsed from free text
    structured: bool = True
    # True if no time was given and 23:59 was assumed
    time_assumed: bool = False
    extra_sources: list[str] = field(default_factory=list)
    posted: datetime | None = None  # when the message was written (text sources only)
    origin: str | None = None  # short "where from": Telegram chat name
    match_text: str = ""  # full text + file names, used to find your submission

    @property
    def sources_label(self) -> str:
        return ", ".join(dict.fromkeys([self.source, *self.extra_sources]))


@dataclass
class Submission:
    """Your finished work: a file you sent in a Telegram chat or one in your Education folder."""

    date: datetime
    text: str  # caption + file name
    where: str  # chat name or path inside the folder
    subject: str | None = None  # Education folder: subject from the top-level folder name
    any_time: bool = False  # files on disk count regardless of when the task was given


@dataclass
class Notice:
    """A message saying a deadline was postponed or cancelled."""

    kind: str  # "postponed" | "cancelled"
    subject: str | None
    text: str
    source: str
    posted: datetime
    dates: list[datetime] = field(default_factory=list)
