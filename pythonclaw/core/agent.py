"""
Agent — the core reasoning loop for PythonClaw.

Responsibilities
----------------
  - Maintain conversation history (messages list)
  - Build the per-session tool set and dispatch tool calls
  - Three-tier progressive skill loading (catalog → instructions → resources)
  - Trigger context compaction (auto or manual)
  - Interface with memory (MemoryManager) and knowledge (KnowledgeRAG)

What this class is NOT responsible for
---------------------------------------
  - Session lifecycle (→ SessionManager)
  - Persistence across restarts (→ PersistentAgent subclass)
  - I/O channels like Telegram (→ channels/)
  - Scheduling (→ scheduler/)
"""

from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from .. import config
from .compaction import (
    DEFAULT_AUTO_THRESHOLD_TOKENS,
    DEFAULT_RECENT_KEEP,
    compact as _do_compact,
    estimate_tokens,
)
from .knowledge.rag import KnowledgeRAG
from .llm.base import LLMProvider
from .memory.manager import MemoryManager
from .skill_loader import SkillRegistry
from .tools import (
    AVAILABLE_TOOLS,
    CRON_TOOLS,
    KNOWLEDGE_TOOL,
    MEMORY_TOOLS,
    META_SKILL_TOOLS,
    PRIMITIVE_TOOLS,
    SKILL_TOOLS,
    WEB_SEARCH_TOOL,
    configure_venv,
    set_sandbox,
)

logger = logging.getLogger(__name__)


def _load_text_dir_or_file(path: str | None, label: str = "File") -> str:
    """
    Load text from a single file or from all .md/.txt files in a directory.
    Returns an empty string if *path* is None or does not exist.
    """
    if not path or not os.path.exists(path):
        return ""
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    if os.path.isdir(path):
        parts = []
        for filename in sorted(os.listdir(path)):
            if filename.lower().endswith((".md", ".txt")):
                with open(os.path.join(path, filename), "r", encoding="utf-8") as f:
                    parts.append(f"\n\n--- {label}: {filename} ---\n" + f.read())
        return "".join(parts)
    return ""


_DETAIL_LOG_DIR = os.path.join("context", "logs")
_DETAIL_LOG_FILE = os.path.join(_DETAIL_LOG_DIR, "history_detail.jsonl")


