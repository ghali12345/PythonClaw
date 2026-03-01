"""
Markdown-backed memory storage (inspired by OpenClaw).

Layout
------
  context/memory/MEMORY.md         — curated long-term memory (latest value per key)
  context/memory/YYYY-MM-DD.md     — daily append-only log

Write flow
----------
  set(key, value)  →  append to today's daily log  +  upsert into MEMORY.md

Read flow
---------
  get(key)         →  read from MEMORY.md (always holds the latest)
  list_all()       →  parse MEMORY.md and return {key: value}

Conflict resolution
-------------------
  MEMORY.md always holds the latest value for each key. When set() is called,
  it updates MEMORY.md with the new timestamp, so the most recent write wins.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Dict


_KEY_HEADER = re.compile(r"^## (.+)$", re.MULTILINE)
_UPDATED_LINE = re.compile(r"^> Updated: (.+)$", re.MULTILINE)


class MemoryStorage:
    """Markdown-backed key-value memory with daily logs."""

    def __init__(self, memory_dir: str | None = None) -> None:
        if memory_dir is None:
            from ... import config as _cfg
            memory_dir = os.path.join(str(_cfg.PYTHONCLAW_HOME), "context", "memory")
        self.memory_dir = memory_dir
        os.makedirs(memory_dir, exist_ok=True)
        self._memory_file = os.path.join(memory_dir, "MEMORY.md")
        self.data: Dict[str, dict] = {}   # key → {"value": ..., "updated": ...}
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Parse MEMORY.md into self.data."""
        if not os.path.exists(self._memory_file):
            self.data = {}
            return

        try:
            with open(self._memory_file, "r", encoding="utf-8") as f:
                text = f.read()
        except OSError:
            self.data = {}
            return

        self.data = self._parse_memory_md(text)

    @staticmethod
    def _parse_memory_md(text: str) -> Dict[str, dict]:
        """
        Parse a MEMORY.md into {key: {"value": str, "updated": str}}.

        Expected format per entry::

            ## key_name
            > Updated: 2026-02-23 15:30:00

            The actual value content here.
        """
        entries: Dict[str, dict] = {}
        sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)

        for section in sections:
            section = section.strip()
            if not section:
                continue
            key_match = _KEY_HEADER.match(section)
            if not key_match:
                continue
            key = key_match.group(1).strip()

            updated = ""
            upd_match = _UPDATED_LINE.search(section)
            if upd_match:
                updated = upd_match.group(1).strip()

            # Content is everything after the metadata lines
            lines = section.split("\n")
            content_lines = []
            past_header = False
            for line in lines[1:]:  # skip the ## heading
                if not past_header:
                    if line.startswith("> Updated:") or line.strip() == "":
                        continue
                    past_header = True
                content_lines.append(line)

            entries[key] = {
                "value": "\n".join(content_lines).strip(),
                "updated": updated,
            }

        return entries

    def _save_memory_md(self) -> None:
        """Write self.data back to MEMORY.md."""
        os.makedirs(os.path.dirname(self._memory_file) or ".", exist_ok=True)
        lines = ["# Long-Term Memory\n"]

        for key, entry in self.data.items():
            updated = entry.get("updated", "")
            value = entry.get("value", "")
            lines.append(f"## {key}")
            lines.append(f"> Updated: {updated}")
            lines.append("")
            lines.append(value)
            lines.append("")

        try:
            with open(self._memory_file, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except OSError as e:
            print(f"Error saving MEMORY.md: {e}")

    def _append_daily_log(self, key: str, value: str) -> None:
        """Append an entry to today's daily log file."""
        today = datetime.now().strftime("%Y-%m-%d")
        daily_file = os.path.join(self.memory_dir, f"{today}.md")
        now = datetime.now().strftime("%H:%M:%S")

        is_new = not os.path.exists(daily_file)
        try:
            with open(daily_file, "a", encoding="utf-8") as f:
                if is_new:
                    f.write(f"# Daily Memory — {today}\n\n")
                f.write(f"### {now} — {key}\n\n{value}\n\n")
        except OSError as e:
            print(f"Error writing daily memory log: {e}")

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self, key: str) -> Any:
        entry = self.data.get(key)
        return entry["value"] if entry else None

    def set(self, key: str, value: Any) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.data[key] = {"value": str(value), "updated": now}
        self._save_memory_md()
        self._append_daily_log(key, str(value))

    def delete(self, key: str) -> None:
        if key in self.data:
            del self.data[key]
            self._save_memory_md()

    def list_all(self) -> Dict[str, Any]:
        """Return {key: value} for all entries (latest version)."""
        return {k: v["value"] for k, v in self.data.items()}
