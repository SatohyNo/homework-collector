from datetime import datetime
from html import escape

from .models import TELEGRAM, Notice, Task

HEADERS = ["#", "Subject", "Task", "Source"]


def _cut(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def source_short(t: Task) -> str:
    """Short: "Moodle · due 14.11" or "TG · Graphics · 22.10"."""
    parts = []
    for src in dict.fromkeys([t.source, *t.extra_sources]):
        parts.append(f"TG · {t.origin}" if src == TELEGRAM and t.origin else ("TG" if src == TELEGRAM else src))
    if t.deadline:
        parts.append(f"due {t.deadline:%d.%m}")
    elif t.posted:
        parts.append(f"{t.posted:%d.%m}")
    return " · ".join(parts)


def render(tasks: list[Task], notices: list[tuple[Notice, list[Task]]], warnings: list[str],
           now: datetime, until: datetime, hidden: list) -> str:
    rows = [[str(i), _cut(t.subject or "?", 24), _cut(t.title, 70), source_short(t)] for i, t in enumerate(tasks, 1)]
    for n, hit in notices:
        what = ", ".join(h.title for h in hit) or n.text
        rows.append(["", _cut(n.subject or "?", 24), _cut(f"[{n.kind}] {what}", 70), f"{n.source} · {n.posted:%d.%m}"])

    widths = [max(len(h), *(len(r[c]) for r in rows)) if rows else len(h) for c, h in enumerate(HEADERS)]

    def line(cells):
        return "| " + " | ".join(c.ljust(w) for c, w in zip(cells, widths)) + " |"

    out = [f"Homework due by {until:%d.%m.%Y}  (updated {now:%d.%m %H:%M})", "",
           line(HEADERS), "|" + "|".join("-" * (w + 2) for w in widths) + "|"]
    out += [line(r) for r in rows] or ["(no tasks)"]
    out += ["", f"Tasks: {len(tasks)}"]
    if hidden:
        out += ["", f"Hidden as done ({len(hidden)}), your file was found:"]
        out += [f"  ✓ {t.subject or '?'} — {_cut(t.title, 50)}  ←  {_cut(s.text.strip(), 45)} ({s.where}, {s.date:%d.%m})"
                for t, s in hidden]
    if warnings:
        out += [""] + [f"! {w}" for w in warnings]
    return "\n".join(out)


def render_telegram(tasks: list[Task], notices: list[tuple[Notice, list[Task]]], now: datetime, until: datetime) -> str:
    """The same list for Saved Messages: a wide table does not fit a phone screen, so it is a list."""
    out = [f"<b>📚 Homework due by {until:%d.%m}</b>  <i>({now:%d.%m %H:%M})</i>", ""]
    for i, t in enumerate(tasks, 1):
        head = f"{i}. <b>{escape(t.subject or '?')}</b> — {escape(t.title)}"
        if t.url:
            head += f' <a href="{escape(t.url)}">↗</a>'
        out += [head, f"    <i>{escape(source_short(t))}</i>"]
    for n, hit in notices:
        what = ", ".join(h.title for h in hit) or n.text
        out.append(f"🔁 <b>{escape(n.subject or '?')}</b> — {escape(n.kind)}: {escape(what)}")
    if not tasks and not notices:
        out.append("No tasks 🎉")
    return "\n".join(out)
