---
name: skill_creator
description: >
  Dynamically create new skills when no existing skill can handle the user's
  request. Use this when you need a capability that doesn't exist yet —
  write the code, bundle it as a skill, install dependencies, and make it
  immediately available.
---

## Instructions

You have the ability to **create brand-new skills on the fly** using the
`create_skill` tool. This is your "god mode" — if no existing skill can
fulfill a request, design and build one yourself.

### When to Use

- The user asks for something none of the installed skills cover
- An existing skill is too limited and a better replacement is needed
- A recurring task would benefit from a dedicated, reusable skill

### When NOT to Use

- **DON'T** create a skill for a one-off task that existing tools can handle
  (e.g. `run_command` can already execute shell commands)
- **DON'T** create a skill that's too specific to be reused — always think
  about what the **general category** of the request is and build for that
- **DON'T** hardcode user-specific values (names, URLs, topics) into the
  skill — make them parameters

### Design Principles

1. **GENERIC over specific** — NEVER create a skill that only works for
   one narrow task. Always generalize:
   - BAD: `us_iran_news_fetcher` (hardcoded topic, useless for anything else)
   - GOOD: `news` (searches any topic, parameterized query)
   - BAD: `send_meeting_invite_to_bob` (single use case)
   - GOOD: `email` (sends any email to any recipient)
2. **Parameterized** — use command-line arguments, not hardcoded values.
   Every specific detail (query, recipient, URL, etc.) should be an argument.
3. **Single Responsibility** — each skill should do one thing well
4. **Clean Code** — write production-quality Python scripts with proper
   error handling, logging, and docstrings
5. **Minimal Dependencies** — only add pip packages that are truly needed
6. **Clear Instructions** — the SKILL.md body should explain exactly how
   to use the skill so your future self (or another agent) can follow it
7. **Reusable** — design the skill to work for ANY similar future request.
   Ask yourself: "Would this skill be useful to someone with a completely
   different task?" If not, generalize it.
8. **Config-driven credentials** — if the skill needs API keys or tokens,
   read them from `pythonclaw.json` (under `skills.<name>`) instead of
   hardcoding or requiring environment variables

### Step-by-Step Workflow

1. **Analyze the gap**: identify exactly what capability is missing
2. **Plan the skill**: decide on the name, category, required scripts,
   and any pip dependencies
3. **Call `create_skill`** with:
   - `name` — short, descriptive, snake_case (e.g. `pdf_summarizer`)
   - `description` — one-line summary for the skill catalog
   - `instructions` — full Markdown body (see template below)
   - `category` — group folder (e.g. `data`, `dev`, `web`, `automation`)
   - `resources` — dict mapping filenames to their source code
   - `dependencies` — list of pip packages to install
4. **Activate the skill**: call `use_skill(skill_name="<name>")` to load
   the new instructions
5. **Run it**: follow the loaded instructions to execute the task

### SKILL.md Body Template

Use this structure for the `instructions` argument:

```
## Instructions

<Clear explanation of what the skill does and when to use it.>

### Prerequisites

- <any setup steps or API keys needed>

### Usage

1. <step-by-step usage instructions>
2. Call `run_command` with: `python context/skills/<category>/<name>/<script>.py <args>`
3. <interpret results>

### Examples

**Example:** <describe a typical use case>

## Resources

| File | Description |
|------|-------------|
| `script.py` | <what it does> |
```

### Resource Script Template

When writing Python scripts for `resources`, follow this pattern:

```python
#!/usr/bin/env python3
"""One-line description of the script."""
import argparse
import json
import sys

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Input to process")
    parser.add_argument("--format", default="text", choices=["text", "json"])
    args = parser.parse_args()

    try:
        result = process(args.input)
        if args.format == "json":
            print(json.dumps(result, indent=2))
        else:
            print(result)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

def process(data):
    # ... actual logic ...
    return data

if __name__ == "__main__":
    main()
```

### Example: Creating a CSV Analyzer Skill

```
create_skill(
    name="csv_analyzer",
    description="Analyze CSV files — summary statistics, column info, and data preview.",
    category="data",
    instructions="## Instructions\n\nAnalyze CSV files ...",
    resources={
        "analyze.py": "#!/usr/bin/env python3\nimport pandas as pd\n..."
    },
    dependencies=["pandas"]
)
```

After creation, call `use_skill(skill_name="csv_analyzer")` to activate it,
then follow its instructions.
