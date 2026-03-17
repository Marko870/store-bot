"""
🤖 معالجات البوت الرئيسية - User Handlers
"""
import json
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ApplicationHandlerStop
)
from database import Database
from config import Config
from i18n import t
from bot_logger import (
    log_new_user, log_new_order, log_payment_proof,
    log_order_approved, log_order_rejected,
    log_recharge_order, log_exchange_order,
    log_error, log_admin_action, log_banned_attempt,
    bot_log
)

import re
import time
from collections import defaultdict

logger = logging.getLogger(__name__)
db  = Database()
cfg = Config()

# ══ نظام Anti-Spam ══════════════════════════════════
# {uid: [timestamps]} — نتتبع وقت كل ضغطة
_user_actions: dict = defaultdict(list)
SPAM_WINDOW   = 10   # ثواني
SPAM_MAX      = 15   # أقصى عدد ضغطات في الـ window
SPAM_COOLDOWN = 30   # ثواني حظر بعد الـ spam

def is_spamming(uid: int) -> bool:
    """يرجع True لو المستخدم يضغط بشكل مشبوه"""
    now = time.time()
    actions = _user_actions[uid]
    # نشيل الأحداث القديمة
    _user_actions[uid] = [t for t in actions if now - t < SPAM_WINDOW]
    _user_actions[uid].append(now)
    if len(_user_actions[uid]) > SPAM_MAX:
        bot_log.warning(f"SPAM_DETECTED | uid={uid} | actions={len(_user_actions[uid])}")
        return True
    return False

# ══ حدود النصوص ═══════════════════════════════════
MAX_TEXT_LEN   = 500    # أقصى طول لأي نص من المستخدم
MAX_FILE_SIZE  = 5 * 1024 * 1024  # 5 MB للملفات

async def _notify(bot, channel_id: str, targets: list,
                  text: str = None, photo=None, document=None,
                  caption: str = None, kb=None, parse_mode="Markdown"):
    """
    يرسل الإشعار للقناة لو محددة، وإلا للأدمن مباشرة.
    channel_id: قيمة من cfg مثل cfg.CHANNEL_SUBSCRIPTIONS
    targets: cfg.ADMIN_IDS (fallback)
    """
    destinations = [int(channel_id)] if channel_id else targets
    for dest in destinations:
        try:
            if photo:
                await bot.send_photo(chat_id=dest, photo=photo,
                    caption=caption, parse_mode=parse_mode, reply_markup=kb)
            elif document:
                await bot.send_document(chat_id=dest, document=document,
                    caption=caption, parse_mode=parse_mode, reply_markup=kb)
            else:
                await bot.send_message(chat_id=dest, text=text,
                    parse_mode=parse_mode, reply_markup=kb)
        except Exception as e:
            logger.error(f"Notify failed → {dest}: {e}")

# ══ حالات الانتظار ══
AWAITING_PROOF    = "awaiting_proof"
AWAITING_SUPPORT  = "awaiting_support"
AWAITING_INPUT    = "awaiting_input"
AWAITING_COUNTRY  = "awaiting_country"
EXCHANGE_AMOUNT   = "exchange_amount"
EXCHANGE_PHONE    = "exchange_phone"
EXCHANGE_PROOF    = "exchange_proof"

# ══ Validation ══
def validate_email(email: str) -> bool:
    """التحقق من صحة الإيميل بالمعايير الدولية"""
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email)) and len(email) <= 254

def validate_phone(phone: str) -> bool:
    cleaned = phone.replace(" ", "").replace("-", "")
    patterns = [
        r"^09\d{8}$",
        r"^9\d{8}$",
        r"^\+963\d{9}$",
        r"^00963\d{9}$",
        r"^(\+|00)[1-9]\d{6,14}$",
    ]
    return any(re.match(p, cleaned) for p in patterns)



def save_flow(uid, flow):
    db.save_flow(uid, flow)

def load_flow(uid):
    return db.get_flow(uid)

def clear_flow(uid):
    db.clear_flow(uid)

def is_admin(uid):  return uid in cfg.ADMIN_IDS
def get_lang(uid):
    u = db.get_user(uid)
    return u["lang"] if u else "ar"

def fmt_date(dt):
    if not dt: return "—"
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    return dt.strftime("%Y/%m/%d")

def progress_bar(days_total, days_remaining):
    if not days_total or days_total <= 0:
        return ""
    pct     = max(0, min(1, days_remaining / days_total))
    filled  = int(pct * 10)
    bar     = "█" * filled + "░" * (10 - filled)
    return f"[{bar}] {int(pct*100)}%"


# ══════════════════════════════════════════
#   /start — القائمة الرئيسية
# ══════════════════════════════════════════

async def security_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    فحص أمني شامل — يُشغَّل أول كل update:
    1. وضع الصيانة
    2. المستخدم محظور
    3. Anti-spam
    """
    user = update.effective_user
    if not user:
        return False
    uid = user.id

    # ١. وضع الصيانة — الأدمن معفى
    if cfg.MAINTENANCE_MODE and not is_admin(uid):
        msg = (
            "🔧 *البوت في وضع الصيانة*\n\n"
            "نعمل على تحسين الخدمة وسنعود قريباً.\n"
            f"للاستفسار: {cfg.SUPPORT_USERNAME}"
        )
        if update.callback_query:
            await update.callback_query.answer("🔧 البوت في صيانة", show_alert=True)
        elif update.message:
            await update.message.reply_text(msg, parse_mode="Markdown")
        return True

    # ٢. فحص الحظر — الأدمن معفى
    if not is_admin(uid):
        u = db.get_user(uid)
        if u and u.get("is_banned"):
            log_banned_attempt(uid)
            if update.callback_query:
                await update.callback_query.answer("🚫 تم حظرك من استخدام البوت", show_alert=True)
            elif update.message:
                await update.message.reply_text("🚫 تم حظرك من استخدام البوت.")
            return True

    # ٣. Anti-spam — الأدمن معفى
    if not is_admin(uid) and is_spamming(uid):
        if update.callback_query:
            await update.callback_query.answer("⚠️ أنت تضغط بسرعة كبيرة، انتظر قليلاً", show_alert=True)
        elif update.message:
            await update.message.reply_text("⚠️ أنت ترسل رسائل بسرعة كبيرة، انتظر قليلاً.")
        return True

    return False


async def maintenance_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """للتوافق مع الكود القديم"""
    return await security_check(update, context)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await security_check(update, context): return
    context.user_data.clear()
    # FIX: مسح DB state عند /start لمنع تعارض states قديمة
    if update.effective_user:
        db.clear_user_state(update.effective_user.id)
        db.clear_flow(update.effective_user.id)
    user = update.effective_user
    is_new = db.ensure_user_new(user.id, user.username or "", user.full_name)
    lang = get_lang(user.id)

    # مستخدم جديد — اسأله عن دولته
    if is_new:
        log_new_user(user.id, user.username or "")
        db.set_user_state(user.id, AWAITING_COUNTRY)
        text = f"👋 أهلاً *{user.first_name}*! مرحباً بك في Nova Plus 🛍️\n\nقبل أن نبدأ، من أي دولة أنت؟\n_مثال: سوريا، السعودية، الإمارات_"
        if update.message:
            await update.message.reply_text(text, parse_mode="Markdown")
        return

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 الخدمات | Services",        callback_data="services"),
         InlineKeyboardButton("📋 اشتراكاتي | My Subs",       callback_data="my_subs")],
        [InlineKeyboardButton("👤 ملفي | Profile",             callback_data="profile"),
         InlineKeyboardButton("📨 الدعم | Support",            callback_data="support")],
        [InlineKeyboardButton("🌐 English" if lang=="ar" else "🌐 العربية",
                              callback_data="lang_en" if lang=="ar" else "lang_ar")],
    ])
    text = t("welcome", lang, name=user.first_name)
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)


async def cb_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await cmd_start(update, context)


async def cb_set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang = q.data.split("_")[1]
    db.set_user_lang(q.from_user.id, lang)
    await cmd_start(update, context)


# ══════════════════════════════════════════
#   الخدمات
# ══════════════════════════════════════════

async def cb_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang = get_lang(q.from_user.id)

    kbd = InlineKeyboardMarkup([
        [InlineKeyboardButton("📺 اشتراكات رقمية",     callback_data="svccat_subscription")],
        [InlineKeyboardButton("📱 تعبئة سيرياتيل",     callback_data="svccat_recharge")],
        [InlineKeyboardButton("💱 تصريف USDT",         callback_data="svccat_exchange")],
        [InlineKeyboardButton(t("back", lang),          callback_data="main_menu")],
    ])
    await q.edit_message_text(
        "🛒 *الخدمات*\n\nاختر التصنيف:",
        reply_markup=kbd,
        parse_mode="Markdown"
    )


async def cb_services_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض خدمات تصنيف معين"""
    q = update.callback_query; await q.answer()
    lang = get_lang(q.from_user.id)
    cat  = q.data.replace("svccat_", "")

    # تعبئة الرصيد — تفتح flow مباشرة
    if cat == "recharge":
        services = db.get_services()
        recharge_svcs = [s for s in (services or []) if s.get("type_name") == "recharge"]
        if not recharge_svcs:
            await q.edit_message_text(
                "_(لا توجد خدمات تعبئة متاحة حالياً)_",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="services")
                ]])
            )
            return
        if len(recharge_svcs) == 1:
            # خدمة واحدة — نفتحها مباشرة
            await cb_recharge_start(update, context, svc_id=recharge_svcs[0]['id'])
        else:
            # أكثر من خدمة — نعرضهم
            btns = [[InlineKeyboardButton(s["name_ar"], callback_data=f"svc_{s['id']}")] for s in recharge_svcs]
            btns.append([InlineKeyboardButton("🔙 رجوع", callback_data="services")])
            await q.edit_message_text("📱 *تعبئة رصيد*\n\nاختر الخدمة:", reply_markup=InlineKeyboardMarkup(btns), parse_mode="Markdown")
        return

    # تصريف USDT — تفتح flow مباشرة
    if cat == "exchange":
        await cb_exchange_start(update, context)
        return

    # اشتراكات رقمية — تعرض الخدمات
    services = db.get_services()
    filtered = [s for s in (services or []) if s.get("type_name") == "subscription"]

    if not filtered:
        await q.edit_message_text(
            "📺 *اشتراكات رقمية*\n\n_(لا توجد خدمات متاحة حالياً)_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 رجوع", callback_data="services")
            ]])
        )
        return

    btns = [[InlineKeyboardButton(s["name_ar"] if lang == "ar" else s["name_en"], callback_data=f"svc_{s['id']}")] for s in filtered]
    btns.append([InlineKeyboardButton("🔙 رجوع", callback_data="services")])
    await q.edit_message_text(
        "📺 *اشتراكات رقمية*\n\nاختر الخدمة:",
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode="Markdown"
    )


