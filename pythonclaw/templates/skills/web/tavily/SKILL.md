---
name: tavily_search
description: >
  Advanced web search using the Tavily API. Use when the user asks to search
  the web, look up current events, find real-time information, research a topic,
  check facts, or retrieve data from the internet.
---
# Tavily Web Search

## Overview

You have a built-in `web_search` tool powered by [Tavily](https://tavily.com).
It provides real-time web search with AI-generated summaries and source links.

## Instructions

Use the `web_search` tool directly — no external scripts needed.

### Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `query` | string | The search query (be specific) | **required** |
| `search_depth` | string | `"basic"` (fast) or `"advanced"` (thorough) | `"basic"` |
| `topic` | string | `"general"`, `"news"`, or `"finance"` | `"general"` |
| `max_results` | integer | Number of results (1-20) | `5` |
| `time_range` | string | `"day"`, `"week"`, `"month"`, or `"year"` | none |

### Examples

**Basic search:**
```
web_search(query="Python 3.13 new features")
```

**News search (last week):**
```
web_search(query="AI industry news", topic="news", time_range="week", max_results=10)
```

**Finance search (advanced depth):**
```
web_search(query="NVIDIA stock analysis 2026", topic="finance", search_depth="advanced")
```

## Best Practices

1. **Be specific** — "Python asyncio best practices 2026" is better than "Python async"
2. **Use `topic`** — set `"news"` for current events, `"finance"` for market data
3. **Use `time_range`** — filter by `"day"` or `"week"` when freshness matters
4. **Use `advanced`** — set `search_depth="advanced"` for research-heavy queries
5. **Cite sources** — always include the URLs returned in your response to the user

## Setup

1. Get a free API key at [app.tavily.com](https://app.tavily.com/home)
2. Add your key to `pythonclaw.json`:
   ```json5
   "tavily": { "apiKey": "tvly-..." }
   ```
3. Install the SDK: `pip install tavily-python`
