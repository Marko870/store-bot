"""
🚀 نقطة الإطلاق - Main
"""
import asyncio
import logging
from datetime import datetime
from telegram import BotCommand, BotCommandScopeChat, BotCommandScopeDefault
from telegram.ext import Application
from config import Config
from handlers import register_handlers
from database import Database

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
cfg = Config()
db  = Database()


async def set_commands(app: Application):
    user_cmds = [
        BotCommand("start",   "🏠 القائمة الرئيسية"),
        BotCommand("admin",   "⚙️ لوحة الإدارة"),
    ]
    await app.bot.set_my_commands(user_cmds, scope=BotCommandScopeDefault())
    admin_cmds = user_cmds
    for aid in cfg.ADMIN_IDS:
        try:
            await app.bot.set_my_commands(admin_cmds, scope=BotCommandScopeChat(chat_id=aid))
        except Exception as e:
            logger.warning(f"Could not set admin commands: {e}")
    logger.info("✅ Commands set")


async def send_reminders(app: Application):
    """إرسال تذكيرات انتهاء الاشتراك"""
    from i18n import t
    now = datetime.now()

    for days, key in [(7, "expiry_7d"), (3, "expiry_3d"), (1, "expiry_1d")]:
        for sub in db.get_expiring_soon(days=days):
            # تحقق إن التذكير لم يُرسل اليوم
            try:
                await app.bot.send_message(
                    chat_id=sub["user_id"],
                    text=t(key, "ar", service=sub["service_ar"]),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.warning(f"Reminder failed for {sub['user_id']}: {e}")


async def main():
    logger.info("🚀 Starting Nova Plus Bot...")
    app = Application.builder().token(cfg.BOT_TOKEN).build()
    register_handlers(app)

    async with app:
        await app.start()
        await set_commands(app)
        await app.updater.start_polling(drop_pending_updates=True)
        logger.info("✅ Bot is running!")

        reminder_interval = 6 * 3600  # كل 6 ساعات
        while True:
            await asyncio.sleep(reminder_interval)
            await send_reminders(app)


if __name__ == "__main__":
    asyncio.run(main())
