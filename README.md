# Homework Collector

One command gathers all your homework from **Moodle**, **Google Classroom** and **Telegram** and
gives you one clean list: in the terminal as a table and in your Telegram **Saved Messages**.

```
Homework due by 08.11.2026  (updated 27.10 17:30)

| # | Subject            | Task                                          | Source                   |
|---|--------------------|-----------------------------------------------|--------------------------|
| 1 | Programming        | Replacement for KP 4 📎 KP_11_functions.docx  | TG · Programming · 24.10 |
| 2 | Physics            | Study part 2 of the lecture on your own       | TG · Physics · 27.10     |
| 3 | Higher Mathematics | Homework: 3.2.43, 3.2.47(2), 3.2.48(2)        | TG · Math · 23.10        |
| 4 | Civil Defense      | Practical work 6                              | Moodle · due 17.11       |

Tasks: 4

Hidden as done (2), your file was found:
  ✓ Programming — Lab 4  ←  KP4_Petrenko (Education/02 Programming/KP4_Petrenko.cpp, 24.10)
  ✓ Graphics — RGR 1     ←  RGR1_Petrenko.pdf (TG · Graphics group, 23.10)
```

---

## Why

At university, homework is scattered: some is in Moodle, some in Google Classroom, and a lot is
only mentioned by a teacher in a Telegram group between dozens of messages like "join the call",
"I'll be late" and stickers. It is easy to miss a task, and hard to remember what you already did.

## What it does

1. **Moodle**: reads assignments and quizzes due **from today until the end of next week** that you
   have **not submitted yet** (Moodle tells it your submission status).
2. **Google Classroom**: the same, for every course you are in.
3. **Telegram**: reads the last **7 days** of the chats you list (subject groups, class chats,
   channels) and picks out assignments:
   - only messages from **chat admins** (usually the teacher or the class representative),
     anonymous posts on behalf of the group, and channel posts. Classmates' chatter is ignored;
   - several messages from one author in a row (within 30 minutes, in the same topic) are glued
     together, so "This is the assignment for the test" + `rgr1_task.pdf` becomes one task;
   - **groups with topics** are supported: in a class group with topics like "Physics", "Math",
     "Materials science", the subject is taken from the topic name;
   - a post that is just a file is picked up when the file name names a kind of work
     (`4 пр.pdf`, `ЛР3_звіт.pdf`, `КП_11.docx`, `РГР1.pdf`);
   - a message must clearly be an assignment (homework, lab, essay, draw, solve, test on
     classtime…). "Join the lesson", Zoom links and grades are skipped;
   - bot messages are skipped.
4. **Hides work you already did**:
   - files **you sent** in any Telegram group or private chat after the task was given
     (e.g. you sent `KP4_Petrenko.cpp` → the "KP 4" task disappears);
   - files in your **local study folder** (e.g. `~/Education/02 Programming/KP4_Petrenko.cpp`).

   The bottom of the terminal output always shows what was hidden and because of which file.
5. **Removes duplicates**: a task posted in Moodle and repeated in Telegram, or forwarded to
   several chats, appears once.
6. Prints the **table** in the terminal and sends the same list to your Telegram **Saved Messages**
   (only to yourself).

It is **read-only**: it never posts in chats, never submits anything, never changes Moodle or
Classroom. The only thing it sends is the list to your own Saved Messages (you can turn that off).

