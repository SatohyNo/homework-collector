"""Setup wizard for access keys. Everything is typed only in your terminal and saved in ~/.dz
with mode 600 (only you can read it). Nothing is written into the project or git.

    python -m dz.setup moodle      # Moodle token from login + password (or paste an existing key)
    python -m dz.setup telegram    # api_id/api_hash and sign-in to your account
    python -m dz.setup chats       # list your groups and channels with ids, for config.json
    python -m dz.setup classroom   # Google Classroom via your own Apps Script
    python -m dz.setup classroom-oauth  # Google Classroom via your own Google Cloud OAuth client (fallback)
    python -m dz.setup check       # show what is already set up
"""

import asyncio
import base64
import getpass
import hashlib
import http.server
import json
import secrets
import shutil
import subprocess
import sys
import urllib.parse
import webbrowser
from pathlib import Path

import requests

from .config import ROOT, load_config, secret_path

TEMPLATE = ROOT / "tools" / "classroom" / "Code.gs"


def _save_private(path: Path, text: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.touch(mode=0o600, exist_ok=True)
    path.chmod(0o600)
    path.write_text(text)


def _ensure_config() -> Path:
    cfg = ROOT / "config.json"
    if not cfg.exists():
        shutil.copy(ROOT / "config.example.json", cfg)
        print(f"Created {cfg.name} from config.example.json. Edit your subjects and chats there.")
    return cfg


# --- Moodle -----------------------------------------------------------------

def moodle() -> None:
    print("Moodle: enter your site address, e.g. https://moodle.univ.edu (nothing after the domain).")
    url = input("Moodle address: ").strip().rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url
    print("\nNext: your Moodle login and password. The password is hidden and goes only to your Moodle site.")
    print("If you sign in with Google/SSO and have no password, just press Enter and paste a key instead")
    print("(Moodle → profile → Preferences → Security keys → \"Moodle mobile web service\").")
    login = input("Login (or Enter): ").strip()
    if login:
        password = getpass.getpass("Password: ")
        resp = requests.post(f"{url}/login/token.php", timeout=30, data={
            "username": login, "password": password, "service": "moodle_mobile_app"})
        del password
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        token = data.get("token")
        if not token:
            sys.exit(f"Failed: {data.get('error') or resp.text[:200]}\n"
                     "The mobile service may be disabled on your site. Try a key from \"Security keys\".")
    else:
        token = getpass.getpass("Paste the key (hidden): ").strip()

    check = requests.post(f"{url}/webservice/rest/server.php", timeout=30, data={
        "wstoken": token, "wsfunction": "core_webservice_get_site_info", "moodlewsrestformat": "json"}).json()
    if "exception" in check:
        sys.exit(f"The key does not work: {check.get('message')}")
    _save_private(secret_path("MOODLE_TOKEN_FILE"), token)

    cfg_path = _ensure_config()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["moodle_url"] = url
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n✓ Moodle: signed in as {check.get('fullname')}. Token: {secret_path('MOODLE_TOKEN_FILE')}")


# --- Telegram ---------------------------------------------------------------

def _tg_client():
    from telethon import TelegramClient

    keys = json.loads(secret_path("TG_CONFIG_FILE").read_text())
    return TelegramClient(str(secret_path("TG_SESSION_FILE").with_suffix("")), keys["api_id"], keys["api_hash"])


def telegram() -> None:
    cfg_file = secret_path("TG_CONFIG_FILE")
    if not cfg_file.exists():
        print("Telegram: you need an api_id and api_hash. How to get them: README, section \"Telegram\".")
        api_id = int(input("api_id (a number): ").strip())
        api_hash = getpass.getpass("api_hash (hidden): ").strip()
        _save_private(cfg_file, json.dumps({"api_id": api_id, "api_hash": api_hash}))

    async def login():
        client = _tg_client()
        # start() asks for your phone number, the code from Telegram and your 2FA password if you have one
        await client.start(password=lambda: getpass.getpass("Two-step verification password (hidden): "))
        me = await client.get_me()
        await client.disconnect()
        return me

    me = asyncio.run(login())
    session = secret_path("TG_SESSION_FILE")
    if session.exists():
        session.chmod(0o600)
    print(f"\n✓ Telegram: signed in as {me.first_name}. Session: {session}")
    print("  The session file is full access to your account. Never share it.")
    print("  Next: python -m dz.setup chats, to see the ids of your groups.")


def chats() -> None:
    async def run():
        async with _tg_client() as client:
            rows = []
            async for d in client.iter_dialogs():
                if d.is_group or d.is_channel:
                    rows.append((d.id, "channel" if d.is_channel and not d.is_group else "group", d.name))
            return rows

    rows = asyncio.run(run())
    print("Your groups and channels. Copy the ones you need into config.json → telegram.chats:\n")
    for cid, kind, name in rows:
        entry = {"chat": cid, "subject": None, "name": name, "short": name[:20]}
        print(f"  {json.dumps(entry, ensure_ascii=False)},   // {kind}")
    print("\nSet \"subject\" to a subject name from config.json → subjects (or null for a general group chat).")
    print("Remove the // comments: JSON does not allow them.")


# --- Google Classroom -------------------------------------------------------

def classroom() -> None:
    key = secrets.token_urlsafe(24)
    code = TEMPLATE.read_text(encoding="utf-8").replace("__SECRET_KEY__", key)
    out = secret_path("CLASSROOM_URL_FILE").parent / "classroom-Code.gs"
    _save_private(out, code)
    copied = False
    if shutil.which("pbcopy"):
        subprocess.run(["pbcopy"], input=code.encode(), check=False)
        copied = True

    print("Google Classroom via Apps Script (the script runs as you, no Google Cloud project needed).\n")
    print(f"1. The script code with your secret key was {'copied to the clipboard' if copied else 'saved'}:")
    print(f"   {out}")
    print("2. Open https://script.google.com/home/projects/create with the Google account that has your Classroom.")
    print("3. Delete everything in the editor, paste the code (Cmd+V / Ctrl+V), save (Cmd+S / Ctrl+S).")
    print("4. On the left: \"Services\" (+) → \"Google Classroom API\" → \"Add\".")
    print("5. Top right: \"Deploy\" → \"New deployment\" → gear icon → \"Web app\".")
    print("   Execute as: Me.  Who has access: Anyone.  → \"Deploy\".")
    print("6. Google asks for access: \"Authorize access\" → your account → \"Advanced\" →")
    print("   \"Go to … (unsafe)\" → \"Allow\". It is your own script, so the warning is expected.")
    print("7. Copy the \"Web app URL\" (https://script.google.com/macros/s/…/exec).\n")
    url = input("Paste the Web app URL: ").strip()
    full = f"{url}?key={key}"
    print("Checking (the first request can take up to a minute)…")
    try:
        data = requests.get(full, timeout=360).json()
    except ValueError:
        sys.exit("The answer is not JSON. Check that the deployment has \"Who has access: Anyone\".")
    if "error" in data:
        sys.exit(f"The script returned an error: {data['error']}")
    _save_private(secret_path("CLASSROOM_URL_FILE"), full)
    print(f"\n✓ Classroom: {len(data.get('courses', []))} courses found. URL saved to {secret_path('CLASSROOM_URL_FILE')}")


CLASSROOM_SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
    "https://www.googleapis.com/auth/classroom.announcements.readonly",
]


