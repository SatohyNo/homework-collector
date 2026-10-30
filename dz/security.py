"""Small safety helpers: private key files, HTTPS-only endpoints, secret redaction, safe text output."""

import os
import re
import stat
from pathlib import Path
from urllib.parse import urlsplit

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def require_https(url: str, what: str) -> str:
    """Tokens must never travel in clear text. http:// is allowed only for a local test server."""
    parts = urlsplit(url)
    if parts.scheme == "https" and parts.hostname:
        return url
    if parts.scheme == "http" and parts.hostname in _LOCAL_HOSTS:
        return url
    raise ValueError(f"{what} must be an https:// address, got {parts.scheme or 'no scheme'}://{parts.hostname or '?'}")


def require_host(url: str, allowed: tuple[str, ...], what: str) -> str:
    """The URL must be https and its host must be one of `allowed` (or a subdomain of it)."""
    require_https(url, what)
    host = (urlsplit(url).hostname or "").lower()
    if not any(host == a or host.endswith("." + a) for a in allowed):
        raise ValueError(f"{what} must point to {' or '.join(allowed)}, got {host}")
    return url


def ensure_private(path: Path, warn=None) -> None:
    """Key files must be readable only by you (mode 600). Fix and warn if someone else could read them."""
    try:
        st = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(st.st_mode):
        raise PermissionError(f"{path} is a symlink; refusing to read a key through a link")
    if st.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        os.chmod(path, 0o600)
        if warn:
            warn(f"{path.name} was readable by other users; permissions fixed to 600")


_SECRET_PATTERNS = [
    (re.compile(r"(?i)\b(key|token|wstoken|access_token|refresh_token|api_hash|client_secret|password)=([^&\s\"']+)"),
     r"\1=***"),
    (re.compile(r"(?i)(\"(?:api_hash|token|refresh_token|access_token|client_secret)\"\s*:\s*\")[^\"]+"), r"\1***"),
    (re.compile(r"\b[0-9a-f]{32}\b"), "***"),  # Moodle tokens and Telegram api_hash are 32 hex chars
    (re.compile(r"/macros/s/[A-Za-z0-9_-]{20,}"), "/macros/s/***"),  # Apps Script deployment id
]


def redact(text: str) -> str:
    """Remove tokens and keys from error messages before they are printed or logged."""
    for rx, repl in _SECRET_PATTERNS:
        text = rx.sub(repl, text)
    return text


# ANSI escape sequences, other control characters, and bidi overrides that can disguise text
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b.")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f‎‏‪-‮⁦-⁩]")


def safe_text(text: str) -> str:
    """Text from chats and file names, made safe to print in a terminal (one line per value)."""
    text = _ANSI_RE.sub("", text or "")
    text = _CONTROL_RE.sub("", text)
    return text.replace("\n", " ").replace("\t", " ")
