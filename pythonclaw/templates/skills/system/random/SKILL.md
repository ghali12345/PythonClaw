---
name: system_random
description: >
  Generate random numbers, UUIDs, passwords, or pick random items from a list.
  Use when the user needs any kind of randomness.
---

## Instructions

Generate random values using the bundled script.

```bash
# Random integer in range
python {skill_path}/random_util.py --int 1 100

# Random float in range
python {skill_path}/random_util.py --float 0.0 1.0

# UUID
python {skill_path}/random_util.py --uuid

# Random password (default 16 chars)
python {skill_path}/random_util.py --password 20

# Pick N random items from a comma-separated list
python {skill_path}/random_util.py --choice "apple,banana,cherry,date" --count 2
```

## Resources

| File | Description |
|------|-------------|
| `random_util.py` | CLI tool for generating random values |
