"""
Daemon server for PythonClaw — multi-channel mode.

Supports Telegram and Discord channels, individually or combined.

Architecture
------------
                    +----------------------------------------+
                    |          SessionManager                 |
                    |  "{channel}:{id}" → Agent               |
                    |  "cron:{job_id}"  → Agent               |
                    |  (Markdown-backed via SessionStore)      |
                    +----------------------------------------+
                               |
          +--------------------+--------------------+
          |                    |                    |
    TelegramBot          CronScheduler       HeartbeatMonitor
    DiscordBot           static + dynamic
                         jobs
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal

from .core.llm.base import LLMProvider
from .core.persistent_agent import PersistentAgent
from .core.session_store import SessionStore
from .scheduler.cron import CronScheduler
from .scheduler.heartbeat import create_heartbeat
from .session_manager import SessionManager

logger = logging.getLogger(__name__)


async def run_server(
    provider: LLMProvider,
    channels: list[str] | None = None,
) -> None:
    """
    Main entry point for daemon mode.

    Parameters
    ----------
    provider  : the LLM provider to use
    channels  : list of channels to start, e.g. ["telegram", "discord"].
                Defaults to ["telegram"] for backward compatibility.
    """
    if channels is None:
        channels = ["telegram"]

    # ── 1. Session store (Markdown persistence) ───────────────────────────────
    store = SessionStore()
    logger.info("[Server] SessionStore initialised at '%s'", store.base_dir)

    # ── 2. SessionManager (placeholder factory, updated below) ────────────────
    session_manager = SessionManager(agent_factory=lambda sid: None, store=store)

    # ── 3. CronScheduler ─────────────────────────────────────────────────────
    jobs_path = os.path.join("context", "cron", "jobs.yaml")
    scheduler = CronScheduler(
        session_manager=session_manager,
        jobs_path=jobs_path,
    )

    # ── 4. Real agent factory ─────────────────────────────────────────────────
    def agent_factory(session_id: str) -> PersistentAgent:
        return PersistentAgent(
            provider=provider,
            store=store,
            session_id=session_id,
            cron_manager=scheduler,
            verbose=False,
        )

    session_manager.set_factory(agent_factory)

    # ── 5. Start channels ─────────────────────────────────────────────────────
    active_bots: list = []

    if "telegram" in channels:
        try:
            from .channels.telegram_bot import create_bot_from_env
            bot = create_bot_from_env(session_manager)
            scheduler._telegram_bot = bot
            await bot.start_async()
            active_bots.append(bot)
            logger.info("[Server] Telegram bot started.")
        except (ValueError, ImportError) as exc:
            logger.warning("[Server] Telegram skipped: %s", exc)

    if "discord" in channels:
        try:
            from .channels.discord_bot import create_bot_from_env as create_discord
            discord_bot = create_discord(session_manager)
            asyncio.create_task(discord_bot.start_async())
            active_bots.append(discord_bot)
            logger.info("[Server] Discord bot started.")
        except (ValueError, ImportError) as exc:
            logger.warning("[Server] Discord skipped: %s", exc)

    if not active_bots:
        logger.error("[Server] No channels started. Check your pythonclaw.json configuration.")
        return

    # ── 6. Start scheduler ────────────────────────────────────────────────────
    scheduler.start()

    # ── 7. Heartbeat monitor ──────────────────────────────────────────────────
    telegram_bot = next((b for b in active_bots if hasattr(b, '_app')), None)
    heartbeat = create_heartbeat(provider=provider, telegram_bot=telegram_bot)
    await heartbeat.start()

    logger.info("[Server] All subsystems running (%s). Press Ctrl-C to stop.",
                ", ".join(channels))

    # ── Graceful shutdown ─────────────────────────────────────────────────────
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("[Server] Shutdown signal received.")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except (NotImplementedError, OSError):
            pass

    try:
        await stop_event.wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        logger.info("[Server] Shutting down subsystems...")
        await heartbeat.stop()
        scheduler.stop()
        for bot in active_bots:
            if hasattr(bot, 'stop_async'):
                await bot.stop_async()
        logger.info("[Server] Shutdown complete.")
