"""
🤖 معالجات البوت الرئيسية - User Handlers
"""
import json
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from database import Database
from config import Config
from i18n import t

import re
logger = logging.getLogger(__name__)
db  = Database()
cfg = Config()

# ══ حالات الانتظار ══
AWAITING_PROOF   = "awaiting_proof"
AWAITING_SUPPORT = "awaiting_support"
AWAITING_INPUT   = "awaiting_input"
AWAITING_COUNTRY = "awaiting_country"

# ══ Validation ══
def validate_email(email: str) -> bool:
    """التحقق من صحة الإيميل بالمعايير الدولية"""
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email)) and len(email) <= 254

def validate_phone(phone: str) -> bool:
    """التحقق من صحة رقم الهاتف مع رمز الدولة"""
    # يقبل: +963xxxxxxxxx أو 00963xxxxxxxxx
    pattern = r'^(\+|00)[1-9]\d{6,14}$'
    cleaned = phone.replace(' ', '').replace('-', '')
    return bool(re.match(pattern, cleaned))


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

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user = update.effective_user
    is_new = db.ensure_user_new(user.id, user.username or "", user.full_name)
    lang = get_lang(user.id)

    # مستخدم جديد — اسأله عن دولته
    if is_new:
        context.application.user_data.setdefault(user.id, {})[AWAITING_COUNTRY] = True
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
    lang     = get_lang(q.from_user.id)
    services = db.get_services()

    if not services:
        await q.edit_message_text(t("no_services", lang),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t("back", lang), callback_data="main_menu")
            ]]))
        return

    # تجميع الخدمات حسب نوعها
    TYPE_EMOJI = {"subscription": "📺", "recharge": "📱", "exchange": "💱"}
    btns = []
    for svc in services:
        emoji = TYPE_EMOJI.get(svc.get("type_name", ""), "🔹")
        name  = svc["name_ar"] if lang == "ar" else svc["name_en"]
        btns.append([InlineKeyboardButton(f"{emoji} {name}", callback_data=f"svc_{svc['id']}")])

    btns.append([InlineKeyboardButton(t("back", lang), callback_data="main_menu")])
    await q.edit_message_text(t("services_title", lang), parse_mode="Markdown",
                               reply_markup=InlineKeyboardMarkup(btns))


async def cb_service_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang   = get_lang(q.from_user.id)
    svc_id = int(q.data.split("_")[1])
    svc    = db.get_service(svc_id)
    plans  = db.get_plans(svc_id)

    if not svc:
        await q.answer("❌", show_alert=True); return

    name = svc["name_ar"] if lang == "ar" else svc["name_en"]
    desc = svc.get("description_ar", "") if lang == "ar" else svc.get("description_en", "")
    type_name = svc.get("type_name", "subscription")

    text = f"🔵 *{name}*"
    if desc:
        text += f"\n\n{desc}"

    # للخدمات التبادلية — اعرض سعر الصرف
    if type_name == "exchange":
        rate = db.get_exchange_rate(svc_id)
        if rate:
            text += f"\n\n💱 سعر الصرف: `1 {rate['unit']} = {rate['rate']:,.0f} ل.س`"
            text += f"\n🕐 آخر تحديث: {fmt_date(rate['updated_at'])}"

    if not plans:
        btns = [[InlineKeyboardButton(t("back", lang), callback_data="services")]]
        await q.edit_message_text(text + "\n\n_(لا توجد خطط متاحة حالياً)_",
                                   parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))
        return

    btns = []
    for p in plans:
        pname = p["name_ar"] if lang == "ar" else p["name_en"]
        btns.append([InlineKeyboardButton(
            f"📦 {pname} — {p['price']} USDT",
            callback_data=f"plan_{p['id']}"
        )])

    btns.append([InlineKeyboardButton(t("back", lang), callback_data="services")])
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))


# ══════════════════════════════════════════
#   تفاصيل الخطة + الخيارات الديناميكية
# ══════════════════════════════════════════

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

    text = f"🔵 *{svc_name}*\n📦 *{plan_name}*\n💰 {plan['price']} USDT"
    if plan["duration_days"] > 0:
        text += f" / {plan['duration_days']} يوم"
    if feats_text:
        text += f"\n\n{feats_text}"

    # خيارات ديناميكية
    options = db.get_plan_options(plan_id)
    if options:
        context.user_data["flow"] = {
            "plan_id":  plan_id,
            "options":  options,
            "step":     0,
            "answers":  {},
            "inputs":   {}
        }
        await _ask_next_option(q, context, lang, text)
    else:
        context.user_data["flow"] = {"plan_id": plan_id, "answers": {}, "inputs": {}}
        await _show_checkout(q, context, lang, plan)


