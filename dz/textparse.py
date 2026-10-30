"""Free-text parsing: keywords, dates, subject, postponed/cancelled notices.

The keyword lists are Ukrainian and Russian on purpose: they match how teachers and
classmates actually write in university chats.
"""

import html
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

KEYWORDS_RE = re.compile(
    r"(?<!\w)(дз|д/з|завдання|здати|здач\w*|дедлайн\w*|deadline|термін\w*|лаб\w*|кп|до|включно)(?!\w)",
    re.IGNORECASE,
)

POSTPONED_RE = re.compile(r"перен[еі]с\w*|перенос\w*|відклад\w*|продовж\w* (термін|дедлайн)", re.IGNORECASE)
CANCELLED_RE = re.compile(
    r"скасов\w*|відмін\w*|отмен\w*|не потрібно здавати|не треба здавати|не здаємо", re.IGNORECASE
)

MONTHS = {
    # Ukrainian, genitive case
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4, "травня": 5, "червня": 6,
    "липня": 7, "серпня": 8, "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12,
    # Russian
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

# (?!\.\d|\() keeps exercise numbers like "3.2.43" or "3.2.47(2)" from becoming the date 03.02
NUM_DATE_RE = re.compile(r"(?<![\d:.])(\d{1,2})[./](\d{1,2})(?:[./](\d{4}|\d{2}))?(?![\d:(]|[./]\d)")
TEXT_DATE_RE = re.compile(
    r"(?<!\d)(\d{1,2})(?:-?(?:го|е|ого))?\s+(" + "|".join(MONTHS) + r")(?:\s+(\d{4}))?",
    re.IGNORECASE,
)
# 23:59 anywhere; 23.59 only after "о/об" ("at"), otherwise it clashes with a date like 15.11
TIME_RE = re.compile(r"(?<![\d.])([01]?\d|2[0-3]):([0-5]\d)(?!\d)|(?<!\w)(?:о|об)\s+([01]?\d|2[0-3])\.([0-5]\d)(?!\d)")
RELATIVE_RE = re.compile(r"(?<!\w)(сьогодні|сегодня|післязавтра|послезавтра|завтра)(?!\w)", re.IGNORECASE)
RELATIVE_SHIFT = {"сьогодні": 0, "сегодня": 0, "завтра": 1, "післязавтра": 2, "послезавтра": 2}
# words after which a date is most likely the deadline ("until", "submit", "deadline", ...)
DEADLINE_HINT_RE = re.compile(r"(до|здати|здача|дедлайн|deadline|термін|включно)\W{0,3}(\w+\W{0,3}){0,2}$", re.IGNORECASE)


@dataclass
class ParsedDeadline:
    deadline: datetime | None = None
    time_assumed: bool = False
    problems: list[str] = field(default_factory=list)
    all_dates: list[date] = field(default_factory=list)
    found_anything: bool = False  # whether the text has any date or time at all


def strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", text or "", flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"[ \t ]+", " ", text).strip()


def has_keyword(text: str) -> bool:
    return bool(KEYWORDS_RE.search(text or ""))


# For undated messages "до" ("until") and "включно" ("inclusive") are too generic, so an explicit
# assignment word is required (homework, lab, essay, draw, solve...). "КП-51" is a group code,
# not "КП" (computer practicum). "4 пр", "пр 4", "ЛР 3" are short forms of practical/lab work,
# common in file names a teacher posts without any text.
ASSIGNMENT_RE = re.compile(
    r"(?<!\w)(дз|д/з|домашн\w*|завдан\w*|задани\w*|здати|здаємо|здавати|сдать|сдавать|лаб\w*|кп(?!-\d)|ргр|"
    r"практичн\w*|практическ\w*|самостійн\w*|самостійно|контрольн\w*|реферат\w*|презентаці\w*|презентации|"
    r"конспект\w*|задач\w*|вправ\w*|номер\w*|№|classtime|тест\w*|дедлайн\w*|термін\w*|включно|"
    r"накреслит\w*|креслит\w*|виконат\w*|зробит\w*|підготуват\w*|опрацюван\w*|опрацюват\w*|розв'?язат\w*|"
    r"вивчит\w*|прочитат\w*|делать|сделать|подготовить|"
    r"(?:пр|лр)\.?\s*№?\s*\d{1,2}|\d{1,2}\s*(?:пр|лр))(?!\w)",
    re.IGNORECASE,
)


# For a post that is only a file (no assignment words in the text) the file name must name a kind
# of work. The generic "завдання" is not enough: "Тема_3_Структура_та_завдання_ЗСУ.pdf" is a lecture.
FILE_TASK_RE = re.compile(
    r"(?<!\w)(дз|домашн\w*|лаб\w*|кп|ргр|мкр|практичн\w*|самостійн\w*|контрольн\w*|реферат\w*|"
    r"варіант\w*|вар|(?:пр|лр)\.?\s*№?\s*\d{1,2}|\d{1,2}\s*(?:пр|лр))(?!\w)",
    re.IGNORECASE,
)


def file_names_task(names: list[str]) -> bool:
    # "ЛР3_звіт" -> "ЛР 3 звіт"
    return any(FILE_TASK_RE.search(re.sub(r"(?<=\D)(?=\d)|(?<=\d)(?=\D)", " ", n.replace("_", " ")))
               for n in names)


# In a general class chat classmates and the class representative talk about labs all the time
# ("I haven't heard about lab 3"). There a post must actually tell you to do something.
DIRECTIVE_RE = re.compile(
    r"(?<!\w)(дз|д/з|домашн\w*|задан[оі]|задали|задал[аи]?|здати|здавати|здаємо|сдать|сдавать|сдаем|"
    r"зробити|сделать|делать|виконати|выполнить|підготувати|подготовить|опрацювати|написати|написать|"
    r"накреслити|креслити|розв'?язати|решить|прочитати|прочитать|вивчити|выучить|дедлайн\w*|термін\w*|"
    r"срок\w*|треба|потрібно|необхідно|нужно|надо|classtime)(?!\w)",
    re.IGNORECASE,
)
# optional things ("you can prepare theses for the conference") are not homework
OPTIONAL_RE = re.compile(r"(?<!\w)(можете|можна за бажанням|за бажанням|по бажанню|по желанию)(?!\w)",
                         re.IGNORECASE)


def is_directive(text: str) -> bool:
    return bool(DIRECTIVE_RE.search(text or ""))


def is_optional(text: str) -> bool:
    return bool(OPTIONAL_RE.search(text or ""))


def looks_like_assignment(text: str) -> bool:
    t = (text or "").strip()
    if not ASSIGNMENT_RE.search(t.replace("_", " ")):  # file names: "ЛР3_звіт.pdf"
        return False
    # short questions in a chat ("what's the homework?") are not assignments
    return not (t.endswith("?") and len(t) < 120)


def notice_kind(text: str) -> str | None:
    if CANCELLED_RE.search(text):
        return "cancelled"
    if POSTPONED_RE.search(text):
        return "postponed"
    return None


def _infer_year(day: int, month: int, posted: date) -> date | None:
    """No year given: take the nearest date that is not more than ~2 months before the message."""
    for year in (posted.year, posted.year + 1):
        try:
            d = date(year, month, day)
        except ValueError:
            return None
        if d >= posted - timedelta(days=60):
            return d
    return None


# "таблиця 6.1", "пункт 2.3", "рис. 4.5", "тема 3.2", "№ 1.12" are references, not dates
NOT_A_DATE_BEFORE_RE = re.compile(
    r"(таблиц\w*|табл\.?|рис\w*\.?|пункт\w*|п\.|розділ\w*|раздел\w*|§|стор\.?|с\.|№|вправ\w*|"
    r"упражнени\w*|задач\w*|тем[аиуы]|варіант\w*|вариант\w*|формул\w*|параграф\w*)\s*$",
    re.IGNORECASE,
)

# "дедлайн 2 тижні", "термін 3 дні", "срок неделя": a period counted from the message date
PERIOD_RE = re.compile(
    r"(?:дедлайн|deadline|термін|срок|на виконання|здати за|сдать за)\W{0,3}"
    r"(\d{1,2}|один|одна|одну|два|дві|две|три|чотири|четыре)?\s*"
    r"(тиж\w*|недел\w*|дн\w*|день|дня)",
    re.IGNORECASE,
)
_NUMBER_WORDS = {"один": 1, "одна": 1, "одну": 1, "два": 2, "дві": 2, "две": 2, "три": 3, "чотири": 4, "четыре": 4}


def _period_deadline(text: str, posted: date) -> date | None:
    m = PERIOD_RE.search(text)
    if not m:
        return None
    raw = (m.group(1) or "1").lower()
    n = int(raw) if raw.isdigit() else _NUMBER_WORDS[raw]
    weeks = m.group(2).lower().startswith(("тиж", "недел"))
    return posted + timedelta(days=n * 7 if weeks else n)


def _find_dates(text: str, posted: date) -> list[tuple[int, date]]:
    found: list[tuple[int, date]] = []
    for m in NUM_DATE_RE.finditer(text):
        if NOT_A_DATE_BEFORE_RE.search(text[max(0, m.start() - 20):m.start()]):
            continue
        day, month, year = int(m.group(1)), int(m.group(2)), m.group(3)
        if not (1 <= day <= 31 and 1 <= month <= 12):
            continue
        if year:
            y = int(year) + (2000 if len(year) == 2 else 0)
            if abs(y - posted.year) > 1:  # "3.2.20" is an exercise number, not 03.02.2020
                continue
            try:
                found.append((m.start(), date(y, month, day)))
            except ValueError:
                pass
        elif (d := _infer_year(day, month, posted)) is not None:
            found.append((m.start(), d))
    for m in TEXT_DATE_RE.finditer(text):
        day, month = int(m.group(1)), MONTHS[m.group(2).lower()]
        if m.group(3):
            try:
                found.append((m.start(), date(int(m.group(3)), month, day)))
            except ValueError:
                pass
        elif (d := _infer_year(day, month, posted)) is not None:
            found.append((m.start(), d))
    return sorted(found)


def _find_times(text: str) -> list[tuple[int, time]]:
    out = []
    for m in TIME_RE.finditer(text):
        h, mi = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        out.append((m.start(), time(int(h), int(mi))))
    return out


def _pick(items: list[tuple[int, object]], text: str):
    """One unique value: take it. Several: take the one preceded by "until/submit/deadline"."""
    unique = list(dict.fromkeys(v for _, v in items))
    if len(unique) <= 1:
        return (unique[0] if unique else None), unique
    hinted = list(dict.fromkeys(v for pos, v in items if DEADLINE_HINT_RE.search(text[max(0, pos - 25):pos])))
    if len(hinted) == 1:
        return hinted[0], unique
    return None, unique


def extract_deadline(text: str, posted: datetime, tz: ZoneInfo) -> ParsedDeadline:
    posted_local = posted.astimezone(tz)
    res = ParsedDeadline()

    dates = _find_dates(text, posted_local.date())
    times = _find_times(text)
    rel = RELATIVE_RE.search(text)

    the_date, uniq_dates = _pick(dates, text)
    the_time, uniq_times = _pick(times, text)
    res.all_dates = uniq_dates
    if not uniq_dates and (period := _period_deadline(text, posted_local.date())):
        the_date, uniq_dates = period, [period]
    res.found_anything = bool(uniq_dates or uniq_times)
    if not res.found_anything:
        return res

    if len(uniq_dates) > 1 and the_date is None:
        res.problems.append("several dates (" + ", ".join(d.strftime("%d.%m") for d in uniq_dates) + "), unclear which is the deadline")
    if len(uniq_times) > 1 and the_time is None:
        res.problems.append("several times (" + ", ".join(t.strftime("%H:%M") for t in uniq_times) + ")")

    if not uniq_dates and the_time is not None:
        if rel:
            the_date = posted_local.date() + timedelta(days=RELATIVE_SHIFT[rel.group(1).lower()])
        else:
            res.problems.append(f"only a time is given ({the_time:%H:%M}), the date is unknown")

    if the_date is None:
        return res

    if the_time is None:
        if not uniq_times:
            res.problems.append("no time given (23:59 assumed)")
        the_time = time(23, 59)
        res.time_assumed = True
    res.deadline = datetime.combine(the_date, the_time, tzinfo=tz)
    return res


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def canonical_subject(name: str | None, subjects: dict[str, list[str]]) -> str | None:
    """Course/chat name -> canonical subject name from config.json (or the name as is)."""
    if not name:
        return None
    matches = guess_subjects(name, subjects)
    return matches[0] if len(matches) == 1 else name.strip()


def guess_subjects(text: str, subjects: dict[str, list[str]]) -> list[str]:
    t = _norm(text)
    hits = []
    for canon, aliases in subjects.items():
        for alias in [canon, *aliases]:
            if re.search(r"(?<!\w)" + re.escape(_norm(alias)) + r"(?!\w)", t):
                hits.append(canon)
                break
    return hits


def short_title(text: str, limit: int = 90) -> str:
    """One line: the first line with an assignment keyword (or simply the first line)."""
    lines = [ln.strip(" -•*\t") for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return "(no text)"
    line = next((ln for ln in lines if ASSIGNMENT_RE.search(ln) and not ln.startswith("📎")),
                next((ln for ln in lines if has_keyword(ln)), lines[0]))
    line = re.sub(r"https?://(?:www\.)?([^/\s]+)\S*", r"\1", line)  # long link -> classtime.com
    line = re.sub(r"\s+", " ", line)
    return line if len(line) <= limit else line[: limit - 1].rstrip() + "…"
