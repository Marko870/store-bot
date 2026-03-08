"""
⚙️ إعدادات البوت - Bot Configuration
"""

import os

class Config:
    # ——— بيانات البوت ———
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")      # يُقرأ من Railway Variables

    ADMIN_IDS = [123456789]                      # ← غيّر هذا لمعرفك من @userinfobot

    # ——— عنوان USDT للدفع ———
    USDT_ADDRESS = "YOUR_USDT_TRC20_ADDRESS_HERE"   # ← ضع عنوان محفظتك هنا
    USDT_NETWORK = "TRC20"

    # ——— إعدادات عامة ———
    SUPPORT_USERNAME = "@YourSupportUsername"
    BOT_NAME = "🛍️ متجر الخدمات الرقمية"