async def _ask_next_option(q_or_msg, context, lang, prefix_text=""):
    flow    = context.user_data["flow"]
    options = flow["options"]
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
        prompt = f"{prefix_text}\n\n🔸 *{opt['question']}*" if prefix_text else f"🔸 *{opt['question']}*"
        if hasattr(q_or_msg, "edit_message_text"):
            await q_or_msg.edit_message_text(prompt, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(t("cancel", lang), callback_data="main_menu")
                ]]))
        else:
            await q_or_msg.reply_text(prompt, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(t("cancel", lang), callback_data="main_menu")
                ]]))
    else:
        # خيارات أزرار
        btns = [[InlineKeyboardButton(c, callback_data=f"opt_{step}_{i}")]
                for i, c in enumerate(opt["choices"])]
        prompt = f"{prefix_text}\n\n🔸 *{opt['question']}*" if prefix_text else f"🔸 *{opt['question']}*"
        if hasattr(q_or_msg, "edit_message_text"):
            await q_or_msg.edit_message_text(prompt, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(btns))
        else:
            await q_or_msg.reply_text(prompt, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(btns))


async def cb_plan_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang  = get_lang(q.from_user.id)
    parts = q.data.split("_")
    step  = int(parts[1])
    cidx  = int(parts[2])

    flow = context.user_data.get("flow")
    if not flow:
        await q.answer("❌ انتهت الجلسة", show_alert=True); return

    opt    = flow["options"][step]
    choice = opt["choices"][cidx]
    flow["answers"][opt["question"]] = choice
    flow["step"] = step + 1

    # لو اختار "على إيميلك" — اطلب الإيميل تلقائياً
    choice_lower = choice.strip()
    EMAIL_TRIGGERS = ["على إيميلك", "ايميلي", "إيميلي", "my email", "my account"]
    if any(t in choice_lower for t in EMAIL_TRIGGERS):
        context.user_data[AWAITING_INPUT] = {"field": "email", "label": "📧 أدخل إيميلك:"}
        await q.edit_message_text(
            "📧 *أدخل إيميلك:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t("cancel", lang), callback_data="main_menu")
            ]])
        )
        return

    await _ask_next_option(q, context, lang)


