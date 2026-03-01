---
name: translator
description: >
  Translate text between any languages. Supports 100+ languages with
  automatic source language detection. Use when the user asks to
  translate text, detect a language, or work with multilingual content.
---

## Instructions

Translate text between languages using the `deep-translator` library.
Supports 100+ languages with automatic detection of the source language.

### Prerequisites

Install dependency: `pip install deep-translator`

### Usage

```bash
python {skill_path}/translate.py "text to translate" --to TARGET_LANG [options]
```

Options:
- `--to LANG` — target language code or name (required, e.g. `zh-CN`, `french`, `ja`)
- `--from LANG` — source language (default: `auto` for auto-detection)
- `--format json` — output as JSON

### Language Codes

Common codes: `en` (English), `zh-CN` (Chinese Simplified), `zh-TW` (Chinese Traditional),
`ja` (Japanese), `ko` (Korean), `fr` (French), `de` (German), `es` (Spanish),
`pt` (Portuguese), `ru` (Russian), `ar` (Arabic), `hi` (Hindi), `it` (Italian).

You can also use full names: `chinese (simplified)`, `japanese`, `french`, etc.

### Examples

- "Translate 'Hello world' to Chinese" → `python {skill_path}/translate.py "Hello world" --to zh-CN`
- "Translate this Japanese text to English" → `python {skill_path}/translate.py "..." --from ja --to en`
- "How do you say 'thank you' in Korean?" → `python {skill_path}/translate.py "thank you" --to ko`

## Resources

| File | Description |
|------|-------------|
| `translate.py` | Multi-language translator |
