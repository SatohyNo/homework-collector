"""Telegram through your own account (Telethon / MTProto).

Tasks are taken only from chat admins (teacher, class representative), anonymous posts made on
behalf of the group, and channel posts. Messages from other students are ignored. Messages from
one author sent in a row (within 30 min) are glued together with their file names, because a
teacher often writes "This is the assignment for the test" and then posts the pdf separately.
Your own messages with files in all chats are also read, to hide work you already submitted.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .config import Config
from .models import TELEGRAM, Notice, Submission, Task
from .textitems import text_to_item
from .textparse import (
    ASSIGNMENT_RE,
    extract_deadline,
    file_names_task,
    guess_subjects,
    is_directive,
    is_optional,
    looks_like_assignment,
)

GROUP_GAP = timedelta(minutes=30)  # a teacher's text, files and clarifications during one class
SUBMISSIONS_DAYS = 14


@dataclass
class Post:
    sender_id: int | None
    topic_id: int  # forum topic (1 = General, or a group without topics)
    first: datetime
    last: datetime
    msg_id: int
    is_reply: bool = False  # every message of the post answers someone else's message
    texts: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)

    def text(self) -> str:
        return "\n".join([*self.texts, *(f"📎 {f}" for f in self.files)])


def _file_name(msg) -> str | None:
    if not msg.file or msg.sticker or msg.gif:
        return None
    return msg.file.name or None


def _topic_id(msg) -> int:
    """Forum topic of a message. Messages in a topic carry forum_topic=True and the topic id
    (reply_to_top_id when it is a reply inside the topic, otherwise reply_to_msg_id)."""
    rt = msg.reply_to
    if rt and getattr(rt, "forum_topic", False):
        return rt.reply_to_top_id or rt.reply_to_msg_id
    return 1


def _is_reply(msg) -> bool:
    """A reply to another message. In a topic, a plain message also points at the topic
    (reply_to_msg_id = topic id, reply_to_top_id = None), which is not a reply."""
    rt = msg.reply_to
    if not rt or not getattr(rt, "reply_to_msg_id", None):
        return False
    return not (getattr(rt, "forum_topic", False) and rt.reply_to_top_id is None)


async def _topic_titles(client, entity) -> dict[int, str]:
    """Topic id -> title for groups with topics ("Physics", "Math", ...); empty for normal groups."""
    if not getattr(entity, "forum", False):
        return {}
    from telethon import functions

    try:
        req = functions.channels.GetForumTopicsRequest(
            channel=entity, offset_date=None, offset_id=0, offset_topic=0, limit=100)
    except AttributeError:  # newer Telegram layers moved the method to messages.*
        req = functions.messages.GetForumTopicsRequest(
            peer=entity, offset_date=None, offset_id=0, offset_topic=0, limit=100)
    try:
        res = await client(req)
    except Exception:  # noqa: BLE001 - without topics we fall back to subject-from-text
        return {}
    return {t.id: t.title for t in res.topics if getattr(t, "title", None)}


async def _admin_ids(client, entity) -> set[int]:
    from telethon.tl.types import ChannelParticipantsAdmins

    try:
        return {u.id for u in await client.get_participants(entity, filter=ChannelParticipantsAdmins)}
    except Exception:  # noqa: BLE001 - admin list is unavailable without rights
        return set()


def make_client(warn=None):
    """Telegram client whose api keys and session come from the system keychain (no session file).
    None if Telegram is not set up yet."""
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    from . import keystore

    keys = keystore.get("TG_CONFIG_FILE", warn)
    session = keystore.get("TG_SESSION_FILE", warn)
    if not keys or not session:
        return None
    keys = json.loads(keys)
    return TelegramClient(StringSession(session), int(keys["api_id"]), keys["api_hash"])


async def collect(client, cfg: Config, now: datetime, warn) -> tuple[list[Task], list[Notice], list[Submission]]:
    from telethon import utils

    tasks: list[Task] = []
    notices: list[Notice] = []
    since = now - timedelta(days=cfg.days_back)

    async with client:
        if not await client.is_user_authorized():
            raise RuntimeError("the Telegram session has expired, run `python -m dz.setup telegram`")
        # a keychain session keeps no cache of chats; loading the dialog list fills it, so ids resolve
        await client.get_dialogs()
        for entry in cfg.telegram_chats:
            try:
                entity = await _resolve(client, entry["chat"])
            except Exception as e:  # noqa: BLE001
                warn(f"Telegram: chat \"{entry.get('name', entry['chat'])}\" not found ({e})")
                continue
            chat_name = entry.get("short") or entry.get("name") or getattr(entity, "title", "?")
            chat_id = utils.get_peer_id(entity)
            broadcast = bool(getattr(entity, "broadcast", False))
            admins = await _admin_ids(client, entity)
            topics = await _topic_titles(client, entity)

            posts: list[Post] = []
            async for msg in client.iter_messages(entity):
                if msg.date < since:
                    break
                # if no admins are visible, take everyone; the strict keyword filter still applies
                official = (broadcast or msg.post or not admins or msg.sender_id in admins
                            or msg.sender_id == chat_id)
                if not official or msg.via_bot_id:
                    continue
                p = Post(msg.sender_id, _topic_id(msg), msg.date, msg.date, msg.id, is_reply=_is_reply(msg))
                if msg.message:
                    p.texts.append(msg.message)
                if name := _file_name(msg):
                    p.files.append(name)
                if p.texts or p.files:
                    posts.append(p)

            # glue messages sent in a row by one author in one topic (walk in chronological order)
            merged: list[Post] = []
            last_of: dict[tuple[int | None, int], Post] = {}
            for p in reversed(posts):
                key = (p.sender_id, p.topic_id)
                prev = last_of.get(key)
                if prev and p.first - prev.last <= GROUP_GAP:
                    prev.texts += p.texts
                    prev.files += p.files
                    prev.last = p.first
                    prev.is_reply = prev.is_reply and p.is_reply
                else:
                    merged.append(p)
                    last_of[key] = p

            username = getattr(entity, "username", None)
            for p in merged:
                text = p.text()
                # only files and no assignment words: the file name itself must name a kind of work
                if not looks_like_assignment("\n".join(p.texts)) and not file_names_task(p.files):
                    continue
                # answers in a conversation ("I haven't heard anything about lab 3") are not assignments,
                # unless they give a concrete date
                if p.is_reply and not extract_deadline(text, p.first, cfg.tz).found_anything:
                    continue
                written = "\n".join(p.texts)
                if is_optional(written):
                    continue
                # general class chat: the post must tell you to do something, or carry a task file
                if not entry.get("subject") and not is_directive(written) and not file_names_task(p.files):
                    continue
                url = f"https://t.me/{username}/{p.msg_id}" if username else None
                # a chat-level subject wins; in a general chat with topics the topic name gives the subject
                topic = topics.get(p.topic_id) if p.topic_id != 1 else None
                subject = entry.get("subject") or _topic_subject(topic, cfg)
                item = text_to_item(text, p.first, TELEGRAM, cfg, fixed_subject=subject, url=url,
                                    keep_undated=True, strict=True)
                if isinstance(item, Notice):
                    notices.append(item)
                elif item is not None:
                    file = next((f for f in p.files if ASSIGNMENT_RE.search(f.replace("_", " "))), None)
                    if file and file.lower() not in item.title.lower():
                        item.title = f"{item.title} 📎 {file}"
                    item.origin = f"{chat_name}/{topic}" if topic else chat_name
                    item.match_text = text
                    tasks.append(item)

        submissions = await _my_submissions(client, now - timedelta(days=SUBMISSIONS_DAYS))

    return tasks, notices, submissions


def _topic_subject(topic: str | None, cfg: Config) -> str | None:
    """Topic title -> subject from config.json ("Вишмат" -> "Higher Mathematics"); None if unclear."""
    if not topic:
        return None
    hits = guess_subjects(topic, cfg.subjects)
    return hits[0] if len(hits) == 1 else None


async def _my_submissions(client, since: datetime) -> list[Submission]:
    """Your messages with files in all groups and private chats (submitted work)."""
    out: list[Submission] = []
    async for dialog in client.iter_dialogs():
        if dialog.is_channel and not dialog.is_group:
            continue  # you do not submit work to channels
        if dialog.date and dialog.date < since:
            continue  # nothing new in this chat, so no submissions either
        try:
            async for msg in client.iter_messages(dialog.entity, from_user="me"):
                if msg.date < since:
                    break
                if msg.fwd_from:
                    continue  # a forward (e.g. a teacher's manual) is not your submission
                if name := _file_name(msg):
                    out.append(Submission(msg.date, f"{msg.message or ''} {name}", f"TG · {dialog.name}"))
        except Exception:  # noqa: BLE001 - one unavailable chat must not break the whole run
            continue
    return out


async def _resolve(client, chat):
    if isinstance(chat, int) or (isinstance(chat, str) and (chat.startswith("@") or chat.lstrip("-").isdigit())):
        return await client.get_entity(int(chat) if str(chat).lstrip("-").isdigit() else chat)
    async for dialog in client.iter_dialogs():
        if dialog.name == chat:
            return dialog.entity
    raise LookupError("no dialog with this name")


async def send_to_saved(client, text: str) -> None:
    """Sends the text to your own Saved Messages, nobody else."""
    async with client:
        # Telegram limit is 4096 characters; split by lines
        chunk = ""
        for line in text.split("\n"):
            if len(chunk) + len(line) + 1 > 4000:
                await client.send_message("me", chunk, parse_mode="html", link_preview=False)
                chunk = ""
            chunk += line + "\n"
        if chunk.strip():
            await client.send_message("me", chunk, parse_mode="html", link_preview=False)