async def cb_service_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang   = get_lang(q.from_user.id)
    svc_id = int(q.data.split("_")[1])
    svc    = db.get_service(svc_id)

    if not svc:
        await q.answer("❌", show_alert=True); return

    type_name = svc.get("type_name", "subscription")

    # خدمة التعبئة — flow خاص
    if type_name == "recharge":
        await cb_recharge_start(update, context)
        return

    # خدمة تصريف العملات — flow خاص
    if type_name == "exchange":
        context.user_data["exc_svc_id"] = svc_id
        await cb_exchange_start(update, context)
        return

    name = svc["name_ar"] if lang == "ar" else svc["name_en"]
    desc = svc.get("description_ar", "") if lang == "ar" else svc.get("description_en", "")
    text      = "🔵 *" + name + "*"
    if desc:
        text += "\n\n" + desc

    if type_name == "exchange":
        rate = db.get_exchange_rate(svc_id)
        if rate:
            text += "\n\n💱 سعر الصرف: `1 " + rate["unit"] + " = " + f"{rate['rate']:,.0f}" + " ل.س`"

    btns = []

    # لو في variants — اعرضهم أولاً
    variants = db.get_variants(svc_id)
    if variants:
        for v in variants:
            vname = v["name_ar"] if lang == "ar" else v.get("name_en", v["name_ar"])
            btns.append([InlineKeyboardButton("🗂️ " + vname, callback_data="variant_" + str(v["id"]))])
        # خطط بدون variant
        direct = db.get_plans_no_variant(svc_id)
        for p in direct:
            pname = p["name_ar"] if lang == "ar" else p["name_en"]
            btns.append([InlineKeyboardButton("📦 " + pname + " — " + str(p["price"]) + " USDT",
                callback_data="plan_" + str(p["id"]))])
    else:
        # لا variants — اعرض الخطط مباشرة
        plans = db.get_plans(svc_id)
        if not plans:
            btns = [[InlineKeyboardButton(t("back", lang), callback_data="services")]]
            await q.edit_message_text(text + "\n\n_(لا توجد خطط متاحة حالياً)_",
                parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))
            return
        for p in plans:
            pname = p["name_ar"] if lang == "ar" else p["name_en"]
            btns.append([InlineKeyboardButton(f"📦 {pname}",
                callback_data="plan_" + str(p["id"]))])

    btns.append([InlineKeyboardButton(t("back", lang), callback_data="services")])
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))



async def cb_variant_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang       = get_lang(q.from_user.id)
    variant_id = int(q.data.split("_")[1])
    plans      = db.get_plans_by_variant(variant_id)

    if not plans:
        await q.answer("لا توجد خطط لهذا النوع حالياً", show_alert=True); return

    svc_id   = plans[0]["service_id"]
    svc      = db.get_service(svc_id)
    svc_name = svc["name_ar"] if lang == "ar" else svc["name_en"]
    # نجيب اسم الـ variant
    variants = db.get_variants(svc_id)
    var_name = next((v["name_ar"] for v in variants if v["id"] == variant_id), "")

    text = "🔵 *" + svc_name + "*\n🗂️ *" + var_name + "*"
    btns = []
    for p in plans:
        pname = p["name_ar"] if lang == "ar" else p["name_en"]
        btns.append([InlineKeyboardButton(f"📦 {pname}", callback_data=f"plan_{p['id']}")])
    btns.append([InlineKeyboardButton(t("back", lang), callback_data=f"svc_{svc_id}")])
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))

async def cb_plan_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang    = get_lang(q.from_user.id)
    plan_id = int(q.data.split("_")[1])
    plan    = db.get_plan(plan_id)

    if not plan:
        await q.answer("❌ الخطة غير موجودة", show_alert=True); return

    svc_name  = plan["service_name_ar"] if lang == "ar" else plan["service_name_en"]
    plan_name = plan["name_ar"] if lang == "ar" else plan["name_en"]
    features  = json.loads(plan.get("features", "[]"))
    feats_text = "\n".join(f"  ✔️ {f}" for f in features) if features else ""

    syp = plan.get("price_syp", 0) or 0
    price_line = f"💰 *{plan['price']} USDT*"
    if syp > 0:
        price_line += f"  |  *{syp:,.0f} ل.س*"
    duration_line = f"\n⏱ {plan['duration_days']} يوم" if plan["duration_days"] > 0 else ""
    text = f"🔵 *{svc_name}*\n📦 *{plan_name}*\n{price_line}{duration_line}"
    if feats_text:
        text += f"\n\n{feats_text}"

    # خيارات ديناميكية
    options = db.get_plan_options(plan_id)
    if options:
        flow = {
            "plan_id":  plan_id,
            "options":  options,
            "step":     0,
            "answers":  {},
            "inputs":   {}
        }
        save_flow(q.from_user.id, flow)
        context.user_data["flow"] = flow
        await _ask_next_option(q, context, lang, text)
    else:
        flow = {"plan_id": plan_id, "answers": {}, "inputs": {}}
        save_flow(q.from_user.id, flow)
        context.user_data["flow"] = flow
        await _show_checkout(q, context, lang, plan)


async def _ask_next_option(q_or_msg, context, lang, prefix_text=""):
    flow = context.user_data.get("flow")
    if not flow:
        uid  = q_or_msg.from_user.id if hasattr(q_or_msg, "from_user") else q_or_msg.chat.id
        flow = load_flow(uid)
        if not flow:
            return
        context.user_data["flow"] = flow

    # دايماً نقرأ الخيارات من الـ plan مباشرة (مش من الـ flow القديم)
    options = db.get_plan_options(flow["plan_id"])
    flow["options"] = options
    step    = flow["step"]

    if step >= len(options):
        # انتهت الخيارات — روح للدفع
        plan = db.get_plan(flow["plan_id"])
        await _show_checkout(q_or_msg, context, lang, plan)
        return

    opt = options[step]

    # نوع الخيار: اختيار أزرار أو إدخال نص
    if opt.get("type") == "input":
        # طلب نص من المستخدم
        context.user_data[AWAITING_INPUT] = {"field": opt["key"], "label": opt["question"]}
        uid = q_or_msg.from_user.id if hasattr(q_or_msg, "from_user") else q_or_msg.chat.id
        db.set_user_state(uid, AWAITING_INPUT + ":" + opt["key"])
        prompt = f"{prefix_text}\n\n🔸 *{opt['question']}*" if prefix_text else f"🔸 *{opt['question']}*"
        if hasattr(q_or_msg, "edit_message_text"):
            try:
                await q_or_msg.edit_message_text(prompt, parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 رجوع", callback_data=f"back_plan_{flow['plan_id']}")],
                        [InlineKeyboardButton(t("cancel", lang), callback_data="main_menu")]
                    ]))
            except Exception as e:
                if "not modified" not in str(e).lower():
                    logger.warning(f"edit_message_text failed (input): {e}")
        else:
            await q_or_msg.reply_text(prompt, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 رجوع", callback_data=f"back_plan_{flow['plan_id']}")],
                    [InlineKeyboardButton(t("cancel", lang), callback_data="main_menu")]
                ]))
    else:
        # خيارات أزرار
        btns = [[InlineKeyboardButton(c, callback_data=f"opt_{step}_{i}")]
                for i, c in enumerate(opt["choices"])]
        prompt = f"{prefix_text}\n\n🔸 *{opt['question']}*" if prefix_text else f"🔸 *{opt['question']}*"
        btns.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"back_plan_{flow['plan_id']}")])
        if hasattr(q_or_msg, "edit_message_text"):
            try:
                await q_or_msg.edit_message_text(prompt, parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(btns))
            except Exception as e:
                if "not modified" not in str(e).lower():
                    logger.warning(f"edit_message_text failed (choice): {e}")
        else:
            await q_or_msg.reply_text(prompt, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(btns))


async def cb_plan_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang  = get_lang(q.from_user.id)
    parts = q.data.split("_")
    step  = int(parts[1])
    cidx  = int(parts[2])

    flow = context.user_data.get("flow") or load_flow(q.from_user.id)
    if not flow:
        await q.answer("❌ انتهت الجلسة، اضغط /start", show_alert=True); return
    context.user_data["flow"] = flow

    # دايماً نقرأ الخيارات من DB مش من flow القديم
    options = db.get_plan_options(flow["plan_id"])
    flow["options"] = options
    if step >= len(options):
        await q.answer("❌ انتهت الجلسة، اضغط /start", show_alert=True); return
    opt    = options[step]
    if cidx >= len(opt.get("choices", [])):
        await q.answer("❌ خيار غير صالح", show_alert=True); return
    choice = opt["choices"][cidx]
    flow["answers"][opt["question"]] = choice
    flow["step"] = step + 1
    save_flow(q.from_user.id, flow)

    # لو اختار "على إيميلك" — اطلب الإيميل تلقائياً
    choice_lower = choice.strip()
    EMAIL_TRIGGERS = ["على إيميلك", "ايميلي", "إيميلي", "my email", "my account"]
    if any(t in choice_lower for t in EMAIL_TRIGGERS):
        context.user_data[AWAITING_INPUT] = {"field": "email", "label": "📧 أدخل إيميلك:"}
        db.set_user_state(q.from_user.id, AWAITING_INPUT + ":email")
        await q.edit_message_text(
            "📧 *أدخل إيميلك:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع", callback_data=f"back_plan_{flow['plan_id']}")],
                [InlineKeyboardButton(t("cancel", lang), callback_data="main_menu")]
            ])
        )
        return

    await _ask_next_option(q, context, lang)


