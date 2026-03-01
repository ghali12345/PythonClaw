---
name: onboarding
description: >
  First-time setup wizard. Asks the user their preferred name, desired
  agent personality, and focus area, then writes soul.md and persona.md.
  Use when the agent starts for the first time with no soul/persona
  configured, or when the user asks to reconfigure their agent identity.
---

## Instructions

Guide the user through initial agent setup with a friendly conversation.

### When to Use

- Agent starts with empty/default soul.md and persona.md
- User says "reconfigure", "setup", "change my agent", etc.

### Onboarding Flow

Ask these questions **one at a time** in a friendly, conversational tone:

1. **Name**: "What should I call you?"
2. **Personality**: "What kind of personality would you like me to have?
   For example: professional & concise, friendly & casual, humorous,
   formal, encouraging, etc."
3. **Focus area**: "What area would you like me to focus on?
   For example: software development, finance & investing, research,
   daily assistant, creative writing, etc."
4. **Language preference**: "What language do you prefer I respond in?
   (English, Chinese, etc.)"

### After Collecting Answers

Use `run_command` to write the files:

**Write soul.md:**
```bash
python {skill_path}/write_identity.py --type soul \
  --user-name "NAME" \
  --personality "PERSONALITY" \
  --focus "FOCUS" \
  --language "LANGUAGE"
```

**Write persona.md:**
```bash
python {skill_path}/write_identity.py --type persona \
  --user-name "NAME" \
  --personality "PERSONALITY" \
  --focus "FOCUS" \
  --language "LANGUAGE"
```

After writing, tell the user: "Setup complete! Your preferences have been
saved. Use `/clear` to start a fresh conversation with your new identity,
or just keep chatting."

## Resources

| File | Description |
|------|-------------|
| `write_identity.py` | Generates soul.md and persona.md files |
