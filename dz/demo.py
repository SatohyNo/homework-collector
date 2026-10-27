"""Sample data for --demo: shows parsing, duplicate merging and postponed tasks without any network access.

Task titles are English; the Telegram messages stay Ukrainian because that is what the parser reads.
"""

from datetime import datetime, time, timedelta

from .config import Config
from .models import CLASSROOM, DONE, MOODLE, TELEGRAM, Notice, Task
from .textitems import text_to_item


def collect(cfg: Config, now: datetime) -> tuple[list[Task], list[Notice]]:
    def at(days: int, hh: int, mm: int) -> datetime:
        return datetime.combine((now + timedelta(days=days)).date(), time(hh, mm), tzinfo=cfg.tz)

    def ddmm(days: int) -> str:
        return (now + timedelta(days=days)).strftime("%d.%m")

    tasks = [
        Task("Programming", "Lab 3. Classes and objects", at(5, 23, 59), MOODLE),
        Task("Programming", "Lab 2. Functions", at(2, 23, 59), MOODLE, status=DONE),
        Task("Calculus", "Quiz: limits of sequences", at(9, 18, 0), MOODLE),
        Task("Databases", "ER diagram for the course project", at(12, 12, 0), CLASSROOM),
        Task("Databases", "Old task outside the window", at(45, 12, 0), CLASSROOM),
    ]
    notices: list[Notice] = []
    messages = [
        # duplicate of Lab 3 from Moodle: "Reminder: submit lab 3 by <date> 23:59 inclusive"
        ("Programming", f"Нагадую: лаба 3 здати до {ddmm(5)} 23:59 включно", 1),
        # new task only in Telegram, no time: "Homework: exercises 145-150, by <date>"
        ("Calculus", f"ДЗ: №145-150 зі збірника, до {ddmm(3)}", 2),
        # two dates, the deadline is not guessed: "Course project: stage one <date>, stage two <date>"
        ("Databases", f"КП: перший етап {ddmm(7)}, другий етап {ddmm(20)}", 3),
        # postponed: "The limits quiz is moved from <date> to later"
        ("Calculus", f"Тест з границь перенесено з {ddmm(9)} на пізніше, дату повідомлю", 0),
        # no date and nothing concrete: ignored ("Don't forget about the lab")
        ("Programming", "Не забудьте про лабу", 1),
    ]
    for subject, text, days_ago in messages:
        item = text_to_item(text, now - timedelta(days=days_ago), TELEGRAM, cfg, fixed_subject=subject)
        if isinstance(item, Notice):
            notices.append(item)
        elif item is not None:
            tasks.append(item)
    return tasks, notices
