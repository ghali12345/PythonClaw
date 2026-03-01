---
name: code_runner
description: >
  Execute Python code snippets safely in an isolated subprocess with
  timeout protection. Use when the user asks to run, test, or evaluate
  Python code, calculate expressions, or prototype logic.
---

## Instructions

Run Python code in an isolated subprocess with stdout/stderr capture
and timeout protection. No extra dependencies needed.

### Usage

```bash
python {skill_path}/run_code.py [options]
```

Input methods:
- `--code "print(2+2)"` — inline code string
- `--file script.py` — run a Python file
- `stdin` — pipe code via stdin

Options:
- `--timeout 30` — max execution time in seconds (default: 30)
- `--format json` — output as JSON with stdout, stderr, exit code
- `--no-capture` — stream output directly (no capture)

### Examples

- "Calculate 2^100" → `run_code.py --code "print(2**100)"`
- "Run this Python snippet" → `run_code.py --code "import math; print(math.pi)"`
- "Test this function" → `run_code.py --file test.py`

### Security

- Code runs in a **subprocess** (not eval/exec in the agent process)
- Timeout prevents infinite loops
- Working directory is the project root

## Resources

| File | Description |
|------|-------------|
| `run_code.py` | Safe Python code executor |
