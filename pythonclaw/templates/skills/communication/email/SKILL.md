---
name: email
description: >
  Send emails via SMTP. Supports plain text and HTML, attachments, CC/BCC.
  Use when the user asks to send any kind of email — notifications,
  messages, reports, etc. Credentials are read from pythonclaw.json.
---

## Instructions

Send emails through an SMTP server.  Credentials are stored in the
`skills.email` section of `pythonclaw.json`.

### Prerequisites

The user must configure these fields in `pythonclaw.json` (or the web dashboard Config page):

```json
"skills": {
  "email": {
    "smtpServer": "smtp.gmail.com",
    "smtpPort": 587,
    "senderEmail": "you@gmail.com",
    "senderPassword": "your-app-password"
  }
}
```

For Gmail, use an [App Password](https://myaccount.google.com/apppasswords).

### Usage

```bash
python {skill_path}/send_email.py \
  --to "recipient@example.com" \
  --subject "Hello" \
  --body "Message body here"
```

Optional flags:
- `--cc "a@b.com,c@d.com"` — CC recipients
- `--bcc "x@y.com"` — BCC recipients
- `--html` — treat body as HTML

### Examples

- "Send an email to alice@example.com saying the report is ready"
- "Email bob@company.com with subject 'Meeting Update' and body 'Rescheduled to 3pm'"

## Resources

| File | Description |
|------|-------------|
| `send_email.py` | Generic SMTP email sender |
