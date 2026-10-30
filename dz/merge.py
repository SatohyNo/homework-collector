"""Date window filter, duplicate merging, postponed/cancelled notices, sorting, "already done" checks."""

import re
from datetime import datetime
from difflib import SequenceMatcher

from .models import DONE, NEW, UNCLEAR, Notice, Submission, Task

_WORD_RE = re.compile(r"\w+", re.UNICODE)
_STOP = {"завдання", "здати", "робота", "роботу", "дедлайн", "термін", "включно", "будь", "ласка"}


def _keywords(title: str) -> tuple[set[str], set[str]]:
    words = [w.lower() for w in _WORD_RE.findall(title)]
    numbers = {w for w in words if w.isdigit() and len(w) <= 2}  # "lab 3", "КП №2"; dates/years are dropped
    stems = {w[:5] for w in words if len(w) > 3 and not w.isdigit() and w not in _STOP}
    return numbers, stems


def _similar(a: Task, b: Task) -> bool:
    na, sa = _keywords(a.title)
    nb, sb = _keywords(b.title)
    if na and nb and not (na & nb):
        return False  # "lab 2" and "lab 3" are different tasks
    if na & nb and sa & sb:
        return True
    return len(sa & sb) >= 2 or SequenceMatcher(None, a.title.lower(), b.title.lower()).ratio() >= 0.6


# Kind of work: "ргр-1" and "Только ргр" (both "RGR", a calculation-graphic assignment) are the same
# task even though the wording differs. Keys are internal labels; patterns match Ukrainian/Russian.
_KINDS = {
    "ргр": r"ргр", "мкр": r"мкр", "кп": r"кп", "лаба": r"лаб\w*|лр", "тест": r"тест\w*",
    "конспект": r"конспект\w*", "практична": r"практи\w*|пр", "самостійна": r"самостійн\w*",
    "презентація": r"презентаці\w*", "реферат": r"реферат\w*",
}
_KIND_RES = {k: re.compile(r"(?<!\w)(" + v + r")(?!\w)", re.IGNORECASE) for k, v in _KINDS.items()}


def _kinds(title: str) -> set[str]:
    return {k for k, rx in _KIND_RES.items() if rx.search(title)}


def _same_kind(a: Task, b: Task) -> bool:
    """Same kind of work and the numbers do not contradict ("lab 3" != "lab 4")."""
    if not (_kinds(a.title) & _kinds(b.title)):
        return False
    na, nb = _keywords(a.title)[0], _keywords(b.title)[0]
    return not na or not nb or na == nb


def _subject_ok(a: Task, b: Task) -> bool:
    return _same_subject(a, b) or a.subject is None or b.subject is None


def _same_subject(a: Task, b: Task) -> bool:
    return a.subject is not None and b.subject is not None and a.subject.lower() == b.subject.lower()


def is_duplicate(a: Task, b: Task) -> bool:
    if a.deadline is None and b.deadline is None:
        # undated tasks: forwarded to several chats, or the same task worded differently
        if SequenceMatcher(None, a.title.lower(), b.title.lower()).ratio() >= 0.85:
            return True
        return _subject_ok(a, b) and _same_kind(a, b)
    if a.deadline is None or b.deadline is None:
        # an undated Telegram message about a task that Moodle/Classroom already has with a deadline
        undated = a if a.deadline is None else b
        return not undated.structured and _same_subject(a, b) and (_same_kind(a, b) or _similar(a, b))
    if a.deadline.date() != b.deadline.date():
        return False
    if a.structured and b.structured and a.source == b.source:
        return False  # two separate Moodle entries are two tasks
    same_time = a.deadline == b.deadline or a.time_assumed or b.time_assumed
    if _same_subject(a, b):
        return _similar(a, b) or (same_time and (a.structured != b.structured))
    if a.subject is None or b.subject is None:
        return same_time and _similar(a, b)
    return False


