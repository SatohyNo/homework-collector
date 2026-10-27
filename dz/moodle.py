"""Moodle via its REST web service (the same one the Moodle mobile app uses). Read-only."""

from datetime import datetime, timedelta, timezone

import requests

from .config import Config
from .models import DONE, MOODLE, NEW, Notice, Task
from .textitems import text_to_item
from .textparse import canonical_subject, strip_html


class MoodleError(RuntimeError):
    pass


class MoodleClient:
    def __init__(self, base_url: str, token: str):
        self.url = base_url.rstrip("/") + "/webservice/rest/server.php"
        self.token = token

    def call(self, function: str, **params):
        data = {"wstoken": self.token, "wsfunction": function, "moodlewsrestformat": "json"}
        data.update(_flatten(params))
        resp = requests.post(self.url, data=data, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        if isinstance(body, dict) and body.get("exception"):
            raise MoodleError(f"{function}: {body.get('message') or body.get('errorcode')}")
        return body


def _flatten(params: dict, prefix: str = "") -> dict:
    """{'courseids': [1, 2]} -> {'courseids[0]': 1, 'courseids[1]': 2}"""
    out = {}
    for key, value in params.items():
        name = f"{prefix}[{key}]" if prefix else str(key)
        if isinstance(value, dict):
            out.update(_flatten(value, name))
        elif isinstance(value, (list, tuple)):
            out.update(_flatten(dict(enumerate(value)), name))
        else:
            out[name] = value
    return out


def collect(client: MoodleClient, cfg: Config, now: datetime, warn) -> tuple[list[Task], list[Notice]]:
    tasks: list[Task] = []
    notices: list[Notice] = []
    until = cfg.deadline_until(now)
    since = now - timedelta(days=cfg.days_back)

    site = client.call("core_webservice_get_site_info")
    base = site.get("siteurl", "").rstrip("/")
    courses = client.call("core_enrol_get_users_courses", userid=site["userid"])
    course_names = {c["id"]: c.get("fullname") or c.get("shortname") for c in courses}
    course_ids = list(course_names)
    if not course_ids:
        return tasks, notices

    # 1. Assignments with a due date inside the window + your submission status
    seen_assign: set[int] = set()
    try:
        data = client.call("mod_assign_get_assignments", courseids=course_ids)
        for course in data.get("courses", []):
            for a in course.get("assignments", []):
                due = a.get("duedate") or 0
                if not due:
                    continue
                deadline = datetime.fromtimestamp(due, tz=timezone.utc).astimezone(cfg.tz)
                if not (now <= deadline <= until):
                    continue
                seen_assign.add(a.get("cmid"))
                tasks.append(Task(
                    subject=canonical_subject(course_names.get(course["id"]), cfg.subjects),
                    title=a["name"],
                    deadline=deadline,
                    source=MOODLE,
                    status=_assign_status(client, a["id"], warn),
                    url=f"{base}/mod/assign/view.php?id={a['cmid']}" if base and a.get("cmid") else None,
                ))
    except MoodleError as e:
        warn(f"Moodle: could not load assignments ({e})")

    # 2. Other activities with deadlines (quizzes, workshops...) from the calendar
    try:
        events = client.call(
            "core_calendar_get_action_events_by_timesort",
            timesortfrom=int(now.timestamp()), timesortto=int(until.timestamp()), limitnum=50,
        ).get("events", [])
        for ev in events:
            # in calendar events "instance" is the assignment cmid, not its id
            if ev.get("modulename") == "assign" and ev.get("instance") in seen_assign:
                continue
            course = ev.get("course") or {}
            tasks.append(Task(
                subject=canonical_subject(course.get("fullname") or course_names.get(ev.get("courseid")), cfg.subjects),
                title=ev.get("activityname") or ev.get("name"),
                deadline=datetime.fromtimestamp(ev["timesort"], tz=timezone.utc).astimezone(cfg.tz),
                source=MOODLE,
                status=NEW,
                url=ev.get("url"),
            ))
    except MoodleError as e:
        warn(f"Moodle: could not load the calendar ({e})")

    # 3. Announcements (news forum) from the last N days, if they contain a deadline
    try:
        forums = client.call("mod_forum_get_forums_by_courses", courseids=course_ids)
        for forum in forums:
            if forum.get("type") != "news":
                continue
            subject = course_names.get(forum.get("course"))
            try:
                discussions = client.call("mod_forum_get_forum_discussions", forumid=forum["id"], page=0, perpage=30)
            except MoodleError:
                discussions = client.call("mod_forum_get_forum_discussions_paginated", forumid=forum["id"], page=0, perpage=30)
            for d in discussions.get("discussions", []):
                posted = datetime.fromtimestamp(d.get("created") or d.get("timemodified"), tz=timezone.utc)
                if posted < since:
                    continue
                text = (d.get("name") or d.get("subject") or "") + "\n" + strip_html(d.get("message", ""))
                item = text_to_item(text, posted, MOODLE, cfg, fixed_subject=subject,
                                    url=f"{base}/mod/forum/discuss.php?d={d.get('discussion')}" if base else None)
                if isinstance(item, Notice):
                    notices.append(item)
                elif item is not None:
                    tasks.append(item)
    except MoodleError as e:
        warn(f"Moodle: could not load announcements ({e})")

    return tasks, notices


def _assign_status(client: MoodleClient, assign_id: int, warn) -> str:
    try:
        st = client.call("mod_assign_get_submission_status", assignid=assign_id)
    except MoodleError as e:
        warn(f"Moodle: submission status for assignment {assign_id} is unavailable ({e})")
        return NEW
    attempt = st.get("lastattempt") or {}
    sub = attempt.get("submission") or attempt.get("teamsubmission") or {}
    return DONE if sub.get("status") == "submitted" else NEW
