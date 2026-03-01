---
name: news
description: >
  Search and summarise news on any topic using web search.
  Use when the user asks about recent news, current events, or wants
  a news briefing on any subject.
---

## Instructions

Search for recent news on any topic.  This skill uses the built-in
`web_search` tool (Tavily) or falls back to a script that uses
DuckDuckGo if Tavily is not configured.

### Usage

**Option A — use the `web_search` tool directly** (preferred when Tavily is configured):

```
web_search(query="latest news about <topic>", topic="news", max_results=10)
```

**Option B — use the bundled script** (works without Tavily):

```bash
python {skill_path}/search_news.py "topic" [--max 10]
```

### Examples

- "What's happening in the tech industry today?"
- "Give me the latest AI news"
- "News about the 2026 World Cup"

## Resources

| File | Description |
|------|-------------|
| `search_news.py` | Fallback news search via DuckDuckGo |
