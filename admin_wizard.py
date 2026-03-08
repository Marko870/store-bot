"""
🛠️ نظام إدارة الخدمات والخطط للأدمن - Admin Management Wizard
محادثة تفاعلية خطوة بخطوة
"""

import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from database import Database
from config import Config

logger = logging.getLogger(__name__)
db  = Database()
cfg = Config()

def is_admin(uid): return uid in cfg.ADMIN_IDS

# ═══════════════════════════════════════════
#   حالات المحادثة - Conversation States
# ═══════════════════════════════════════════

# ——— إضافة خدمة ———
(
    SVC_NAME_AR, SVC_NAME_EN, SVC_DESC_AR, SVC_CATEGORY,
) = range(10, 14)

# ——— إضافة خطة ———
(
    PLAN_CHOOSE_SVC, PLAN_NAME_AR, PLAN_NAME_EN,
    PLAN_DURATION, PLAN_PRICE, PLAN_FEATURES, PLAN_OPTIONS,
) = range(20, 27)

# ——— إضافة اشتراك يدوي ———
(
    MANSUB_USER_ID, MANSUB_CHOOSE_PLAN, MANSUB_CREDENTIALS,
) = range(30, 33)

# ——— تعديل خدمة ———
(
    EDIT_CHOOSE_SVC, EDIT_CHOOSE_FIELD, EDIT_NEW_VALUE,
    EDIT_PLAN_OPTS, EDIT_PLAN_OPTS_INPUT,
) = range(40, 45)

# ——— حذف ———
(
    DEL_CHOOSE_TYPE, DEL_CHOOSE_ITEM, DEL_CONFIRM,
) = range(50, 53)


def cancel_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")
    ]])

def back_kb(cb):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("◀️ رجوع", callback_data=cb),
        InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")
    ]])


# ═══════════════════════════════════════════
#         لوحة الإدارة الرئيسية
# ═══════════════════════════════════════════

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    stats = db.get_stats()
    text = (
        f"⚙️ *لوحة الإدارة*\n\n"
        f"👥 المستخدمون: {stats['total_users']}\n"
        f"✅ الاشتراكات النشطة: {stats['active_subs']}\n"
        f"💰 الإيرادات: {stats['total_revenue']} USDT\n"
        f"⏳ الطلبات المعلقة: {stats['pending_orders']}\n"
        f"🎫 التذاكر المفتوحة: {stats['open_tickets']}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة خدمة",    callback_data="admin_add_svc"),
         InlineKeyboardButton("➕ إضافة خطة",     callback_data="admin_add_plan")],
        [InlineKeyboardButton("✏️ تعديل خدمة",    callback_data="admin_edit_svc"),
         InlineKeyboardButton("🗑️ حذف",           callback_data="admin_delete")],
        [InlineKeyboardButton("🎁 اشتراك يدوي",   callback_data="admin_mansub"),
         InlineKeyboardButton("📋 عرض الخدمات",   callback_data="admin_list_svc")],
        [InlineKeyboardButton("⏳ الطلبات المعلقة",callback_data="admin_orders"),
         InlineKeyboardButton("🎫 التذاكر",        callback_data="admin_tickets")],
        [InlineKeyboardButton("📢 إذاعة",          callback_data="admin_broadcast_prompt")],
    ])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)


# ═══════════════════════════════════════════
#         عرض الخدمات والخطط الحالية
# ═══════════════════════════════════════════

