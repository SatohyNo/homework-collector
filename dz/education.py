"""Your folder with finished work on disk (e.g. ~/Education). Only file names are read.

The subject comes from the top-level folder ("05 Programming" -> Programming).
Manuals, syllabi, lectures etc. (`ignore`) are skipped, otherwise "Lab2_manual.pdf" would look
like your finished Lab 2. Files lying directly in a subject folder (books, task sheets from the
teacher) count only if your surname is in the file name.
"""

from datetime import datetime
from pathlib import Path

from .config import Config
from .models import Submission

SKIP_SUFFIXES = {".bak", ".log", ".tmp", ".ds_store"}


def scan(cfg: Config, warn) -> list[Submission]:
    edu = cfg.education
    if not edu:
        return []
    root = Path(edu.get("path", "~/Education")).expanduser()
    if not root.is_dir():
        warn(f"Education folder not found: {root}")
        return []
    owners = [n.lower() for n in edu.get("owner_names", [])]
    ignore = {n.lower() for n in edu.get("ignore", [])}

    out: list[Submission] = []
    for folder, subject in edu.get("folders", {}).items():
        base = root / folder
        if not base.is_dir():
            continue
        for f in base.rglob("*"):
            if f.is_symlink() or not f.is_file() or f.name.startswith(".") or f.suffix.lower() in SKIP_SUFFIXES:
                continue
            rel = f.relative_to(base)
            if any(part.lower() in ignore for part in rel.parts[:-1]):
                continue
            mine = any(o in f.name.lower() for o in owners)
            if len(rel.parts) == 1 and not mine:
                continue  # a book or task sheet lying directly in the subject folder
            out.append(Submission(
                date=datetime.fromtimestamp(f.stat().st_mtime, tz=cfg.tz),
                text=f.stem,
                where=f"{root.name}/{folder}/{rel}",
                subject=subject,
                any_time=True,
            ))
    return out
