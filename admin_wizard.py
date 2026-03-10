"""
🛠️ لوحة إدارة الأدمن - Admin Wizard
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

def cancel_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")]])

# ══ حالات المحادثات ══
(SVC_TYPE, SVC_NAME_AR, SVC_NAME_EN, SVC_DESC, SVC_MIN) = range(10, 15)
(PLAN_SVC, PLAN_NAME_AR, PLAN_NAME_EN, PLAN_DAYS, PLAN_PRICE, PLAN_FEATS, PLAN_OPTS_Q) = range(20, 27)
(EDIT_SVC, EDIT_FIELD, EDIT_VALUE, EDIT_PLAN_OPTS) = range(30, 34)
(DEL_TYPE, DEL_ITEM, DEL_CONFIRM) = range(40, 43)
(MANSUB_USER, MANSUB_PLAN, MANSUB_CREDS) = range(50, 53)
(RATE_SVC, RATE_VALUE) = range(60, 62)
(BROADCAST_MSG,) = range(70, 71)


# ══════════════════════════════════════════
#   لوحة الأدمن الرئيسية
# ══════════════════════════════════════════

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    stats = db.get_stats()
    text = (
        f"⚙️ *لوحة الإدارة — Nova Plus*\n\n"
        f"👥 المستخدمون: *{stats['total_users']}*\n"
        f"✅ اشتراكات نشطة: *{stats['active_subs']}*\n"
        f"💰 إجمالي الإيرادات: *{stats['total_revenue']} USDT*\n"
        f"⏳ طلبات معلقة: *{stats['pending_orders']}*\n"
        f"🎫 تذاكر مفتوحة: *{stats['open_tickets']}*"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ خدمة جديدة",    callback_data="wiz_add_svc"),
         InlineKeyboardButton("➕ خطة جديدة",     callback_data="wiz_add_plan")],
        [InlineKeyboardButton("✏️ تعديل خدمة",    callback_data="wiz_edit_svc"),
         InlineKeyboardButton("🗑️ حذف",           callback_data="wiz_delete")],
        [InlineKeyboardButton("💱 تحديث سعر صرف", callback_data="wiz_rate"),
         InlineKeyboardButton("📋 عرض الخدمات",   callback_data="wiz_list")],
        [InlineKeyboardButton("🎁 اشتراك يدوي",   callback_data="wiz_mansub"),
         InlineKeyboardButton("⏳ الطلبات",        callback_data="wiz_orders")],
        [InlineKeyboardButton("🎫 التذاكر",        callback_data="wiz_tickets"),
         InlineKeyboardButton("📢 إذاعة",          callback_data="wiz_broadcast")],
    ])
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)


async def cb_admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await cmd_admin(update, context)


# ══════════════════════════════════════════
#   عرض الخدمات
# ══════════════════════════════════════════

async def cb_list_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    services = db.get_services()
    if not services:
        await q.edit_message_text("❌ لا توجد خدمات",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ رجوع", callback_data="admin_back")]]))
        return

    lines = ["📋 *الخدمات والخطط:*\n"]
    del_btns = []
    for svc in services:
        plans = db.get_plans(svc["id"])
        lines.append(f"\n🔵 *{svc['name_ar']}* | {svc.get('type_label_ar','—')} | ID:{svc['id']}")
        if svc.get("min_amount", 0) > 0:
            lines.append(f"   📊 حد أدنى: {svc['min_amount']}")
        rate = db.get_exchange_rate(svc["id"])
        if rate:
            lines.append(f"   💱 سعر الصرف: 1 {rate['unit']} = {rate['rate']:,.0f} ل.س")
        for p in plans:
            opts = json.loads(p.get("extra_options", "[]"))
            lines.append(f"   📦 {p['name_ar']} — {p['price']} USDT"
                         + (f" / {p['duration_days']}ي" if p['duration_days'] > 0 else "")
                         + (f" | {len(opts)} خيارات" if opts else "")
                         + f" (ID:{p['id']})")
        del_btns.append([InlineKeyboardButton(
            f"🗑️ حذف: {svc['name_ar']}",
            callback_data=f"quickdel_svc_{svc['id']}"
        )])

    del_btns.append([InlineKeyboardButton("◀️ رجوع", callback_data="admin_back")])
    await q.edit_message_text("\n".join(lines), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(del_btns))


async def cb_quickdel_svc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    svc_id = int(q.data.split("_")[2])
    svc    = db.get_service(svc_id)
    if not svc:
        await q.answer("❌ الخدمة غير موجودة", show_alert=True); return
    await q.edit_message_text(
        f"⚠️ هل أنت متأكد من حذف *{svc['name_ar']}*؟\n\nسيتم حذف الخدمة وجميع خططها.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ نعم، احذف", callback_data=f"quickdel_confirm_{svc_id}"),
             InlineKeyboardButton("❌ لا",         callback_data="wiz_list")]
        ])
    )


async def cb_quickdel_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    svc_id = int(q.data.split("_")[2])
    svc    = db.get_service(svc_id)
    name   = svc["name_ar"] if svc else "—"
    # حذف الخطط أولاً
    plans = db.get_plans(svc_id)
    for p in plans:
        db.delete_plan(p["id"])
    db.delete_service(svc_id)
    await q.edit_message_text(
        f"✅ تم حذف *{name}* وجميع خططها.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ رجوع للخدمات", callback_data="wiz_list"),
            InlineKeyboardButton("🏠 الأدمن", callback_data="admin_back")
        ]])
    )


# ══════════════════════════════════════════
#   ① إضافة خدمة
# ══════════════════════════════════════════

async def wiz_add_svc_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return ConversationHandler.END
    context.user_data["wiz"] = {}
    types = db.get_service_types()
    btns  = [[InlineKeyboardButton(f"{t['label_ar']}", callback_data=f"svctype_{t['id']}")]
             for t in types]
    btns.append([InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")])
    await q.edit_message_text(
        "➕ *خدمة جديدة*\n\nالخطوة 1/5 — اختر *نوع الخدمة*:",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))
    return SVC_TYPE

async def svc_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["wiz"]["type_id"] = int(q.data.split("_")[1])
    await q.edit_message_text("الخطوة 2/5 — أرسل *اسم الخدمة بالعربي*:",
        parse_mode="Markdown", reply_markup=cancel_kb())
    return SVC_NAME_AR

async def svc_name_ar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["wiz"]["name_ar"] = update.message.text
    await update.message.reply_text("الخطوة 3/5 — أرسل *اسم الخدمة بالإنجليزي*:",
        parse_mode="Markdown", reply_markup=cancel_kb())
    return SVC_NAME_EN

async def svc_name_en(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["wiz"]["name_en"] = update.message.text
    await update.message.reply_text(
        "الخطوة 4/5 — أرسل *وصف الخدمة* (أو `-` لتخطي):",
        parse_mode="Markdown", reply_markup=cancel_kb())
    return SVC_DESC

async def svc_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data["wiz"]["desc"] = "" if text == "-" else text
    await update.message.reply_text(
        "الخطوة 5/5 — أرسل *الحد الأدنى للطلب* (رقم، أو `0` بدون حد):",
        parse_mode="Markdown", reply_markup=cancel_kb())
    return SVC_MIN

async def svc_min(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        min_val = float(update.message.text)
    except:
        await update.message.reply_text("❌ أرسل رقماً صحيحاً مثل: 5 أو 0")
        return SVC_MIN
    w = context.user_data["wiz"]
    db.add_service(w["name_ar"], w["name_en"], w["desc"], "", "digital", w["type_id"], min_val)
    context.user_data.pop("wiz", None)
    await update.message.reply_text(
        f"✅ *تم إضافة الخدمة!*\n\n🔵 {w['name_ar']}\nالآن أضف خطة لها من /admin ← ➕ خطة جديدة",
        parse_mode="Markdown")
    return ConversationHandler.END


# ══════════════════════════════════════════
#   ② إضافة خطة
# ══════════════════════════════════════════

async def wiz_add_plan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return ConversationHandler.END
    services = db.get_services()
    if not services:
        await q.edit_message_text("❌ أضف خدمة أولاً")
        return ConversationHandler.END
    context.user_data["wiz"] = {}
    btns = [[InlineKeyboardButton(s["name_ar"], callback_data=f"plansvc_{s['id']}")] for s in services]
    btns.append([InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")])
    await q.edit_message_text("➕ *خطة جديدة*\n\nاختر الخدمة:",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))
    return PLAN_SVC

async def plan_svc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["wiz"]["svc_id"] = int(q.data.split("_")[1])
    await q.edit_message_text("أرسل *اسم الخطة بالعربي*:\nمثال: شهر واحد، شحن 500 ل.س، بيع 10 USDT",
        parse_mode="Markdown", reply_markup=cancel_kb())
    return PLAN_NAME_AR

async def plan_name_ar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["wiz"]["name_ar"] = update.message.text
    await update.message.reply_text("أرسل *اسم الخطة بالإنجليزي*:",
        parse_mode="Markdown", reply_markup=cancel_kb())
    return PLAN_NAME_EN

async def plan_name_en(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["wiz"]["name_en"] = update.message.text
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("30 يوم",  callback_data="pdays_30"),
         InlineKeyboardButton("90 يوم",  callback_data="pdays_90"),
         InlineKeyboardButton("365 يوم", callback_data="pdays_365")],
        [InlineKeyboardButton("لا ينطبق (رصيد/تحويل)", callback_data="pdays_0")],
        [InlineKeyboardButton("✏️ أدخل يدوياً", callback_data="pdays_custom")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")],
    ])
    await update.message.reply_text("اختر *المدة*:", parse_mode="Markdown", reply_markup=kb)
    return PLAN_DAYS

async def plan_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    val = q.data.split("_")[1]
    if val == "custom":
        context.user_data["wiz"]["_custom_days"] = True
        await q.edit_message_text("أرسل عدد الأيام (رقم):", reply_markup=cancel_kb())
        return PLAN_DAYS
    context.user_data["wiz"]["days"] = int(val)
    await q.edit_message_text("أرسل *السعر بالـ USDT*:\nمثال: 5.99",
        parse_mode="Markdown", reply_markup=cancel_kb())
    return PLAN_PRICE

async def plan_days_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data["wiz"].get("_custom_days"):
        try:
            context.user_data["wiz"]["days"] = int(update.message.text)
            context.user_data["wiz"].pop("_custom_days", None)
        except:
            await update.message.reply_text("❌ أرسل رقماً صحيحاً:")
            return PLAN_DAYS
        await update.message.reply_text("أرسل *السعر بالـ USDT*:", parse_mode="Markdown", reply_markup=cancel_kb())
        return PLAN_PRICE
    return PLAN_DAYS

async def plan_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["wiz"]["price"] = float(update.message.text)
    except:
        await update.message.reply_text("❌ أرسل رقماً مثل: 5.99")
        return PLAN_PRICE
    await update.message.reply_text(
        "أرسل *مميزات الخطة* (كل ميزة في سطر)\nأو `-` لتخطي:",
        parse_mode="Markdown", reply_markup=cancel_kb())
    return PLAN_FEATS

async def plan_feats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data["wiz"]["features"] = [] if text == "-" else [l.strip() for l in text.split("\n") if l.strip()]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ نعم، أضف خيارات", callback_data="plan_add_opts"),
         InlineKeyboardButton("⏭️ تخطي", callback_data="plan_skip_opts")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")],
    ])
    await update.message.reply_text(
        "🔘 *هل تريد إضافة خيارات/حقول للزبون؟*\n\n"
        "مثال:\n"
        "• اختيار أزرار: (على إيميلك / إيميل من عندنا)\n"
        "• إدخال نص: (رقم هاتفك، رقم المحفظة، إلخ)",
        parse_mode="Markdown", reply_markup=kb)
    return PLAN_OPTS_Q

async def plan_skip_opts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await _save_plan(update.callback_query, context, [])
    return ConversationHandler.END

async def plan_add_opts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["wiz"]["options"]         = []
    context.user_data["wiz"]["collecting_opts"] = True
    await q.edit_message_text(
        "🔘 *إضافة خيارات*\n\n"
        "لكل خيار، أرسل رسالة بهذا الشكل:\n\n"
        "*خيارات أزرار:*\n"
        "`السؤال: كيف تريد الاشتراك؟`\n"
        "`خيار1: على إيميلك`\n"
        "`خيار2: إيميل من عندنا`\n\n"
        "*حقل نص (إدخال يدوي):*\n"
        "`حقل: رقم هاتفك`\n"
        "`مفتاح: phone`\n\n"
        "أرسل `تم` لما تخلص.",
        parse_mode="Markdown", reply_markup=cancel_kb())
    return PLAN_OPTS_Q

async def plan_collect_opts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "تم":
        opts = context.user_data["wiz"].get("options", [])
        await _save_plan_msg(update, context, opts)
        return ConversationHandler.END

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    wiz   = context.user_data["wiz"]
    added = []

    # نقرأ الرسالة سطراً سطراً بالترتيب
    i = 0
    while i < len(lines):
        line = lines[i]

        # خيارات أزرار — السؤال أولاً
        if line.startswith("السؤال:"):
            question = line.replace("السؤال:", "").strip()
            choices  = []
            i += 1
            while i < len(lines) and lines[i].startswith("خيار"):
                choices.append(lines[i].split(":", 1)[-1].strip())
                i += 1
            if question and choices:
                wiz["options"].append({"type": "choice", "question": question, "choices": choices})
                added.append(f"🔘 {question}: " + " | ".join(choices))
            else:
                await update.message.reply_text(
                    "❌ السؤال بدون خيارات، أعد المحاولة:\n`السؤال: نص`\n`خيار1: ...`",
                    parse_mode="Markdown")
                return PLAN_OPTS_Q

        # حقل نص
        elif line.startswith("حقل:"):
            question = line.replace("حقل:", "").strip()
            key = question
            if i + 1 < len(lines) and lines[i + 1].startswith("مفتاح:"):
                key = lines[i + 1].replace("مفتاح:", "").strip()
                i += 1
            if question:
                wiz["options"].append({"type": "input", "question": question, "key": key})
                added.append(f"📝 حقل نص: {question}")
            i += 1

        else:
            i += 1

    if added:
        summary = "\n".join(f"✅ {a}" for a in added)
        await update.message.reply_text(
            f"{summary}\n\nأرسل خياراً آخر أو `تم`",
            parse_mode="Markdown")
    else:
        await update.message.reply_text(
            "❌ الصيغة غلط. استخدم:\n\n"
            "*خيارات أزرار:*\n`السؤال: كيف تريد الاشتراك؟`\n`خيار1: على إيميلك`\n`خيار2: إيميل من عندنا`\n\n"
            "*حقل نص:*\n`حقل: رقم هاتفك`\n`مفتاح: phone`",
            parse_mode="Markdown")
    return PLAN_OPTS_Q

async def _save_plan(q, context, options):
    w = context.user_data["wiz"]
    db.add_plan_full(w["svc_id"], w["name_ar"], w["name_en"],
                     w.get("days", 0), w["price"], w.get("features", []), options)
    context.user_data.pop("wiz", None)
    svc = db.get_service(w["svc_id"])
    await q.edit_message_text(
        f"✅ *تم إضافة الخطة!*\n\n"
        f"🔵 {svc['name_ar']}\n"
        f"📦 {w['name_ar']} — {w['price']} USDT\n"
        f"🔘 خيارات: {len(options)}",
        parse_mode="Markdown")

async def _save_plan_msg(update, context, options):
    w = context.user_data["wiz"]
    db.add_plan_full(w["svc_id"], w["name_ar"], w["name_en"],
                     w.get("days", 0), w["price"], w.get("features", []), options)
    context.user_data.pop("wiz", None)
    svc = db.get_service(w["svc_id"])
    await update.message.reply_text(
        f"✅ *تم إضافة الخطة!*\n\n"
        f"🔵 {svc['name_ar']}\n"
        f"📦 {w['name_ar']} — {w['price']} USDT\n"
        f"🔘 خيارات: {len(options)}",
        parse_mode="Markdown")


# ══════════════════════════════════════════
#   ③ تعديل خدمة
# ══════════════════════════════════════════

async def wiz_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    services = db.get_services()
    if not services:
        await q.edit_message_text("❌ لا توجد خدمات")
        return ConversationHandler.END
    context.user_data["wiz"] = {}
    btns = [[InlineKeyboardButton(s["name_ar"], callback_data=f"editsvc_{s['id']}")] for s in services]
    btns.append([InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")])
    await q.edit_message_text("✏️ *تعديل خدمة*\n\nاختر الخدمة:",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))
    return EDIT_SVC

async def edit_svc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    svc_id = int(q.data.split("_")[1])
    svc    = db.get_service(svc_id)
    plans  = db.get_plans(svc_id)
    context.user_data["wiz"]["svc_id"] = svc_id

    # أزرار تعديل حقول الخدمة
    btns = [
        [InlineKeyboardButton("الاسم العربي",    callback_data="ef_name_ar"),
         InlineKeyboardButton("الاسم الإنجليزي", callback_data="ef_name_en")],
        [InlineKeyboardButton("الوصف",           callback_data="ef_description_ar"),
         InlineKeyboardButton("الحد الأدنى",     callback_data="ef_min_amount")],
        [InlineKeyboardButton("🔴 إخفاء",        callback_data="ef_hide"),
         InlineKeyboardButton("🟢 إظهار",        callback_data="ef_show")],
    ]
    # أزرار تعديل خيارات الخطط
    for p in plans:
        btns.append([InlineKeyboardButton(
            f"🔘 خيارات: {p['name_ar']} (ID:{p['id']})",
            callback_data=f"ef_planopts_{p['id']}"
        )])
    btns.append([InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")])

    await q.edit_message_text(
        f"✏️ *{svc['name_ar']}*\n\nاختر ما تريد تعديله:",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))
    return EDIT_FIELD

async def edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q     = update.callback_query; await q.answer()
    field = q.data.replace("ef_", "")
    svc_id = context.user_data["wiz"]["svc_id"]

    if field == "hide":
        db.toggle_service(svc_id, 0)
        await q.edit_message_text("✅ تم إخفاء الخدمة")
        return ConversationHandler.END

    if field == "show":
        db.toggle_service(svc_id, 1)
        await q.edit_message_text("✅ تم إظهار الخدمة")
        return ConversationHandler.END

    if field.startswith("planopts_"):
        plan_id = int(field.replace("planopts_", ""))
        context.user_data["wiz"]["edit_plan_id"] = plan_id
        current = db.get_plan_options(plan_id)
        current_text = ""
        for o in current:
            if o.get("type") == "input":
                current_text += f"\n  📝 حقل: {o['question']}"
            else:
                current_text += f"\n  🔘 {o['question']}: " + " | ".join(o.get("choices", []))

        await q.edit_message_text(
            f"🔘 *تعديل خيارات الخطة*\n"
            f"الخيارات الحالية:{current_text or ' (لا يوجد)'}\n\n"
            f"أرسل الخيارات الجديدة بنفس الصيغة:\n"
            f"`السؤال: ...`\n`خيار1: ...`\n`خيار2: ...`\n\n"
            f"أو `حقل: ...` + `مفتاح: ...` للحقول النصية\n\n"
            f"أرسل `حذف` لإزالة كل الخيارات.",
            parse_mode="Markdown", reply_markup=cancel_kb())
        return EDIT_PLAN_OPTS

    LABELS = {"name_ar": "الاسم العربي", "name_en": "الاسم الإنجليزي",
              "description_ar": "الوصف", "min_amount": "الحد الأدنى"}
    context.user_data["wiz"]["field"] = field
    await q.edit_message_text(
        f"✏️ أرسل *{LABELS.get(field, field)}* الجديد:",
        parse_mode="Markdown", reply_markup=cancel_kb())
    return EDIT_VALUE

async def edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    w     = context.user_data["wiz"]
    field = w["field"]
    value = update.message.text.strip()
    if field == "min_amount":
        try: value = float(value)
        except:
            await update.message.reply_text("❌ أرسل رقماً صحيحاً")
            return EDIT_VALUE
    db.update_service_field(w["svc_id"], field, value)
    context.user_data.pop("wiz", None)
    await update.message.reply_text("✅ تم التحديث!")
    return ConversationHandler.END

async def edit_plan_opts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text    = update.message.text.strip()
    plan_id = context.user_data["wiz"]["edit_plan_id"]

    if text == "حذف":
        db.update_plan_options(plan_id, [])
        context.user_data.pop("wiz", None)
        await update.message.reply_text("✅ تم حذف كل الخيارات!")
        return ConversationHandler.END

    lines    = [l.strip() for l in text.split("\n") if l.strip()]
    options  = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("حقل:"):
            question = line.replace("حقل:", "").strip()
            key      = lines[i+1].replace("مفتاح:", "").strip() if i+1 < len(lines) and lines[i+1].startswith("مفتاح:") else question
            options.append({"type": "input", "question": question, "key": key})
            i += 2
        elif line.startswith("السؤال:"):
            question = line.replace("السؤال:", "").strip()
            choices  = []
            i += 1
            while i < len(lines) and lines[i].startswith("خيار"):
                choices.append(lines[i].split(":", 1)[-1].strip())
                i += 1
            if choices:
                options.append({"type": "choice", "question": question, "choices": choices})
        else:
            i += 1

    if not options:
        await update.message.reply_text("❌ الصيغة غلط، أعد المحاولة")
        return EDIT_PLAN_OPTS

    db.update_plan_options(plan_id, options)
    context.user_data.pop("wiz", None)
    summary = "\n".join(
        f"  📝 {o['question']}" if o.get("type") == "input"
        else f"  🔘 {o['question']}: " + " | ".join(o.get("choices", []))
        for o in options
    )
    await update.message.reply_text(f"✅ *تم تحديث الخيارات!*\n\n{summary}", parse_mode="Markdown")
    return ConversationHandler.END


# ══════════════════════════════════════════
#   ④ حذف
# ══════════════════════════════════════════

async def wiz_delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑️ حذف خدمة", callback_data="deltype_svc"),
         InlineKeyboardButton("🗑️ حذف خطة",  callback_data="deltype_plan")],
        [InlineKeyboardButton("❌ إلغاء",      callback_data="wizard_cancel")],
    ])
    await q.edit_message_text("🗑️ *حذف*\n\nماذا تريد حذف؟", parse_mode="Markdown", reply_markup=kb)
    return DEL_TYPE

async def del_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    dtype = q.data.split("_")[1]
    context.user_data["wiz"] = {"dtype": dtype}
    if dtype == "svc":
        items = db.get_services()
        btns  = [[InlineKeyboardButton(s["name_ar"], callback_data=f"delitem_{s['id']}")] for s in items]
    else:
        btns = []
        for svc in db.get_services():
            for p in db.get_plans(svc["id"]):
                btns.append([InlineKeyboardButton(f"{svc['name_ar']} — {p['name_ar']}", callback_data=f"delitem_{p['id']}")])
    btns.append([InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")])
    await q.edit_message_text("اختر العنصر:", reply_markup=InlineKeyboardMarkup(btns))
    return DEL_ITEM

async def del_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    item_id = int(q.data.split("_")[1])
    context.user_data["wiz"]["item_id"] = item_id
    dtype = context.user_data["wiz"]["dtype"]
    name  = (db.get_service(item_id) or db.get_plan(item_id) or {}).get("name_ar", "—")
    await q.edit_message_text(
        f"⚠️ هل أنت متأكد من حذف *{name}*؟",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ نعم", callback_data="delconfirm_yes"),
             InlineKeyboardButton("❌ لا",  callback_data="wizard_cancel")]
        ]))
    return DEL_CONFIRM

async def del_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    w = context.user_data["wiz"]
    if w["dtype"] == "svc":
        db.delete_service(w["item_id"])
    else:
        db.delete_plan(w["item_id"])
    context.user_data.pop("wiz", None)
    await q.edit_message_text("✅ تم الحذف")
    return ConversationHandler.END


# ══════════════════════════════════════════
#   ⑤ سعر الصرف
# ══════════════════════════════════════════

async def wiz_rate_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    services = db.get_services()
    exchange = [s for s in services if s.get("type_name") == "exchange"]
    if not exchange:
        # اعرض كل الخدمات إذا ما في exchange
        exchange = services
    btns = [[InlineKeyboardButton(s["name_ar"], callback_data=f"ratesvc_{s['id']}")] for s in exchange]
    btns.append([InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")])
    await q.edit_message_text("💱 *تحديث سعر الصرف*\n\nاختر الخدمة:",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))
    return RATE_SVC

async def rate_svc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    svc_id = int(q.data.split("_")[1])
    context.user_data["wiz"] = {"svc_id": svc_id}
    current = db.get_exchange_rate(svc_id)
    current_text = f"\nالسعر الحالي: `{current['rate']:,.0f}` ل.س" if current else ""
    await q.edit_message_text(
        f"💱 أرسل السعر الجديد (كم ليرة سورية = 1 USDT):{current_text}",
        parse_mode="Markdown", reply_markup=cancel_kb())
    return RATE_VALUE

async def rate_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rate = float(update.message.text.replace(",", ""))
    except:
        await update.message.reply_text("❌ أرسل رقماً صحيحاً مثل: 14500")
        return RATE_VALUE
    svc_id = context.user_data["wiz"]["svc_id"]
    db.set_exchange_rate(svc_id, rate)
    context.user_data.pop("wiz", None)
    await update.message.reply_text(f"✅ تم تحديث السعر: 1 USDT = *{rate:,.0f}* ل.س",
        parse_mode="Markdown")
    return ConversationHandler.END


# ══════════════════════════════════════════
#   ⑥ اشتراك يدوي
# ══════════════════════════════════════════

async def wiz_mansub_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["wiz"] = {}
    await q.edit_message_text(
        "🎁 *اشتراك يدوي*\n\nأرسل ID المستخدم أو @username:",
        parse_mode="Markdown", reply_markup=cancel_kb())
    return MANSUB_USER

async def mansub_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace("@", "")
    user = None
    try:
        user = db.get_user(int(text))
    except:
        for u in db.get_all_users():
            if (u.get("username") or "").lower() == text.lower():
                user = u; break
    if not user:
        await update.message.reply_text("❌ المستخدم غير موجود. لازم يضغط /start أولاً")
        return MANSUB_USER
    context.user_data["wiz"]["user"] = user
    services = db.get_services()
    btns = []
    for svc in services:
        for p in db.get_plans(svc["id"]):
            btns.append([InlineKeyboardButton(
                f"{svc['name_ar']} — {p['name_ar']} ({p['price']} USDT)",
                callback_data=f"mansubplan_{p['id']}"
            )])
    btns.append([InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")])
    await update.message.reply_text(
        f"✅ المستخدم: *{user['full_name']}*\n\nاختر الخطة:",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))
    return MANSUB_PLAN

async def mansub_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    plan_id = int(q.data.split("_")[1])
    context.user_data["wiz"]["plan_id"] = plan_id
    plan = db.get_plan(plan_id)
    await q.edit_message_text(
        f"✅ الخطة: *{plan['name_ar']}*\n\n"
        f"أرسل بيانات الدخول للزبون (اختياري)\n"
        f"مثال:\n`إيميل: test@gmail.com\nكلمة السر: 123456`\n\n"
        f"أو `-` بدون بيانات:",
        parse_mode="Markdown", reply_markup=cancel_kb())
    return MANSUB_CREDS

async def mansub_creds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    w    = context.user_data["wiz"]
    plan = db.get_plan(w["plan_id"])
    user = w["user"]
    creds = {}
    if text != "-":
        for line in text.split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                creds[k.strip()] = v.strip()

    order_id = db.create_order(user["id"], w["plan_id"], plan["service_id"], plan["price"])
    db.complete_order(order_id)
    db.create_subscription(user["id"], w["plan_id"], order_id, plan["service_id"],
                           plan["duration_days"], json.dumps(creds))

    creds_text = ""
    if creds:
        creds_text = "\n\n🔑 *بيانات الدخول:*\n" + "\n".join(f"`{k}: {v}`" for k, v in creds.items())

    try:
        await context.bot.send_message(
            chat_id=user["id"],
            text=f"🎉 *تم تفعيل اشتراكك!*\n\n"
                 f"🛍️ {plan['service_name_ar']}\n"
                 f"📦 {plan['name_ar']}{creds_text}\n\n"
                 f"اضغط /start لعرض اشتراكك ✅",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Notify failed: {e}")

    context.user_data.pop("wiz", None)
    await update.message.reply_text(
        f"✅ *تم إضافة الاشتراك!*\n\n"
        f"👤 {user['full_name']}\n"
        f"📦 {plan['name_ar']} — {plan['price']} USDT",
        parse_mode="Markdown")
    return ConversationHandler.END


# ══════════════════════════════════════════
#   ⑦ الطلبات والتذاكر
# ══════════════════════════════════════════

async def cb_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    orders = db.get_pending_orders()
    if not orders:
        await q.edit_message_text("✅ لا توجد طلبات معلقة",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ رجوع", callback_data="admin_back")]]))
        return
    for o in orders[:5]:
        user_opts = json.loads(o.get("user_options") or "{}")
        user_inps = json.loads(o.get("user_inputs") or "{}")
        opts_text = ""
        for k, v in {**user_opts, **user_inps}.items():
            opts_text += f"\n  • {k}: {v}"
        text = (
            f"🔖 *طلب #{o['id']}*\n"
            f"👤 {o['full_name']} (@{o.get('username','—')})\n"
            f"🛍️ {o['svc_ar']} — {o['plan_name_ar']}\n"
            f"💰 {o['amount']} USDT"
            + (f"\n📋 خيارات:{opts_text}" if opts_text else "")
        )
        await context.bot.send_message(
            chat_id=q.from_user.id, text=text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ قبول", callback_data=f"approve_{o['id']}_{o['user_id']}_{o['plan_id']}"),
                InlineKeyboardButton("❌ رفض",  callback_data=f"reject_{o['id']}_{o['user_id']}")
            ]])
        )

async def cb_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tickets = db.get_open_tickets()
    if not tickets:
        await q.edit_message_text("✅ لا توجد تذاكر مفتوحة",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ رجوع", callback_data="admin_back")]]))
        return
    for t in tickets[:5]:
        await context.bot.send_message(
            chat_id=q.from_user.id,
            text=f"🎫 *تذكرة #{t['id']}*\n👤 {t['full_name']}\n\n💬 {t['message']}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💬 رد", callback_data=f"replyticket_{t['id']}_{t['user_id']}")
            ]])
        )


# ══════════════════════════════════════════
#   ⑧ إذاعة
# ══════════════════════════════════════════

async def wiz_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(
        "📢 *إذاعة لكل المستخدمين*\n\nأرسل الرسالة:",
        parse_mode="Markdown", reply_markup=cancel_kb())
    return BROADCAST_MSG

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = db.get_all_users()
    text  = update.message.text
    ok, fail = 0, 0
    for u in users:
        try:
            await context.bot.send_message(chat_id=u["id"], text=text, parse_mode="Markdown")
            ok += 1
        except:
            fail += 1
    await update.message.reply_text(f"📢 تم الإرسال: ✅ {ok} | ❌ {fail}")
    return ConversationHandler.END


# ══════════════════════════════════════════
#   إلغاء
# ══════════════════════════════════════════

async def wizard_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("wiz", None)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ تم الإلغاء. أرسل /admin للوحة الإدارة.")
    else:
        await update.message.reply_text("❌ تم الإلغاء.")
    return ConversationHandler.END


# ══════════════════════════════════════════
#   تسجيل الـ Handlers
# ══════════════════════════════════════════

def get_wizard_handlers():
    CANCEL = [CallbackQueryHandler(wizard_cancel, pattern="^wizard_cancel$")]

    return [
        ConversationHandler(
            entry_points=[CallbackQueryHandler(wiz_add_svc_start, pattern="^wiz_add_svc$")],
            states={
                SVC_TYPE:    [CallbackQueryHandler(svc_type, pattern="^svctype_")],
                SVC_NAME_AR: [MessageHandler(filters.TEXT & ~filters.COMMAND, svc_name_ar)],
                SVC_NAME_EN: [MessageHandler(filters.TEXT & ~filters.COMMAND, svc_name_en)],
                SVC_DESC:    [MessageHandler(filters.TEXT & ~filters.COMMAND, svc_desc)],
                SVC_MIN:     [MessageHandler(filters.TEXT & ~filters.COMMAND, svc_min)],
            }, fallbacks=CANCEL, per_message=False),

        ConversationHandler(
            entry_points=[CallbackQueryHandler(wiz_add_plan_start, pattern="^wiz_add_plan$")],
            states={
                PLAN_SVC:     [CallbackQueryHandler(plan_svc, pattern="^plansvc_")],
                PLAN_NAME_AR: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_name_ar)],
                PLAN_NAME_EN: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_name_en)],
                PLAN_DAYS:    [
                    CallbackQueryHandler(plan_days, pattern="^pdays_"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, plan_days_text)
                ],
                PLAN_PRICE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_price)],
                PLAN_FEATS:   [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_feats)],
                PLAN_OPTS_Q:  [
                    CallbackQueryHandler(plan_skip_opts, pattern="^plan_skip_opts$"),
                    CallbackQueryHandler(plan_add_opts,  pattern="^plan_add_opts$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, plan_collect_opts)
                ],
            }, fallbacks=CANCEL, per_message=False, allow_reentry=True),

        ConversationHandler(
            entry_points=[CallbackQueryHandler(wiz_edit_start, pattern="^wiz_edit_svc$")],
            states={
                EDIT_SVC:       [CallbackQueryHandler(edit_svc, pattern="^editsvc_")],
                EDIT_FIELD:     [CallbackQueryHandler(edit_field, pattern="^ef_")],
                EDIT_VALUE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value)],
                EDIT_PLAN_OPTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_plan_opts)],
            }, fallbacks=CANCEL, per_message=False),

        ConversationHandler(
            entry_points=[CallbackQueryHandler(wiz_delete_start, pattern="^wiz_delete$")],
            states={
                DEL_TYPE:    [CallbackQueryHandler(del_type, pattern="^deltype_")],
                DEL_ITEM:    [CallbackQueryHandler(del_item, pattern="^delitem_")],
                DEL_CONFIRM: [CallbackQueryHandler(del_confirm, pattern="^delconfirm_yes$")],
            }, fallbacks=CANCEL, per_message=False),

        ConversationHandler(
            entry_points=[CallbackQueryHandler(wiz_rate_start, pattern="^wiz_rate$")],
            states={
                RATE_SVC:   [CallbackQueryHandler(rate_svc, pattern="^ratesvc_")],
                RATE_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, rate_value)],
            }, fallbacks=CANCEL, per_message=False),

        ConversationHandler(
            entry_points=[CallbackQueryHandler(wiz_mansub_start, pattern="^wiz_mansub$")],
            states={
                MANSUB_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, mansub_user)],
                MANSUB_PLAN: [CallbackQueryHandler(mansub_plan, pattern="^mansubplan_")],
                MANSUB_CREDS:[MessageHandler(filters.TEXT & ~filters.COMMAND, mansub_creds)],
            }, fallbacks=CANCEL, per_message=False),

        ConversationHandler(
            entry_points=[CallbackQueryHandler(wiz_broadcast_start, pattern="^wiz_broadcast$")],
            states={
                BROADCAST_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)],
            }, fallbacks=CANCEL, per_message=False),
    ]

