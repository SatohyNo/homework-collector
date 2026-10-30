"""Google Classroom. Main path: your own Apps Script web app (URL in ~/.dz/classroom-url) that
returns all courses, coursework, submissions and announcements as one JSON. Fallback: an OAuth
token (~/.dz/google-token.json) and the official Classroom API. Read-only."""

import json
from datetime import datetime, timedelta, timezone

import requests

from .config import Config, read_secret, secret_path
from .security import ensure_private, require_host
from .models import CLASSROOM, NEW, UNCLEAR, Notice, Task
from .textitems import text_to_item
from .textparse import canonical_subject

API = "https://classroom.googleapis.com/v1/"
SUBMITTED_STATES = {"TURNED_IN", "RETURNED"}


def available() -> bool:
    return secret_path("CLASSROOM_URL_FILE").exists() or secret_path("CLASSROOM_TOKEN_FILE").exists()


def fetch_dump() -> dict:
    url = read_secret("CLASSROOM_URL_FILE")
    if url:
        require_host(url, ("script.google.com",), "Classroom web app URL")
        resp = requests.get(url, timeout=360)  # Apps Script redirects to googleusercontent
        require_host(resp.url, ("google.com", "googleusercontent.com"), "Classroom redirect")
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError:
            raise RuntimeError("the web app did not return JSON (check that access is set to Anyone)") from None
        if "error" in data:
            raise RuntimeError(f"web app: {data['error']}")
        return data
    return _dump_via_api()


def _dump_via_api() -> dict:
    ensure_private(secret_path("CLASSROOM_CLIENT_FILE"))
    ensure_private(secret_path("CLASSROOM_TOKEN_FILE"))
    client = json.loads(secret_path("CLASSROOM_CLIENT_FILE").read_text())
    client = client.get("installed") or client.get("web")
    token = json.loads(secret_path("CLASSROOM_TOKEN_FILE").read_text())
    access = requests.post("https://oauth2.googleapis.com/token", timeout=60, data={
        "client_id": client["client_id"], "client_secret": client["client_secret"],
        "refresh_token": token["refresh_token"], "grant_type": "refresh_token",
    }).json()["access_token"]
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {access}"

    def get_all(path: str, key: str, **params) -> list:
        items, page = [], None
        while True:
            q = {"pageSize": 100, **params, **({"pageToken": page} if page else {})}
            res = session.get(API + path, params=q, timeout=60)
            res.raise_for_status()
            body = res.json()
            items += body.get(key, [])
            page = body.get("nextPageToken")
            if not page:
                return items

    def safe(*a, **kw):
        try:
            return get_all(*a, **kw)
        except requests.RequestException as e:
            return {"error": str(e)}

    courses = get_all("courses", "courses", studentId="me")
    detail = {}
    for c in courses:
        base = f"courses/{c['id']}/"
        detail[c["id"]] = {
            "name": c.get("name"), "state": c.get("courseState"), "link": c.get("alternateLink"),
            "coursework": safe(base + "courseWork", "courseWork"),
            "submissions": safe(base + "courseWork/-/studentSubmissions", "studentSubmissions", userId="me"),
            "announcements": safe(base + "announcements", "announcements"),
        }
    return {"courses": courses, "courses_detail": detail}


def _due(work: dict, cfg: Config) -> tuple[datetime | None, bool]:
    d = work.get("dueDate")
    if not d:
        return None, False
    t = work.get("dueTime")
    if not t:
        # no time given: do not guess, use 23:59 and mark it
        return datetime(d["year"], d["month"], d["day"], 23, 59, tzinfo=cfg.tz), True
    utc = datetime(d["year"], d["month"], d["day"], t.get("hours", 0), t.get("minutes", 0), tzinfo=timezone.utc)
    return utc.astimezone(cfg.tz), False


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def collect(dump: dict, cfg: Config, now: datetime, warn) -> tuple[list[Task], list[Notice]]:
    tasks: list[Task] = []
    notices: list[Notice] = []
    until = cfg.deadline_until(now)
    since = now - timedelta(days=cfg.days_back)

    for cid, c in dump.get("courses_detail", {}).items():
        if c.get("state") not in (None, "ACTIVE"):
            continue
        name = c.get("name") or cid
        subject = canonical_subject(name, cfg.subjects)

        work_list, subs = c.get("coursework"), c.get("submissions")
        if isinstance(work_list, dict):
            err = str(work_list.get("error", ""))
            warn(f"Classroom: \"{name}\": " + ("coursework is hidden from students" if "permission" in err else f"coursework unavailable ({err[:80]})"))
            work_list = []
        submitted = set()
        if isinstance(subs, list):
            submitted = {s["courseWorkId"] for s in subs if s.get("state") in SUBMITTED_STATES}
        for work in work_list or []:
            if work.get("state", "PUBLISHED") != "PUBLISHED":
                continue
            deadline, time_missing = _due(work, cfg)
            if deadline is None or not (now <= deadline <= until) or work["id"] in submitted:
                continue
            tasks.append(Task(
                subject=subject,
                title=work.get("title", "(untitled)"),
                deadline=deadline,
                source=CLASSROOM,
                status=UNCLEAR if time_missing else NEW,
                notes=["no time given (23:59 assumed)"] if time_missing else [],
                url=work.get("alternateLink"),
                time_assumed=time_missing,
            ))

        anns = c.get("announcements")
        if isinstance(anns, dict):
            warn(f"Classroom: \"{name}\": announcements unavailable ({anns.get('error')})")
            anns = []
        for ann in anns or []:
            posted = _ts(ann.get("updateTime") or ann["creationTime"])
            if posted < since:
                continue
            item = text_to_item(ann.get("text", ""), posted, CLASSROOM, cfg, fixed_subject=name, url=ann.get("alternateLink"))
            if isinstance(item, Notice):
                notices.append(item)
            elif item is not None:
                tasks.append(item)

    return tasks, notices
