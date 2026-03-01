---
name: youtube
description: >
  Get YouTube video information, metadata, and transcripts/subtitles.
  Use when the user asks about a YouTube video, wants a video summary,
  needs a transcript, or asks to extract info from a YouTube URL.
---

## Instructions

Extract information and transcripts from YouTube videos.

### Prerequisites

Install dependencies: `pip install yt-dlp youtube-transcript-api`

### Usage

```bash
python {skill_path}/youtube_info.py URL [command] [options]
```

Commands:
- `info` (default) — video title, duration, views, description
- `transcript` — full transcript/subtitles
- `search` — search YouTube for videos (uses URL arg as search query)

Options:
- `--lang en` — transcript language (default: en)
- `--format json` — output as JSON
- `--max 5` — max results for search (default: 5)

### Examples

- "What's this video about? https://youtube.com/watch?v=xyz" → `youtube_info.py URL info`
- "Get the transcript of this video" → `youtube_info.py URL transcript`
- "Search YouTube for Python tutorials" → `youtube_info.py "Python tutorials" search`

## Resources

| File | Description |
|------|-------------|
| `youtube_info.py` | YouTube info and transcript extractor |
