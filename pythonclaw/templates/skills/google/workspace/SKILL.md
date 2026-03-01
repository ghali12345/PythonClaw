---
name: google_workspace
description: >
  Google Workspace CLI — Gmail, Calendar, Drive, Contacts, Sheets, and Docs
  via the gog command-line tool. Use when the user asks to send email, search
  Gmail, check calendar events, manage Google Drive files, read or edit
  Google Sheets, export Google Docs, or look up contacts.
---
# Google Workspace (gog CLI)

Powered by [gog](https://github.com/steipete/gogcli) — a Google Workspace
CLI for Gmail, Calendar, Drive, Contacts, Sheets, and Docs.

## Prerequisites

Install gog:
```
brew install steipete/tap/gogcli
```

On Linux (manual install):
```
curl -fsSL https://api.github.com/repos/steipete/gogcli/releases/latest \
  | grep browser_download_url | grep linux_amd64
# Download the tarball, extract, and install:
# sudo install -m 0755 gog /usr/local/bin/gog
```

## Setup (one-time)

1. Create OAuth credentials at [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
   (Desktop App type) and download `client_secret.json`.
2. Run:
```
gog auth credentials /path/to/client_secret.json
gog auth add you@gmail.com --services gmail,calendar,drive,contacts,sheets,docs
```
3. Optionally set `GOG_ACCOUNT=you@gmail.com` as an environment variable to avoid `--account` on every call.

## Commands

### Gmail

| Action | Command |
|--------|---------|
| Search mail | `gog gmail search 'newer_than:7d' --max 10` |
| Send email | `gog gmail send --to user@example.com --subject "Hi" --body "Hello"` |
| Read message | `gog gmail read <message_id>` |
| Mark as read | `gog gmail labels modify <message_id> --remove UNREAD` |
| List labels | `gog gmail labels list` |

### Calendar

| Action | Command |
|--------|---------|
| List events | `gog calendar events --from 2026-02-23 --to 2026-02-28` |
| Create event | `gog calendar create --title "Meeting" --start "2026-02-24T10:00" --end "2026-02-24T11:00"` |

### Drive

| Action | Command |
|--------|---------|
| Search files | `gog drive search "query" --max 10` |
| List files | `gog drive list --max 20` |
| Download | `gog drive download <file_id> --out /tmp/file.pdf` |

### Google Sheets

| Action | Command |
|--------|---------|
| Get data | `gog sheets get <spreadsheet_id> "Sheet1!A1:D10" --json` |
| Metadata | `gog sheets metadata <spreadsheet_id> --json` |
| Append rows | `gog sheets append <spreadsheet_id> "Sheet1!A:C" --values-json '[["x","y","z"]]' --insert I...
| Update cells | `gog sheets update <spreadsheet_id> "Sheet1!A1:B2" --values-json '[["A","B"],["1","2"]]' -...
| Clear range | `gog sheets clear <spreadsheet_id> "Sheet1!A2:Z"` |

### Google Docs

| Action | Command |
|--------|---------|
| Read content | `gog docs cat <document_id>` |
| Export | `gog docs export <document_id> --format txt --out /tmp/doc.txt` |
| Copy | `gog docs copy <document_id> --title "Copy of Doc"` |

### Contacts

| Action | Command |
|--------|---------|
| List contacts | `gog contacts list --max 20` |
| Search | `gog contacts search "name"` |

## Important Notes

- **Always confirm** before sending emails or creating calendar events.
- For scripting/automation, prefer `--json` and `--no-input` flags.
- Google Docs in-place editing requires the Docs API directly (not available in gog).
- Set `GOG_ACCOUNT` env var to skip `--account` on every command.
- Use `gog auth list` to check configured accounts.
