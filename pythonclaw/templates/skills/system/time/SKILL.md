---
name: system_time
description: >
  Get the current date, time, timezone, or convert between timezones.
  Use when the user asks what time it is, needs a date, or timezone conversion.
---

## Instructions

Get time information using the bundled script.

```bash
# Current local time
python {skill_path}/time_util.py

# Time in a specific timezone
python {skill_path}/time_util.py --tz "America/New_York"

# List common timezone names
python {skill_path}/time_util.py --list-tz

# Unix timestamp
python {skill_path}/time_util.py --unix

# Convert a time between timezones
python {skill_path}/time_util.py --convert "2026-03-01 14:30" --from-tz "Asia/Shanghai" --to-tz "America/New_York"
```

## Resources

| File | Description |
|------|-------------|
| `time_util.py` | CLI tool for time queries and conversions |
