"""Telegram Bot – direct interface for sending commands and receiving status."""

from __future__ import annotations

import logging
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config.settings import settings
from core.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


def _authorised(update: Update) -> bool:
    if not settings.telegram_allowed_user_ids:
        return True  # no whitelist → allow all
    user = update.effective_user
    return user is not None and user.id in settings.telegram_allowed_user_ids


class TelegramBot:
    """Wraps python-telegram-bot with commands to drive the Orchestrator."""

    def __init__(self, orchestrator: Orchestrator) -> None:
        self.orch = orchestrator
        self.app: Application | None = None

    async def start(self) -> None:
        if not settings.telegram_bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not set – Telegram bot disabled")
            return

        self.app = (
            Application.builder()
            .token(settings.telegram_bot_token)
            .build()
        )

        # Register handlers
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(CommandHandler("profiles", self._cmd_profiles))
        self.app.add_handler(CommandHandler("templates", self._cmd_templates))
        self.app.add_handler(CommandHandler("run", self._cmd_run))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("stop", self._cmd_stop))
        self.app.add_handler(CallbackQueryHandler(self._cb_platform, pattern="^platform:"))
        self.app.add_handler(CallbackQueryHandler(self._cb_task, pattern="^task:"))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._msg_custom))

        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        logger.info("Telegram bot started")

    async def stop(self) -> None:
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()

    # ── command handlers ─────────────────────────────────────────────

    async def _cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorised(update):
            return
        await update.message.reply_text(
            "🤖 *IXBrowser Automation Bot*\n\n"
            "Commands:\n"
            "/profiles – List profiles\n"
            "/templates – List task templates\n"
            "/run – Start automation\n"
            "/status <batch_id> – Check status\n"
            "/stop <batch_id> – Cancel batch\n"
            "/help – Show this message",
            parse_mode="Markdown",
        )

    async def _cmd_help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        await self._cmd_start(update, ctx)

    async def _cmd_profiles(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorised(update):
            return
        profiles = await self.orch.profiles.list_profiles(limit=20)
        if not profiles:
            await update.message.reply_text("No profiles found.")
            return
        lines = [f"• `{p.profile_id}` — {p.name}" for p in profiles[:20]]
        total_text = f"Showing {len(lines)} profiles"
        if self.orch.profiles._client.total:
            total_text += f" of {self.orch.profiles._client.total}"
        await update.message.reply_text(
            f"📋 *Profiles* ({total_text}):\n" + "\n".join(lines),
            parse_mode="Markdown",
        )

    async def _cmd_templates(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorised(update):
            return
        lines = []
        for plat in self.orch.registry.platforms:
            tasks = self.orch.registry.task_types(plat)
            lines.append(f"*{plat}*: {', '.join(tasks)}")
        await update.message.reply_text(
            "📝 *Task Templates*:\n" + "\n".join(lines),
            parse_mode="Markdown",
        )

    async def _cmd_run(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Interactive task builder: /run  or  /run <platform> <task> [params]."""
        if not _authorised(update):
            return

        args = ctx.args or []

        # Quick mode: /run x post_tweet content="Hello World"
        if len(args) >= 2:
            platform = args[0]
            task_type = args[1]
            params = _parse_kv_args(args[2:])
            result = await self.orch.execute(
                platform=platform, task_type=task_type, params=params
            )
            if "error" in result:
                await update.message.reply_text(f"❌ {result['error']}")
            else:
                await update.message.reply_text(
                    f"✅ Batch `{result['batch_id']}` created\n"
                    f"Tasks: {result['count']}\n"
                    f"Use /status {result['batch_id']} to monitor",
                    parse_mode="Markdown",
                )
            return

        # Interactive mode: show platform picker
        keyboard = [
            [InlineKeyboardButton(p.upper(), callback_data=f"platform:{p}")]
            for p in self.orch.registry.platforms
        ]
        await update.message.reply_text(
            "Select a platform:", reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorised(update):
            return
        args = ctx.args or []
        if not args:
            # Show overview
            tasks = self.orch.queue.get_all_tasks()
            pending = sum(1 for t in tasks if t.status.value == "pending")
            running = sum(1 for t in tasks if t.status.value == "running")
            done = sum(1 for t in tasks if t.status.value == "done")
            failed = sum(1 for t in tasks if t.status.value == "failed")
            await update.message.reply_text(
                f"📊 *Queue Status*\n"
                f"Pending: {pending}\nRunning: {running}\n"
                f"Done: {done}\nFailed: {failed}\nTotal: {len(tasks)}",
                parse_mode="Markdown",
            )
            return

        batch_id = args[0]
        status = self.orch.batch_status(batch_id)
        if status is None:
            await update.message.reply_text(f"Batch `{batch_id}` not found.", parse_mode="Markdown")
            return

        await update.message.reply_text(
            f"📊 *Batch {batch_id}*\n"
            f"Total: {status['total']}\n"
            f"✅ Done: {status.get('done', 0)}  "
            f"🔄 Running: {status.get('running', 0)}  "
            f"⏳ Pending: {status.get('pending', 0)}  "
            f"❌ Failed: {status.get('failed', 0)}",
            parse_mode="Markdown",
        )

    async def _cmd_stop(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorised(update):
            return
        args = ctx.args or []
        if not args:
            await update.message.reply_text("Usage: /stop <batch_id>")
            return
        batch_id = args[0]
        status = self.orch.batch_status(batch_id)
        if status is None:
            await update.message.reply_text("Batch not found.")
            return
        cancelled = 0
        for t in status.get("tasks", []):
            if self.orch.queue.cancel_task(t["id"]):
                cancelled += 1
        await update.message.reply_text(f"Cancelled {cancelled} pending tasks in batch {batch_id}.")

    # ── callback query handlers ──────────────────────────────────────

    async def _cb_platform(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        platform = query.data.split(":", 1)[1]
        ctx.user_data["platform"] = platform

        tasks = self.orch.registry.task_types(platform)
        keyboard = [
            [InlineKeyboardButton(t, callback_data=f"task:{platform}:{t}")]
            for t in tasks
        ]
        await query.edit_message_text(
            f"Platform: *{platform}*\nSelect task:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    async def _cb_task(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        _, platform, task_type = query.data.split(":", 2)

        if task_type in ("custom", "post_tweet", "post_status", "reply", "comment"):
            ctx.user_data["pending_task"] = (platform, task_type)
            await query.edit_message_text(
                f"Send me the text content for *{platform}/{task_type}*:",
                parse_mode="Markdown",
            )
            return

        # Execute immediately (no extra params needed)
        result = await self.orch.execute(platform=platform, task_type=task_type)
        if "error" in result:
            await query.edit_message_text(f"❌ {result['error']}")
        else:
            await query.edit_message_text(
                f"✅ Batch `{result['batch_id']}` — {result['count']} tasks enqueued",
                parse_mode="Markdown",
            )

    # ── free-text message handler ────────────────────────────────────

    async def _msg_custom(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorised(update):
            return
        pending = ctx.user_data.get("pending_task")
        if not pending:
            return

        platform, task_type = pending
        ctx.user_data.pop("pending_task", None)
        content = update.message.text.strip()

        params: dict[str, str] = {}
        if task_type == "custom":
            params["instruction"] = content
        else:
            params["content"] = content

        result = await self.orch.execute(
            platform=platform, task_type=task_type, params=params
        )
        if "error" in result:
            await update.message.reply_text(f"❌ {result['error']}")
        else:
            await update.message.reply_text(
                f"✅ Batch `{result['batch_id']}` — {result['count']} tasks\n"
                f"/status {result['batch_id']}",
                parse_mode="Markdown",
            )


# ── helpers ──────────────────────────────────────────────────────────

def _parse_kv_args(args: list[str]) -> dict[str, str]:
    """Parse key=value pairs from command arguments."""
    params: dict[str, str] = {}
    for arg in args:
        if "=" in arg:
            k, v = arg.split("=", 1)
            params[k.strip()] = v.strip().strip('"').strip("'")
    return params