def _merge(primary: Task, other: Task) -> Task:
    if other.structured and not primary.structured:
        primary, other = other, primary
    elif primary.deadline is None and other.deadline is not None:
        primary, other = other, primary  # keep the entry that has a date
    elif primary.deadline is None and other.deadline is None:
        if len(other.match_text or other.title) > len(primary.match_text or primary.title):
            primary, other = other, primary  # no dates: keep the more detailed message
    primary.extra_sources.append(other.source)
    primary.extra_sources.extend(other.extra_sources)
    if other.status == DONE:
        primary.status = DONE
    if primary.subject is None:
        primary.subject = other.subject
    if primary.time_assumed and not other.time_assumed:
        primary.deadline, primary.time_assumed = other.deadline, False
    if primary.structured or other.structured:
        # exact API data resolves doubts that came from parsing free text
        primary.notes = [n for n in primary.notes if "subject" in n and primary.subject is None]
        if primary.status == UNCLEAR and not primary.notes:
            primary.status = NEW
    primary.url = primary.url or other.url
    return primary


def dedupe(tasks: list[Task]) -> list[Task]:
    # structured entries first, so they become the "primary" records
    ordered = sorted(tasks, key=lambda t: not t.structured)
    result: list[Task] = []
    for t in ordered:
        for i, existing in enumerate(result):
            if is_duplicate(existing, t):
                result[i] = _merge(existing, t)
                break
        else:
            result.append(t)
    return result


def in_window(task: Task, now: datetime, until: datetime) -> bool:
    if task.deadline is None:
        return task.status == UNCLEAR  # undated tasks are kept (they are marked unclear)
    if not task.structured:
        # a task given in Telegram during the last days is shown even if it is due after the horizon
        return task.deadline >= now
    return now <= task.deadline <= until


def apply_notices(tasks: list[Task], notices: list[Notice]) -> tuple[list[Task], list[tuple[Notice, list[Task]]]]:
    """Tasks affected by a postponement/cancellation are removed from the table."""
    removed_by: list[tuple[Notice, list[Task]]] = []
    remaining = list(tasks)
    for n in notices:
        hit = []
        if n.subject:
            probe = Task(subject=n.subject, title=n.text, deadline=None, source=n.source)
            for t in remaining:
                if not _same_subject(t, probe):
                    continue
                if (t.deadline and t.deadline.date() in n.dates) or _similar(t, probe):
                    hit.append(t)
        remaining = [t for t in remaining if t not in hit]
        removed_by.append((n, hit))
    return remaining, removed_by


def sort_tasks(tasks: list[Task]) -> list[Task]:
    return sorted(tasks, key=lambda t: t.deadline.timestamp() if t.deadline else float("inf"))


_SPLIT_RE = re.compile(r"[\W_]+", re.UNICODE)
_LETTER_DIGIT_RE = re.compile(r"(?<=[^\W\d_])(?=\d)|(?<=\d)(?=[^\W\d_])")
_SUB_STOP = {"завдання", "робота", "роботи", "роботу", "варіант", "файл", "docx", "pdf", "jpg", "png", "здача"}


# Latin look-alikes inside Cyrillic words: "Cкладні" (Latin C) must match "Складний"
_LOOKALIKES = str.maketrans("aceiopxyk", "асеіорхук")
_CYR_RE = re.compile(r"[а-яіїєґ]")


_LATIN_KINDS = {"kp": "кп", "rgr": "ргр", "lab": "лаб", "laba": "лаба", "mkr": "мкр"}


def _fix_lookalikes(word: str) -> str:
    if word in _LATIN_KINDS:  # KP5_Petrenko.cpp
        return _LATIN_KINDS[word]
    return word.translate(_LOOKALIKES) if _CYR_RE.search(word) else word


