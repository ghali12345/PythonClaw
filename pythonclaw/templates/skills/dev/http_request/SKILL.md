---
name: http_request
description: >
  Make HTTP requests (GET, POST, PUT, DELETE, PATCH) to any API endpoint.
  Use when the user asks to call an API, test an endpoint, fetch JSON data
  from a URL, or interact with a REST API.
---

## Instructions

Make arbitrary HTTP requests to any API endpoint.

### Prerequisites

Install dependency: `pip install requests`

### Usage

```bash
python {skill_path}/request.py URL [options]
```

Options:
- `--method GET|POST|PUT|DELETE|PATCH` (default: GET)
- `--data '{"key": "value"}'` — JSON request body
- `--header "Name: Value"` — custom header (repeatable)
- `--timeout 30` — timeout in seconds
- `--format text|json|headers` — output format

### Examples

- "GET https://api.github.com/users/octocat"
- "POST to https://httpbin.org/post with body {'name': 'test'}"
- "Call the weather API at https://api.example.com/weather?city=Tokyo"

## Resources

| File | Description |
|------|-------------|
| `request.py` | Generic HTTP request tool |
