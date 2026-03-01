---
name: change_soul
description: >
  Modify the agent's core identity (soul.md). Use when the user wants to
  change their name, the agent's core values, language preference, or
  fundamental behavior.
---

## Instructions

Modify the agent's soul (core identity) file at `context/soul/SOUL.md`.

### When to Use

- User says "change my name to ...", "call me ...", "change language to ..."
- User wants to modify core values or ethical boundaries
- User asks to update fundamental agent behavior

### How to Use

1. Ask the user what they want to change
2. Read the current soul file:
   ```
   read_file("context/soul/SOUL.md")
   ```
3. Modify the relevant section and write it back:
   ```
   write_file("context/soul/SOUL.md", "...updated content...")
   ```
4. Tell the user: "Soul updated. Use `/clear` to apply the changes in
   a fresh conversation, or they will take effect on next restart."

### Important

- Preserve the overall structure of SOUL.md
- Only change the specific section the user asked about
- Keep core ethical boundaries intact — never remove safety guidelines

## Resources

This skill uses the built-in `read_file` and `write_file` tools directly.