The keyword matching is tuned for **Ukrainian and Russian** chats ("дз", "лаба", "здати", "до
15.11"…). The program's own output is in English.

---

## Contents

- [Requirements](#requirements)
- [Step 1. Install](#step-1-install)
- [Step 2. Get access](#step-2-get-access)
  - [Moodle](#moodle)
  - [Telegram](#telegram)
  - [Google Classroom](#google-classroom)
- [Step 3. Configure](#step-3-configure)
- [Step 4. Run](#step-4-run)
- [How the filtering works](#how-the-filtering-works)
- [Privacy and security](#privacy-and-security)
- [Troubleshooting](#troubleshooting)
- [Project structure](#project-structure)

---

## Requirements

- **Python 3.10 or newer.** Check with `python3 --version` (Windows: `python --version`).
  Download from <https://www.python.org/downloads/> if you do not have it.
  On Windows, tick **"Add python.exe to PATH"** in the installer.
- **git** (optional, to clone): <https://git-scm.com/downloads>. You can also press
  **Code → Download ZIP** on GitHub and unpack it.
- The accounts you want to use: Moodle, Google (Classroom), Telegram. Any of them can be skipped.

---

## Step 1. Install

### macOS / Linux

Open **Terminal** and run these lines one by one:

```bash
git clone https://github.com/SatohyNo/homework-collector.git
cd homework-collector
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Windows

Open **PowerShell** and run:

```powershell
git clone https://github.com/SatohyNo/homework-collector.git
cd homework-collector
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell says running scripts is disabled, run this once and try the activate line again:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

> **Every time you open a new terminal**, go to the folder and activate the environment again:
> `cd homework-collector`, then `source .venv/bin/activate` (Windows: `.venv\Scripts\Activate.ps1`).
> You will see `(.venv)` at the start of the line when it is active.

Check that it works with sample data (no accounts needed):

```bash
python -m dz --demo
```

You should see a small table. Now create your own config file:

```bash
cp config.example.json config.json        # Windows: copy config.example.json config.json
```

---

## Step 2. Get access

All keys are saved in a hidden folder **`~/.dz`** in your home directory (Windows:
`C:\Users\<you>\.dz`), readable only by you. They are **never** stored in the project folder,
so they cannot end up on GitHub by accident.

You can set up all three sources or only some of them. Missing ones are skipped with a short note.

### Moodle

Run:

```bash
python -m dz.setup moodle
```

It asks for:

1. **Your Moodle address**: what you see in the browser on the Moodle home page, only up to the
   domain. Example: `https://moodle.univ.edu` or `https://do.example.edu.ua`.
2. **Login and password**: the same as on the Moodle website. The password is hidden while you
   type and goes **only to your Moodle site**, which returns an access token. The password is
   not saved anywhere.

That's it. The token is saved to `~/.dz/moodle-token`, and `moodle_url` is written into `config.json`.

**If you sign in to Moodle with Google / Microsoft / SSO** (no Moodle password), press **Enter**
at the login prompt and paste a key instead:

1. Open Moodle in the browser and sign in.
2. Click your avatar (top right) → **Preferences** → **Security keys**.
   (Ukrainian UI: **Налаштування** → **Ключі безпеки**.)
3. Find the row **"Moodle mobile web service"** and copy the **Key**.
   - If there is no such row, install the official **Moodle app** on your phone, sign in once,
     then reload the page: the key appears.
4. Paste it when asked (it is hidden).

**If both fail** with "web services are not enabled" or "invalid service": your university has
turned off the Moodle API. Moodle cannot be used then; Telegram and Classroom still work.

**To revoke access later:** Moodle → Preferences → Security keys → **Reset** next to the key.

### Telegram

Telegram is read through **your own account** (not a bot), because a bot cannot read old
messages or channels. For that Telegram requires a personal **api_id** and **api_hash**.

#### Get api_id and api_hash (once, 3 minutes)

1. Open <https://my.telegram.org> in a browser.
2. Enter your phone number **in international format**, e.g. `+380 67 123 4567`, and press **Next**.
3. Telegram sends you a **code inside the Telegram app** (a message from "Telegram", not an SMS).
   Type it on the website and press **Sign In**.
4. Click **API development tools**.
5. Fill in the form (it appears the first time):
   - **App title**: anything, e.g. `Homework Collector`
   - **Short name**: 5 to 32 letters/digits, e.g. `hwcollector`
   - **URL**: leave empty
   - **Platform**: `Desktop`
   - **Description**: anything or empty
6. Press **Create application**.
7. You now see **App api_id** (a number) and **App api_hash** (a long string of letters and digits).
   Keep this page open.

> If you get an "ERROR" when creating the app: turn off VPN / ad blocker, try another browser or
> wait a few hours. This is a known quirk of my.telegram.org.

#### Sign in

```bash
python -m dz.setup telegram
```

It asks for:

1. **api_id**: the number from step 7.
2. **api_hash**: the string from step 7 (hidden while typing).
3. **Phone number**: the same one, international format.
4. **Code**: Telegram sends it to your Telegram app again. Type it in the terminal.
5. **Two-step verification password**, only if you enabled it in Telegram settings.

You will see `✓ Telegram: signed in as <your name>`. The session is saved to
`~/.dz/telegram.session`.

> ⚠️ **The session file is full access to your Telegram account.** Never send it to anyone or
> upload it anywhere. To revoke it: Telegram → Settings → Devices → end the session with your
> app's name.

#### Find your chats

```bash
python -m dz.setup chats
```

It prints all your groups and channels with their ids, ready to copy into `config.json`
(see [Step 3](#step-3-configure)).

### Google Classroom

There are two ways. **Option A** is simpler and works for most personal and many school accounts.
Use **option B** only if A is blocked.

#### Option A: your own Apps Script (recommended, about 3 minutes)

You deploy a tiny script **in your own Google account** that reads your Classroom and returns it
as JSON. It is protected by a random secret key, so nobody else can read it.

```bash
python -m dz.setup classroom
```

The wizard generates the script with a secret key and (on macOS) copies it to the clipboard.
It is also saved to `~/.dz/classroom-Code.gs`. Then follow the steps it prints:

1. Open <https://script.google.com/home/projects/create>. Use the **same Google account** that
   you use for Classroom (check the avatar top right).
2. Select everything in the editor and delete it. Paste the code: Cmd+V (macOS) / Ctrl+V.
   On Windows/Linux open `~/.dz/classroom-Code.gs` in a text editor and copy from there.
3. Press **Save** (disk icon, or Cmd+S / Ctrl+S). You may rename the project, e.g. "Classroom export".
4. In the left panel, next to **Services**, click **+** → choose **Google Classroom API** → **Add**.
5. Top right: **Deploy** → **New deployment**.
6. Click the **gear icon** next to "Select type" → **Web app**.
7. Set:
   - **Execute as**: `Me (your@email)`
   - **Who has access**: `Anyone`
8. Press **Deploy**.
9. Google asks for permission: **Authorize access** → choose your account → you will see
   "Google hasn't verified this app" → click **Advanced** → **Go to <project name> (unsafe)** →
   **Allow**. This warning appears because it is your own unpublished script; that is expected.
   It only gets **read-only** access to Classroom.
10. Copy the **Web app URL** (looks like `https://script.google.com/macros/s/AKfy…/exec`).
11. Paste it into the terminal. The wizard checks it and prints how many courses it found.

> "Anyone" means anyone **with the URL and the secret key**. Without the key the script only
> answers `bad key`. The URL with the key is saved in `~/.dz/classroom-url`. Do not share it.

**If "Anyone" is not available** (some school domains hide it) or you see
"blocked by your administrator", use option B.

**To revoke later:** <https://script.google.com> → your project → Deploy → Manage deployments →
Archive. Or delete the project.

#### Option B: your own Google Cloud OAuth client

1. Open <https://console.cloud.google.com/projectcreate>, enter any name (e.g. `classroom-reader`)
   → **Create**. Make sure this new project is selected at the top of the page.
2. Enable the API: <https://console.cloud.google.com/apis/library/classroom.googleapis.com> →
   **Enable**.
3. Consent screen: <https://console.cloud.google.com/auth/branding> → **Get started**:
   - App name: anything; support email: yours → **Next**
   - Audience: **External** → **Next**
   - Contact email: yours → **Next** → agree → **Create**
4. Test user: <https://console.cloud.google.com/auth/audience> → **Test users** → **Add users** →
   add the Google account that has your Classroom → **Save**.
5. Client: <https://console.cloud.google.com/auth/clients> → **Create client** →
   Application type **Desktop app** → any name → **Create** → **Download JSON**.
6. Move the downloaded file to `~/.dz/google-client.json`:
   - macOS / Linux: `mkdir -p ~/.dz && mv ~/Downloads/client_secret_*.json ~/.dz/google-client.json`
   - Windows: create the folder `C:\Users\<you>\.dz` and move the file there as `google-client.json`.
7. Run:

   ```bash
   python -m dz.setup classroom-oauth
   ```

   A browser opens. Sign in **on Google's page**, accept the warning
   (**Advanced → Continue**) and allow read-only access. The terminal shows `✓ Classroom: token saved`.

> While the app is in **Testing** mode Google expires the sign-in after 7 days. To avoid that,
> on the Audience page press **Publish app** (no Google review is needed for personal use;
> you will just see the "unverified app" warning when signing in).

### Check everything

```bash
python -m dz.setup check
```

```
  ✓ Moodle token + moodle_url
  ✓ Telegram keys
  ✓ Telegram session
  ✓ Classroom
  ✓ config.json
  ✓ Chats in config.json
```

---

## Step 3. Configure

Open `config.json` in any text editor (VS Code, TextEdit, Notepad). It is **your private file**
and is ignored by git. Every setting:

| Key | What it means | Example |
|---|---|---|
| `timezone` | Your time zone (used for dates) | `"Europe/Kyiv"` |
| `horizon` | How far ahead to look for deadlines. `"next_week"` = until Sunday of next week, or a number of days | `"next_week"`, `"30"` |
| `days_back` | How many recent days of Telegram and announcements to read | `7` |
| `send_to_saved` | Send the list to your Telegram Saved Messages | `true` / `false` |
| `moodle_url` | Your Moodle address (filled in by `dz.setup moodle`) | `"https://moodle.univ.edu"` |
| `subjects` | Your subjects and the words people use for them | see below |
| `telegram.chats` | Which Telegram chats to read | see below |
| `education` | Your local folder with finished work (optional) | see below |

### `subjects`

The key is the subject name you want to see in the table. The list contains words that identify
the subject in course names, chat names and messages: different spellings, Ukrainian and Russian
forms, slang. Matching ignores case and works on whole words.

```json
"subjects": {
  "Higher Mathematics": ["вища математика", "вищої математики", "вишмат", "вышмат", "матан"],
  "Programming": ["програмування", "программирование", "прога"],
  "Physics": ["фізика", "фізики", "физика"]
}
```

Tip: Moodle and Classroom course names are matched against these words too, so a course called
"ЗАГАЛЬНА ФІЗИКА. Частина 1" becomes "Physics" and merges with Telegram tasks.

### `telegram.chats`

Run `python -m dz.setup chats`, copy the lines for the chats you need and fill in `subject`:

```json
"telegram": {
  "chats": [
    {"chat": -1001234567890, "subject": "Higher Mathematics", "name": "Group 61 Math", "short": "Math"},
    {"chat": -1001234567891, "subject": "Programming",        "name": "Programming 2026", "short": "Prog"},
    {"chat": -1001234567892, "subject": null,                 "name": "Group 61", "short": "Group"}
  ]
}
```

- `chat`: the id from `dz.setup chats` (a number, usually negative). A `@username` or the exact
  chat title also works.
- `subject`: one of the names from `subjects`. Use `null` for a **general class chat** about many
  subjects. Then the subject is taken from the **topic name** (if the group has topics, e.g. a
  topic called "Вишмат" matches the alias `вишмат`), otherwise from the message text. Messages
  without a clear subject are skipped. So make sure every topic name appears in some alias list.
- `name`: for you, any text.
- `short`: what the "Source" column shows.

Only add chats where homework is actually given. Do not add news channels, memes, etc.

### `education` (optional)

If you keep your finished work in a folder, the collector hides tasks you already have a file for.

```json
"education": {
  "path": "~/Education",
  "owner_names": ["Petrenko", "Петренко"],
  "folders": {
    "01 Higher Mathematics": "Higher Mathematics",
    "02 Programming": "Programming",
    "03 Physics": "Physics"
  },
  "ignore": ["Manuals", "Syllabus", "Lectures", "Certificates", "Task Photos", "Old Versions"]
}
```

- `path`: the folder. `~` means your home folder.
- `folders`: top-level subfolder → subject name from `subjects`. Only these are scanned, and a
  file only counts for **its own subject** (a physics file never hides a math task).
- `ignore`: subfolders that are **not** your work (manuals, task sheets, lectures). Otherwise a
  file like `Lab2_manual.pdf` would look like your finished Lab 2.
- `owner_names`: your surname as it appears in your file names. Files lying **directly** in a
  subject folder (not in a subfolder) count only if they contain one of these names, because
  that is usually where books and task sheets end up.

Remove the whole `education` block if you do not use it.

### `.env` (optional)

Only needed if your keys are not in `~/.dz`. Copy `.env.example` to `.env` and uncomment the
paths you want to change.

---

## Step 4. Run

```bash
python -m dz
```

That's all. The first Telegram request can take 10 to 30 seconds. You get the table in the
terminal and the same list in Telegram → **Saved Messages**.

Options:

| Command | What it does |
|---|---|
| `python -m dz` | Everything: table + Saved Messages |
| `python -m dz --no-send` | Only the terminal, nothing is sent |
| `python -m dz --demo` | Sample data, no accounts or internet needed |
| `python -m dz --no-moodle` | Skip Moodle (also `--no-classroom`, `--no-telegram`) |

### Run it automatically (optional)

**macOS / Linux** with cron, every day at 08:00: run `crontab -e` and add this line
(replace the path with your real one):

```
0 8 * * * cd /Users/you/homework-collector && .venv/bin/python -m dz >/dev/null 2>&1
```

**Windows**: Task Scheduler → Create Basic Task → Daily → Action "Start a program":
- Program: `C:\path\to\homework-collector\.venv\Scripts\python.exe`
- Arguments: `-m dz`
- Start in: `C:\path\to\homework-collector`

The computer must be on (and not asleep) at that time.

---

## How the filtering works

**Which deadlines are shown.** Moodle and Classroom tasks due between now and the end of next
week (`horizon`) that you have not submitted. Telegram tasks given in the last `days_back` days,
even if their deadline is later than `horizon` (only past deadlines are dropped).

**Dates in text.** "до 15.11", "15 листопада", "23:59", "завтра до 10:00", and periods counted
from the message date: "дедлайн 2 тижні", "срок 2 недели", "термін 3 дні". Numbers after
"таблиця", "пункт", "рис.", "тема", "варіант", "№" are references, not dates ("таблиця 6.1"
is not 6 January).

**What counts as an assignment in Telegram.** The message (with the messages glued to it) must
contain an assignment word: дз, завдання, здати, лаба, КП, РГР, практична, самостійна, конспект,
презентація, контрольна, тест, classtime, креслити, виконати, підготувати, розв'язати… (and
Russian forms), or short forms like "4 пр", "пр 4", "ЛР 3". Short questions ("а дз яке?") are
skipped. Group codes like "КП-51" are not mistaken for "КП". Exercise numbers like `3.2.43` are
not mistaken for dates.

**Posts that are only a file.** A teacher or class representative often just forwards a pdf.
Such a post counts if the **file name** names a kind of work: пр / ЛР with a number, КП, РГР,
МКР, лаба, практична, самостійна, контрольна, варіант, ДЗ. A generic word like "завдання" in a
file name is not enough, because lecture files are often called "Topic 3: structure and tasks of…".

**Groups with topics.** Messages are grouped per topic, and the topic name gives the subject when
the chat itself has `"subject": null`.

**General class chats** (`"subject": null`) are noisy, so there a post must actually tell you to
do something (зробити / сделать, здати / сдать, задали, треба / нужно, ДЗ, дедлайн…) or carry a
task file. "I haven't heard about lab 3" is not a task. Replies to other people's messages are
skipped unless they contain a date. Everywhere, optional things ("ви можете підготувати тези",
"за бажанням", "по желанию") are skipped.

**Whose messages count.** Admins of the chat, anonymous admin posts, channel posts. If a chat
shows no admins at all, all authors are read (the keyword filter still applies).

**Duplicates.** Tasks are merged when they are the same subject and:
the same text was forwarded to several chats; or it is the same kind of work with no conflicting
numbers ("РГР-1" and "РГР 1"; but "lab 3" and "lab 4" stay separate); or a Telegram message
repeats a task that Moodle/Classroom already has.

**"Already done".** A task is hidden when one of your files matches it:
- the same kind of work **and** the same number (`KP4_Petrenko.cpp` ↔ "КП 4",
  `RGR1_Epure.pdf` ↔ "РГР 1"). This is the strongest match and wins. A number belongs to the work
  only when it stands right after the word ("лаба 3", "практична робота 4", "ЛР_1-3" → lab 1) or
  right before a short form ("4 пр"). "Здати 4 лабораторні" is a count, not lab 4, and a task
  without a number is never closed by a numbered file;
- or at least two meaningful words in common (`Складний_розріз_2.pdf` ↔ `Складні_розрізи.pdf`).

Files sent in Telegram count only if sent **after** the task was given, and forwarded files never
count. Files in your Education folder count regardless of date, but only for their subject.
Latin look-alike letters (`Cкладні` typed with a Latin C) and Latin abbreviations
(`KP`, `RGR`, `LAB`) are understood.

**Postponed / cancelled.** A message saying a deadline was moved or cancelled removes the
affected task and shows one line marked `[postponed]` or `[cancelled]`.

---

## Privacy and security

- **What is stored and where:**

  | File | Contains |
  |---|---|
  | `~/.dz/moodle-token` | Moodle token |
  | `~/.dz/telegram-api.json` | Telegram api_id and api_hash |
  | `~/.dz/telegram.session` | Telegram session (**full account access**) |
  | `~/.dz/classroom-url` | Apps Script URL with its secret key |
  | `~/.dz/google-client.json`, `google-token.json` | Option B OAuth client and token |
  | `config.json` (project folder) | Your subjects, chat ids, folder paths |

  All files in `~/.dz` are created with permissions `600` (only your user can read them).
- **What git ignores:** `config.json`, `.env`, `*.session`, `my_tasks.json`, `.venv/`.
  If you fork this repo, check `git status` before every commit anyway.
- **What is read:** Moodle/Classroom courses and your submission status; the chats you list;
  **your own** messages with files in your groups and private chats (only the names of files you
  sent, to detect submissions); file **names** in your Education folder (never their contents).
- **What is sent:** nothing except the final list to **your own** Saved Messages.
  Nothing goes to any third-party server.
- **Passwords:** your Moodle password is sent only to your Moodle site to get a token and is not
  saved. Google and Telegram sign-in happens on Google's / Telegram's own pages and prompts.
- **Revoking access:** see the "revoke" notes in each section of [Step 2](#step-2-get-access).
  Deleting the `~/.dz` folder removes all keys from your computer.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'telethon'` (or `requests`, `dotenv`)**
The environment is not active. Run `source .venv/bin/activate` (Windows: `.venv\Scripts\Activate.ps1`)
in the project folder, then try again.

**`Telegram unavailable: database is locked`**
Another program is using the same session file at this moment (for example a second run).
Wait a minute and run again.

**`Moodle skipped: set moodle_url in config.json`**
Run `python -m dz.setup moodle` again, or put your Moodle address into `config.json`.

**Moodle: `Invalid token` / `Invalid login`**
The token was reset or your password changed. Run `python -m dz.setup moodle` again.

**Classroom: `coursework is hidden from students`**
The teacher's course does not let students list coursework through the API. Nothing to fix;
that course is skipped.

**Classroom: `the web app did not return JSON`**
In Apps Script → Deploy → Manage deployments, check that **Who has access** is **Anyone**.
If you changed the code, create a **New deployment** and run `python -m dz.setup classroom` again.

**Telegram: `chat "…" not found`**
The id in `config.json` is wrong or you left the chat. Run `python -m dz.setup chats` again.

**A real task is missing**
- Is the chat in `telegram.chats`?
- Was it written by an admin of the chat? If the teacher is not an admin, the task is skipped.
- Does the message contain an assignment word? A bare file without any text is skipped.
- In a general chat (`"subject": null`), does the topic name or the text name the subject?
  Add the topic name to the aliases in `subjects` if not.
- Is it a bare file? Its name must contain a kind of work (пр 4, ЛР, КП, РГР…).
- Is it hidden as done? Look at the "Hidden as done" lines at the bottom of the output.

**Something is hidden as done but you did not do it**
The bottom of the output shows which file matched. Rename that file so it does not look like the
task, or move it into an `ignore` folder.

**Garbage tasks appear**
Remove non-homework chats from `telegram.chats`. For a general chat, consider setting a specific
`subject` or removing it.

---

## Project structure

```
dz/
  __main__.py      entry point: python -m dz
  setup.py         setup wizard: python -m dz.setup ...
  config.py        loads config.json, .env and key paths
  moodle.py        Moodle REST API (assignments, calendar, announcements)
  classroom.py     Google Classroom (Apps Script JSON or OAuth API)
  telegram_src.py  Telegram: admin posts, gluing, your sent files, Saved Messages
  education.py     scans your local folder with finished work
  textparse.py     keywords, dates, subjects in free text
  textitems.py     message → task
  merge.py         window, duplicates, postponed tasks, "already done" matching
  render.py        terminal table and Telegram message
  demo.py          sample data for --demo
tools/classroom/   Apps Script template (the key is inserted by dz.setup)
config.example.json  template for your config.json
```

## License

MIT, see [LICENSE](LICENSE).
