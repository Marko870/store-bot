"""
🚀 نقطة الإطلاق - Main
"""
import asyncio
import logging
import traceback
from datetime import datetime
from telegram import BotCommand, BotCommandScopeChat, BotCommandScopeDefault, Update
from telegram.ext import Application, ContextTypes
from config import Config
from handlers import register_handlers
from database import Database
from bot_logger import bot_log, error_log, log_error

cfg = Config()
db  = Database()

# ── إعداد الـ root logger ──────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
    handlers=[logging.StreamHandler()]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    if "not modified" in str(error).lower():
        return

    uid = None
    if isinstance(update, Update) and update.effective_user:
        uid = update.effective_user.id
    log_error("unhandled_exception", error, uid=uid)

    tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    tb_short = "\n".join(tb.strip().split("\n")[-4:])

    user_info = ""
    if isinstance(update, Update) and update.effective_user:
        u = update.effective_user
        user_info = f"\n👤 uid=`{u.id}` @{u.username or '—'}"

    msg = (
        f"⚠️ *خطأ في البوت*{user_info}\n\n"
        f"`{type(error).__name__}: {str(error)[:200]}`\n\n"
        f"```\n{tb_short}\n```"
    )
    for admin_id in cfg.ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=msg, parse_mode="Markdown")
        except Exception as e:
            error_log.error(f"Failed to notify admin {admin_id}: {e}")


async def set_commands(app: Application):
    user_cmds = [
        BotCommand("start", "🏠 القائمة الرئيسية"),
        BotCommand("admin", "⚙️ لوحة الإدارة"),
    ]
    await app.bot.set_my_commands(user_cmds, scope=BotCommandScopeDefault())
    for aid in cfg.ADMIN_IDS:
        try:
            await app.bot.set_my_commands(user_cmds, scope=BotCommandScopeChat(chat_id=aid))
        except Exception as e:
            bot_log.warning(f"Could not set admin commands for {aid}: {e}")
    bot_log.info("✅ Commands set")


async def send_reminders(app: Application):
    from i18n import t
    sent = failed = 0
    for days, key in [(7, "expiry_7d"), (3, "expiry_3d"), (1, "expiry_1d")]:
        for sub in db.get_expiring_soon(days=days):
            try:
                await app.bot.send_message(
                    chat_id=sub["user_id"],
                    text=t(key, "ar", service=sub["service_ar"]),
                    parse_mode="Markdown"
                )
                sent += 1
            except Exception as e:
                bot_log.warning(f"Reminder failed uid={sub['user_id']}: {e}")
                failed += 1
    if sent or failed:
        bot_log.info(f"REMINDERS | sent={sent} | failed={failed}")


async def main():
    bot_log.info("🚀 Starting Nova Plus Bot...")
    app = Application.builder().token(cfg.BOT_TOKEN).build()
    register_handlers(app)
    app.add_error_handler(error_handler)

    async with app:
        await app.start()
        await set_commands(app)
        await app.updater.start_polling(drop_pending_updates=True)
        bot_log.info("✅ Bot is running!")

        while True:
            await asyncio.sleep(6 * 3600)
            await send_reminders(app)


if __name__ == "__main__":
    asyncio.run(main())
