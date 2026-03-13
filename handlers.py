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

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user = update.effective_user
    is_new = db.ensure_user_new(user.id, user.username or "", user.full_name)
    lang = get_lang(user.id)

    # مستخدم جديد — اسأله عن دولته
    if is_new:
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

    if not svc:
        await q.answer("❌", show_alert=True); return

    type_name = svc.get("type_name", "subscription")

    # خدمة التعبئة — flow خاص
    if type_name == "recharge":
        await cb_recharge_start(update, context)
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
            btns.append([InlineKeyboardButton("📦 " + pname + " — " + str(p["price"]) + " USDT",
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
    btns = [[InlineKeyboardButton(
        f"📦 {p['name_ar'] if lang=='ar' else p['name_en']} — {p['price']} USDT",
        callback_data=f"plan_{p['id']}"
    )] for p in plans]
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

    text = f"🔵 *{svc_name}*\n📦 *{plan_name}*\n💰 {plan['price']} USDT"
    if plan["duration_days"] > 0:
        text += f" / {plan['duration_days']} يوم"
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

    flow = context.user_data.get("flow") or load_flow(q.from_user.id)
    if not flow:
        await q.answer("❌ انتهت الجلسة، اضغط /start", show_alert=True); return
    context.user_data["flow"] = flow

    opt    = flow["options"][step]
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
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t("cancel", lang), callback_data="main_menu")
            ]])
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

    lang      = get_lang(uid)
    ticket_id = db.create_ticket(uid, update.message.text)
    user      = db.get_user(uid)
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
                    f"🆔 `{uid}`\n\n"
                    f"💬 {update.message.text}"
                ),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("💬 رد", callback_data=f"replyticket_{ticket_id}_{uid}")
                ]])
            )
        except Exception as e:
            logger.error(f"Ticket notify failed: {e}")

    context.user_data.pop(AWAITING_SUPPORT, None)
    db.clear_user_state(uid)
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
        if await handle_recharge_proof(update, context):
            return
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

    # ٣. نصوص التعبئة
    if await handle_recharge_text(update, context):
        return

    # ٤. إدخال ديناميكي (رقم هاتف، كمية، إلخ)
    if await handle_input_response(update, context):
        return

    # ٤. رسالة دعم
    if await handle_support_message(update, context):
        return


# ══════════════════════════════════════════
#   تسجيل الـ Handlers
# ══════════════════════════════════════════


# ══════════════════════════════════════════
#   خدمة التعبئة / سيرياتيل كاش
# ══════════════════════════════════════════

async def cb_recharge_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أول خطوة: اظهار سعر الصرف + المبالغ الجاهزة"""
    q = update.callback_query; await q.answer()
    lang   = get_lang(q.from_user.id)
    svc_id = int(q.data.split("_")[1])
    svc    = db.get_service(svc_id)
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
        [InlineKeyboardButton("الغاء", callback_data="services")]
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
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("الغاء", callback_data="services")]]))



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
        for admin_id in cfg.ADMIN_IDS:
            try:
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=file_id,
                    caption=admin_text,
                    parse_mode="Markdown",
                    reply_markup=kb)
            except Exception:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=admin_text,
                        parse_mode="Markdown",
                        reply_markup=kb)
                except Exception:
                    pass
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
        text = update.message.text.strip().replace(",", "")
        try:
            amount = float(text)
        except Exception:
            await update.message.reply_text("ارسل رقماً صحيحاً مثل: 1000")
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
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("الغاء", callback_data="services")]]))
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
                [InlineKeyboardButton("تأكيد", callback_data="rchconfirm_yes"),
                 InlineKeyboardButton("الغاء", callback_data="rchconfirm_no")]
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
            [InlineKeyboardButton("❌ إلغاء", callback_data="rchconfirm_no")]
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

    # edit_country أولاً قبل الـ wizards
    app.add_handler(CallbackQueryHandler(cb_edit_country, pattern="^edit_country$"))

    # Wizards الأدمن
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
    app.add_handler(CallbackQueryHandler(cb_send_proof,     pattern=r"^sendproof_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_my_subs,        pattern="^my_subs$"))
    app.add_handler(CallbackQueryHandler(cb_profile,          pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(cb_recharge_history, pattern="^recharge_history$"))
    app.add_handler(CallbackQueryHandler(cb_support,        pattern="^support$"))
    app.add_handler(CallbackQueryHandler(cb_reply_ticket,   pattern=r"^replyticket_\d+_\d+$"))


    # Callbacks الأدمن
    app.add_handler(CallbackQueryHandler(cb_approve_order,  pattern=r"^approve_\d+_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_reject_order,   pattern=r"^reject_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_send_creds,     pattern=r"^sendcreds_\d+_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_skip,     pattern="^admin_skip$"))

    # Callbacks لوحة الأدمن — كانت ناقصة
    from admin_wizard import (cb_list_services, cb_admin_back, cb_orders_main, cb_tickets,
                              cb_quickdel_svc, cb_quickdel_confirm)
    app.add_handler(CallbackQueryHandler(
        lambda u, c: __import__("admin_wizard").wiz_variants_start(u, c),
        pattern="^wiz_variants$"))
    app.add_handler(CallbackQueryHandler(cb_list_services,    pattern="^wiz_list$"))
    app.add_handler(CallbackQueryHandler(cb_admin_back,       pattern="^admin_back$"))
    app.add_handler(CallbackQueryHandler(cb_orders_main,      pattern="^wiz_orders$"))
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

