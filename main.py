"""
🚀 نقطة الإطلاق - Main Entry Point (بدون Cryptomus)
"""

import asyncio
import logging
from telegram.ext import Application
from config import Config
from handlers import register_handlers
from database import Database

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
cfg = Config()
db  = Database()


async def send_expiry_reminders(app):
    for sub in db.get_expiring_soon(days=3):
        try:
            await app.bot.send_message(
                chat_id=sub["user_id"],
                text=(
                    f"⚠️ *اشتراكك سينتهي خلال 3 أيام!*\n"
                    f"📦 {sub['plan_name']}\n"
                    f"📅 {sub['expires_at'][:10]}\n\n"
                    f"اضغط /start للتجديد ♻️"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Reminder failed {sub['user_id']}: {e}")


async def main():
    logger.info("🚀 Starting bot...")
    app = Application.builder().token(cfg.BOT_TOKEN).build()
    register_handlers(app)

    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        logger.info("✅ Bot is running! Press Ctrl+C to stop.")
        while True:
            await asyncio.sleep(43200)          # كل 12 ساعة
            await send_expiry_reminders(app)


if __name__ == "__main__":
    asyncio.run(main())
