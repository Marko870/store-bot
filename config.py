"""
⚙️ إعدادات البوت - Bot Configuration
"""

import os

class Config:
    # ——— بيانات البوت ———
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")      # يُقرأ من Railway Variables

    ADMIN_IDS = [565781136]                      # ← غيّر هذا لمعرفك من @userinfobot

    # ——— عنوان USDT للدفع ———
    USDT_ADDRESS = "0xd29c0f1d945a650b0c8158396682c56f586af13e"   # ← ضع عنوان محفظتك هنا
    USDT_NETWORK = "Beb20"

    # ——— إعدادات عامة ———
    SUPPORT_USERNAME = "@@ARTIZILLO"
    BOT_NAME = "Nova Plus"