async def handle_input_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يستقبل نص المستخدم لأي حقل ديناميكي مع validation"""
    awaiting = context.user_data.get(AWAITING_INPUT)
    flow     = context.user_data.get("flow")

    if awaiting and flow:
        field = awaiting["field"]
        value = update.message.text.strip()
        lang  = get_lang(update.effective_user.id)

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
    q = update.callback_query; await q.answer()
    lang    = get_lang(q.from_user.id)
    plan_id = int(q.data.split("_")[1])
    plan    = db.get_plan(plan_id)
    flow    = context.user_data.get("flow", {})

    user_options = flow.get("answers", {})
    user_inputs  = flow.get("inputs", {})

    order_id = db.create_order(
        q.from_user.id, plan_id, plan["service_id"],
        plan["price"], user_options, user_inputs
    )
    context.user_data["last_order_id"] = order_id

    svc_name  = plan["service_name_ar"] if lang == "ar" else plan["service_name_en"]
    plan_name = plan["name_ar"] if lang == "ar" else plan["name_en"]

    text = t("payment_details", lang,
             service=svc_name, plan=plan_name,
             amount=plan["price"], network=cfg.USDT_NETWORK,
             address=cfg.USDT_ADDRESS, order_id=order_id)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 إرسال إثبات الدفع | Send Proof",
                              callback_data=f"sendproof_{order_id}_{plan_id}")],
        [InlineKeyboardButton(t("back", lang), callback_data=f"plan_{plan_id}")]
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
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(t("cancel", lang), callback_data=f"checkout_{plan_id}")
        ]])
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
    username  = f"@{user['username']}" if user.get("username") else "—"

    admin_text = (
        f"🔔 *طلب دفع جديد*\n\n"
        f"👤 المستخدم: {user['full_name']}\n"
        f"🆔 ID: `{update.effective_user.id}`\n"
        f"📱 يوزر: {username}\n\n"
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
    for admin_id in cfg.ADMIN_IDS:
        try:
            if photo:
                await context.bot.send_photo(
                    chat_id=admin_id, photo=photo,
                    caption=admin_text, parse_mode="Markdown",
                    reply_markup=admin_kb
                )
            else:
                await context.bot.send_document(
                    chat_id=admin_id,
                    document=update.message.document.file_id,
                    caption=admin_text, parse_mode="Markdown",
                    reply_markup=admin_kb
                )
        except Exception as e:
            logger.error(f"Admin notify failed: {e}")

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
    plan     = db.get_plan(plan_id)

    db.complete_order(order_id)
    db.create_subscription(
        user_id, plan_id, order_id, plan["service_id"],
        plan["duration_days"]
    )

    # اسأل الأدمن إذا بدو يبعت بيانات الآن
    await q.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 إرسال بيانات للزبون الآن",
                              callback_data=f"sendcreds_{user_id}_{order_id}_{plan_id}")],
        [InlineKeyboardButton("⏭️ تخطي", callback_data="admin_skip")]
    ]))

    # إشعار الزبون
    lang = get_lang(user_id)
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=t("sub_activated", lang,
                   service=plan["service_name_ar"],
                   plan=plan["name_ar"],
                   credentials=""),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"User notify failed: {e}")


async def cb_reject_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return

    parts    = q.data.split("_")
    order_id = int(parts[1])
    user_id  = int(parts[2])

    db.update_order_status(order_id, "rejected")
    await q.edit_message_caption(caption=f"❌ *تم رفض الطلب #{order_id}*", parse_mode="Markdown")

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
    """الأدمن يضغط 'إرسال بيانات' من الطلب"""
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return

    parts    = q.data.split("_")
    user_id  = int(parts[1])
    order_id = int(parts[2])
    plan_id  = int(parts[3])

    context.user_data["sending_creds"] = {
        "user_id":  user_id,
        "order_id": order_id,
        "plan_id":  plan_id
    }

    await q.message.reply_text(
        f"✏️ أرسل البيانات التي تريد إرسالها للزبون (ID: `{user_id}`)\n\n"
        f"مثال:\n`إيميل: test@gmail.com\nكلمة السر: 123456`\n\n"
        f"أو أرسل أي نص تريده:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ إلغاء", callback_data="admin_skip")
        ]])
    )


async def cb_admin_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data.pop("sending_creds", None)
    await q.edit_message_reply_markup(reply_markup=None)


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
            [InlineKeyboardButton("🌍 تعديل الدولة", callback_data="edit_country")],
            [InlineKeyboardButton(t("back", lang),   callback_data="main_menu")]
        ]))


# ══════════════════════════════════════════
#   تعديل الدولة
# ══════════════════════════════════════════

async def cb_edit_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang = get_lang(q.from_user.id)
    context.application.user_data.setdefault(q.from_user.id, {})[AWAITING_COUNTRY] = True
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
    await q.edit_message_text(
        t("support_prompt", lang),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(t("cancel", lang), callback_data="main_menu")
        ]])
    )


async def handle_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get(AWAITING_SUPPORT):
        return False

    lang      = get_lang(update.effective_user.id)
    ticket_id = db.create_ticket(update.effective_user.id, update.message.text)
    user      = db.get_user(update.effective_user.id)
    username  = f"@{user['username']}" if user.get("username") else "—"

    await update.message.reply_text(t("support_sent", lang), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(t("main_menu", lang), callback_data="main_menu")
        ]]))

    for admin_id in cfg.ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"🎫 *تذكرة دعم جديدة #{ticket_id}*\n\n"
                    f"👤 {user['full_name']} | {username}\n"
                    f"🆔 `{update.effective_user.id}`\n\n"
                    f"💬 {update.message.text}"
                ),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("💬 رد", callback_data=f"replyticket_{ticket_id}_{update.effective_user.id}")
                ]])
            )
        except Exception as e:
            logger.error(f"Ticket notify failed: {e}")

    context.user_data.pop(AWAITING_SUPPORT, None)
    return True


async def cb_reply_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    parts     = q.data.split("_")
    ticket_id = int(parts[1])
    user_id   = int(parts[2])
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
    if not update.message: return

    # ٠. رد على سؤال الدولة (مستخدم جديد أو تعديل)
    uid = update.effective_user.id
    udata = context.application.user_data.get(uid, {})
    if udata.get(AWAITING_COUNTRY) and update.message.text:
        country = update.message.text.strip()
        db.set_user_country(uid, country)
        context.application.user_data.get(uid, {}).pop(AWAITING_COUNTRY, None)
        lang = get_lang(uid)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 الخدمات | Services",  callback_data="services"),
             InlineKeyboardButton("📋 اشتراكاتي | My Subs", callback_data="my_subs")],
            [InlineKeyboardButton("👤 ملفي | Profile",       callback_data="profile"),
             InlineKeyboardButton("📨 الدعم | Support",      callback_data="support")],
        ])
        await update.message.reply_text(
            f"✅ تم! أنت من *{country}*\n\nاختر من القائمة أدناه:",
            parse_mode="Markdown", reply_markup=kb
        )
        return

    # ١. إثبات دفع (صورة أو ملف)
    if update.message.photo or update.message.document:
        if await handle_payment_proof(update, context):
            return

    if not update.message.text:
        return

    # ٢. الأدمن يرسل بيانات للزبون
    if is_admin(update.effective_user.id):
        sending = context.user_data.get("sending_creds")
        if sending:
            user_id  = sending["user_id"]
            order_id = sending["order_id"]
            text     = update.message.text.strip()
            lang     = get_lang(user_id)
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"📬 *بيانات طلبك #{order_id}:*\n\n{text}",
                    parse_mode="Markdown"
                )
                await update.message.reply_text(f"✅ تم إرسال البيانات للزبون (ID: {user_id})")
            except Exception as e:
                await update.message.reply_text(f"❌ فشل الإرسال: {e}")
            context.user_data.pop("sending_creds", None)
            return

        # الأدمن يرد على تذكرة
        replying = context.user_data.get("replying_ticket")
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
            return

    # ٣. إدخال ديناميكي (رقم هاتف، كمية، إلخ)
    if await handle_input_response(update, context):
        return

    # ٤. رسالة دعم
    if await handle_support_message(update, context):
        return


# ══════════════════════════════════════════
#   تسجيل الـ Handlers
# ══════════════════════════════════════════

def register_handlers(app: Application):
    from admin_wizard import get_wizard_handlers

    # Wizards الأدمن أولاً
    for h in get_wizard_handlers():
        app.add_handler(h)

    # أوامر
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("admin",   _cmd_admin_shortcut))

    # Callbacks المستخدم
    app.add_handler(CallbackQueryHandler(cb_main_menu,      pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(cb_set_lang,       pattern="^lang_(ar|en)$"))
    app.add_handler(CallbackQueryHandler(cb_services,       pattern="^services$"))
    app.add_handler(CallbackQueryHandler(cb_service_detail, pattern=r"^svc_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_plan_detail,    pattern=r"^plan_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_plan_option,    pattern=r"^opt_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_checkout,       pattern=r"^checkout_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_send_proof,     pattern=r"^sendproof_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_my_subs,        pattern="^my_subs$"))
    app.add_handler(CallbackQueryHandler(cb_profile,        pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(cb_support,        pattern="^support$"))
    app.add_handler(CallbackQueryHandler(cb_reply_ticket,   pattern=r"^replyticket_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_edit_country,   pattern="^edit_country$"))

    # Callbacks الأدمن
    app.add_handler(CallbackQueryHandler(cb_approve_order,  pattern=r"^approve_\d+_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_reject_order,   pattern=r"^reject_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_send_creds,     pattern=r"^sendcreds_\d+_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_skip,     pattern="^admin_skip$"))

    # Callbacks لوحة الأدمن — كانت ناقصة
    from admin_wizard import (cb_list_services, cb_admin_back, cb_orders, cb_tickets,
                              cb_quickdel_svc, cb_quickdel_confirm)
    app.add_handler(CallbackQueryHandler(cb_list_services,    pattern="^wiz_list$"))
    app.add_handler(CallbackQueryHandler(cb_admin_back,       pattern="^admin_back$"))
    app.add_handler(CallbackQueryHandler(cb_orders,           pattern="^wiz_orders$"))
    app.add_handler(CallbackQueryHandler(cb_tickets,          pattern="^wiz_tickets$"))
    app.add_handler(CallbackQueryHandler(cb_quickdel_svc,     pattern=r"^quickdel_svc_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_quickdel_confirm, pattern=r"^quickdel_confirm_\d+$"))

    # رسائل واردة
    app.add_handler(MessageHandler(
        (filters.PHOTO | filters.Document.ALL | filters.TEXT) & ~filters.COMMAND,
        handle_incoming
    ))


async def _cmd_admin_shortcut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from admin_wizard import cmd_admin
    await cmd_admin(update, context)

