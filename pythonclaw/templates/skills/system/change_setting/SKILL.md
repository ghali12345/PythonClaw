---
name: change_setting
description: >
  Modify pythonclaw.json configuration at runtime. Use when the user wants
  to set API keys, tokens, change LLM provider, adjust web port, or
  update any configuration value.
---

## Instructions

Read and modify the project configuration file `pythonclaw.json`.

### When to Use

- User says "set my API key to ...", "change provider to ...",
  "update my token", "configure email", etc.
- User wants to change any runtime setting without editing files manually

### How to Use

1. Read the current config:
   ```bash
   python {skill_path}/update_config.py --show
   ```

2. Update a specific value using dot-notation for the key path:
   ```bash
   python {skill_path}/update_config.py --set "llm.deepseek.apiKey" "sk-xxx"
   ```

   Examples:
   ```bash
   # Change LLM provider
   python {skill_path}/update_config.py --set "llm.provider" "claude"

   # Set Tavily API key
   python {skill_path}/update_config.py --set "tavily.apiKey" "tvly-xxx"

   # Set Telegram token
   python {skill_path}/update_config.py --set "channels.telegram.token" "123:ABC"

   # Set GitHub token
   python {skill_path}/update_config.py --set "skills.github.token" "ghp_xxx"

   # Change web port
   python {skill_path}/update_config.py --set "web.port" "8080"

   # Set email credentials
   python {skill_path}/update_config.py --set "skills.email.senderEmail" "me@gmail.com"
   python {skill_path}/update_config.py --set "skills.email.senderPassword" "app-password"
   ```

3. After updating, tell the user the change was saved and whether
   a restart is needed to take effect.

### Security Notes

- When displaying config, API keys / passwords / tokens are masked
- Only `pythonclaw.json` is modified — no other files

## Resources

| File | Description |
|------|-------------|
| `update_config.py` | CLI tool to read and update pythonclaw.json |