async def handle_input_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يستقبل نص المستخدم لأي حقل ديناميكي مع validation"""
    uid      = update.effective_user.id
    awaiting = context.user_data.get(AWAITING_INPUT)
    flow     = context.user_data.get("flow")

    # استرجاع من DB لو context فارغ
    if not flow:
        flow = load_flow(uid)
        if flow:
            context.user_data["flow"] = flow

    if not awaiting:
        state = db.get_user_state(uid)
        if state and state.startswith(AWAITING_INPUT + ":"):
            field = state.split(":", 1)[1]
            awaiting = {"field": field}
            context.user_data[AWAITING_INPUT] = awaiting

    if awaiting and flow:
        field = awaiting["field"]
        value = update.message.text.strip()
        lang  = get_lang(update.effective_user.id)

        if not value:
            await update.message.reply_text("❌ لا يمكن إرسال نص فارغ")
            return True
        if len(value) > 200:
            await update.message.reply_text("❌ النص طويل جداً (الحد 200 حرف)")
            return True
        # FIX F: تحقق من صحة plan_id في الـ flow
        if not flow.get("plan_id"):
            db.clear_user_state(uid)
            await update.message.reply_text("❌ انتهت الجلسة، اضغط /start")
            return True

        # ══ التحقق من الإيميل ══
        if field == "email":
            if not validate_email(value):
                await update.message.reply_text(
                    "❌ *الإيميل غير صحيح*\n\nتأكد من الصيغة الصحيحة، مثال:\n`example@gmail.com`",
                    parse_mode="Markdown"
                )
                return True
        # ══ التحقق من رقم الهاتف ══
        elif field in ("phone", "رقم هاتفك", "phone_number"):
            if not validate_phone(value):
                await update.message.reply_text(
                    "❌ *رقم الهاتف غير صحيح*\n\n"
                    "لازم تضيف رمز الدولة في البداية، مثال:\n"
                    "`+963912345678` (سوريا)\n"
                    "`+966512345678` (السعودية)\n"
                    "`+9715XXXXXXXX` (الإمارات)",
                    parse_mode="Markdown"
                )
                return True
        flow["inputs"][field] = value
        flow["step"] += 1
        context.user_data.pop(AWAITING_INPUT, None)
        db.clear_user_state(uid)
        save_flow(uid, flow)

        plan = db.get_plan(flow["plan_id"])
        await _ask_next_option(update.message, context, lang)
        return True
    return False


async def _show_checkout(q_or_msg, context, lang, plan):
    flow      = context.user_data.get("flow", {})
    answers   = flow.get("answers", {})
    inputs    = flow.get("inputs", {})
    svc_name  = plan["service_name_ar"] if lang == "ar" else plan["service_name_en"]
    plan_name = plan["name_ar"] if lang == "ar" else plan["name_en"]

    # ملخص الخيارات
    extras = ""
    for k, v in answers.items():
        extras += f"\n  • {k}: *{v}*"
    for k, v in inputs.items():
        extras += f"\n  • {k}: `{v}`"

    text = t("order_summary", lang,
             service=svc_name, plan=plan_name,
             amount=plan["price"], extras=extras)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 متابعة للدفع | Proceed", callback_data=f"checkout_{plan['id']}")],
        [InlineKeyboardButton(t("back", lang), callback_data=f"svc_{plan['service_id']}")]
    ])

    if hasattr(q_or_msg, "edit_message_text"):
        await q_or_msg.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await q_or_msg.reply_text(text, parse_mode="Markdown", reply_markup=kb)


# ══════════════════════════════════════════
#   الدفع
# ══════════════════════════════════════════

async def cb_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شاشة اختيار طريقة الدفع"""
    q = update.callback_query; await q.answer()
    lang    = get_lang(q.from_user.id)
    plan_id = int(q.data.split("_")[1])
    plan    = db.get_plan(plan_id)
    if not plan:
        await q.answer("❌ الخطة غير موجودة", show_alert=True); return

    flow    = context.user_data.get("flow", {})
    user_options = flow.get("answers", {})
    user_inputs  = flow.get("inputs", {})

    # FIX: منع تكرار إنشاء الطلب — لو في طلب pending لنفس المستخدم والخطة نعيد استخدامه
    existing_order_id = context.user_data.get("last_order_id")
    existing_plan_id  = context.user_data.get("checkout_plan_id")
    if existing_order_id and existing_plan_id == plan_id:
        existing = db.get_order(existing_order_id)
        if existing and existing.get("status") == "pending":
            order_id = existing_order_id
        else:
            order_id = db.create_order(
                q.from_user.id, plan_id, plan["service_id"],
                plan["price"], user_options, user_inputs
            )
    else:
        order_id = db.create_order(
            q.from_user.id, plan_id, plan["service_id"],
            plan["price"], user_options, user_inputs
        )
    context.user_data["last_order_id"] = order_id
    context.user_data["checkout_plan_id"] = plan_id

    svc_name  = plan["service_name_ar"] if lang == "ar" else plan["service_name_en"]
    plan_name = plan["name_ar"] if lang == "ar" else plan["name_en"]
    syp       = plan.get("price_syp", 0) or 0
    log_new_order(q.from_user.id, order_id, plan_name, plan["price"])

    syp_line = f"\n💵 *{syp:,.0f} ل.س*" if syp > 0 else ""
    text = (
        f"🧾 *ملخص الطلب*\n\n"
        f"🛍️ {svc_name}\n"
        f"📦 {plan_name}\n"
        f"💰 *{plan['price']} USDT*{syp_line}\n"
        f"🔖 رقم الطلب: `#{order_id}`\n\n"
        f"اختر طريقة الدفع:"
    )

    btns = [
        [InlineKeyboardButton("💎 USDT",      callback_data=f"paymethod_usdt_{order_id}_{plan_id}"),
         InlineKeyboardButton("🏦 شام كاش",  callback_data=f"paymethod_shamcash_{order_id}_{plan_id}")],
        [InlineKeyboardButton(t("back", lang), callback_data=f"plan_{plan_id}")]
    ]
    # لو شام كاش غير مفعل — أخفيه
    if not cfg.SHAMCASH_ADDRESS:
        btns = [
            [InlineKeyboardButton("💎 USDT", callback_data=f"paymethod_usdt_{order_id}_{plan_id}")],
            [InlineKeyboardButton(t("back", lang), callback_data=f"plan_{plan_id}")]
        ]

    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))


async def cb_pay_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بعد اختيار طريقة الدفع"""
    q = update.callback_query; await q.answer()
    lang    = get_lang(q.from_user.id)
    parts   = q.data.split("_")
    method  = parts[1]           # usdt أو shamcash
    try:
        order_id = int(parts[2])
        plan_id  = int(parts[3])
    except (IndexError, ValueError):
        await q.answer("❌ بيانات غير صحيحة", show_alert=True); return
    plan = db.get_plan(plan_id)
    if not plan:
        await q.answer("❌ الخطة غير موجودة", show_alert=True); return

    svc_name  = plan["service_name_ar"] if lang == "ar" else plan["service_name_en"]
    plan_name = plan["name_ar"] if lang == "ar" else plan["name_en"]
    syp       = plan.get("price_syp", 0) or 0

    if method == "usdt":
        text = t("payment_details", lang,
                 service=svc_name, plan=plan_name,
                 amount=plan["price"], network=cfg.USDT_NETWORK,
                 address=cfg.USDT_ADDRESS, order_id=order_id)
    else:
        # شام كاش — يدفع الدولار أو السوري على نفس العنوان
        price_line = f"💰 *{plan['price']} USDT*"
        if syp > 0:
            price_line += f"  أو  *{syp:,.0f} ل.س*"
        text = (
            f"🏦 *الدفع عبر شام كاش*\n\n"
            f"🛍️ {svc_name} — {plan_name}\n"
            f"{price_line}\n"
            f"🔖 رقم الطلب: `#{order_id}`\n\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📲 *رقم المحفظة:*\n"
            f"`{cfg.SHAMCASH_ADDRESS}`\n"
        )
        if cfg.SHAMCASH_NAME:
            text += f"👤 *الاسم:* {cfg.SHAMCASH_NAME}\n"
        text += (
            f"━━━━━━━━━━━━━━━━\n\n"
            f"⚠️ أرسل المبلغ بالضبط ثم أرسل لقطة الإشعار."
        )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 إرسال إثبات الدفع",
                              callback_data=f"sendproof_{order_id}_{plan_id}")],
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"checkout_{plan_id}")]
    ])
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)


async def cb_send_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang  = get_lang(q.from_user.id)
    parts = q.data.split("_")
    order_id = int(parts[1])
    plan_id  = int(parts[2])

    context.user_data[AWAITING_PROOF] = {"order_id": order_id, "plan_id": plan_id}
    db.update_order_status(order_id, "awaiting_approval")

    await q.edit_message_text(
        t("proof_prompt", lang),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data=f"back_checkout_{plan_id}")],
            [InlineKeyboardButton(t("cancel", lang), callback_data="main_menu")]
        ])
    )


async def handle_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    proof_data = context.user_data.get(AWAITING_PROOF)
    if not proof_data:
        return False

    order_id = proof_data["order_id"]
    plan_id  = proof_data["plan_id"]
    lang     = get_lang(update.effective_user.id)
    user     = db.get_user(update.effective_user.id)
    order    = db.get_order(order_id)
    plan     = db.get_plan(plan_id)

    # FIX: تحقق من حالة الطلب — لا ترسل إثبات لطلب مرفوض أو مكتمل
    if order and order.get("status") not in ("pending", "awaiting_approval"):
        await update.message.reply_text(
            "❌ هذا الطلب تم معالجته مسبقاً. أنشئ طلباً جديداً.",
            parse_mode="Markdown"
        )
        context.user_data.pop(AWAITING_PROOF, None)
        return True

    log_payment_proof(update.effective_user.id, order_id)

    # إشعار المستخدم
    await update.message.reply_text(
        t("proof_received", lang, order_id=order_id),
        parse_mode="Markdown"
    )

    # تجميع كل تفاصيل الطلب للأدمن
    user_options = json.loads(order.get("user_options") or "{}")
    user_inputs  = json.loads(order.get("user_inputs") or "{}")

    options_text = ""
    for k, v in user_options.items():
        options_text += f"\n  • {k}: *{v}*"
    for k, v in user_inputs.items():
        options_text += f"\n  • {k}: `{v}`"

    svc_name  = plan["service_name_ar"]
    plan_name = plan["name_ar"]
    username  = f"@{user['username']}" if user.get('username') else '—'  # backtick added at usage

    admin_text = (
        f"🔔 *طلب دفع جديد*\n\n"
        f"👤 المستخدم: {user['full_name']}\n"
        f"🆔 ID: `{update.effective_user.id}`\n"
        f"📱 يوزر: `{username}`\n\n"
        f"🛍️ الخدمة: *{svc_name}*\n"
        f"📦 الخطة: *{plan_name}*\n"
        f"💰 المبلغ: *{plan['price']} USDT*\n"
        f"🔖 رقم الطلب: `#{order_id}`"
    )
    if options_text:
        admin_text += f"\n\n📋 *خيارات الزبون:*{options_text}"

    admin_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ قبول وتفعيل",  callback_data=f"approve_{order_id}_{update.effective_user.id}_{plan_id}"),
         InlineKeyboardButton("❌ رفض",          callback_data=f"reject_{order_id}_{update.effective_user.id}")],
        [InlineKeyboardButton("💬 إرسال بيانات للزبون", callback_data=f"sendcreds_{update.effective_user.id}_{order_id}_{plan_id}")]
    ])

    photo = update.message.photo[-1].file_id if update.message.photo else None
    await _notify(
        bot=context.bot,
        channel_id=cfg.CHANNEL_SUBSCRIPTIONS,
        targets=cfg.ADMIN_IDS,
        photo=photo,
        document=update.message.document.file_id if not photo and update.message.document else None,
        caption=admin_text,
        kb=admin_kb
    )

    context.user_data.pop(AWAITING_PROOF, None)
    return True


# ══════════════════════════════════════════
#   أزرار الأدمن على الطلب
# ══════════════════════════════════════════

async def cb_approve_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return

    parts    = q.data.split("_")
    order_id = int(parts[1])
    user_id  = int(parts[2])
    plan_id  = int(parts[3])

    # تحقق من حالة الطلب قبل القبول
    order = db.get_order(order_id)
    if not order:
        await q.answer("❌ الطلب غير موجود", show_alert=True); return
    if order["status"] not in ("awaiting_approval", "pending"):
        await q.answer(f"⚠️ الطلب مُعالج مسبقاً ({order['status']})", show_alert=True); return

    plan = db.get_plan(plan_id)
    if not plan:
        await q.answer("❌ الخطة غير موجودة", show_alert=True); return

    # FIX: تحقق مرة أخرى قبل التنفيذ لمنع القبول المزدوج
    fresh_order = db.get_order(order_id)
    if not fresh_order or fresh_order.get("status") not in ("awaiting_approval", "pending"):
        await q.answer("⚠️ الطلب مُعالج مسبقاً", show_alert=True); return

    db.complete_order(order_id)
    db.create_subscription(
        user_id, plan_id, order_id, plan["service_id"],
        plan["duration_days"]
    )
    log_order_approved(order_id, q.from_user.id, user_id)

    admin_name = f"@{q.from_user.username}" if q.from_user.username else str(q.from_user.id)
    now_str    = datetime.now().strftime("%Y-%m-%d %H:%M")

    # حفظ بيانات الطلب للاستخدام عند إرسال البيانات
    creds_data = {
        "user_id":    user_id,
        "order_id":   order_id,
        "plan_id":    plan_id,
        "plan_name":  plan["name_ar"],
        "svc_name":   plan["service_name_ar"],
    }
    db.set_user_state(q.from_user.id,
        f"SENDING_CREDS:{json.dumps(creds_data)}")
    context.user_data["sending_creds"] = creds_data

    # تعديل الأزرار في المجموعة/البوت
    new_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 إرسال بيانات للزبون",
                              callback_data=f"sendcreds_{user_id}_{order_id}_{plan_id}")],
    ])
    try:
        await q.edit_message_reply_markup(reply_markup=new_kb)
    except Exception:
        pass
    try:
        await q.message.reply_text(
            f"✅ تم القبول — {admin_name} | 🕐 {now_str}\n"
            f"أرسل بيانات الدخول للزبون الآن:",
            parse_mode=None
        )
    except Exception:
        pass
    # لا نرسل إشعار للزبون هنا — ننتظر حتى الأدمن يرسل البيانات


async def cb_reject_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return

    parts    = q.data.split("_")
    order_id = int(parts[1])
    user_id  = int(parts[2])

    db.update_order_status(order_id, "rejected")
    log_order_rejected(order_id, q.from_user.id, user_id)

    admin_name = f"@{q.from_user.username}" if q.from_user.username else str(q.from_user.id)
    now_str    = datetime.now().strftime("%Y-%m-%d %H:%M")

    # نزيل الأزرار ونبعت رسالة حالة منفصلة
    try:
        await q.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    try:
        await q.message.reply_text(
            f"❌ تم الرفض — {admin_name} | 🕐 {now_str}",
            parse_mode=None
        )
    except Exception:
        pass

    lang = get_lang(user_id)
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=t("order_rejected", lang, order_id=order_id),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"User notify failed: {e}")


async def cb_send_creds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الأدمن يضغط 'إرسال بيانات' — يشتغل من المجموعة والبوت"""
    q = update.callback_query; await q.answer()

    admin_id = q.from_user.id if q.from_user else None
    if not admin_id or not is_admin(admin_id):
        await q.answer("❌ غير مصرح", show_alert=True); return

    parts    = q.data.split("_")
    user_id  = int(parts[1])
    order_id = int(parts[2])
    plan_id  = int(parts[3])

    db.set_user_state(admin_id, f"SENDING_CREDS:{json.dumps({'user_id': user_id, 'order_id': order_id, 'plan_id': plan_id})}")
    context.user_data["sending_creds"] = {
        "user_id":  user_id,
        "order_id": order_id,
        "plan_id":  plan_id
    }

    msg_text = (
        f"✏️ أرسل البيانات للزبون\n"
        f"🆔 ID: `{user_id}` | طلب: `#{order_id}`\n\n"
        f"مثال:\n`إيميل: test@gmail.com\nكلمة السر: 123456`\n\n"
        f"أو أي نص تريده:"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="admin_skip")]])

    # لو الضغطة من خاص البوت — يطلب هناك مباشرة
    # لو من مجموعة — يرد في المجموعة
    chat_type = q.message.chat.type if q.message else "private"
    if chat_type == "private":
        await q.message.reply_text(msg_text, parse_mode="Markdown", reply_markup=kb)
    else:
        # من المجموعة — يرد في المجموعة
        try:
            await q.message.reply_text(
                f"✏️ @{q.from_user.username or admin_id} {msg_text}",
                parse_mode="Markdown", reply_markup=kb
            )
        except Exception as e:
            logger.error(f"Send creds group failed: {e}")
            await q.answer("❌ حدث خطأ", show_alert=True)

