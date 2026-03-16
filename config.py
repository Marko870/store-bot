"""
⚙️ الإعدادات - Config
"""
import os

class Config:
    BOT_TOKEN        = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS        = [565781136]
    DATABASE_URL     = os.getenv("DATABASE_URL", "")
    USDT_ADDRESS     = os.getenv("USDT_ADDRESS", "0xd29c0f1d945a650b0c8158396682c56f586af13e")
    USDT_NETWORK     = os.getenv("USDT_NETWORK", "ERC20")
    SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "@ARTIZILLO")
    BOT_NAME         = "🛍️ Nova Plus"
    MAINTENANCE_MODE = os.getenv("MAINTENANCE_MODE", "false").lower() == "true"