def _sub_tokens(text: str) -> tuple[set[str], set[str], set[str]]:
    text = _LETTER_DIGIT_RE.sub(" ", text.replace("_", " "))  # "КП4", "РГР1" -> "КП 4", "РГР 1"
    words = [_fix_lookalikes(w.lower()) for w in _SPLIT_RE.split(text) if w]
    numbers = {w for w in words if w.isdigit() and len(w) <= 2}
    stems = {w[:5] for w in words if len(w) >= 5 and not w.isdigit() and w not in _SUB_STOP}
    return numbers, stems, _kinds(" ".join(words))


# a number belongs to a kind of work only when it stands right after it ("лаба 3", "практична робота 4",
# "ЛР 1-3" -> 1) or right before a short form ("4 пр", "KP4"); "здати 4 лабораторні" is a count, not lab 4
_FILLER = {"робота", "роботу", "роботи", "работа", "работу", "работы", "номер", "no", "n"}
_SHORT_KINDS = {"пр", "лр", "кп", "ргр", "мкр", "лаб"}


def _kind_numbers(text: str) -> dict[str, set[str]]:
    text = _LETTER_DIGIT_RE.sub(" ", text.replace("_", " "))
    words = [_fix_lookalikes(w.lower()) for w in _SPLIT_RE.split(text) if w]
    out: dict[str, set[str]] = {}
    for i, w in enumerate(words):
        kinds = _kinds(w)
        if not kinds:
            continue
        nums: set[str] = set()
        j = i + 1
        while j < len(words) and words[j] in _FILLER:
            j += 1
        if j < len(words) and words[j].isdigit() and len(words[j]) <= 2:
            nums.add(words[j])
            # "лабу 3 и 4" / "3 і 4": a second number joined by "and"
            if j + 2 < len(words) and words[j + 1] in ("і", "и", "та", "й") and words[j + 2].isdigit():
                nums.add(words[j + 2])
        elif w in _SHORT_KINDS and i > 0 and words[i - 1].isdigit() and len(words[i - 1]) <= 2:
            nums.add(words[i - 1])
        for k in kinds:
            out.setdefault(k, set()).update(nums)
    return out


def match_strength(task: Task, sub_text: str) -> int:
    """2: same kind of work with the same number (RGR 1, KP 4); 1: two or more shared words; 0: no match.
    A task without a number ("submit 4 labs") is never closed by a numbered file ("Lab_1-3")."""
    _, ts, _ = _sub_tokens(task.match_text or task.title)
    _, ss, _ = _sub_tokens(sub_text)
    tk, sk = _kind_numbers(task.match_text or task.title), _kind_numbers(sub_text)
    shared = tk.keys() & sk.keys()
    for kind in shared:
        tnums, snums = tk[kind], sk[kind]
        if (tnums and snums and tnums & snums) or (not tnums and not snums):
            return 2
    # same kind but different numbers ("lab 3" vs "lab 1") is a mismatch, not a weak match
    return 1 if not shared and len(ts & ss) >= 2 else 0


def is_submitted(task: Task, sub_text: str) -> bool:
    return match_strength(task, sub_text) > 0


def _applies(t: Task, s: Submission) -> bool:
    if s.subject and t.subject and s.subject != t.subject:
        return False  # a file from the "Physics" folder does not close a graphics task
    if s.any_time or t.posted is None:
        return True
    return s.date >= t.posted  # a file in a chat counts only if sent after the task was given


def hide_submitted(tasks: list[Task], submissions: list[Submission]) -> tuple[list[Task], list[tuple[Task, Submission]]]:
    """Removes tasks for which your finished work was found: a file in a chat or in the Education folder.
    Chats are checked only for Telegram tasks (Moodle/Classroom already report submission status)."""
    kept, hidden = [], []
    for t in tasks:
        scored = [(match_strength(t, s.text), s) for s in submissions
                  if (not t.structured or s.any_time) and _applies(t, s)]
        best = max(scored, key=lambda x: x[0], default=(0, None))
        match = best[1] if best[0] > 0 else None
        if match:
            hidden.append((t, match))
        else:
            kept.append(t)
    return kept, hidden