async def cb_admin_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data.pop("sending_creds", None)
    context.user_data.pop("replying_ticket", None)
    if q.from_user:
        db.clear_user_state(q.from_user.id)
    try:
        await q.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass


async def cb_go_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """زر الرجوع المركزي — يمسح الـ state والـ flow ثم يروح للصفحة المطلوبة"""
    q = update.callback_query; await q.answer()
    uid = q.from_user.id

    # مسح كل الـ states من DB ومن الذاكرة
    try: db.clear_user_state(uid)
    except: pass
    try: db.clear_flow(uid)
    except: pass
    context.user_data.pop(AWAITING_INPUT, None)
    context.user_data.pop(AWAITING_PROOF, None)
    context.user_data.pop(AWAITING_SUPPORT, None)
    context.user_data.pop("flow", None)
    context.user_data.pop("exc_op", None)
    context.user_data.pop("exc_method", None)
    context.user_data.pop("exc_rate", None)
    context.user_data.pop("exc_amount", None)
    context.user_data.pop("exc_phone", None)
    context.user_data.pop("exc_syp", None)
    context.user_data.pop("exc_order_id", None)

    dest = q.data.replace("back_", "", 1)

    try:
        # كل دالة تقرأ q.data — نعطيها dest مباشرة عبر استدعاء مخصص
        if dest == "main_menu":
            await cb_main_menu(update, context)

        elif dest == "services":
            await cb_services(update, context)

        elif dest.startswith("svccat_"):
            # cb_services_category تقرأ: cat = q.data.replace("svccat_", "")
            cat = dest.replace("svccat_", "")
            lang = get_lang(uid)
            if cat == "recharge":
                services = db.get_services()
                recharge_svcs = [s for s in (services or []) if s.get("type_name") == "recharge"]
                if not recharge_svcs:
                    await q.edit_message_text("_(لا توجد خدمات تعبئة متاحة)_", parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="services")]]))
                elif len(recharge_svcs) == 1:
                    await cb_recharge_start(update, context, svc_id=recharge_svcs[0]['id'])
                else:
                    btns = [[InlineKeyboardButton(s["name_ar"], callback_data=f"svc_{s['id']}")] for s in recharge_svcs]
                    btns.append([InlineKeyboardButton("🔙 رجوع", callback_data="services")])
                    await q.edit_message_text("📱 *تعبئة رصيد*\n\nاختر الخدمة:", reply_markup=InlineKeyboardMarkup(btns), parse_mode="Markdown")
            elif cat == "exchange":
                await cb_exchange_start(update, context)
            else:
                services = db.get_services()
                filtered = [s for s in (services or []) if s.get("type_name") == "subscription"]
                if not filtered:
                    await q.edit_message_text("📺 *اشتراكات رقمية*\n\n_(لا توجد خدمات متاحة)_", parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="services")]]))
                else:
                    btns = [[InlineKeyboardButton(s["name_ar"], callback_data=f"svc_{s['id']}")] for s in filtered]
                    btns.append([InlineKeyboardButton("🔙 رجوع", callback_data="services")])
                    await q.edit_message_text("📺 *اشتراكات رقمية*\n\nاختر الخدمة:", reply_markup=InlineKeyboardMarkup(btns), parse_mode="Markdown")

        elif dest.startswith("svc_"):
            # cb_service_detail تقرأ: svc_id = int(q.data.split("_")[1])
            svc_id = int(dest.split("_")[1])
            svc = db.get_service(svc_id)
            if svc:
                lang = get_lang(uid)
                name = svc["name_ar"]
                variants = db.get_variants(svc_id)
                plans = db.get_plans(svc_id)
                btns = []
                if variants:
                    for v in variants:
                        btns.append([InlineKeyboardButton("🗂️ " + v["name_ar"], callback_data=f"variant_{v['id']}")])
                    for p in db.get_plans_no_variant(svc_id):
                        btns.append([InlineKeyboardButton(f"📦 {p['name_ar']} — {p['price']} USDT", callback_data=f"plan_{p['id']}")])
                else:
                    for p in plans:
                        btns.append([InlineKeyboardButton(f"📦 {p['name_ar']} — {p['price']} USDT", callback_data=f"plan_{p['id']}")])
                btns.append([InlineKeyboardButton("🔙 رجوع", callback_data="services")])
                await q.edit_message_text(f"🔵 *{name}*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))

        elif dest.startswith("plan_"):
            plan_id = int(dest.split("_")[1])
            lang = get_lang(uid)
            plan = db.get_plan(plan_id)
            if plan:
                import json as _json
                options = db.get_plan_options(plan_id)
                flow = {"plan_id": plan_id, "options": options, "step": 0, "answers": {}, "inputs": {}}
                save_flow(uid, flow)
                context.user_data["flow"] = flow
                svc_name = plan["service_name_ar"]
                plan_name = plan["name_ar"]
                features = _json.loads(plan.get("features", "[]"))
                feats_text = "\n".join(f"  ✔️ {f}" for f in features) if features else ""
                syp = plan.get("price_syp", 0) or 0
                syp_line = f"\n💵 {syp:,.0f} ل.س" if syp > 0 else ""
                text = f"🔵 *{svc_name}*\n📦 *{plan_name}*\n💰 {plan['price']} USDT{syp_line}"
                if plan["duration_days"] > 0:
                    text += f" / {plan['duration_days']} يوم"
                if feats_text:
                    text += f"\n\n{feats_text}"
                if options:
                    await _ask_next_option(q, context, lang, text)
                else:
                    await _show_checkout(q, context, lang, plan)

        elif dest.startswith("checkout_"):
            plan_id = int(dest.split("_")[1])
            plan = db.get_plan(plan_id)
            if not plan:
                await q.edit_message_text("❌ الخطة غير موجودة.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
                    ]]))
            else:
                lang = get_lang(uid)
                await _show_checkout(q, context, lang, plan)

        elif dest.startswith("variant_"):
            variant_id = int(dest.split("_")[1])
            lang = get_lang(uid)
            plans = db.get_plans_by_variant(variant_id)
            # FIX 9: تحقق من وجود خطط
            if not plans:
                await q.edit_message_text(
                    "لا توجد خطط لهذا النوع حالياً.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 رجوع", callback_data="services")
                    ]]))
            else:
                svc_id = plans[0]["service_id"]
                svc = db.get_service(svc_id)
                var = db.get_variant(variant_id)
                text = f"🔵 *{svc['name_ar']}*\n🗂️ *{var['name_ar']}*"
                btns = []
                for p in plans:
                    pname = p["name_ar"] if lang == "ar" else p["name_en"]
                    btns.append([InlineKeyboardButton(f"📦 {pname}", callback_data=f"plan_{p['id']}")])
                btns.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"svc_{svc_id}")])
                await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))
        elif dest.startswith("svccat_exchange") or dest == "exchange":
            # FIX 12: مسح state الصرافة عند الرجوع
            for k in ["exc_op","exc_method","exc_rate","exc_amount","exc_phone","exc_syp","exc_order_id"]:
                context.user_data.pop(k, None)
            db.clear_user_state(uid)
            await cb_services_category(update, context)

        elif dest.startswith("exc_op_"):
            # cb_exchange_op تقرأ: op = q.data.replace("exc_op_", "")
            op = dest.replace("exc_op_", "")
            context.user_data["exc_op"] = op
            op_label = "شراء USDT" if op == "buy" else "بيع USDT"
            pay_recv = 'الدفع' if op == 'buy' else 'الاستلام'
            text = f"💱 *{op_label}*\n\nاختر طريقة {pay_recv}:"
            kbd = InlineKeyboardMarkup([
                [InlineKeyboardButton("📱 سيرياتيل كاش", callback_data="exc_method_syriatel")],
                [InlineKeyboardButton("💳 شام كاش",       callback_data="exc_method_shamcash")],
                [InlineKeyboardButton("🏦 حوالة",         callback_data="exc_method_hawala")],
                [InlineKeyboardButton("🤝 يد بيد",        callback_data="exc_method_hand")],
                [InlineKeyboardButton("🔙 رجوع",          callback_data="back_svccat_exchange")],
            ])
            await q.edit_message_text(text, reply_markup=kbd, parse_mode="Markdown")

        else:
            await cb_main_menu(update, context)

    except Exception as e:
        if "not modified" not in str(e).lower():
            logger.error(f"cb_go_back failed ({dest}): {e}")

    raise ApplicationHandlerStop


