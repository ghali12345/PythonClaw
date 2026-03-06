"""
Telegram channel for pythonclaw.

Telegram is purely a *channel* — it handles sending and receiving messages.
Session lifecycle (which Agent handles which chat) is delegated to the
SessionManager, which is shared across all channels and the cron scheduler.

Session IDs used by this channel: "telegram:{chat_id}"

Commands
--------
  /start          — greeting + usage hint
  /reset          — discard and recreate the current session
  /status         — show session info (provider, skills, memory, tokens, compactions)
  /compact [hint] — compact conversation history
  <text>          — forwarded to Agent.chat(), reply sent back
  <photo>         — image sent to LLM with optional caption

Access control
--------------
Set TELEGRAM_ALLOWED_USERS to a comma-separated list of integer Telegram user
IDs to restrict access.  Leave empty (or unset) to allow all users.

Group behaviour
---------------
Set ``channels.telegram.requireMention`` to ``true`` in pythonclaw.json to
require @bot mention in group chats.  DMs always respond.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import TYPE_CHECKING

from telegram import BotCommand, ReactionTypeEmoji, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .. import config

if TYPE_CHECKING:
    from ..session_manager import SessionManager

logger = logging.getLogger(__name__)


class TelegramBot:
    """
    Telegram channel — pure I/O layer.

    Receives messages from Telegram and routes them to the appropriate Agent
    via the shared SessionManager.  Does not own or manage Agent instances.
    """

    def __init__(
        self,
        session_manager: "SessionManager",
        token: str,
        allowed_users: list[int] | None = None,
        require_mention: bool = False,
    ) -> None:
        self._sm = session_manager
        self._token = token
        self._allowed_users: set[int] = set(allowed_users) if allowed_users else set()
        self._require_mention = require_mention
        self._app: Application | None = None
        self._bot_username: str | None = None

    # ── Session ID convention ─────────────────────────────────────────────────

    @staticmethod
    def _session_id(chat_id: int) -> str:
        return f"telegram:{chat_id}"

    # ── Push message (called by cron / heartbeat) ─────────────────────────────

    async def send_message(self, chat_id: int, text: str) -> None:
        """Send a message to a specific chat (used by cron/heartbeat)."""
        if self._app is None:
            logger.warning("[Telegram] send_message called before bot is running")
            return
        await self._app.bot.send_message(chat_id=chat_id, text=text)

    # ── Access control ────────────────────────────────────────────────────────

    def _is_allowed(self, user_id: int) -> bool:
        if not self._allowed_users:
            return True
        return user_id in self._allowed_users

    async def _check_access(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        user = update.effective_user
        if user is None or not self._is_allowed(user.id):
            logger.warning("[Telegram] Rejected user_id=%s", user.id if user else "unknown")
            await update.message.reply_text("Sorry, you are not authorised to use this bot.")
            return False
        return True

    def _is_group(self, update: Update) -> bool:
        """Return True if the message is from a group/supergroup."""
        return update.effective_chat.type in ("group", "supergroup")

    def _is_mentioned(self, update: Update) -> bool:
        """Check if the bot is @mentioned in the message text."""
        text = update.message.text or update.message.caption or ""
        if self._bot_username and f"@{self._bot_username}" in text:
            return True
        entities = update.message.entities or update.message.caption_entities or []
        for ent in entities:
            if ent.type == "mention" and self._bot_username:
                mention = text[ent.offset:ent.offset + ent.length]
                if mention.lower() == f"@{self._bot_username.lower()}":
                    return True
        return False

    def _strip_mention(self, text: str) -> str:
        """Remove the @bot mention from message text."""
        if self._bot_username:
            text = text.replace(f"@{self._bot_username}", "").strip()
        return text

    # ── Command handlers ──────────────────────────────────────────────────────

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._check_access(update, context):
            return
        sid = self._session_id(update.effective_chat.id)
        self._sm.get_or_create(sid)
        await update.message.reply_text(
            "\U0001f44b Hi! I'm your PythonClaw agent.\n\n"
            "Just send me a message and I'll do my best to help.\n"
            "You can also send photos and I'll analyze them.\n\n"
            "Commands:\n"
            "  /start          \u2014 show this message\n"
            "  /reset          \u2014 start a fresh session\n"
            "  /status         \u2014 show session info\n"
            "  /compact [hint] \u2014 compact conversation history"
        )

    async def _cmd_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._check_access(update, context):
            return
        sid = self._session_id(update.effective_chat.id)
        self._sm.reset(sid)
        await update.message.reply_text("Session reset. Starting fresh! Send me a message.")

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._check_access(update, context):
            return
        sid = self._session_id(update.effective_chat.id)
        agent = self._sm.get_or_create(sid)
        from ..core.compaction import estimate_tokens
        await update.message.reply_text(
            f"\U0001f4ca Session Status\n"
            f"  Session ID   : {sid}\n"
            f"  Provider     : {type(agent.provider).__name__}\n"
            f"  Skills       : {len(agent.loaded_skill_names)} loaded\n"
            f"  Memories     : {len(agent.memory.list_all())} entries\n"
            f"  History      : {len(agent.messages)} messages\n"
            f"  Est. tokens  : ~{estimate_tokens(agent.messages):,}\n"
            f"  Compactions  : {agent.compaction_count}\n"
            f"  Total sessions: {len(self._sm)}"
        )

    async def _cmd_compact(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._check_access(update, context):
            return
        sid = self._session_id(update.effective_chat.id)
        agent = self._sm.get_or_create(sid)
        hint: str | None = " ".join(context.args).strip() or None if context.args else None
        await update.message.reply_text("\u23f3 Compacting conversation history...")
        try:
            result = agent.compact(instruction=hint)
        except Exception as exc:
            result = f"Compaction failed: {exc}"
        for chunk in _split_message(result):
            await update.message.reply_text(chunk)

    # ── Message handler (text + photos) ───────────────────────────────────────

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._check_access(update, context):
            return

        if self._is_group(update) and self._require_mention:
            if not self._is_mentioned(update):
                return

        user_text = (update.message.text or update.message.caption or "").strip()
        user_text = self._strip_mention(user_text)

        has_photo = bool(update.message.photo)

        if not user_text and not has_photo:
            return

        sid = self._session_id(update.effective_chat.id)
        agent = self._sm.get_or_create(sid)

        if self._sm.is_locked(sid):
            await update.message.reply_text("\u23f3 Processing previous message\u2026")

        try:
            await update.message.set_reaction([ReactionTypeEmoji("\U0001f440")])
        except Exception:
            pass

        # Build multimodal input if photo is present
        chat_input = user_text or ""
        if has_photo:
            chat_input = await self._build_image_input(
                update, user_text or "What's in this image?"
            )

        typing_task = asyncio.create_task(
            self._keep_typing(update.message.chat_id)
        )
        try:
            async with self._sm.acquire(sid):
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, agent.chat, chat_input)
        except Exception as exc:
            logger.exception("[Telegram] Agent.chat() raised an exception")
            response = f"Sorry, something went wrong: {exc}"
        finally:
            typing_task.cancel()

        try:
            await update.message.set_reaction([])
        except Exception:
            pass

        for chunk in _split_message(response or "(no response)"):
            await update.message.reply_text(chunk)

    async def _build_image_input(self, update: Update, caption: str) -> list:
        """Download photo and build a multimodal content array."""
        photo = update.message.photo[-1]  # highest resolution
        file = await photo.get_file()
        data = await file.download_as_bytearray()
        b64 = base64.b64encode(bytes(data)).decode()

        return [
            {"type": "text", "text": caption},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{b64}",
                },
            },
        ]

    async def _keep_typing(self, chat_id: int) -> None:
        """Re-send the 'typing' chat action every 4 s until cancelled."""
        try:
            while True:
                await self._app.bot.send_chat_action(chat_id=chat_id, action="typing")
                await asyncio.sleep(4)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.debug("[Telegram] _keep_typing stopped unexpectedly", exc_info=True)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    _BOT_COMMANDS = [
        BotCommand("start", "Show welcome message"),
        BotCommand("reset", "Start a fresh session"),
        BotCommand("status", "Show session info"),
        BotCommand("compact", "Compact conversation history"),
    ]

    def build_application(self) -> Application:
        app = Application.builder().token(self._token).build()
        app.add_handler(CommandHandler("start", self._cmd_start))
        app.add_handler(CommandHandler("reset", self._cmd_reset))
        app.add_handler(CommandHandler("status", self._cmd_status))
        app.add_handler(CommandHandler("compact", self._cmd_compact))
        app.add_handler(MessageHandler(
            (filters.TEXT | filters.PHOTO) & ~filters.COMMAND,
            self._handle_message,
        ))
        self._app = app
        return app

    async def _register_commands(self) -> None:
        """Register slash-commands with Telegram so they appear in the menu."""
        try:
            await self._app.bot.set_my_commands(self._BOT_COMMANDS)
            me = await self._app.bot.get_me()
            self._bot_username = me.username
            logger.info(
                "[Telegram] Registered %d bot commands, username=@%s",
                len(self._BOT_COMMANDS), self._bot_username,
            )
        except Exception:
            logger.warning("[Telegram] Failed to register bot commands", exc_info=True)

    def run_polling(self) -> None:
        """Blocking call — starts the bot using long polling (for standalone use)."""
        app = self.build_application()
        logger.info("[Telegram] Starting bot (polling mode)...")
        app.post_init = lambda _app: self._register_commands()
        app.run_polling(drop_pending_updates=True)

    async def start_async(self) -> None:
        """Non-blocking start — for use inside an existing asyncio event loop."""
        app = self.build_application()
        logger.info("[Telegram] Initialising bot (async mode)...")
        await app.initialize()
        await app.start()
        await self._register_commands()
        await app.updater.start_polling(drop_pending_updates=True)

    async def stop_async(self) -> None:
        if self._app is None:
            return
        logger.info("[Telegram] Stopping bot...")
        await self._app.updater.stop()
        await self._app.stop()
        await self._app.shutdown()


# ── Utility ───────────────────────────────────────────────────────────────────

def _split_message(text: str, limit: int = 4096) -> list[str]:
    """Split a long string into chunks that fit within Telegram's message limit."""
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:limit])
        text = text[limit:]
    return chunks


def create_bot(session_manager: "SessionManager") -> TelegramBot:
    """Create a TelegramBot from pythonclaw.json / env vars."""
    token = config.get_str(
        "channels", "telegram", "token", env="TELEGRAM_BOT_TOKEN",
    )
    if not token:
        raise ValueError("Telegram token not set (env TELEGRAM_BOT_TOKEN or channels.telegram.token)")
    allowed_users = config.get_int_list(
        "channels", "telegram", "allowedUsers", env="TELEGRAM_ALLOWED_USERS",
    )
    require_mention = config.get_bool(
        "channels", "telegram", "requireMention", default=False,
    )
    return TelegramBot(
        session_manager=session_manager,
        token=token,
        allowed_users=allowed_users or None,
        require_mention=require_mention,
    )


# Backward-compatible alias
create_bot_from_env = create_bot
