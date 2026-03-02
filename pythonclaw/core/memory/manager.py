"""
MemoryManager — long-term key-value memory with hybrid RAG recall.

Storage
-------
Memories are stored as Markdown files:
  - MEMORY.md        — curated long-term memory (latest value per key)
  - YYYY-MM-DD.md    — daily append-only log

When writing, both MEMORY.md and today's daily log are updated.
When reading, MEMORY.md is the source of truth (holds latest per key).
Conflict resolution: if the same key is written multiple times, the most
recent write wins (MEMORY.md is always overwritten with the latest value).

Per-group isolation
-------------------
When ``global_memory_dir`` is set, recall merges results from BOTH the
local (group-specific) memory AND the global (shared) memory.  Writes
always go to the local memory only.  This lets each Telegram/Discord/
WhatsApp group maintain private memories while still having access to
shared knowledge.

Recall
------
When a specific query is given, the manager converts every memory entry into a
short "chunk"  ("{key}: {value}")  and runs hybrid sparse + dense retrieval to
return the most relevant ones.  When the query is empty or "*", ALL memories
are returned (full-dump mode, used by compaction and legacy callers).
"""

from __future__ import annotations

import logging

from ..retrieval.retriever import HybridRetriever
from .storage import MemoryStorage

logger = logging.getLogger(__name__)

_DUMP_TRIGGERS = {"", "*", "all", "everything"}


class MemoryManager:
    """
    Manages long-term memories stored as Markdown files.

    Parameters
    ----------
    memory_dir        : path to the local memory directory.
    global_memory_dir : optional path to a shared/global memory directory.
                        When set, recall() merges results from both local and
                        global stores.  Writes always go to local only.
    use_dense         : include embedding retrieval for recall (False by default
                        — BM25 alone is fast and sufficient for small corpora).
    """

    def __init__(
        self,
        memory_dir: str | None = None,
        global_memory_dir: str | None = None,
        use_dense: bool = False,
    ) -> None:
        import os

        if memory_dir is None:
            from ... import config as _cfg
            memory_dir = os.path.join(str(_cfg.PYTHONCLAW_HOME), "context", "memory")

        self.storage = MemoryStorage(memory_dir)
        self._global_storage: MemoryStorage | None = None
        if global_memory_dir and os.path.isdir(global_memory_dir):
            self._global_storage = MemoryStorage(global_memory_dir)
        self._use_dense = use_dense

    # ── Merged memories (local + global) ─────────────────────────────────────

    def _merged_memories(self) -> dict[str, str]:
        """Return local memories overlaid on global memories."""
        merged: dict[str, str] = {}
        if self._global_storage is not None:
            for k, v in self._global_storage.list_all().items():
                merged[f"[global] {k}"] = v
        merged.update(self.storage.list_all())
        return merged

    # ── Core operations ──────────────────────────────────────────────────────

    def remember(self, content: str, key: str | None = None) -> str:
        """Store *content* under *key* in local (group) memory."""
        if not key:
            raise ValueError("Key is required for memory storage.")
        self.storage.set(key, content)
        return f"Memory stored: [{key}] = {content}"

    def recall(self, query: str, top_k: int = 10) -> str:
        """
        Retrieve memories relevant to *query*.

        Searches both local and global memories when global_memory_dir is set.

        - If query is empty / "*" / "all" → returns ALL memories (full dump).
        - Otherwise → runs hybrid BM25 (+ optional dense) retrieval and
          returns the top *top_k* most relevant entries.
        """
        all_memories = self._merged_memories()
        if not all_memories:
            return "No memories found."

        if query.strip().lower() in _DUMP_TRIGGERS:
            lines = [f"- {k}: {v}" for k, v in all_memories.items()]
            return "\n".join(lines)

        corpus = [
            {"source": k, "content": f"{k}: {v}"}
            for k, v in all_memories.items()
        ]

        retriever = HybridRetriever(
            provider=None,
            use_sparse=True,
            use_dense=self._use_dense,
            use_reranker=False,
        )
        retriever.fit(corpus)
        hits = retriever.retrieve(query, top_k=top_k)

        if not hits:
            logger.debug("[MemoryManager] No RAG hits for '%s', returning all.", query)
            lines = [f"- {k}: {v}" for k, v in all_memories.items()]
            return "(No close match found; showing all memories)\n" + "\n".join(lines)

        lines = [f"- {h['source']}: {h['content'].split(': ', 1)[-1]}" for h in hits]
        return "\n".join(lines)

    def forget(self, key: str) -> str:
        """Remove a memory entry by key from local memory."""
        if self.storage.get(key) is not None:
            self.storage.delete(key)
            return f"Forgot: {key}"
        return f"Nothing found for: {key}"

    # ── Helpers used by compaction ───────────────────────────────────────────

    def list_all(self) -> dict:
        """Return the raw {key: value} dict (local only, used by compaction)."""
        return self.storage.list_all()