# ══════════════════════════════════════════
#   اشتراكاتي
# ══════════════════════════════════════════

async def cb_my_subs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang = get_lang(q.from_user.id)
    subs = db.get_all_subscriptions(q.from_user.id)

    if not subs:
        await q.edit_message_text(
            t("no_subs", lang),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 الخدمات", callback_data="services")],
                [InlineKeyboardButton(t("back", lang), callback_data="main_menu")]
            ])
        )
        return

    text = t("my_subs", lang) + "\n"
    renewal_btns = []

    for sub in subs[:5]:
        creds_raw = json.loads(sub.get("credentials", "{}"))
        now       = datetime.now()

        # حساب الأيام المتبقية
        if sub.get("expires_at"):
            exp = sub["expires_at"]
            if isinstance(exp, str):
                exp = datetime.fromisoformat(exp)
            remaining = (exp - now).days
            started   = sub.get("started_at")
            if isinstance(started, str):
                started = datetime.fromisoformat(started)
            total_days = sub.get("duration_days", 30) or 30
            bar = progress_bar(total_days, max(0, remaining))
            remaining_text = f"{remaining} يوم" if remaining > 0 else "⚠️ منتهي"
            exp_str = fmt_date(exp)
        else:
            remaining_text = "—"
            bar = ""
            exp_str = "—"

        # حالة الاشتراك
        status_emoji = "✅" if sub["status"] == "active" and remaining > 0 else "❌"

        # بيانات الدخول
        creds_text = ""
        if creds_raw:
            creds_text = "\n" + "\n".join(f"  🔑 {k}: `{v}`" for k, v in creds_raw.items())

        started_str = fmt_date(sub.get("started_at"))

        text += (
            f"\n━━━━━━━━━━━━━━━━\n"
            f"{status_emoji} *{sub['service_ar']}*\n"
            f"📦 {sub['plan_name']}\n"
            f"📅 بدأ: {started_str} | ينتهي: {exp_str}\n"
            f"⏳ باقي: {remaining_text}\n"
            f"{bar}"
            f"{creds_text}\n"
        )

        # زر تجديد للاشتراكات النشطة
        if sub["status"] == "active" and sub.get("plan_id"):
            renewal_btns.append([InlineKeyboardButton(
                f"♻️ جدد: {sub['service_ar']}",
                callback_data=f"plan_{sub['plan_id']}"
            )])

    btns = renewal_btns + [[InlineKeyboardButton(t("back", lang), callback_data="main_menu")]]
    await q.edit_message_text(text, parse_mode="Markdown",
                               reply_markup=InlineKeyboardMarkup(btns))


# ══════════════════════════════════════════
#   الملف الشخصي
# ══════════════════════════════════════════

async def cb_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang    = get_lang(q.from_user.id)
    u       = db.get_user(q.from_user.id)
    country = u.get("country", "") or "—"
    subs    = db.get_all_subscriptions(q.from_user.id)
    active  = sum(1 for s in subs if s["status"] == "active")

    text = (
        f"👤 *ملفي الشخصي*\n\n"
        f"🆔 المعرف: `{q.from_user.id}`\n"
        f"👤 الاسم: {u['full_name']}\n"
        f"🌍 الدولة: {country}\n"
        f"📅 تاريخ التسجيل: {fmt_date(u['joined_at'])}\n"
        f"✅ اشتراكات نشطة: {active}"
    )
    await q.edit_message_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🌍 تعديل الدولة",   callback_data="edit_country")],
            [InlineKeyboardButton("📋 سجل التعبئة",   callback_data="recharge_history")],
            [InlineKeyboardButton(t("back", lang),     callback_data="main_menu")]
        ]))


async def cb_recharge_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid    = q.from_user.id
    lang   = get_lang(uid)
    orders = db.get_user_recharge_history(uid, limit=10)

    if not orders:
        await q.edit_message_text(
            "لا توجد طلبات تعبئة سابقة.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("رجوع", callback_data="profile")
            ]]))
        return

    STATUS_EMOJI = {"pending": "⏳", "completed": "✅", "rejected": "❌"}
    lines = ["سجل طلبات التعبئة:\n"]
    for o in orders:
        emoji = STATUS_EMOJI.get(o["status"], "•")
        lines.append(
            emoji + " " + o["svc_ar"] + " — " +
            f"{o['amount_local']:,.0f}" + " ل.س" +
            " (" + (o.get("phone_number") or "—") + ")" +
            " | " + fmt_date(o["created_at"])
        )
    await q.edit_message_text("\n".join(lines),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data="profile")]]))


# ══════════════════════════════════════════
#   تعديل الدولة
# ══════════════════════════════════════════

async def cb_edit_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang = get_lang(q.from_user.id)
    db.set_user_state(q.from_user.id, AWAITING_COUNTRY)
    await q.edit_message_text(
        "🌍 *تعديل الدولة*\n\nأرسل اسم دولتك:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(t("cancel", lang), callback_data="profile")
        ]])
    )


# ══════════════════════════════════════════
#   الدعم
# ══════════════════════════════════════════

async def cb_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang = get_lang(q.from_user.id)
    context.user_data[AWAITING_SUPPORT] = True
    db.set_user_state(q.from_user.id, AWAITING_SUPPORT)
    await q.edit_message_text(
        t("support_prompt", lang),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(t("cancel", lang), callback_data="main_menu")
        ]])
    )


async def handle_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    in_memory = context.user_data.get(AWAITING_SUPPORT)
    db_state  = db.get_user_state(uid)
    if not in_memory and db_state != AWAITING_SUPPORT:
        return False

    # تحقق من طول الرسالة
    msg_text = update.message.text or ""
    if len(msg_text) > 1000:
        await update.message.reply_text("❌ رسالتك طويلة جداً (الحد 1000 حرف)")
        return True
    if len(msg_text.strip()) < 5:
        await update.message.reply_text("❌ الرسالة قصيرة جداً")
        return True

    lang      = get_lang(uid)
    ticket_id = db.create_ticket(uid, msg_text)
    user      = db.get_user(uid)
    username  = f"@{user['username']}" if user.get('username') else '—'  # backtick added at usage

    await update.message.reply_text(t("support_sent", lang), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(t("main_menu", lang), callback_data="main_menu")
        ]]))

    await _notify(
        bot=context.bot,
        channel_id=cfg.CHANNEL_SUPPORT,
        targets=cfg.ADMIN_IDS,
        text=(
            f"🎫 *تذكرة دعم جديدة #{ticket_id}*\n\n"
            f"👤 {user['full_name']} | {username}\n"
            f"🆔 `{uid}`\n\n"
            f"💬 {msg_text}"
        ),
        kb=InlineKeyboardMarkup([[
            InlineKeyboardButton("💬 رد", callback_data=f"replyticket_{ticket_id}_{uid}")
        ]])
    )

    context.user_data.pop(AWAITING_SUPPORT, None)
    db.clear_user_state(uid)
    return True


    db.clear_user_state(uid)
    return True


# ══════════════════════════════════════════
#   تصريف العملات — Currency Exchange
# ══════════════════════════════════════════

METHOD_LABELS = {
    "syriatel": "📱 سيرياتيل كاش",
    "shamcash": "💳 شام كاش",
    "hawala":   "🏦 حوالة",
    "hand":     "🤝 يد بيد (اللاذقية)",
}

OP_LABELS = {
    "buy":  "شراء USDT",
    "sell": "بيع USDT",
}


async def cb_exchange_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يظهر خيار شراء أو بيع USDT"""
    q = update.callback_query
    await q.answer()

    text = (
        "💱 *تصريف العملات*\n\n"
        "اختر العملية التي تريد تنفيذها:"
    )

    kbd = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 شراء USDT",  callback_data="exc_op_buy"),
         InlineKeyboardButton("💰 بيع USDT",   callback_data="exc_op_sell")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="services")],
    ])
    await q.edit_message_text(text, reply_markup=kbd, parse_mode="Markdown")


async def cb_exchange_op(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يختار العملية (شراء/بيع) ثم يختار طريقة الدفع/الاستلام"""
    q = update.callback_query
    await q.answer()
    op = q.data.replace("exc_op_", "")
    context.user_data["exc_op"] = op

    op_label = "ستدفع بـ" if op == "buy" else "ستستلم عبر"
    text = f"💱 *{OP_LABELS[op]}*\n\nاختر طريقة {'الدفع' if op == 'buy' else 'الاستلام'}:"

    kbd = InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 سيرياتيل كاش", callback_data="exc_method_syriatel")],
        [InlineKeyboardButton("💳 شام كاش",       callback_data="exc_method_shamcash")],
        [InlineKeyboardButton("🏦 حوالة",         callback_data="exc_method_hawala")],
        [InlineKeyboardButton("🤝 يد بيد",        callback_data="exc_method_hand")],
        [InlineKeyboardButton("🔙 رجوع",          callback_data="svccat_exchange")],
    ])
    await q.edit_message_text(text, reply_markup=kbd, parse_mode="Markdown")


