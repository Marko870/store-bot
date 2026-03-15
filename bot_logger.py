"""
📊 نظام التسجيل - Bot Logger
يوفر loggers منفصلة لكل نوع حدث
"""
import logging
import os
from logging.handlers import RotatingFileHandler

# ── إنشاء مجلد الـ logs ──────────────────────────────
LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# ── صيغة موحدة للرسائل ──────────────────────────────
FORMATTER = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def _make_handler(filename: str, level=logging.DEBUG) -> RotatingFileHandler:
    """ينشئ handler يكتب لملف، وعند وصوله 5MB يعمل rotate ويحتفظ بـ 3 نسخ"""
    path = os.path.join(LOGS_DIR, filename)
    handler = RotatingFileHandler(
        path,
        maxBytes=5 * 1024 * 1024,   # 5 MB
        backupCount=3,
        encoding="utf-8"
    )
    handler.setLevel(level)
    handler.setFormatter(FORMATTER)
    return handler

def _make_console_handler(level=logging.INFO) -> logging.StreamHandler:
    h = logging.StreamHandler()
    h.setLevel(level)
    h.setFormatter(FORMATTER)
    return h

def _build_logger(name: str, filename: str, level=logging.DEBUG) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False   # لا يرسل للـ root logger
    if not logger.handlers:
        logger.addHandler(_make_handler(filename, level))
        logger.addHandler(_make_console_handler(logging.INFO))
    return logger


# ══════════════════════════════════════════════════════
#   الـ Loggers المتاحة — كل ملف يستورد ما يحتاجه
# ══════════════════════════════════════════════════════

# 📋 bot.log — سجل عام: كل شي
bot_log = _build_logger("bot", "bot.log", logging.DEBUG)

# ❌ errors.log — الأخطاء فقط (ERROR + CRITICAL)
error_log = _build_logger("errors", "errors.log", logging.ERROR)

# 🛒 orders.log — كل ما يتعلق بالطلبات والمبيعات
order_log = _build_logger("orders", "orders.log", logging.INFO)

# 👤 users.log — تسجيل دخول + حظر + مستخدمين جدد
user_log = _build_logger("users", "users.log", logging.INFO)


# ══════════════════════════════════════════════════════
#   دوال مساعدة — اكتب بسطر واحد
# ══════════════════════════════════════════════════════

def log_new_user(uid: int, username: str, country: str = ""):
    msg = f"NEW_USER | uid={uid} | @{username or '—'} | country={country or '—'}"
    user_log.info(msg)
    bot_log.info(msg)

def log_banned_attempt(uid: int):
    msg = f"BANNED_ATTEMPT | uid={uid}"
    user_log.warning(msg)
    bot_log.warning(msg)

def log_new_order(uid: int, order_id: int, plan: str, amount: float):
    msg = f"NEW_ORDER | uid={uid} | order=#{order_id} | plan={plan} | amount={amount} USDT"
    order_log.info(msg)
    bot_log.info(msg)

def log_order_approved(order_id: int, admin_id: int, user_id: int):
    msg = f"ORDER_APPROVED | order=#{order_id} | admin={admin_id} | user={user_id}"
    order_log.info(msg)
    bot_log.info(msg)

def log_order_rejected(order_id: int, admin_id: int, user_id: int):
    msg = f"ORDER_REJECTED | order=#{order_id} | admin={admin_id} | user={user_id}"
    order_log.warning(msg)
    bot_log.warning(msg)

def log_payment_proof(uid: int, order_id: int):
    msg = f"PROOF_RECEIVED | uid={uid} | order=#{order_id}"
    order_log.info(msg)
    bot_log.info(msg)

def log_recharge_order(uid: int, order_id: int, amount_syp: float, phone: str):
    msg = f"RECHARGE_ORDER | uid={uid} | order=#{order_id} | amount={amount_syp:,.0f} SYP | phone={phone}"
    order_log.info(msg)
    bot_log.info(msg)

def log_exchange_order(uid: int, order_id: int, op: str, amount_usdt: float, method: str):
    msg = f"EXCHANGE_ORDER | uid={uid} | order=#{order_id} | op={op} | amount={amount_usdt} USDT | method={method}"
    order_log.info(msg)
    bot_log.info(msg)

def log_error(location: str, error: Exception, uid: int = None):
    uid_part = f" | uid={uid}" if uid else ""
    msg = f"ERROR | {location}{uid_part} | {type(error).__name__}: {error}"
    error_log.error(msg, exc_info=True)
    bot_log.error(msg)

def log_admin_action(admin_id: int, action: str, detail: str = ""):
    msg = f"ADMIN_ACTION | admin={admin_id} | action={action}" + (f" | {detail}" if detail else "")
    bot_log.info(msg)
    order_log.info(msg)
