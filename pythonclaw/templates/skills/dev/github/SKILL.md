---
name: github
description: >
  Interact with the GitHub API — list repos, create issues, view PRs,
  manage releases. Use when the user asks about GitHub repositories,
  issues, pull requests, or wants to perform any GitHub operation.
  Requires a GitHub Personal Access Token in pythonclaw.json.
---

## Instructions

Interact with the GitHub REST API.  A Personal Access Token (PAT) is
read from `skills.github.token` in `pythonclaw.json`.

### Prerequisites

1. Create a PAT at https://github.com/settings/tokens
2. Configure in `pythonclaw.json`:

```json
"skills": {
  "github": {
    "token": "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  }
}
```

### Usage

```bash
python {skill_path}/gh.py <command> [options]
```

Commands:
- `repos <user>` — list user's public repositories
- `repo <owner/repo>` — get repository details
- `issues <owner/repo>` — list open issues
- `create-issue <owner/repo> --title "..." --body "..."` — create an issue
- `prs <owner/repo>` — list open pull requests
- `pr <owner/repo> <number>` — get PR details

### Examples

- "List my GitHub repositories" → `gh.py repos <username>`
- "Show open issues on pythonclaw" → `gh.py issues user/pythonclaw`
- "Create an issue for the login bug" → `gh.py create-issue user/repo --title "Login bug" --body "..."`

## Resources

| File | Description |
|------|-------------|
| `gh.py` | GitHub API client |
