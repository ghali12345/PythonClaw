---
name: change_persona
description: >
  Modify the agent's personality and role (persona.md). Use when the user
  wants to change the agent's personality, communication style, focus area,
  or specialization.
---

## Instructions

Modify the agent's persona file at `context/persona/persona.md`.

### When to Use

- User says "be more formal", "be funnier", "focus on finance now"
- User wants to change the agent's specialization or expertise area
- User asks to adjust communication style or personality traits

### How to Use

1. Ask the user what they want to change
2. Read the current persona file:
   ```
   read_file("context/persona/persona.md")
   ```
3. Modify the relevant section and write it back:
   ```
   write_file("context/persona/persona.md", "...updated content...")
   ```
4. Tell the user: "Persona updated. Use `/clear` to apply the changes
   in a fresh conversation, or they will take effect on next restart."

### Important

- Preserve the overall structure of persona.md
- Only change the specific section the user asked about
- If the file doesn't exist yet, create it with a reasonable template

## Resources

This skill uses the built-in `read_file` and `write_file` tools directly.