async def cb_exchange_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بعد اختيار الطريقة"""
    q = update.callback_query
    await q.answer()
    method = q.data.replace("exc_method_", "")
    op     = context.user_data.get("exc_op", "buy")
    context.user_data["exc_method"] = method

    # يد بيد — رسالة مباشرة بدون flow
    if method == "hand":
        support = cfg.SUPPORT_USERNAME
        text = (
            f"🤝 *يد بيد — اللاذقية فقط*\n\n"
            f"التسليم متاح في مدينة اللاذقية فقط.\n"
            f"تواصل معنا مباشرة لترتيب الموعد والمكان:\n\n"
            f"👤 {support}"
        )
        kbd = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 تواصل معنا", url=f"https://t.me/{support.replace('@','')}")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="exchange")],
        ])
        await q.edit_message_text(text, reply_markup=kbd, parse_mode="Markdown")
        return

    # باقي الطرق — نطلب المبلغ مع عرض السعر
    rates = db.get_exchange_rates_all()
    rate_key = f"{op}_{'syriatel' if method == 'syriatel' else 'normal'}"
    rate = rates.get(rate_key, 0)
    context.user_data["exc_rate"] = rate

    method_label = METHOD_LABELS[method]
    op_label = OP_LABELS[op]
    pay_recv = "ستدفع" if op == "buy" else "ستستلم"

    text = (
        f"💱 *{op_label}* — {method_label}\n\n"
        f"💵 السعر: `{rate:,.0f}` ل.س لكل USDT\n"
        f"📌 الحد الأدنى: `5 USDT`\n\n"
        f"أرسل المبلغ بـ USDT:"
    )
    kbd = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"back_exc_op_{op}"),
         InlineKeyboardButton("❌ إلغاء", callback_data="main_menu")]
    ])
    await q.edit_message_text(text, reply_markup=kbd, parse_mode="Markdown")
    db.set_user_state(q.from_user.id, EXCHANGE_AMOUNT)


async def handle_exchange_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """معالجة نصوص flow الصرافة"""
    uid   = update.effective_user.id
    state = db.get_user_state(uid)

    if state == EXCHANGE_AMOUNT:
        text = update.message.text.strip().replace(",", "")
        try:
            amount = float(text)
        except Exception:
            await update.message.reply_text("❌ أرسل رقماً صحيحاً مثل: 10")
            return True

        if amount < 5:
            await update.message.reply_text("❌ الحد الأدنى 5 USDT")
            return True

        op     = context.user_data.get("exc_op", "buy")
        method = context.user_data.get("exc_method", "shamcash")
        rate   = context.user_data.get("exc_rate", 0)

        if not rate or rate <= 0:
            await update.message.reply_text("❌ سعر الصرف غير محدد، تواصل مع الدعم.")
            db.clear_user_state(uid)
            return True
        if amount > 500:
            await update.message.reply_text("❌ الحد الأقصى للعملية 500 USDT")
            return True
        # FIX G: تحقق من وجود exc_method — لو فقد بسبب restart
        if not method or not op:
            db.clear_user_state(uid)
            await update.message.reply_text("❌ انتهت الجلسة، ابدأ من جديد.")
            return True

        amount_syp = amount * rate

        context.user_data["exc_amount"] = amount
        context.user_data["exc_syp"]    = amount_syp

        op_label     = OP_LABELS[op]
        method_label = METHOD_LABELS[method]
        pay_recv     = "ستدفع" if op == "buy" else "ستستلم"

        text = (
            f"💱 *تأكيد العملية*\n\n"
            f"📋 {op_label}\n"
            f"💵 المبلغ: `{amount} USDT`\n"
            f"💴 {pay_recv}: `{amount_syp:,.0f}` ل.س\n"
            f"📲 الطريقة: {method_label}\n\n"
            f"أرسل رقم {'هاتف سيرياتيل كاش' if method == 'syriatel' else 'حسابك أو رقم الهاتف'}:"
        )
        kbd = InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="main_menu")]])
        await update.message.reply_text(text, reply_markup=kbd, parse_mode="Markdown")
        db.set_user_state(uid, EXCHANGE_PHONE)
        return True

    if state == EXCHANGE_PHONE:
        phone = update.message.text.strip()
        # تحقق من طول رقم الهاتف/الحساب
        if len(phone) > 50:
            await update.message.reply_text("❌ الرقم طويل جداً")
            return True
        context.user_data["exc_phone"] = phone

        op     = context.user_data.get("exc_op", "buy")
        method = context.user_data.get("exc_method", "shamcash")
        amount = context.user_data.get("exc_amount", 0)
        amount_syp = context.user_data.get("exc_syp", 0)
        rate   = context.user_data.get("exc_rate", 0)

        # إنشاء الطلب
        order_id = db.create_currency_order(
            user_id=uid, op=op,
            amount_usdt=amount, amount_syp=amount_syp,
            method=method, rate=rate, phone=phone
        )
        log_exchange_order(uid, order_id, op, amount, method)
        context.user_data["exc_order_id"] = order_id

        op_label     = OP_LABELS[op]
        method_label = METHOD_LABELS[method]

        if op == "buy":
            # المستخدم يدفع ليرة ويستلم USDT — يرسل إشعار دفع
            text = (
                f"✅ *تم إنشاء طلبك #{order_id}*\n\n"
                f"لإتمام العملية أرسل {amount_syp:,.0f} ل.س عبر {method_label}\n"
                f"ثم أرسل صورة إشعار الدفع هنا."
            )
            await update.message.reply_text(text, parse_mode="Markdown")
            db.set_user_state(uid, EXCHANGE_PROOF)
        else:
            # المستخدم يبيع USDT — يحول USDT لعنوانا
            usdt_addr = cfg.USDT_ADDRESS
            text = (
                f"✅ *تم إنشاء طلبك #{order_id}*\n\n"
                f"حوّل `{amount} USDT` إلى العنوان التالي:\n"
                f"`{usdt_addr}`\n"
                f"الشبكة: ERC20\n\n"
                f"ثم أرسل صورة إشعار التحويل هنا."
            )
            await update.message.reply_text(text, parse_mode="Markdown")
            db.set_user_state(uid, EXCHANGE_PROOF)

        return True

    return False


async def handle_exchange_proof(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """استلام صورة إشعار الصرافة"""
    uid   = update.effective_user.id
    state = db.get_user_state(uid)

    if state != EXCHANGE_PROOF:
        return False
    if not (update.message.photo or update.message.document):
        return False

    order_id   = context.user_data.get("exc_order_id")
    order      = db.get_currency_order(order_id)
    if not order:
        return False

    op_label     = OP_LABELS[order["op"]]
    method_label = METHOD_LABELS.get(order["method"], order["method"])
    user         = db.get_user(uid)
    username     = f"@{user['username']}" if user.get("username") else "—"

    await update.message.reply_text("✅ تم استلام الإشعار! سيتم مراجعته وتنفيذ الطلب قريباً.")

    # إشعار الأدمن
    caption = (
        f"💱 *طلب صرافة جديد #{order_id}*\n\n"
        f"👤 {user.get('full_name','—')} | {username}\n"
        f"🆔 `{uid}`\n"
        f"📋 {op_label}\n"
        f"💵 {order['amount_usdt']} USDT\n"
        f"💴 {order['amount_syp']:,.0f} ل.س\n"
        f"📲 {method_label}\n"
        f"📞 {order['phone']}"
    )
    kbd = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ تم التنفيذ", callback_data=f"exc_done_{order_id}"),
        InlineKeyboardButton("❌ رفض",        callback_data=f"exc_reject_{order_id}"),
    ]])

    exc_photo = update.message.photo[-1].file_id if update.message.photo else None
    exc_doc   = update.message.document.file_id if not exc_photo and update.message.document else None
    await _notify(
        bot=context.bot,
        channel_id=cfg.CHANNEL_EXCHANGE,
        targets=cfg.ADMIN_IDS,
        photo=exc_photo,
        document=exc_doc,
        caption=caption,
        kb=kbd
    )

    db.clear_user_state(uid)
    return True


async def cb_exchange_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الأدمن يقبل طلب الصرافة"""
    q = update.callback_query
    if not is_admin(q.from_user.id):
        await q.answer("❌ غير مصرح")
        return
    order_id = int(q.data.replace("exc_done_", ""))
    order    = db.get_currency_order(order_id)
    if not order:
        await q.answer("❌ الطلب غير موجود")
        return

    db.complete_currency_order(order_id)
    await q.answer("✅ تم التنفيذ", show_alert=True)
    await q.edit_message_reply_markup(reply_markup=None)

    op_label     = OP_LABELS[order["op"]]
    method_label = METHOD_LABELS.get(order["method"], order["method"])

    try:
        await context.bot.send_message(
            chat_id=order["user_id"],
            text=(
                f"✅ *تم تنفيذ طلبك #{order_id}*\n\n"
                f"📋 {op_label}\n"
                f"💵 {order['amount_usdt']} USDT\n"
                f"📲 {method_label}\n\n"
                f"شكراً لثقتك بنا! 🙏"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Exchange done notify failed: {e}")


async def cb_exchange_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الأدمن يرفض طلب الصرافة"""
    q = update.callback_query
    if not is_admin(q.from_user.id):
        await q.answer("❌ غير مصرح")
        return
    order_id = int(q.data.replace("exc_reject_", ""))
    order    = db.get_currency_order(order_id)
    if not order:
        await q.answer("❌ الطلب غير موجود")
        return

    db.reject_currency_order(order_id)
    await q.answer("❌ تم الرفض", show_alert=True)
    await q.edit_message_reply_markup(reply_markup=None)

    try:
        await context.bot.send_message(
            chat_id=order["user_id"],
            text=(
                f"❌ *تم رفض طلبك #{order_id}*\n\n"
                f"للاستفسار تواصل مع الدعم: {cfg.SUPPORT_USERNAME}"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Exchange reject notify failed: {e}")


async def cb_reply_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    parts     = q.data.split("_")
    ticket_id = int(parts[1])
    user_id   = int(parts[2])
    db.set_user_state(q.from_user.id,
        f"REPLYING_TICKET:{json.dumps({'ticket_id': ticket_id, 'user_id': user_id})}")
    context.user_data["replying_ticket"] = {"ticket_id": ticket_id, "user_id": user_id}
    await q.message.reply_text(
        f"✏️ أرسل ردك على التذكرة #{ticket_id}:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ إلغاء", callback_data="admin_skip")
        ]])
    )


# ══════════════════════════════════════════
#   معالج الرسائل الواردة الموحد
# ══════════════════════════════════════════

async def handle_incoming(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await security_check(update, context): return
    if not update.message: return

    # فحص حجم النص
    if update.message.text and len(update.message.text) > MAX_TEXT_LEN:
        await update.message.reply_text(
            f"❌ الرسالة طويلة جداً (الحد الأقصى {MAX_TEXT_LEN} حرف)"
        )
        return

    # فحص حجم الملف
    if update.message.document and update.message.document.file_size:
        if update.message.document.file_size > MAX_FILE_SIZE:
            await update.message.reply_text("❌ حجم الملف كبير جداً (الحد الأقصى 5 MB)")
            return

    # ٠. رد على سؤال الدولة (مستخدم جديد أو تعديل)
    uid = update.effective_user.id
    # بحث الأدمن في الطلبات
    if db.get_user_state(uid) == "ADMIN_ORD_SEARCH" and is_admin(uid) and update.message.text:
        from admin_wizard import (
            cb_orders_type, _show_orders
        )
        search     = update.message.text.strip()
        order_type = context.user_data.pop("ord_search_type", "subscription")
        db.clear_user_state(uid)
        context.user_data["ord"] = {"type": order_type, "status": "all", "page": 0, "search": search}
        # نبني fake callback query بديل
        orders, total = (
            db.get_recharge_orders(page=0, per_page=5, search=search)
            if order_type == "recharge"
            else db.get_subscription_orders(page=0, per_page=5, search=search)
        )
        from admin_wizard import _build_orders_kb, _order_status_label
        type_label = "التعبئة" if order_type == "recharge" else "الاشتراكات"
        if not orders:
            await update.message.reply_text("لا توجد نتائج للبحث: " + search)
        else:
            await update.message.reply_text(
                f"نتائج البحث في {type_label}: {total} طلب",
                reply_markup=_build_orders_kb(orders, total, 0, order_type, "all", search))
        return

    if db.get_user_state(uid) == AWAITING_COUNTRY and update.message.text:
        country = update.message.text.strip()
        db.set_user_country(uid, country)
        db.clear_user_state(uid)
        lang = get_lang(uid)
        await update.message.reply_text(
            f"✅ تم! الدولة تم تحديثها إلى *{country}* 🌍",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("👤 ملفي", callback_data="profile"),
                InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
            ]])
        )
        return

    # ١. إثبات دفع (صورة أو ملف)
    if update.message.photo or update.message.document:
        if await handle_exchange_proof(update, context):
            return
        if await handle_recharge_proof(update, context):
            return
        if await handle_payment_proof(update, context):
            return

    if not update.message.text:
        return

    # FIX 8: لو المستخدم أرسل نص وهو في AWAITING_PROOF — نذكره
    if context.user_data.get(AWAITING_PROOF):
        lang = get_lang(uid)
        await update.message.reply_text(
            "📸 أرسل صورة إثبات الدفع (screenshot) وليس نصاً."
        )
        return

    # ٢. الأدمن يرسل بيانات للزبون
    if is_admin(update.effective_user.id):
        admin_uid = update.effective_user.id
        # نقرأ من context أو من DB (للمجموعات)
        sending = context.user_data.get("sending_creds")
        if not sending:
            db_state = db.get_user_state(admin_uid) or ""
            if db_state.startswith("SENDING_CREDS:"):
                import json as _json
                try:
                    sending = _json.loads(db_state.replace("SENDING_CREDS:", ""))
                except Exception:
                    sending = None
        if sending:
            user_id   = sending["user_id"]
            order_id  = sending["order_id"]
            plan_name = sending.get("plan_name", "—")
            svc_name  = sending.get("svc_name", "—")
            creds_text = update.message.text.strip()
            lang = get_lang(user_id)
            try:
                # رسالة واحدة تجمع التفعيل والبيانات
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"🎉 *تم تفعيل اشتراكك!*\n\n"
                        f"🛍️ {svc_name}\n"
                        f"📦 {plan_name}\n\n"
                        f"📬 *بيانات الدخول:*\n{creds_text}"
                    ),
                    parse_mode="Markdown"
                )
                await update.message.reply_text(f"✅ تم إرسال التفعيل والبيانات للزبون (ID: {user_id})")
            except Exception as e:
                await update.message.reply_text(f"❌ فشل الإرسال: {e}")
            context.user_data.pop("sending_creds", None)
            db.clear_user_state(admin_uid)
            return

        # الأدمن يرد على تذكرة — نقرأ من context أو DB
        replying = context.user_data.get("replying_ticket")
        if not replying:
            db_state = db.get_user_state(admin_uid) or ""
            if db_state.startswith("REPLYING_TICKET:"):
                import json as _json
                try:
                    replying = _json.loads(db_state.replace("REPLYING_TICKET:", ""))
                    context.user_data["replying_ticket"] = replying
                except Exception:
                    replying = None
        if replying:
            ticket_id = replying["ticket_id"]
            user_id   = replying["user_id"]
            reply     = update.message.text.strip()
            db.reply_ticket(ticket_id, reply)
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"📩 *رد فريق الدعم على تذكرتك #{ticket_id}:*\n\n{reply}",
                    parse_mode="Markdown"
                )
                await update.message.reply_text(f"✅ تم إرسال الرد للزبون")
            except Exception as e:
                await update.message.reply_text(f"❌ فشل الإرسال: {e}")
            context.user_data.pop("replying_ticket", None)
            db.clear_user_state(admin_uid)
            return

    # ٣. نصوص التعبئة
    if await handle_recharge_text(update, context):
        logger.debug(f"uid={uid} handled by handle_recharge_text")
        return

    # ٣ب. نصوص الصرافة
    if await handle_exchange_text(update, context):
        return

    # ٤. رسالة دعم — قبل handle_input_response لأن state DB قد يتعارض
    if await handle_support_message(update, context):
        logger.debug(f"uid={uid} handled by handle_support_message")
        return

    # ٥. إدخال ديناميكي (رقم هاتف، كمية، إلخ)
    if await handle_input_response(update, context):
        logger.debug(f"uid={uid} handled by handle_input_response")
        return

    logger.debug(f"uid={uid} state={db.get_user_state(uid)} — no handler matched")


# ══════════════════════════════════════════
#   تسجيل الـ Handlers
# ══════════════════════════════════════════


# ══════════════════════════════════════════
#   خدمة التعبئة / سيرياتيل كاش
# ══════════════════════════════════════════

async def cb_recharge_start(update: Update, context: ContextTypes.DEFAULT_TYPE, svc_id: int = None):
    """أول خطوة: اظهار سعر الصرف + المبالغ الجاهزة"""
    q = update.callback_query; await q.answer()
    lang = get_lang(q.from_user.id)
    if svc_id is None:
        svc_id = int(q.data.split("_")[1])
    svc = db.get_service(svc_id)
    if not svc:
        await q.answer("خطأ", show_alert=True); return

    rate    = db.get_recharge_rate(svc_id)
    presets = db.get_recharge_presets(svc_id)
    limits  = db.get_service_limits(svc_id)

    svc_name = svc["name_ar"] if lang == "ar" else svc["name_en"]

    if not rate:
        await q.answer("الخدمة غير متاحة حالياً", show_alert=True); return

    text = svc_name + "\n\n"
    text += "سعر الصرف الحالي:\n"
    text += "1 USDT = " + f"{rate:,.0f}" + " ل.س\n\n"
    if limits:
        if limits.get("min_amount"):
            text += "الحد الادنى: " + f"{limits['min_amount']:,.0f}" + " ل.س\n"
        if limits.get("max_amount"):
            text += "الحد الاقصى: " + f"{limits['max_amount']:,.0f}" + " ل.س\n"
    text += "\nاختر المبلغ او ادخل يدوياً:"

    btns = []
    if presets:
        row = []
        for i, p in enumerate(presets):
            row.append(InlineKeyboardButton(
                f"{int(p['rate']):,} ل.س",
                callback_data="rchamt_" + str(svc_id) + "_" + str(int(p["rate"]))
            ))
            if len(row) == 2:
                btns.append(row); row = []
        if row: btns.append(row)

    btns.append([InlineKeyboardButton("✏️ مبلغ يدوي", callback_data="rchamtcustom_" + str(svc_id))])
    btns.append([InlineKeyboardButton(t("back", lang), callback_data="services")])

    save_flow(q.from_user.id, {"svc_id": svc_id, "step": "amount"})
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(btns))


async def cb_recharge_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختيار مبلغ جاهز"""
    q = update.callback_query; await q.answer()
    uid    = q.from_user.id
    lang   = get_lang(uid)
    parts  = q.data.split("_")
    svc_id = int(parts[1])
    amount = int(parts[2])

    rate = db.get_recharge_rate(svc_id)
    usdt = round(amount / rate, 4)

    text = (
        "ملخص الطلب:\n\n"
        "المبلغ: " + f"{amount:,}" + " ل.س\n"
        "ستدفع: " + str(usdt) + " USDT\n\n"
        "ادخل رقم هاتفك:"
    )
    save_flow(uid, {"svc_id": svc_id, "amount": amount, "usdt": usdt, "step": "phone"})
    db.set_user_state(uid, "RECHARGE_PHONE")
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"back_svc_{svc_id}"),
         InlineKeyboardButton("❌ إلغاء", callback_data="services")]
    ]))