async def cb_list_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    services = db.get_services()
    if not services:
        await q.edit_message_text("❌ لا توجد خدمات", reply_markup=back_kb("admin_back"))
        return
    lines = ["📋 *الخدمات والخطط الحالية:*\n"]
    for svc in services:
        plans = db.get_plans(svc["id"])
        lines.append(f"\n🔵 *{svc['name_ar']}* (ID: {svc['id']})")
        lines.append(f"   📂 {svc['category']} | {svc['description_ar'] or '—'}")
        if plans:
            for p in plans:
                opts = json.loads(p.get("extra_options", "[]"))
                opts_text = f" | 🔘 {len(opts)} خيارات" if opts else ""
                lines.append(f"   📦 {p['name_ar']} — {p['price']} USDT / {p['duration_days']}يوم{opts_text} (ID:{p['id']})")
        else:
            lines.append("   _(لا توجد خطط)_")
    await q.edit_message_text("\n".join(lines), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ رجوع", callback_data="admin_back")]]))


# ═══════════════════════════════════════════
#         ① إضافة خدمة جديدة
# ═══════════════════════════════════════════

async def cb_start_add_svc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    context.user_data["wizard"] = {}
    await q.edit_message_text(
        "➕ *إضافة خدمة جديدة*\n\nالخطوة 1/4\n\n✏️ أرسل *اسم الخدمة بالعربي*:",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return SVC_NAME_AR

async def svc_get_name_ar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    context.user_data["wizard"]["name_ar"] = update.message.text
    await update.message.reply_text(
        "الخطوة 2/4\n\n✏️ أرسل *اسم الخدمة بالإنجليزي*:",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return SVC_NAME_EN

async def svc_get_name_en(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    context.user_data["wizard"]["name_en"] = update.message.text
    await update.message.reply_text(
        "الخطوة 3/4\n\n✏️ أرسل *وصف الخدمة بالعربي* (أو أرسل `-` لتخطي):",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return SVC_DESC_AR

async def svc_get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    desc = update.message.text
    context.user_data["wizard"]["desc_ar"] = "" if desc == "-" else desc
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Streaming", callback_data="svc_cat_streaming"),
         InlineKeyboardButton("🔒 Security",  callback_data="svc_cat_security")],
        [InlineKeyboardButton("🤖 Bot",       callback_data="svc_cat_bot"),
         InlineKeyboardButton("💻 Digital",   callback_data="svc_cat_digital")],
        [InlineKeyboardButton("❌ إلغاء",     callback_data="wizard_cancel")],
    ])
    await update.message.reply_text(
        "الخطوة 4/4\n\n📂 اختر *تصنيف الخدمة*:",
        parse_mode="Markdown", reply_markup=kb
    )
    return SVC_CATEGORY

async def svc_get_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return ConversationHandler.END
    cat = q.data.replace("svc_cat_", "")
    w   = context.user_data.get("wizard", {})
    db.add_service(w["name_ar"], w["name_en"], w.get("desc_ar",""), "", cat)
    context.user_data.pop("wizard", None)
    await q.edit_message_text(
        f"✅ *تم إضافة الخدمة بنجاح!*\n\n"
        f"🔵 {w['name_ar']} / {w['name_en']}\n"
        f"📂 {cat}\n\n"
        f"الآن يمكنك إضافة خطط لها من /admin ← ➕ إضافة خطة",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


# ═══════════════════════════════════════════
#         ② إضافة خطة لخدمة
# ═══════════════════════════════════════════

async def cb_start_add_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    services = db.get_services()
    if not services:
        await q.edit_message_text("❌ لا توجد خدمات. أضف خدمة أولاً.", reply_markup=back_kb("admin_back"))
        return ConversationHandler.END
    context.user_data["wizard"] = {}
    btns = [[InlineKeyboardButton(f"🔵 {s['name_ar']}", callback_data=f"plan_svc_{s['id']}")] for s in services]
    btns.append([InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")])
    await q.edit_message_text(
        "➕ *إضافة خطة جديدة*\n\nالخطوة 1/6\n\n📂 اختر الخدمة:",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns)
    )
    return PLAN_CHOOSE_SVC

async def plan_choose_svc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return ConversationHandler.END
    svc_id = int(q.data.replace("plan_svc_", ""))
    context.user_data["wizard"]["svc_id"] = svc_id
    await q.edit_message_text(
        "الخطوة 2/6\n\n✏️ أرسل *اسم الخطة بالعربي*\nمثال: شهر واحد، 3 أشهر، سنة كاملة",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return PLAN_NAME_AR

async def plan_get_name_ar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    context.user_data["wizard"]["name_ar"] = update.message.text
    await update.message.reply_text(
        "الخطوة 3/6\n\n✏️ أرسل *اسم الخطة بالإنجليزي*\nمثال: 1 Month, 3 Months, 1 Year",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return PLAN_NAME_EN

async def plan_get_name_en(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    context.user_data["wizard"]["name_en"] = update.message.text
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("30 يوم",  callback_data="plan_dur_30"),
         InlineKeyboardButton("90 يوم",  callback_data="plan_dur_90")],
        [InlineKeyboardButton("180 يوم", callback_data="plan_dur_180"),
         InlineKeyboardButton("365 يوم", callback_data="plan_dur_365")],
        [InlineKeyboardButton("✏️ أدخل يدوياً", callback_data="plan_dur_custom")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")],
    ])
    await update.message.reply_text(
        "الخطوة 4/6\n\n⏳ اختر *مدة الخطة*:",
        parse_mode="Markdown", reply_markup=kb
    )
    return PLAN_DURATION

async def plan_get_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return ConversationHandler.END
    if q.data == "plan_dur_custom":
        context.user_data["wizard"]["awaiting_custom_dur"] = True
        await q.edit_message_text("✏️ أرسل عدد الأيام (رقم فقط):", reply_markup=cancel_kb())
        return PLAN_DURATION
    days = int(q.data.replace("plan_dur_", ""))
    context.user_data["wizard"]["days"] = days
    await q.edit_message_text(
        "الخطوة 5/6\n\n💰 أرسل *السعر بالـ USDT*\nمثال: 5.99",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return PLAN_PRICE

async def plan_get_duration_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    if context.user_data["wizard"].get("awaiting_custom_dur"):
        try:
            days = int(update.message.text)
            context.user_data["wizard"]["days"] = days
            context.user_data["wizard"].pop("awaiting_custom_dur", None)
            await update.message.reply_text(
                "الخطوة 5/6\n\n💰 أرسل *السعر بالـ USDT*\nمثال: 5.99",
                parse_mode="Markdown", reply_markup=cancel_kb()
            )
            return PLAN_PRICE
        except:
            await update.message.reply_text("❌ أرسل رقماً صحيحاً فقط:")
            return PLAN_DURATION

async def plan_get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    try:
        price = float(update.message.text)
        context.user_data["wizard"]["price"] = price
    except:
        await update.message.reply_text("❌ أرسل رقماً صحيحاً مثل: 5.99")
        return PLAN_PRICE
    await update.message.reply_text(
        "الخطوة 6/6\n\n✨ أرسل *مميزات الخطة* (كل ميزة في سطر)\n"
        "مثال:\n`جودة 4K\nحساب خاص\nدعم 24/7`\n\n"
        "أو أرسل `-` لتخطي:",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return PLAN_FEATURES

async def plan_get_features(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    text = update.message.text
    if text == "-":
        features = []
    else:
        features = [line.strip() for line in text.split("\n") if line.strip()]
    context.user_data["wizard"]["features"] = features

    # سؤال عن الخيارات الإضافية
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ نعم، أضف خيارات", callback_data="plan_add_options"),
         InlineKeyboardButton("⏭️ تخطي",            callback_data="plan_skip_options")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")],
    ])
    await update.message.reply_text(
        "🔘 *هل تريد إضافة خيارات للمستخدم؟*\n\n"
        "مثال: (الاشتراك على إيميلك / إيميل من عندنا)\n"
        "أو: (حساب مشترك / حساب خاص)",
        parse_mode="Markdown", reply_markup=kb
    )
    return PLAN_OPTIONS

async def plan_skip_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return ConversationHandler.END
    await _save_plan(q, context, options=[])
    return ConversationHandler.END

async def plan_add_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return ConversationHandler.END
    context.user_data["wizard"]["collecting_options"] = True
    context.user_data["wizard"]["options"] = []
    await q.edit_message_text(
        "🔘 *إضافة خيارات*\n\n"
        "أرسل *سؤال الخيار* ثم *الخيارات* كل خيار في سطر\n\n"
        "الصيغة:\n"
        "`السؤال: كيف تريد الاشتراك؟`\n"
        "`خيار1: على إيميلك`\n"
        "`خيار2: إيميل من عندنا`\n\n"
        "يمكنك إضافة مجموعة خيارات متعددة، أرسل `تم` لما تخلص.",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return PLAN_OPTIONS

async def plan_collect_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    text = update.message.text.strip()

    if text.lower() == "تم":
        options = context.user_data["wizard"].get("options", [])
        await _save_plan_msg(update, context, options)
        return ConversationHandler.END

    # تحليل الخيارات
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    question = ""
    choices  = []
    for line in lines:
        if line.startswith("السؤال:"):
            question = line.replace("السؤال:", "").strip()
        elif line.startswith("خيار"):
            val = line.split(":", 1)[-1].strip()
            choices.append(val)

    if question and choices:
        context.user_data["wizard"]["options"].append({
            "question": question,
            "choices": choices
        })
        added = len(context.user_data["wizard"]["options"])
        await update.message.reply_text(
            f"✅ تم إضافة مجموعة خيارات #{added}\n\n"
            f"❓ {question}\n" +
            "\n".join(f"  • {c}" for c in choices) +
            "\n\nأرسل مجموعة خيارات أخرى أو أرسل `تم` لحفظ الخطة.",
            reply_markup=cancel_kb()
        )
    else:
        await update.message.reply_text(
            "❌ الصيغة غلط. استخدم:\n"
            "`السؤال: نص السؤال`\n"
            "`خيار1: الخيار الأول`\n"
            "`خيار2: الخيار الثاني`",
            parse_mode="Markdown"
        )
    return PLAN_OPTIONS

async def _save_plan(q, context, options):
    w = context.user_data.get("wizard", {})
    features = w.get("features", [])
    db.add_plan_full(
        svc_id=w["svc_id"],
        name_ar=w["name_ar"],
        name_en=w["name_en"],
        days=w["days"],
        price=w["price"],
        features=features,
        options=options
    )
    context.user_data.pop("wizard", None)
    svc = db.get_service(w["svc_id"])
    await q.edit_message_text(
        f"✅ *تم إضافة الخطة بنجاح!*\n\n"
        f"🔵 الخدمة: {svc['name_ar']}\n"
        f"📦 الخطة: {w['name_ar']} / {w['name_en']}\n"
        f"⏳ المدة: {w['days']} يوم\n"
        f"💰 السعر: {w['price']} USDT\n"
        f"🔘 الخيارات: {len(options)} مجموعة",
        parse_mode="Markdown"
    )

async def _save_plan_msg(update, context, options):
    w = context.user_data.get("wizard", {})
    features = w.get("features", [])
    db.add_plan_full(
        svc_id=w["svc_id"],
        name_ar=w["name_ar"],
        name_en=w["name_en"],
        days=w["days"],
        price=w["price"],
        features=features,
        options=options
    )
    context.user_data.pop("wizard", None)
    svc = db.get_service(w["svc_id"])
    await update.message.reply_text(
        f"✅ *تم إضافة الخطة بنجاح!*\n\n"
        f"🔵 الخدمة: {svc['name_ar']}\n"
        f"📦 الخطة: {w['name_ar']} / {w['name_en']}\n"
        f"⏳ المدة: {w['days']} يوم\n"
        f"💰 السعر: {w['price']} USDT\n"
        f"🔘 الخيارات: {len(options)} مجموعة",
        parse_mode="Markdown"
    )


# ═══════════════════════════════════════════
#         ③ اشتراك يدوي للمستخدم
# ═══════════════════════════════════════════

async def cb_start_mansub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    context.user_data["wizard"] = {}
    await q.edit_message_text(
        "🎁 *إضافة اشتراك يدوي*\n\nالخطوة 1/3\n\n"
        "✏️ أرسل *ID المستخدم* أو @username:",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return MANSUB_USER_ID

async def mansub_get_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    text = update.message.text.strip().replace("@", "")
    user = None
    try:
        uid  = int(text)
        user = db.get_user(uid)
    except:
        # بحث بالـ username
        all_users = db.get_all_users()
        user = next((u for u in all_users if u.get("username","").lower() == text.lower()), None)

    if not user:
        await update.message.reply_text(
            "❌ المستخدم غير موجود في قاعدة البيانات.\n"
            "لازم يكون المستخدم أرسل /start للبوت مرة واحدة على الأقل.",
            reply_markup=cancel_kb()
        )
        return MANSUB_USER_ID

    context.user_data["wizard"]["user_id"]   = user["id"]
    context.user_data["wizard"]["user_name"] = user["full_name"]

    # عرض الخدمات
    services = db.get_services()
    btns = []
    for svc in services:
        plans = db.get_plans(svc["id"])
        for p in plans:
            btns.append([InlineKeyboardButton(
                f"🔵 {svc['name_ar']} — {p['name_ar']} ({p['price']} USDT)",
                callback_data=f"mansub_plan_{p['id']}"
            )])
    btns.append([InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")])
    await update.message.reply_text(
        f"✅ المستخدم: *{user['full_name']}*\n\n"
        "الخطوة 2/3\n\n📦 اختر الخطة:",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns)
    )
    return MANSUB_CHOOSE_PLAN

async def mansub_choose_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return ConversationHandler.END
    plan_id = int(q.data.replace("mansub_plan_", ""))
    context.user_data["wizard"]["plan_id"] = plan_id
    plan = db.get_plan(plan_id)
    await q.edit_message_text(
        f"✅ الخطة: *{plan['name_ar']}*\n\n"
        "الخطوة 3/3\n\n"
        "🔑 أرسل *بيانات الدخول* (اختياري)\n"
        "مثال:\n`إيميل: test@gmail.com\nكلمة السر: 123456`\n\n"
        "أو أرسل `-` لتخطي:",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return MANSUB_CREDENTIALS

async def mansub_get_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    text = update.message.text.strip()
    w    = context.user_data.get("wizard", {})
    plan = db.get_plan(w["plan_id"])

    credentials = {}
    if text != "-":
        for line in text.split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                credentials[k.strip()] = v.strip()

    # إنشاء الطلب والاشتراك
    order_id = db.create_order(w["user_id"], w["plan_id"], plan["price"])
    db.complete_order(order_id)
    db.create_subscription(
        w["user_id"], w["plan_id"], order_id,
        plan["duration_days"],
        json.dumps(credentials) if credentials else "{}"
    )

    # إشعار المستخدم
    creds_text = ""
    if credentials:
        creds_text = "\n\n🔑 *بيانات الدخول:*\n" + "\n".join(f"`{k}: {v}`" for k, v in credentials.items())

    try:
        await context.bot.send_message(
            chat_id=w["user_id"],
            text=(
                f"🎉 *تم تفعيل اشتراكك!*\n\n"
                f"📦 الخطة: *{plan['name_ar']}*\n"
                f"⏳ المدة: {plan['duration_days']} يوم"
                f"{creds_text}\n\n"
                f"اضغط /start لعرض اشتراكك ✅"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")

    context.user_data.pop("wizard", None)
    await update.message.reply_text(
        f"✅ *تم إضافة الاشتراك بنجاح!*\n\n"
        f"👤 المستخدم: {w['user_name']}\n"
        f"📦 الخطة: {plan['name_ar']}\n"
        f"⏳ المدة: {plan['duration_days']} يوم\n"
        f"💰 السعر: {plan['price']} USDT",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


# ═══════════════════════════════════════════
#         ④ تعديل خدمة
# ═══════════════════════════════════════════

async def cb_start_edit_svc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    services = db.get_services()
    if not services:
        await q.edit_message_text("❌ لا توجد خدمات", reply_markup=back_kb("admin_back"))
        return ConversationHandler.END
    btns = [[InlineKeyboardButton(f"🔵 {s['name_ar']}", callback_data=f"edit_svc_{s['id']}")] for s in services]
    btns.append([InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")])
    await q.edit_message_text("✏️ *تعديل خدمة*\n\nاختر الخدمة:", parse_mode="Markdown",
                               reply_markup=InlineKeyboardMarkup(btns))
    return EDIT_CHOOSE_SVC

async def edit_choose_svc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return ConversationHandler.END
    svc_id = int(q.data.replace("edit_svc_", ""))
    context.user_data["wizard"] = {"svc_id": svc_id}
    svc = db.get_service(svc_id)
    # عرض خطط الخدمة أيضاً لتعديل خياراتها
    plans = db.get_plans(svc["id"])
    plan_btns = []
    for p in plans:
        plan_btns.append([InlineKeyboardButton(
            f"🔘 تعديل خيارات: {p['name_ar']}",
            callback_data=f"edit_plan_opts_{p['id']}"
        )])

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("الاسم العربي",    callback_data="edit_field_name_ar"),
         InlineKeyboardButton("الاسم الإنجليزي", callback_data="edit_field_name_en")],
        [InlineKeyboardButton("الوصف العربي",    callback_data="edit_field_desc_ar"),
         InlineKeyboardButton("التصنيف",         callback_data="edit_field_category")],
        [InlineKeyboardButton("🔴 إخفاء الخدمة", callback_data="edit_field_hide"),
         InlineKeyboardButton("🟢 إظهار الخدمة", callback_data="edit_field_show")],
        *plan_btns,
        [InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")],
    ])
    await q.edit_message_text(
        f"✏️ تعديل: *{svc['name_ar']}*\n\nاختر ما تريد تعديله:",
        parse_mode="Markdown", reply_markup=kb
    )
    return EDIT_CHOOSE_FIELD

async def edit_choose_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return ConversationHandler.END
    field = q.data.replace("edit_field_", "")
    svc_id = context.user_data["wizard"]["svc_id"]

    if field in ["hide", "show"]:
        db.toggle_service(svc_id, 0 if field == "hide" else 1)
        await q.edit_message_text(f"✅ تم {'إخفاء' if field=='hide' else 'إظهار'} الخدمة")
        return ConversationHandler.END

    # تحويل اسم الحقل القصير للاسم الحقيقي في قاعدة البيانات
    field_map = {
        "name_ar":  "name_ar",
        "name_en":  "name_en",
        "desc_ar":  "description_ar",
        "category": "category"
    }
    field = field_map.get(field, field)
    context.user_data["wizard"]["field"] = field
    labels = {"name_ar": "الاسم العربي", "name_en": "الاسم الإنجليزي",
              "description_ar": "الوصف العربي", "category": "التصنيف"}
    await q.edit_message_text(
        f"✏️ أرسل *{labels.get(field, field)}* الجديد:",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return EDIT_NEW_VALUE

async def edit_plan_opts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تعديل خيارات خطة معينة"""
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return ConversationHandler.END
    plan_id = int(q.data.replace("edit_plan_opts_", ""))
    plan    = db.get_plan(plan_id)
    context.user_data["wizard"]["edit_plan_id"] = plan_id
    current_opts = db.get_plan_options(plan_id)
    current_text = ""
    if current_opts:
        for o in current_opts:
            current_text += f"\n❓ {o['question']}\n"
            current_text += "\n".join(f"  • {c}" for c in o["choices"]) + "\n"
    else:
        current_text = "\n_(لا توجد خيارات حالياً)_"

    await q.edit_message_text(
        f"🔘 *تعديل خيارات: {plan['name_ar']}*\n"
        f"الخيارات الحالية:{current_text}\n\n"
        f"أرسل الخيارات الجديدة بهذا الشكل (كل مجموعة في رسالة واحدة):\n\n"
        f"`السؤال: كيف تريد الاشتراك؟`\n"
        f"`خيار1: على إيميلك`\n"
        f"`خيار2: إيميل من عندنا`\n\n"
        f"إذا في أكثر من مجموعة أرسلها بنفس الرسالة مفصولة بسطر فارغ.\n"
        f"أو أرسل `حذف` لإزالة كل الخيارات.",
        parse_mode="Markdown",
        reply_markup=cancel_kb()
    )
    return EDIT_PLAN_OPTS_INPUT

async def edit_plan_opts_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    text    = update.message.text.strip()
    plan_id = context.user_data["wizard"].get("edit_plan_id")

    if text == "حذف":
        db.update_plan_options(plan_id, [])
        context.user_data.pop("wizard", None)
        await update.message.reply_text("✅ تم حذف كل الخيارات!")
        return ConversationHandler.END

    # تحليل الخيارات - كل مجموعة مفصولة بسطر فارغ
    groups  = text.split("\n\n")
    options = []
    for group in groups:
        lines    = [l.strip() for l in group.split("\n") if l.strip()]
        question = ""
        choices  = []
        for line in lines:
            if line.startswith("السؤال:"):
                question = line.replace("السؤال:", "").strip()
            elif line.startswith("خيار"):
                val = line.split(":", 1)[-1].strip()
                choices.append(val)
        if question and choices:
            options.append({"question": question, "choices": choices})

    if not options:
        await update.message.reply_text(
            "❌ الصيغة غلط. استخدم:\n"
            "`السؤال: نص السؤال`\n`خيار1: ...`\n`خيار2: ...`",
            parse_mode="Markdown"
        )
        return EDIT_PLAN_OPTS_INPUT

    db.update_plan_options(plan_id, options)
    context.user_data.pop("wizard", None)
    summary = "\n".join(f"❓ {o['question']}: " + " | ".join(o["choices"]) for o in options)
    await update.message.reply_text(
        f"✅ *تم تحديث الخيارات!*\n\n{summary}",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def edit_save_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    w     = context.user_data.get("wizard", {})
    field = w.get("field")
    value = update.message.text.strip()
    db.update_service_field(w["svc_id"], field, value)
    context.user_data.pop("wizard", None)
    await update.message.reply_text(f"✅ تم التحديث بنجاح!")
    return ConversationHandler.END


# ═══════════════════════════════════════════
#         ⑤ حذف خدمة أو خطة
# ═══════════════════════════════════════════

async def cb_start_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑️ حذف خدمة كاملة", callback_data="del_type_svc"),
         InlineKeyboardButton("🗑️ حذف خطة",        callback_data="del_type_plan")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")],
    ])
    await q.edit_message_text("🗑️ *حذف*\n\nماذا تريد حذف؟", parse_mode="Markdown", reply_markup=kb)
    return DEL_CHOOSE_TYPE

async def del_choose_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return ConversationHandler.END
    del_type = q.data.replace("del_type_", "")
    context.user_data["wizard"] = {"del_type": del_type}

    if del_type == "svc":
        items = db.get_services()
        btns  = [[InlineKeyboardButton(f"🔵 {s['name_ar']}", callback_data=f"del_item_{s['id']}")] for s in items]
    else:
        services = db.get_services()
        btns = []
        for svc in services:
            for p in db.get_plans(svc["id"]):
                btns.append([InlineKeyboardButton(
                    f"📦 {svc['name_ar']} — {p['name_ar']}",
                    callback_data=f"del_item_{p['id']}"
                )])
    btns.append([InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")])
    await q.edit_message_text("اختر العنصر للحذف:", reply_markup=InlineKeyboardMarkup(btns))
    return DEL_CHOOSE_ITEM

async def del_choose_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return ConversationHandler.END
    item_id = int(q.data.replace("del_item_", ""))
    context.user_data["wizard"]["item_id"] = item_id
    del_type = context.user_data["wizard"]["del_type"]
    if del_type == "svc":
        item = db.get_service(item_id)
        name = item["name_ar"] if item else "—"
    else:
        item = db.get_plan(item_id)
        name = item["name_ar"] if item else "—"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ نعم، احذف", callback_data="del_confirm_yes"),
         InlineKeyboardButton("❌ لا",         callback_data="wizard_cancel")],
    ])
    await q.edit_message_text(
        f"⚠️ هل أنت متأكد من حذف *{name}*؟\nلا يمكن التراجع!",
        parse_mode="Markdown", reply_markup=kb
    )
    return DEL_CONFIRM

async def del_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return ConversationHandler.END
    w        = context.user_data.get("wizard", {})
    del_type = w.get("del_type")
    item_id  = w.get("item_id")
    if del_type == "svc":
        db.delete_service(item_id)
        await q.edit_message_text("✅ تم حذف الخدمة")
    else:
        db.delete_plan(item_id)
        await q.edit_message_text("✅ تم حذف الخطة")
    context.user_data.pop("wizard", None)
    return ConversationHandler.END


# ═══════════════════════════════════════════
#         إلغاء أي محادثة
# ═══════════════════════════════════════════

async def wizard_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("wizard", None)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ تم الإلغاء. أرسل /admin للرجوع للوحة الإدارة.")
    else:
        await update.message.reply_text("❌ تم الإلغاء. أرسل /admin للرجوع للوحة الإدارة.")
    return ConversationHandler.END


# ═══════════════════════════════════════════
#         تسجيل المحادثات
# ═══════════════════════════════════════════

def get_wizard_handlers():
    """إرجاع قائمة ConversationHandlers للتسجيل في التطبيق"""

    # ① إضافة خدمة
    add_svc_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_start_add_svc, pattern="^admin_add_svc$")],
        states={
            SVC_NAME_AR:  [MessageHandler(filters.TEXT & ~filters.COMMAND, svc_get_name_ar)],
            SVC_NAME_EN:  [MessageHandler(filters.TEXT & ~filters.COMMAND, svc_get_name_en)],
            SVC_DESC_AR:  [MessageHandler(filters.TEXT & ~filters.COMMAND, svc_get_desc)],
            SVC_CATEGORY: [CallbackQueryHandler(svc_get_category, pattern="^svc_cat_")],
        },
        fallbacks=[CallbackQueryHandler(wizard_cancel, pattern="^wizard_cancel$")],
        per_message=False
    )

    # ② إضافة خطة
    add_plan_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_start_add_plan, pattern="^admin_add_plan$")],
        states={
            PLAN_CHOOSE_SVC: [CallbackQueryHandler(plan_choose_svc, pattern=r"^plan_svc_\d+$")],
            PLAN_NAME_AR:    [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_get_name_ar)],
            PLAN_NAME_EN:    [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_get_name_en)],
            PLAN_DURATION:   [
                CallbackQueryHandler(plan_get_duration, pattern="^plan_dur_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, plan_get_duration_custom)
            ],
            PLAN_PRICE:      [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_get_price)],
            PLAN_FEATURES:   [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_get_features)],
            PLAN_OPTIONS:    [
                CallbackQueryHandler(plan_skip_options, pattern="^plan_skip_options$"),
                CallbackQueryHandler(plan_add_options,  pattern="^plan_add_options$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, plan_collect_options)
            ],
        },
        fallbacks=[CallbackQueryHandler(wizard_cancel, pattern="^wizard_cancel$")],
        per_message=False
    )

    # ③ اشتراك يدوي
    mansub_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_start_mansub, pattern="^admin_mansub$")],
        states={
            MANSUB_USER_ID:    [MessageHandler(filters.TEXT & ~filters.COMMAND, mansub_get_user)],
            MANSUB_CHOOSE_PLAN:[CallbackQueryHandler(mansub_choose_plan, pattern=r"^mansub_plan_\d+$")],
            MANSUB_CREDENTIALS:[MessageHandler(filters.TEXT & ~filters.COMMAND, mansub_get_credentials)],
        },
        fallbacks=[CallbackQueryHandler(wizard_cancel, pattern="^wizard_cancel$")],
        per_message=False
    )

    # ④ تعديل خدمة
    edit_svc_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_start_edit_svc, pattern="^admin_edit_svc$")],
        states={
            EDIT_CHOOSE_SVC:    [CallbackQueryHandler(edit_choose_svc,      pattern=r"^edit_svc_\d+$")],
            EDIT_CHOOSE_FIELD:  [
                CallbackQueryHandler(edit_choose_field, pattern="^edit_field_"),
                CallbackQueryHandler(edit_plan_opts,    pattern=r"^edit_plan_opts_\d+$"),
            ],
            EDIT_NEW_VALUE:      [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_save_value)],
            EDIT_PLAN_OPTS_INPUT:[MessageHandler(filters.TEXT & ~filters.COMMAND, edit_plan_opts_save)],
        },
        fallbacks=[CallbackQueryHandler(wizard_cancel, pattern="^wizard_cancel$")],
        per_message=False
    )

    # ⑤ حذف
    delete_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_start_delete, pattern="^admin_delete$")],
        states={
            DEL_CHOOSE_TYPE: [CallbackQueryHandler(del_choose_type, pattern="^del_type_")],
            DEL_CHOOSE_ITEM: [CallbackQueryHandler(del_choose_item, pattern=r"^del_item_\d+$")],
            DEL_CONFIRM:     [CallbackQueryHandler(del_confirm, pattern="^del_confirm_yes$")],
        },
        fallbacks=[CallbackQueryHandler(wizard_cancel, pattern="^wizard_cancel$")],
        per_message=False
    )

    return [add_svc_conv, add_plan_conv, mansub_conv, edit_svc_conv, delete_conv]

