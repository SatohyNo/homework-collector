# Security

## Reporting a vulnerability

Please do **not** open a public issue for security problems. Use GitHub's private reporting:
**Security → Report a vulnerability** on this repository page. You will get an answer within a week.

Never include real tokens, session files or chat exports in a report.

## How this project protects your data

- **Keys stay outside the project.** Tokens and the Telegram session live in `~/.dz` with
  permissions `600`. On every run the files are checked: if other users on the computer could read
  them, the permissions are fixed and you get a warning. Keys are never read through symlinks.
- **HTTPS only.** The Moodle token is sent only to an `https://` address and redirects are refused,
  so a misconfigured server cannot forward your token elsewhere. The Classroom URL must point to
  `script.google.com`.
- **No secrets in output.** Error messages are scrubbed of tokens, keys and Apps Script ids before
  they are printed.
- **Safe terminal output.** Text from chats and file names is cleaned of terminal escape codes and
  invisible direction-changing characters, so a message cannot rewrite or disguise your terminal.
- **Read-only.** The tool never posts in chats or changes Moodle/Classroom. The only thing it sends
  is the list to your own Telegram Saved Messages (`send_to_saved: false` turns it off).
- **Automated checks.** GitHub code scanning (CodeQL, extended security queries) checks the code
  on every push to `main`, every pull request and weekly; Dependabot proposes dependency updates;
  GitHub secret scanning with push protection blocks commits that contain keys.

## If a key leaks

| Key | How to revoke |
|---|---|
| Telegram session | Telegram → Settings → Devices → terminate the session. Then `python -m dz.setup telegram`. |
| Telegram api_hash | my.telegram.org → API development tools (create a new app if needed). |
| Moodle token | Moodle → Preferences → Security keys → Reset. Then `python -m dz.setup moodle`. |
| Classroom Apps Script URL | script.google.com → your project → Deploy → Manage deployments → Archive. Then `python -m dz.setup classroom`. |
| Google OAuth token | <https://myaccount.google.com/permissions> → remove the app. |
