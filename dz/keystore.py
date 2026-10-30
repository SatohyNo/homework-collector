"""Access keys live in the operating system's keychain (macOS Keychain, Windows Credential Manager,
Linux Secret Service), encrypted and guarded by the OS, never in plain files.

Older setups kept keys in files. The first time a key is missing from the keychain, it is imported
from its old file: files in ~/.dz (created by this project) are deleted after the import, files
elsewhere (e.g. used by your other scripts) are left in place.
"""

from .config import SECRETS_DIR, secret_path
from .security import ensure_private

SERVICE = "homework-collector"
# config name -> keychain entry
ENTRIES = {
    "MOODLE_TOKEN_FILE": "moodle-token",
    "CLASSROOM_URL_FILE": "classroom-url",
    "CLASSROOM_CLIENT_FILE": "google-client",
    "CLASSROOM_TOKEN_FILE": "google-token",
    "TG_CONFIG_FILE": "telegram-api",
    "TG_SESSION_FILE": "telegram-session",
}


class KeystoreError(RuntimeError):
    pass


def _keyring():
    try:
        import keyring
    except ImportError:
        raise KeystoreError("the `keyring` package is missing: run `pip install -r requirements.txt`") from None
    kr = keyring.get_keyring()
    if getattr(kr, "priority", 0) <= 0:
        raise KeystoreError(
            "no system keychain found. On Linux install GNOME Keyring or KWallet "
            "(or `pip install keyrings.alt` for an encrypted file store)")
    return kr


def get(name: str, warn=None) -> str | None:
    kr = _keyring()
    value = kr.get_password(SERVICE, ENTRIES[name])
    if value is None:
        value = _import_old_file(name, kr, warn)
    return value


def put(name: str, value: str) -> None:
    _keyring().set_password(SERVICE, ENTRIES[name], value)


def delete(name: str) -> None:
    import keyring.errors

    try:
        _keyring().delete_password(SERVICE, ENTRIES[name])
    except keyring.errors.PasswordDeleteError:
        pass


def has(name: str) -> bool:
    return get(name) is not None


def _import_old_file(name: str, kr, warn) -> str | None:
    path = secret_path(name)
    if not path.exists():
        return None
    ensure_private(path, warn)
    value = _session_to_string(path) if name == "TG_SESSION_FILE" else path.read_text().strip()
    if not value:
        return None
    kr.set_password(SERVICE, ENTRIES[name], value)
    if path.parent == SECRETS_DIR:
        path.unlink()  # our own plain-text copy is no longer needed
        if warn:
            warn(f"{path.name} moved into the system keychain and deleted from disk")
    elif warn:
        warn(f"{path.name} copied into the system keychain; the file at {path.parent} is left for your other tools")
    return value


def _session_to_string(path) -> str:
    """Telethon SQLite session file -> StringSession text (the same auth key, without the file)."""
    from telethon.sessions import SQLiteSession, StringSession

    session = SQLiteSession(str(path.with_suffix("")))
    try:
        return StringSession.save(session)
    finally:
        session.close()