async def cb_recharge_custom_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """طلب مبلغ يدوي"""
    q = update.callback_query; await q.answer()
    uid    = q.from_user.id
    svc_id = int(q.data.split("_")[1])
    save_flow(uid, {"svc_id": svc_id, "step": "custom_amount"})
    db.set_user_state(uid, "RECHARGE_AMOUNT")
    limits = db.get_service_limits(svc_id)
    hint = ""
    if limits:
        if limits.get("min_amount"): hint += " (الحد الادنى: " + f"{limits['min_amount']:,.0f}" + " ل.س)"
        if limits.get("max_amount"): hint += " (الحد الاقصى: " + f"{limits['max_amount']:,.0f}" + " ل.س)"
    await q.edit_message_text(
        "ادخل المبلغ بالليرة السورية:" + hint,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_svccat_recharge"),
             InlineKeyboardButton("❌ إلغاء", callback_data="services")]
        ]))



async def handle_recharge_proof(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    uid   = update.effective_user.id
    state = db.get_user_state(uid)
    if state != "RECHARGE_PROOF":
        return False

    flow     = load_flow(uid)
    order_id = flow.get("order_id")
    if not order_id:
        return False

    # احفظ file_id الصورة في الطلب
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document:
        file_id = update.message.document.file_id
    else:
        return False

    # حدّث الطلب بـ file_id
    db.execute(
        "UPDATE orders SET user_inputs=%s WHERE id=%s",
        (json.dumps({"proof_file_id": file_id}), order_id)
    )
    db.clear_user_state(uid)
    clear_flow(uid)

    await update.message.reply_text(
        "✅ تم استلام إشعار الدفع. سنتحقق ونعلمك فور اكتمال التعبئة.")

    # إشعار الأدمن مع الصورة
    from config import Config
    cfg = Config()
    order = db.fetchone("""
        SELECT o.*, u.full_name, u.username, s.name_ar as svc_ar
        FROM orders o JOIN users u ON o.user_id=u.id JOIN services s ON o.service_id=s.id
        WHERE o.id=%s
    """, (order_id,))
    if order:
        admin_text = (
            "🔔 طلب تعبئة جديد #" + str(order_id) + "\n\n"
            "👤 " + order["full_name"] + " (@" + (order.get("username") or "—") + ")\n"
            "📱 " + order["svc_ar"] + "\n"
            "💵 " + f"{order['amount_local']:,.0f}" + " ل.س\n"
            "💳 " + str(order["amount"]) + " USDT\n"
            "📞 `" + (order.get("phone_number") or "—") + "`"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ تم التنفيذ", callback_data="rchdone_" + str(order_id) + "_" + str(uid)),
            InlineKeyboardButton("❌ رفض",        callback_data="rchreject_" + str(order_id) + "_" + str(uid))
        ]])
        await _notify(
            bot=context.bot,
            channel_id=cfg.CHANNEL_RECHARGE,
            targets=cfg.ADMIN_IDS,
            photo=file_id,
            caption=admin_text,
            kb=kb
        )
    return True