def _log_detail(entry: dict) -> None:
    """Append a JSON line to the detailed interaction log."""
    try:
        os.makedirs(_DETAIL_LOG_DIR, exist_ok=True)
        entry["ts"] = datetime.now().isoformat(timespec="milliseconds")
        with open(_DETAIL_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


class Agent:
    """
    Stateful LLM agent with tool use, three-tier skill loading, memory,
    and compaction.

    Parameters
    ----------
    provider           : LLM backend (DeepSeek, Grok, Claude, Gemini, …)
    memory_dir         : path to memory directory (auto-detected if None)
    skills_dirs        : list of skill directory paths
    knowledge_path     : path to knowledge directory for RAG
    persona_path       : path to persona .md file or directory
    soul_path          : path to SOUL.md file or directory
    verbose            : print debug info to stdout
    show_full_context  : print the full context window before each LLM call
    max_chat_history   : max non-system messages kept in the sliding window
    auto_compaction    : trigger compaction when token estimate exceeds threshold
    compaction_threshold : token threshold for auto-compaction
    compaction_recent_keep : number of recent messages kept verbatim after compaction
    cron_manager       : CronScheduler instance (enables cron_add/remove/list tools)
    """

    MAX_TOOL_ROUNDS = 15

    def __init__(
        self,
        provider: LLMProvider,
        memory_dir: str | None = None,
        skills_dirs: list[str] | None = None,
        knowledge_path: str | None = None,
        persona_path: str | None = None,
        soul_path: str | None = None,
        verbose: bool = False,
        show_full_context: bool = False,
        max_chat_history: int = 10,
        auto_compaction: bool = True,
        compaction_threshold: int = DEFAULT_AUTO_THRESHOLD_TOKENS,
        compaction_recent_keep: int = DEFAULT_RECENT_KEEP,
        cron_manager=None,
    ) -> None:
        if memory_dir is None and skills_dirs is None and knowledge_path is None and persona_path is None:
            cwd = os.getcwd()
            context_dir = os.path.join(cwd, "context")
            if not os.path.exists(context_dir):
                if verbose:
                    print(f"[Agent] Context not found. Initialising default context in {context_dir}...")
                try:
                    from ...init import init
                    init(cwd)
                except ImportError:
                    try:
                        from pythonclaw.init import init
                        init(cwd)
                    except ImportError:
                        print("[Agent] Warning: Could not auto-initialise context.")
            if verbose:
                print(f"[Agent] Using default context at {context_dir}")
            memory_dir = os.path.join(context_dir, "memory")
            knowledge_path = os.path.join(context_dir, "knowledge")
            skills_dirs = [os.path.join(context_dir, "skills")]
            persona_path = os.path.join(context_dir, "persona")
            if soul_path is None:
                soul_path = os.path.join(context_dir, "soul")

        # Sandbox: restrict file-write tools to the project working tree
        sandbox_root = os.getcwd()
        set_sandbox([sandbox_root])
        if verbose:
            print(f"[Agent] Sandbox root: {sandbox_root}")

        # Venv: ensure all subprocesses use the project's virtual environment
        venv_path = configure_venv()
        if verbose and venv_path:
            print(f"[Agent] Virtual env: {venv_path}")

        self.provider = provider
        self.messages: list[dict] = []
        self.verbose = verbose
        self.show_full_context = show_full_context
        self.max_chat_history = max_chat_history
        self.auto_compaction = auto_compaction
        self.compaction_threshold = compaction_threshold
        self.compaction_recent_keep = compaction_recent_keep
        self.compaction_count: int = 0
        self._cron_manager = cron_manager

        self.loaded_skill_names: set[str] = set()
        self.pending_injections: list[str] = []

        # Memory
        mem_dir = memory_dir or config.get("memory", "dir", env="PYTHONCLAW_MEMORY_DIR")
        self.memory = MemoryManager(mem_dir)

        # Knowledge RAG (hybrid retrieval)
        self.rag: KnowledgeRAG | None = None
        if knowledge_path and os.path.exists(knowledge_path):
            self.rag = KnowledgeRAG(
                knowledge_dir=knowledge_path,
                provider=provider,
                use_reranker=True,
            )
            if verbose:
                print(f"[Agent] KnowledgeRAG: '{knowledge_path}' ({len(self.rag)} chunks)")

        # Web search (Tavily)
        self._web_search_enabled = bool(
            config.get("tavily", "apiKey", env="TAVILY_API_KEY")
        )
        if verbose and self._web_search_enabled:
            print("[Agent] Web search enabled (Tavily)")

        # Skills — always include the built-in templates + user context/skills
        self.skills_dirs: list[str] = []
        pkg_templates = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "templates", "skills",
        )
        if os.path.isdir(pkg_templates):
            self.skills_dirs.append(pkg_templates)
        if skills_dirs:
            for d in ([skills_dirs] if isinstance(skills_dirs, str) else skills_dirs):
                if d not in self.skills_dirs:
                    self.skills_dirs.append(d)

        # Identity layers
        self.soul_instruction = _load_text_dir_or_file(soul_path, label="Soul")
        self.persona_instruction = _load_text_dir_or_file(persona_path, label="Persona")

        # Detect if the user has set up their own soul/persona (not template defaults)
        self._needs_onboarding = not self._has_user_identity(soul_path, persona_path)

        if verbose and self.soul_instruction:
            print(f"[Agent] Soul loaded ({len(self.soul_instruction)} chars)")
        if verbose and self.persona_instruction:
            print(f"[Agent] Persona loaded ({len(self.persona_instruction)} chars)")
        if verbose and self._needs_onboarding:
            print("[Agent] No user identity found — onboarding will be triggered")

        self._init_system_prompt()

    @staticmethod
    def _has_user_identity(soul_path: str | None, persona_path: str | None) -> bool:
        """Return True if the user has customized soul or persona files."""
        for p in (soul_path, persona_path):
            if p is None:
                continue
            if os.path.isdir(p):
                for fname in os.listdir(p):
                    fpath = os.path.join(p, fname)
                    if os.path.isfile(fpath) and os.path.getsize(fpath) > 0:
                        return True
            elif os.path.isfile(p) and os.path.getsize(p) > 0:
                return True
        return False

    # ── Initialisation ────────────────────────────────────────────────────────

    def _init_system_prompt(self) -> None:
        """
        Build the initial system message with three-tier skill loading.

        Level 1 (Metadata) is injected here — the full skill catalog
        (name + description for every installed skill).  This lets the
        LLM decide when to activate a skill without any discovery calls.
        """
        self._registry = SkillRegistry(skills_dirs=self.skills_dirs)
        skill_catalog = self._registry.build_catalog()

        soul_section = f"\n\n## Core Identity (Soul)\n{self.soul_instruction}" if self.soul_instruction else ""
        persona_section = f"\n\n## Role & Persona\n{self.persona_instruction}" if self.persona_instruction else ""

        web_search_section = ""
        if self._web_search_enabled:
            web_search_section = """
3. **Web Search**: `web_search` (powered by Tavily)
   Search the web for real-time information when you need up-to-date data,
   current events, facts you're unsure about, or technical documentation.
   Supports topic filters (general/news/finance) and time range filters."""

        system_msg = f"""You are a PythonClaw agent — an autonomous AI assistant.{soul_section}{persona_section}

You operate in a potentially sandboxed environment where you can execute code.

### Tool Capabilities
1. **Primitive Tools**: `run_command`, `read_file`, `write_file`, `list_files`
   Note: `write_file` can only write within the project directory.
2. **Skills** (three-tier progressive loading):
   You have access to the following skills.  Each skill's description
   tells you WHAT it does and WHEN to use it.

   **Installed Skills:**
{skill_catalog}

   To activate a skill, call `use_skill(skill_name="<name>")`.
   This loads detailed instructions into context.  After activation
   you can use `list_skill_resources` to discover bundled scripts
   and reference files, then `read_file` / `run_command` to use them.
{web_search_section}

### Skill Creation ("God Mode")
If NO existing skill can fulfill the user's request, you can **create a new skill
on the fly** using `create_skill`. This lets you:
- Write a SKILL.md with instructions and bundled Python/shell scripts
- Automatically install pip dependencies
- The new skill becomes immediately available via `use_skill`

Use this when the user needs a capability that doesn't exist yet.  Think carefully
about the skill design: write clean, reusable code and a clear SKILL.md.

**CRITICAL**: Always create GENERIC, reusable skills — NEVER task-specific ones.
- BAD: `us_iran_news_fetcher` (only one topic), `send_bob_email` (one recipient)
- GOOD: `news` (any topic as parameter), `email` (any recipient as parameter)
All specifics (topics, recipients, URLs) must be command-line arguments.

### Workflow
1. User asks a question.
2. Match the request against the skill catalog above.
3. If a skill fits, call `use_skill` to load its instructions (Level 2).
4. Follow the injected instructions.  Use `read_file` / `run_command`
   to access bundled resources as needed (Level 3).
5. If NO skill fits, consider creating one with `create_skill` — write
   the script, install dependencies, then immediately `use_skill` to
   activate and run it.

### Performance — Be Efficient
**CRITICAL RULES for speed:**
1. **Batch tool calls**: When you need multiple independent searches or
   tool calls, issue them ALL in a single response. They run in parallel
   and are MUCH faster. NEVER do one search per round.
2. **Minimize search rounds**: For most topics, 1-3 web searches total
   is enough. Combine queries (e.g. "NVDA stock price P/E ratio analyst
   ratings 2025" instead of 3 separate searches). Use `max_results=2-3`.
3. **Don't repeat**: If a previous search already covered a topic, use
   that data. Never search for the same information twice.
4. **Answer quickly**: Gather just enough data to answer well, then
   respond. Don't exhaustively search every sub-topic.

### Memory
You have a long-term memory.
- **Proactively save** ALL user profile details, preferences, and key facts using `remember`.
- Use `recall(query="<topic>")` to search memory semantically. Use `recall(query="*")` to retrieve ALL memories (full dump).
- ALWAYS check memory (`recall`) if the user asks something that might be stored from a previous session.

Always verify the output of your commands.

### Response Guidelines
- Answer the user's question directly and concisely.
- Do NOT mention what skills or tools you have available, unless explicitly asked.
- Do NOT list other things you can do at the end of your response.
"""
        if getattr(self, "_needs_onboarding", False):
            system_msg += """
### First-Time Onboarding
**IMPORTANT**: No user identity (soul/persona) has been configured yet.
On the VERY FIRST user message, start a friendly onboarding conversation.

**Language rule**: Always conduct onboarding in **English** by default.
If the user replies in another language, switch to that language for
the rest of the onboarding (and set that as their language preference).

1. Greet the user warmly and introduce yourself as PythonClaw
2. Ask: "What should I call you?" (wait for response)
3. Ask: "What kind of personality would you like me to have? (e.g. professional, friendly, humorous, encouraging)"
4. Ask: "What area would you like me to focus on? (e.g. software development, finance, research, daily assistant)"

After collecting ALL answers, use the `onboarding` skill to write the
soul.md and persona.md files. Detect the user's language from their
replies (default to English if they replied in English) and pass it as
the `--language` argument. Then use `remember` to save the user's name
and preferences to long-term memory.

Ask the questions ONE AT A TIME, waiting for each answer before asking the next.
If the user's first message already contains task content (not just "hi"),
still start onboarding but keep it brief — you can help with their task after.
"""

        self.messages.append({"role": "system", "content": system_msg})
        if self.verbose:
            logger.debug("System prompt built. Skill catalog: %d skills.", len(self._registry.discover()))

    # ── Tool management ───────────────────────────────────────────────────────

    def _build_tools(self) -> list[dict]:
        """Assemble the full tool schema list for the current session."""
        tools = PRIMITIVE_TOOLS + SKILL_TOOLS + META_SKILL_TOOLS + MEMORY_TOOLS
        if self._web_search_enabled:
            tools = tools + [WEB_SEARCH_TOOL]
        if self.rag:
            tools = tools + [KNOWLEDGE_TOOL]
        if self._cron_manager:
            tools = tools + CRON_TOOLS
        return tools

    def _execute_tool_call(self, tool_call) -> str:
        """Dispatch a single tool call and return the string result."""
        func_name: str = tool_call.function.name
        try:
            args: dict = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError as exc:
            return f"Error: could not parse tool arguments: {exc}"

        if self.verbose:
            logger.debug("Tool: %s  args=%s", func_name, args)

        try:
            if func_name == "use_skill":
                result = self._use_skill(args.get("skill_name"))
            elif func_name == "list_skill_resources":
                resources = self._registry.list_resources(args.get("skill_name", ""))
                if resources:
                    result = "Resources:\n" + "\n".join(f"  - {r}" for r in resources)
                else:
                    result = "No bundled resources found (or skill not found)."
            elif func_name == "remember":
                result = self.memory.remember(args.get("content"), args.get("key"))
            elif func_name == "recall":
                result = self.memory.recall(args.get("query", "*"))
            elif func_name == "consult_knowledge_base" and self.rag:
                hits = self.rag.retrieve(args.get("query"), top_k=5)
                if hits:
                    result = "Found relevant info:\n" + "\n".join(
                        f"- [{h['source']}]: {h['content']}" for h in hits
                    )
                else:
                    result = "No relevant information found in the knowledge base."
            elif func_name == "cron_add" and self._cron_manager:
                result = self._cron_manager.add_dynamic_job(
                    job_id=args.get("job_id"),
                    cron_expr=args.get("cron"),
                    prompt=args.get("prompt"),
                    deliver_to="telegram" if args.get("deliver_to_chat_id") else None,
                    chat_id=args.get("deliver_to_chat_id"),
                )
            elif func_name == "cron_remove" and self._cron_manager:
                result = self._cron_manager.remove_dynamic_job(args.get("job_id"))
            elif func_name == "cron_list" and self._cron_manager:
                result = self._cron_manager.list_jobs()
            elif func_name == "create_skill":
                result = AVAILABLE_TOOLS["create_skill"](**args)
                self._refresh_skill_registry()
            elif func_name in AVAILABLE_TOOLS:
                result = AVAILABLE_TOOLS[func_name](**args)
            else:
                result = f"Error: unknown tool '{func_name}'."
        except Exception as exc:
            result = f"Error executing '{func_name}': {exc}"

        if self.verbose:
            preview = str(result)[:200] + ("..." if len(str(result)) > 200 else "")
            logger.debug("Result: %s", preview)

        return str(result)

    # ── Skill registry refresh (after create_skill) ────────────────────────

    def _refresh_skill_registry(self) -> None:
        """Invalidate the registry cache so newly created skills are discovered."""
        self._registry.invalidate()
        new_catalog = self._registry.build_catalog()
        self.messages.append({
            "role": "system",
            "content": (
                "[Skill Registry Updated]\n"
                "A new skill has been created. Updated skill catalog:\n\n"
                f"{new_catalog}"
            ),
        })
        if self.verbose:
            count = len(self._registry.discover())
            logger.debug("Skill registry refreshed — %d skills now available.", count)

    # ── Skill loading (Level 2) ───────────────────────────────────────────────

    def _use_skill(self, skill_name: str) -> str:
        """
        Level 2: Load a skill's full instructions into context.

        Called when the LLM triggers ``use_skill``.  The SKILL.md body
        is injected as a system message so subsequent turns can follow
        the instructions.

        If the skill directory contains a ``check_setup.sh`` script, it
        is executed automatically before activation.  When the check fails
        (non-zero exit), the skill is still loaded but a prominent warning
        with the script output is included so the LLM can guide the user
        through the fix.
        """
        if skill_name in self.loaded_skill_names:
            return f"Skill '{skill_name}' is already active."

        skill = self._registry.load_skill(skill_name)
        if not skill:
            return f"Error: skill '{skill_name}' not found in catalog."

        # ── Pre-activation environment check ─────────────────────────────────
        setup_warning = ""
        check_script = os.path.join(skill.metadata.path, "check_setup.sh")
        if os.path.isfile(check_script):
            import subprocess
            from .tools import _venv_env
            try:
                proc = subprocess.run(
                    ["bash", check_script],
                    capture_output=True, text=True, timeout=15,
                    env=_venv_env(),
                )
                if proc.returncode != 0:
                    output = (proc.stdout + proc.stderr).strip()
                    setup_warning = (
                        f"\n\n⚠️ **SETUP CHECK FAILED** (exit code {proc.returncode}):\n"
                        f"```\n{output}\n```\n"
                        f"Please tell the user what went wrong and how to fix it "
                        f"before attempting to use this skill's commands.\n"
                    )
                    if self.verbose:
                        logger.debug("Skill '%s' setup check FAILED: %s", skill_name, output)
                else:
                    setup_info = proc.stdout.strip()
                    setup_warning = f"\n\n✅ Setup check passed:\n```\n{setup_info}\n```\n"
                    if self.verbose:
                        logger.debug("Skill '%s' setup check passed.", skill_name)
            except Exception as exc:
                setup_warning = f"\n\n⚠️ Setup check could not run: {exc}\n"

        resources = self._registry.list_resources(skill_name)
        resource_hint = ""
        if resources:
            resource_hint = (
                "\n\n**Bundled resources** (use `read_file` / `run_command` to access):\n"
                + "\n".join(f"  - `{skill.metadata.path}/{r}`" for r in resources)
            )

        injection = (
            f"\n[SKILL ACTIVATED: {skill.name}]\n"
            f"Path: {skill.metadata.path}\n\n"
            f"{skill.instructions}{resource_hint}{setup_warning}\n"
        )
        self.pending_injections.append(injection)
        self.loaded_skill_names.add(skill_name)
        if self.verbose:
            logger.debug("Skill activated: %s (Level 2 loaded)", skill_name)

        status = "activated"
        if "FAILED" in setup_warning:
            status = "activated with setup warnings — tell the user how to fix"
        return (
            f"Skill '{skill_name}' {status}. "
            f"Instructions loaded into context. "
            f"Bundled resources: {resources or 'none'}."
        )

    # ── History management ────────────────────────────────────────────────────

    def _get_pruned_messages(self) -> list[dict]:
        """
        Build a context window for the API call:
          - All system messages (system prompt + skill injections + compaction summaries)
          - The most recent `max_chat_history` non-system messages

        Ensures the window never starts with an orphaned tool result.
        """
        system_msgs = [m for m in self.messages if m.get("role") == "system"]
        chat_msgs   = [m for m in self.messages if m.get("role") != "system"]

        if len(chat_msgs) > self.max_chat_history:
            chat_msgs = chat_msgs[-self.max_chat_history:]
            while chat_msgs and chat_msgs[0].get("role") == "tool":
                chat_msgs.pop(0)

        return system_msgs + chat_msgs

    # ── Compaction ────────────────────────────────────────────────────────────

    def compact(self, instruction: str | None = None) -> str:
        """
        Manually compact conversation history.

        Summarises older messages into a single [Compaction Summary] system
        entry, flushes important facts to long-term memory, and persists the
        summary to context/compaction/history.jsonl.

        Parameters
        ----------
        instruction : optional focus hint, e.g. "focus on open tasks"
        """
        chat_msgs = [m for m in self.messages if m.get("role") != "system"]
        if len(chat_msgs) <= self.compaction_recent_keep:
            return (
                f"Nothing to compact yet — only {len(chat_msgs)} message(s) in history "
                f"(threshold: {self.compaction_recent_keep})."
            )
        try:
            new_messages, summary = _do_compact(
                messages=self.messages,
                provider=self.provider,
                memory=self.memory,
                recent_keep=self.compaction_recent_keep,
                instruction=instruction,
            )
        except Exception as exc:
            return f"Compaction failed: {exc}"

        self.messages = new_messages
        self.compaction_count += 1

        lines = summary.splitlines()
        preview = "\n".join(lines[:5])
        if len(lines) > 5:
            preview += f"\n... ({len(lines) - 5} more lines)"
        return f"Compaction #{self.compaction_count} complete.\n\nSummary:\n{preview}"

    def _maybe_auto_compact(self) -> bool:
        """Auto-compact if the estimated token count exceeds the threshold."""
        if not self.auto_compaction:
            return False
        if estimate_tokens(self.messages) < self.compaction_threshold:
            return False
        if self.verbose:
            logger.debug("Auto-compaction triggered.")
        try:
            new_messages, _ = _do_compact(
                messages=self.messages,
                provider=self.provider,
                memory=self.memory,
                recent_keep=self.compaction_recent_keep,
            )
            self.messages = new_messages
            self.compaction_count += 1
            return True
        except Exception as exc:
            if self.verbose:
                logger.debug("Auto-compaction failed (non-fatal): %s", exc)
            return False

    # ── Session management ─────────────────────────────────────────────────

    def clear_history(self) -> None:
        """Clear conversation history but keep the agent intact.

        Preserves loaded skills, memory, RAG, provider, and all config.
        Only resets messages to a fresh system prompt and clears
        conversation-specific state.
        """
        self.messages.clear()
        self.loaded_skill_names.clear()
        self.compaction_count = 0
        self._init_system_prompt()

    # ── Main chat loop ────────────────────────────────────────────────────────

    def chat(self, user_input: str) -> str:
        """
        Send *user_input* to the LLM and return the final text response.

        Runs the standard tool-use loop:
          1. Build context window (auto-compact if needed)
          2. Call LLM
          3. If the model requests tool calls → execute → repeat
          4. When the model replies with text → return it
        """
        self.messages.append({"role": "user", "content": user_input})

        _log_detail({"event": "user_input", "content": user_input})

        current_tools = self._build_tools()
        tool_rounds = 0
        chat_start = time.monotonic()

        while True:
            try:
                self._maybe_auto_compact()
                messages_to_send = self._get_pruned_messages()

                if self.show_full_context:
                    logger.debug(
                        "Context window (%d messages):\n%s",
                        len(messages_to_send),
                        json.dumps(messages_to_send, indent=2, ensure_ascii=False),
                    )

                response = self.provider.chat(
                    messages=messages_to_send,
                    tools=current_tools,
                    tool_choice="auto",
                )
                message = response.choices[0].message

                if not message.tool_calls:
                    self.messages.append(message.model_dump())
                    _log_detail({
                        "event": "response",
                        "tool_rounds": tool_rounds,
                        "elapsed_ms": int((time.monotonic() - chat_start) * 1000),
                        "response_len": len(message.content or ""),
                    })
                    return message.content

                tool_rounds += 1
                if tool_rounds > self.MAX_TOOL_ROUNDS:
                    self.messages.append(message.model_dump())
                    limit_msg = (
                        f"Reached the maximum of {self.MAX_TOOL_ROUNDS} tool-call rounds. "
                        "Please provide a final answer with the information gathered so far."
                    )
                    self.messages.append({"role": "system", "content": limit_msg})
                    if self.verbose:
                        logger.debug("Tool round limit (%d) reached, forcing text reply.", self.MAX_TOOL_ROUNDS)
                    # One more LLM call with tool_choice="none" to force a text reply
                    try:
                        final = self.provider.chat(
                            messages=self._get_pruned_messages(),
                            tools=current_tools,
                            tool_choice="none",
                        )
                        final_msg = final.choices[0].message
                        self.messages.append(final_msg.model_dump())
                        return final_msg.content
                    except Exception as exc:
                        return f"Error (after hitting tool limit): {exc}"

                self.messages.append(message.model_dump())
                self.pending_injections = []

                tool_calls = message.tool_calls
                _log_detail({
                    "event": "tool_calls",
                    "round": tool_rounds,
                    "calls": [
                        {"name": tc.function.name, "args": tc.function.arguments}
                        for tc in tool_calls
                    ],
                })

                if len(tool_calls) == 1:
                    t0 = time.monotonic()
                    result = self._execute_tool_call(tool_calls[0])
                    _log_detail({
                        "event": "tool_result",
                        "round": tool_rounds,
                        "name": tool_calls[0].function.name,
                        "elapsed_ms": int((time.monotonic() - t0) * 1000),
                        "result_len": len(result),
                    })
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_calls[0].id,
                        "content": result,
                    })
                else:
                    t0 = time.monotonic()
                    results: dict[str, str] = {}
                    with ThreadPoolExecutor(max_workers=min(len(tool_calls), 8)) as pool:
                        futures = {
                            pool.submit(self._execute_tool_call, tc): tc
                            for tc in tool_calls
                        }
                        for future in as_completed(futures):
                            tc = futures[future]
                            try:
                                results[tc.id] = future.result()
                            except Exception as exc:
                                results[tc.id] = f"Error: {exc}"
                    _log_detail({
                        "event": "tool_results_parallel",
                        "round": tool_rounds,
                        "count": len(tool_calls),
                        "elapsed_ms": int((time.monotonic() - t0) * 1000),
                        "tools": [tc.function.name for tc in tool_calls],
                    })
                    for tc in tool_calls:
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": results[tc.id],
                        })

                for injection in self.pending_injections:
                    self.messages.append({"role": "system", "content": injection})
                self.pending_injections = []

            except Exception as exc:
                logger.exception("Critical error in Agent.chat()")
                return f"Error: {exc}"
