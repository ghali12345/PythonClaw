"""
Discord channel for PythonClaw.

Session IDs: "discord:{user_id}" (DMs) or "discord:{channel_id}" (guilds)

Commands
--------
  !reset          — discard and recreate the current session
  !status         — show session info
  !compact [hint] — compact conversation history
  <text>          — forwarded to Agent.chat(), reply sent back

The bot responds to:
  - Direct messages (always)
  - Channel mentions (@bot message) in guilds
  - Optionally all messages in whitelisted channels

Access control
--------------
Set DISCORD_ALLOWED_USERS to a comma-separated list of Discord user IDs.
Set DISCORD_ALLOWED_CHANNELS to restrict which guild channels the bot listens in.
Leave empty to allow all.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from .. import config

if TYPE_CHECKING:
    from ..session_manager import SessionManager

logger = logging.getLogger(__name__)

MAX_MSG_LEN = 2000  # Discord message character limit


class DiscordBot:
    """
    Discord channel — pure I/O layer.

    Routes messages to the appropriate Agent via the shared SessionManager.
    """

    def __init__(
        self,
        session_manager: "SessionManager",
        token: str,
        allowed_users: list[int] | None = None,
        allowed_channels: list[int] | None = None,
    ) -> None:
        self._sm = session_manager
        self._token = token
        self._allowed_users: set[int] = set(allowed_users) if allowed_users else set()
        self._allowed_channels: set[int] = set(allowed_channels) if allowed_channels else set()

        intents = discord.Intents.default()
        intents.message_content = True
        self._client = discord.Client(intents=intents)
        self._setup_handlers()

    # ── Session ID convention ─────────────────────────────────────────────────

    @staticmethod
    def _session_id(source_id: int, is_dm: bool = False) -> str:
        prefix = "discord:dm" if is_dm else "discord"
        return f"{prefix}:{source_id}"

    # ── Access control ────────────────────────────────────────────────────────

    def _is_allowed_user(self, user_id: int) -> bool:
        if not self._allowed_users:
            return True
        return user_id in self._allowed_users

    def _is_allowed_channel(self, channel_id: int) -> bool:
        if not self._allowed_channels:
            return True
        return channel_id in self._allowed_channels

    # ── Message splitting ─────────────────────────────────────────────────────

    @staticmethod
    def _split_message(text: str, limit: int = MAX_MSG_LEN) -> list[str]:
        if len(text) <= limit:
            return [text]
        chunks = []
        while text:
            chunks.append(text[:limit])
            text = text[limit:]
        return chunks

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _setup_handlers(self) -> None:
        client = self._client

        @client.event
        async def on_ready():
            logger.info("[Discord] Logged in as %s (id=%s)", client.user.name, client.user.id)

        @client.event
        async def on_message(message: discord.Message):
            if message.author == client.user:
                return
            if message.author.bot:
                return

            is_dm = isinstance(message.channel, discord.DMChannel)
            is_mentioned = client.user in message.mentions if not is_dm else False

            # In guilds, only respond to mentions or whitelisted channels
            if not is_dm and not is_mentioned and not self._is_allowed_channel(message.channel.id):
                return

            if not self._is_allowed_user(message.author.id):
                await message.reply("Sorry, you are not authorised to use this bot.")
                return

            content = message.content.strip()
            # Remove bot mention from the beginning
            if is_mentioned and client.user:
                content = content.replace(f"<@{client.user.id}>", "").strip()

            if not content:
                return

            # Command dispatch
            if content.startswith("!reset"):
                await self._cmd_reset(message, is_dm)
                return
            if content.startswith("!status"):
                await self._cmd_status(message, is_dm)
                return
            if content.startswith("!compact"):
                hint = content[len("!compact"):].strip() or None
                await self._cmd_compact(message, is_dm, hint)
                return

            await self._handle_chat(message, content, is_dm)

    # ── Command implementations ───────────────────────────────────────────────

    async def _cmd_reset(self, message: discord.Message, is_dm: bool) -> None:
        sid = self._session_id(message.author.id if is_dm else message.channel.id, is_dm)
        self._sm.reset(sid)
        await message.reply("Session reset. Starting fresh!")

    async def _cmd_status(self, message: discord.Message, is_dm: bool) -> None:
        sid = self._session_id(message.author.id if is_dm else message.channel.id, is_dm)
        agent = self._sm.get_or_create(sid)
        from ..core.compaction import estimate_tokens
        status = (
            f"**Session Status**\n"
            f"```\n"
            f"Session ID   : {sid}\n"
            f"Provider     : {type(agent.provider).__name__}\n"
            f"Skills       : {len(agent.loaded_skill_names)} loaded\n"
            f"Memories     : {len(agent.memory.list_all())} entries\n"
            f"History      : {len(agent.messages)} messages\n"
            f"Est. tokens  : ~{estimate_tokens(agent.messages)}\n"
            f"Compactions  : {agent.compaction_count}\n"
            f"```"
        )
        await message.reply(status)

    async def _cmd_compact(self, message: discord.Message, is_dm: bool, hint: str | None) -> None:
        sid = self._session_id(message.author.id if is_dm else message.channel.id, is_dm)
        agent = self._sm.get_or_create(sid)
        await message.reply("Compacting conversation history...")
        try:
            result = agent.compact(instruction=hint)
        except Exception as exc:
            logger.exception("[Discord] compact() raised an exception")
            result = f"Compaction failed: {exc}"
        for chunk in self._split_message(result or "(no result)"):
            await message.reply(chunk)

    async def _handle_chat(self, message: discord.Message, content: str, is_dm: bool) -> None:
        sid = self._session_id(message.author.id if is_dm else message.channel.id, is_dm)
        agent = self._sm.get_or_create(sid)
        async with message.channel.typing():
            try:
                response = agent.chat(content)
            except Exception as exc:
                logger.exception("[Discord] Agent.chat() raised an exception")
                response = f"Sorry, something went wrong: {exc}"
        for chunk in self._split_message(response or "(no response)"):
            await message.reply(chunk)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start_async(self) -> None:
        """Non-blocking start — for use inside an existing asyncio event loop."""
        logger.info("[Discord] Starting bot (async mode)...")
        await self._client.start(self._token)

    async def stop_async(self) -> None:
        logger.info("[Discord] Stopping bot...")
        await self._client.close()


# ── Utility ───────────────────────────────────────────────────────────────────

def create_bot(session_manager: "SessionManager") -> "DiscordBot":
    """Create a DiscordBot from pythonclaw.json / env vars."""
    token = config.get_str(
        "channels", "discord", "token", env="DISCORD_BOT_TOKEN",
    )
    if not token:
        raise ValueError("Discord token not set (env DISCORD_BOT_TOKEN or channels.discord.token)")
    allowed_users = config.get_int_list(
        "channels", "discord", "allowedUsers", env="DISCORD_ALLOWED_USERS",
    )
    allowed_channels = config.get_int_list(
        "channels", "discord", "allowedChannels", env="DISCORD_ALLOWED_CHANNELS",
    )
    return DiscordBot(
        session_manager=session_manager,
        token=token,
        allowed_users=allowed_users or None,
        allowed_channels=allowed_channels or None,
    )


# Backward-compatible alias
create_bot_from_env = create_bot