async def handle_recharge_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة النصوص المتعلقة بالتعبئة"""
    uid   = update.effective_user.id
    state = db.get_user_state(uid)
    if state not in ("RECHARGE_AMOUNT", "RECHARGE_PHONE"):
        return False

    flow = load_flow(uid)
    lang = get_lang(uid)
    svc_id = flow.get("svc_id")

    if state == "RECHARGE_AMOUNT":
        text = update.message.text.strip().replace(",", "").replace(" ", "")
        if not text.replace(".", "").isdigit():
            await update.message.reply_text("❌ أرسل رقماً صحيحاً مثل: 1000")
            return True
        try:
            amount = float(text)
        except Exception:
            await update.message.reply_text("❌ أرسل رقماً صحيحاً مثل: 1000")
            return True
        if amount <= 0:
            await update.message.reply_text("❌ المبلغ يجب أن يكون أكبر من صفر")
            return True
        # FIX 10: تحقق من الحدود
        flow = get_flow(uid) or {}
        svc_id = flow.get("svc_id")
        if svc_id:
            limits = db.get_service_limits(svc_id)
            if limits:
                if limits.get("min_amount") and amount < limits["min_amount"]:
                    await update.message.reply_text(f"❌ الحد الأدنى {limits['min_amount']:,.0f} ل.س")
                    return True
                if limits.get("max_amount") and amount > limits["max_amount"]:
                    await update.message.reply_text(f"❌ الحد الأقصى {limits['max_amount']:,.0f} ل.س")
                    return True
        limits = db.get_service_limits(svc_id)
        if limits:
            mn = limits.get("min_amount") or 0
            mx = limits.get("max_amount") or 0
            if mn and amount < mn:
                await update.message.reply_text("الحد الادنى هو " + f"{mn:,.0f}" + " ل.س")
                return True
            if mx and amount > mx:
                await update.message.reply_text("الحد الاقصى هو " + f"{mx:,.0f}" + " ل.س")
                return True
        rate = db.get_recharge_rate(svc_id)
        usdt = round(amount / rate, 4)
        save_flow(uid, {"svc_id": svc_id, "amount": amount, "usdt": usdt, "step": "phone"})
        db.set_user_state(uid, "RECHARGE_PHONE")
        await update.message.reply_text(
            "المبلغ: " + f"{amount:,.0f}" + " ل.س = " + str(usdt) + " USDT\n\nادخل رقم هاتفك:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع", callback_data="back_svccat_recharge"),
                 InlineKeyboardButton("❌ إلغاء", callback_data="services")]
            ]))
        return True

    if state == "RECHARGE_PHONE":
        phone = update.message.text.strip()
        if not validate_phone(phone):
            await update.message.reply_text("الرقم غير صحيح. مثال: 0991234567 او +963991234567")
            return True

        # تحقق من الحد اليومي
        limits = db.get_service_limits(svc_id)
        if limits and limits.get("daily_limit"):
            count = db.count_today_recharge_orders(uid, svc_id)
            if count >= limits["daily_limit"]:
                await update.message.reply_text(
                    "وصلت للحد اليومي من الطلبات (" + str(limits["daily_limit"]) + " طلبات). حاول غداً.")
                db.clear_user_state(uid)
                clear_flow(uid)
                return True

        amount = flow.get("amount", 0)
        usdt   = flow.get("usdt", 0)
        svc    = db.get_service(svc_id)

        # تأكيد نهائي
        confirm_text = (
            "تأكيد الطلب:\n\n"
            "الخدمة: " + svc["name_ar"] + "\n"
            "المبلغ: " + f"{amount:,.0f}" + " ل.س\n"
            "ستدفع: " + str(usdt) + " USDT\n"
            "الرقم: " + phone
        )
        save_flow(uid, {"svc_id": svc_id, "amount": amount, "usdt": usdt, "phone": phone, "step": "confirm"})
        db.set_user_state(uid, "RECHARGE_CONFIRM")
        await update.message.reply_text(
            confirm_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ تأكيد", callback_data="rchconfirm_yes"),
                 InlineKeyboardButton("🔙 رجوع", callback_data="back_svccat_recharge"),
                 InlineKeyboardButton("❌ إلغاء", callback_data="services")]
            ]))
        return True

    return False


async def cb_recharge_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id

    if q.data == "rchconfirm_no":
        db.clear_user_state(uid)
        clear_flow(uid)
        await q.edit_message_text("تم الالغاء.")
        return

    flow   = load_flow(uid)
    svc_id = flow["svc_id"]
    amount = flow["amount"]
    usdt   = flow["usdt"]
    phone  = flow["phone"]

    from config import Config
    cfg = Config()

    order_id = db.create_recharge_order(uid, svc_id, usdt, amount, phone)
    log_recharge_order(uid, order_id, amount, phone)
    db.clear_user_state(uid)
    clear_flow(uid)

    usdt_addr = cfg.USDT_ADDRESS
    db.set_user_state(uid, "RECHARGE_PROOF")
    save_flow(uid, {"order_id": order_id, "svc_id": svc_id, "amount": amount, "usdt": usdt, "phone": phone})
    await q.edit_message_text(
        "تعليمات الدفع:\n\n"
        "المبلغ:\n"
        "`" + str(usdt) + "`\n\n"
        "عنوان المحفظة:\n"
        "`" + usdt_addr + "`\n\n"
        "بعد الدفع، أرسل صورة إشعار التحويل هنا.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_svccat_recharge"),
             InlineKeyboardButton("❌ إلغاء", callback_data="main_menu")]
        ]))


async def cb_recharge_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    order_id = int(q.data.split("_")[1])
    await q.edit_message_text(
        "جاري التنفيذ...\n\nسنعلمك عند اكتمال التعبئة.")

    # إشعار الأدمن
    from config import Config
    cfg = Config()
    order = db.fetchone("""
        SELECT o.*, u.full_name, u.username, s.name_ar as svc_ar
        FROM orders o JOIN users u ON o.user_id=u.id JOIN services s ON o.service_id=s.id
        WHERE o.id=%s
    """, (order_id,))
    if order:
        admin_text = (
            "طلب تعبئة جديد #" + str(order_id) + "\n\n"
            "المستخدم: " + order["full_name"] + " (@" + (order.get("username") or "—") + ")\n"
            "الخدمة: " + order["svc_ar"] + "\n"
            "المبلغ: " + f"{order['amount_local']:,.0f}" + " ل.س\n"
            "USDT: " + str(order["amount"]) + "\n"
            "الرقم: `" + (order.get("phone_number") or "—") + "`"
        )
        for admin_id in cfg.ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_text,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("تم التنفيذ", callback_data="rchdone_" + str(order_id) + "_" + str(order["user_id"])),
                        InlineKeyboardButton("رفض",        callback_data="rchreject_" + str(order_id) + "_" + str(order["user_id"]))
                    ]]))
            except Exception:
                pass


async def cb_recharge_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    parts    = q.data.split("_")
    order_id = int(parts[1])
    user_id  = int(parts[2])
    order    = db.fetchone("SELECT * FROM orders WHERE id=%s", (order_id,))
    if not order:
        await q.edit_message_text("الطلب غير موجود"); return
    db.complete_recharge_order(order_id)
    await q.edit_message_text("تم تنفيذ الطلب #" + str(order_id))
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "تمت التعبئة\n\n"
                "المبلغ: " + f"{order['amount_local']:,.0f}" + " ل.س\n"
                "الرقم: " + (order.get("phone_number") or "—") + "\n\n"
                "شكراً لثقتك بنا!"
            ))
    except Exception:
        pass


async def cb_recharge_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    parts    = q.data.split("_")
    order_id = int(parts[1])
    user_id  = int(parts[2])
    db.reject_recharge_order(order_id)
    await q.edit_message_text("تم رفض الطلب #" + str(order_id))
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text="تم رفض طلب التعبئة #" + str(order_id) + "\nللاستفسار تواصل مع الدعم.")
    except Exception:
        pass


def register_handlers(app: Application):
    from admin_wizard import get_wizard_handlers

    # زر الرجوع المركزي — group=-1 يعني أعلى أولوية من ConversationHandler
    app.add_handler(CallbackQueryHandler(cb_go_back, pattern=r"^back_"), group=-1)

    # edit_country أولاً قبل الـ wizards
    app.add_handler(CallbackQueryHandler(cb_edit_country, pattern="^edit_country$"))

    # Wizards الأدمن
    for h in get_wizard_handlers():
        app.add_handler(h)

    # أوامر
    app.add_handler(CommandHandler("start",   cmd_start))
    from admin_wizard import cmd_admin
    app.add_handler(CommandHandler("admin", cmd_admin))

    # Callbacks المستخدم
    app.add_handler(CallbackQueryHandler(cb_main_menu,      pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(cb_set_lang,       pattern="^lang_(ar|en)$"))
    app.add_handler(CallbackQueryHandler(cb_services,          pattern="^services$"))
    app.add_handler(CallbackQueryHandler(cb_services_category, pattern="^svccat_"))
    app.add_handler(CallbackQueryHandler(cb_service_detail,    pattern=r"^svc_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_variant_detail,       pattern=r"^variant_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_recharge_amount,       pattern=r"^rchamt_"))
    app.add_handler(CallbackQueryHandler(cb_recharge_custom_amount,pattern=r"^rchamtcustom_"))
    app.add_handler(CallbackQueryHandler(cb_recharge_confirm,      pattern=r"^rchconfirm_"))
    app.add_handler(CallbackQueryHandler(cb_recharge_paid,         pattern=r"^rchpaid_"))
    app.add_handler(CallbackQueryHandler(cb_recharge_done,         pattern=r"^rchdone_"))
    app.add_handler(CallbackQueryHandler(cb_recharge_reject,       pattern=r"^rchreject_"))
    app.add_handler(CallbackQueryHandler(cb_plan_detail,    pattern=r"^plan_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_plan_option,    pattern=r"^opt_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_checkout,       pattern=r"^checkout_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_pay_method,     pattern=r"^paymethod_"))
    app.add_handler(CallbackQueryHandler(cb_send_proof,     pattern=r"^sendproof_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_my_subs,        pattern="^my_subs$"))
    app.add_handler(CallbackQueryHandler(cb_profile,          pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(cb_recharge_history, pattern="^recharge_history$"))
    app.add_handler(CallbackQueryHandler(cb_support,        pattern="^support$"))
    # تصريف العملات
    app.add_handler(CallbackQueryHandler(cb_exchange_start,  pattern="^exchange$"))
    app.add_handler(CallbackQueryHandler(cb_exchange_op,     pattern="^exc_op_"))
    app.add_handler(CallbackQueryHandler(cb_exchange_method, pattern="^exc_method_"))
    app.add_handler(CallbackQueryHandler(cb_exchange_done,   pattern="^exc_done_"))
    app.add_handler(CallbackQueryHandler(cb_exchange_reject, pattern="^exc_reject_"))
    app.add_handler(CallbackQueryHandler(cb_reply_ticket,   pattern=r"^replyticket_\d+_\d+$"))


    # Callbacks الأدمن
    app.add_handler(CallbackQueryHandler(cb_approve_order,  pattern=r"^approve_\d+_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_reject_order,   pattern=r"^reject_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_send_creds,     pattern=r"^sendcreds_\d+_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_skip,     pattern="^admin_skip$"))

    # Callbacks لوحة الأدمن
    # ملاحظة: wiz_orders و wiz_variants و wiz_tickets مسجلة داخل get_wizard_handlers()
    from admin_wizard import (cb_list_services, cb_admin_back,
                              cb_quickdel_svc, cb_quickdel_confirm)
    app.add_handler(CallbackQueryHandler(cb_list_services,    pattern="^wiz_list$"))
    app.add_handler(CallbackQueryHandler(cb_admin_back,       pattern="^admin_back$"))
    app.add_handler(CallbackQueryHandler(cb_quickdel_svc,     pattern=r"^quickdel_svc_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_quickdel_confirm, pattern=r"^quickdel_confirm_\d+$"))

    # رسائل واردة
    app.add_handler(MessageHandler(
        (filters.PHOTO | filters.Document.ALL | filters.TEXT) & ~filters.COMMAND,
        handle_incoming
    ))


# /admin يستخدم cmd_admin مباشرة من admin_wizard

