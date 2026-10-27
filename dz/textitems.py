"""Turns a text message (Telegram post, course announcement) into a Task or a Notice."""

from datetime import datetime

from .config import Config
from .models import NEW, UNCLEAR, Notice, Task
from .textparse import (
    canonical_subject,
    extract_deadline,
    guess_subjects,
    has_keyword,
    looks_like_assignment,
    notice_kind,
    short_title,
)


def text_to_item(
    text: str,
    posted: datetime,
    source: str,
    cfg: Config,
    fixed_subject: str | None = None,
    url: str | None = None,
    require_keyword: bool = True,
    keep_undated: bool = False,
    strict: bool = False,
) -> Task | Notice | None:
    """strict (Telegram): an explicit assignment word is required, a generic "until" is not enough.
    Postponed/cancelled notices are reported even without keywords."""
    if not text:
        return None
    if strict:
        relevant = looks_like_assignment(text) or notice_kind(text)
    else:
        relevant = has_keyword(text) or notice_kind(text) or (keep_undated and looks_like_assignment(text))
    if require_keyword and not relevant:
        return None

    if fixed_subject:
        subject, subject_problem = canonical_subject(fixed_subject, cfg.subjects), None
    else:
        guesses = guess_subjects(text, cfg.subjects)
        if len(guesses) == 1:
            subject, subject_problem = guesses[0], None
        elif guesses:
            subject, subject_problem = None, "several subjects mentioned: " + ", ".join(guesses)
        else:
            subject, subject_problem = None, "no subject (general chat)"

    parsed = extract_deadline(text, posted, cfg.tz)
    # Rule: only messages with a concrete date or time. Exception: recent (keep_undated)
    # messages that clearly give an assignment.
    if not parsed.found_anything:
        if not (keep_undated and looks_like_assignment(text)):
            return None
        # in general chats, no date and no subject usually means chatter, not an assignment
        if subject is None:
            return None
        parsed.problems.append(f"no deadline given (message of {posted.astimezone(cfg.tz):%d.%m})")

    kind = notice_kind(text)
    if kind:
        return Notice(kind=kind, subject=subject, text=short_title(text, 140), source=source,
                      posted=posted, dates=parsed.all_dates)

    problems = list(parsed.problems)
    if subject_problem:
        problems.insert(0, subject_problem)
    return Task(
        subject=subject,
        title=short_title(text),
        deadline=parsed.deadline,
        source=source,
        status=UNCLEAR if problems else NEW,
        notes=problems,
        url=url,
        structured=False,
        time_assumed=parsed.time_assumed,
        posted=posted.astimezone(cfg.tz),
    )