def classroom_oauth() -> None:
    """Fallback when Apps Script is blocked: sign in with your own OAuth client (Desktop app).
    You sign in on Google's own page in your browser; your password never reaches this script."""
    client_file = secret_path("CLASSROOM_CLIENT_FILE")
    if not client_file.exists():
        sys.exit(f"Put the downloaded OAuth client JSON here first: {client_file}\n"
                 "How to get it: README, section \"Google Classroom, option B\".")
    client_file.chmod(0o600)
    c = json.loads(client_file.read_text())
    c = c.get("installed") or c.get("web")

    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    result: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" not in q and "error" not in q:
                self.send_response(404)
                self.end_headers()
                return
            result.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Done, you can close this tab.")

        def log_message(self, *args):
            pass

    # Google allows any port on 127.0.0.1 for a Desktop client
    srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    redirect = f"http://127.0.0.1:{srv.server_port}/"
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": c["client_id"], "redirect_uri": redirect, "response_type": "code",
        "scope": " ".join(CLASSROOM_SCOPES), "access_type": "offline", "prompt": "consent",
        "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
    })
    print("Opening the browser to sign in to Google. If it did not open, use this link:\n" + url)
    webbrowser.open(url)
    while not result:
        srv.handle_request()
    if result.get("error") or result.get("state") != state:
        sys.exit(f"Sign-in failed: {result.get('error', 'state mismatch')}")

    tok = requests.post("https://oauth2.googleapis.com/token", timeout=60, data={
        "code": result["code"], "client_id": c["client_id"], "client_secret": c["client_secret"],
        "redirect_uri": redirect, "grant_type": "authorization_code", "code_verifier": verifier,
    }).json()
    if "refresh_token" not in tok:
        sys.exit(f"Google did not return a refresh token: {tok.get('error_description') or tok}")
    _save_private(secret_path("CLASSROOM_TOKEN_FILE"), json.dumps({"refresh_token": tok["refresh_token"]}))
    print(f"\n✓ Classroom: token saved to {secret_path('CLASSROOM_TOKEN_FILE')}")


# --- Check ------------------------------------------------------------------

def check() -> None:
    cfg = load_config()
    items = [
        ("Moodle token + moodle_url", secret_path("MOODLE_TOKEN_FILE").exists() and bool(cfg.moodle_url)),
        ("Telegram keys", secret_path("TG_CONFIG_FILE").exists()),
        ("Telegram session", secret_path("TG_SESSION_FILE").exists()),
        ("Classroom", secret_path("CLASSROOM_URL_FILE").exists() or secret_path("CLASSROOM_TOKEN_FILE").exists()),
        ("config.json", (ROOT / "config.json").exists()),
        ("Chats in config.json", bool(cfg.telegram_chats)),
    ]
    for name, ok in items:
        print(f"  {'✓' if ok else '✗'} {name}")


COMMANDS = {"moodle": moodle, "telegram": telegram, "chats": chats, "classroom": classroom,
            "classroom-oauth": classroom_oauth, "check": check}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__)
    COMMANDS[sys.argv[1]]()
