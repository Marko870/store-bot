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

def back_cancel_kb(back_data="admin_back"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ رجوع", callback_data=back_data),
         InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")]
    ])

# ══ حالات المحادثات ══
(SVC_TYPE, SVC_NAME_AR, SVC_NAME_EN, SVC_DESC, SVC_MIN) = range(10, 15)
(PLAN_SVC, PLAN_NAME_AR, PLAN_NAME_EN, PLAN_DAYS, PLAN_PRICE, PLAN_FEATS, PLAN_OPTS_Q) = range(20, 27)
(EDIT_SVC, EDIT_FIELD, EDIT_VALUE, EDIT_PLAN_OPTS) = range(30, 34)
(DEL_TYPE, DEL_ITEM, DEL_CONFIRM) = range(40, 43)
(MANSUB_USER, MANSUB_PLAN, MANSUB_CREDS) = range(50, 53)
(RATE_SVC, RATE_VALUE) = range(60, 62)
(BROADCAST_MSG,) = range(70, 71)
(VAR_SVC, VAR_NAME_AR, VAR_NAME_EN, VAR_OPTS) = range(80, 84)
(ORD_MAIN, ORD_SEARCH, ORD_DETAIL, ORD_CONFIRM) = range(100, 104)
(SUB_MAIN, SUB_SEARCH, SUB_DETAIL, SUB_EXTEND) = range(110, 114)
(USR_MAIN, USR_SEARCH, USR_DETAIL) = range(120, 123)
(STATS_MAIN,) = range(130, 131)
(TKT_MAIN, TKT_SEARCH, TKT_DETAIL, TKT_REPLY) = range(140, 144)
PER_PAGE = 5
(RCH_SVC, RCH_RATE, RCH_PRESETS, RCH_LIMITS) = range(90, 94)


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
        [InlineKeyboardButton("📋 عرض الخدمات",   callback_data="wiz_list"),
         InlineKeyboardButton("🗂️ أنواع الاشتراكات",  callback_data="wiz_variants")],
        [InlineKeyboardButton("📱 إعدادات التعبئة", callback_data="wiz_recharge"),
         InlineKeyboardButton("🎁 اشتراك يدوي",   callback_data="wiz_mansub")],
        [InlineKeyboardButton("⏳ الطلبات",        callback_data="wiz_orders"),
         InlineKeyboardButton("📋 الاشتراكات",    callback_data="wiz_subs")],
        [InlineKeyboardButton("👥 المستخدمون",    callback_data="wiz_users"),
         InlineKeyboardButton("📊 الإحصائيات",    callback_data="wiz_stats")],
        [InlineKeyboardButton("🎫 التذاكر",        callback_data="wiz_tickets"),
         InlineKeyboardButton("💱 أسعار الصرافة",  callback_data="wiz_exc_rates")],
        [InlineKeyboardButton("📢 إذاعة",          callback_data="wiz_broadcast")],
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
        await q.edit_message_text(
            "❌ لا توجد خدمات",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ رجوع", callback_data="admin_back")]]))
        return

    lines    = ["📋 *الخدمات والخطط:*\n"]
    del_btns = []

    for svc in services:
        plans = db.get_plans(svc["id"])
        lines.append(f"\n🔵 *{svc['name_ar']}* | {svc.get('type_label_ar', '—')} | ID:{svc['id']}")
        if svc.get("min_amount", 0) > 0:
            lines.append(f"   📊 حد أدنى: {svc['min_amount']}")
        rate = db.get_exchange_rate(svc["id"])
        if rate:
            lines.append(f"   💱 سعر الصرف: 1 {rate['unit']} = {rate['rate']:,.0f} ل.س")
        # عرض الأنواع
        variants = db.get_variants(svc["id"])
        if variants:
            for v in variants:
                v_opts = []
                try:
                    v_opts = json.loads(v.get("extra_options", "[]"))
                except Exception:
                    pass
                lines.append(f"   🗂️ {v['name_ar']} ({len(v_opts)} خيارات) | ID:{v['id']}")
                v_plans = db.get_plans_by_variant(v["id"])
                for p in v_plans:
                    lines.append(f"      📦 {p['name_ar']} — {p['price']} USDT (ID:{p['id']})")
        # خطط بدون variant
        direct = db.get_plans_no_variant(svc["id"]) if variants else plans
        for p in direct:
            opts = []
            try:
                opts = json.loads(p.get("extra_options", "[]"))
            except Exception:
                pass
            lines.append(
                f"   📦 {p['name_ar']} — {p['price']} USDT"
                + (f" / {p['duration_days']}ي" if p["duration_days"] > 0 else "")
                + (f" | {len(opts)} خيارات" if opts else "")
                + f" (ID:{p['id']})"
            )
        del_btns.append([InlineKeyboardButton(
            f"🗑️ حذف: {svc['name_ar']}",
            callback_data=f"quickdel_svc_{svc['id']}"
        )])

    del_btns.append([InlineKeyboardButton("◀️ رجوع", callback_data="admin_back")])
    await q.edit_message_text(
        "\n".join(lines), parse_mode="Markdown",
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
        ]))


async def cb_quickdel_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q      = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    svc_id = int(q.data.split("_")[2])
    svc    = db.get_service(svc_id)
    name   = svc["name_ar"] if svc else "—"
    plans  = db.get_plans(svc_id)
    for p in plans:
        db.delete_plan(p["id"])
    db.delete_service(svc_id)
    await q.edit_message_text(
        f"✅ تم حذف *{name}* وجميع خططها.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ رجوع للخدمات", callback_data="wiz_list"),
            InlineKeyboardButton("🏠 الرئيسية",      callback_data="admin_back")
        ]]))


# ══════════════════════════════════════════
#   ① إضافة خدمة
# ══════════════════════════════════════════

async def wiz_add_svc_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return ConversationHandler.END
    context.user_data["wiz"] = {}
    types = db.get_service_types()
    # فلترة أنواع الخدمة — عرض الكل مع تمييز الاشتراكات
    btns = []
    for t in types:
        icon = "⭐" if t["name"] == "subscription" else "•"
        btns.append([InlineKeyboardButton(f"{icon} {t['label_ar']}", callback_data=f"svctype_{t['id']}")])
    btns.append([InlineKeyboardButton("◀️ رجوع", callback_data="admin_back")])
    await q.edit_message_text(
        "➕ *خدمة جديدة*\n\nالخطوة 1/5 — اختر *نوع الخدمة*:\n_(⭐ = اشتراك رقمي)_",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))
    return SVC_TYPE


async def svc_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["wiz"]["type_id"] = int(q.data.split("_")[1])
    await q.edit_message_text(
        "الخطوة 2/5 — أرسل *اسم الخدمة بالعربي*:",
        parse_mode="Markdown", reply_markup=back_cancel_kb("wiz_add_svc"))
    return SVC_NAME_AR


async def svc_name_ar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["wiz"]["name_ar"] = update.message.text
    await update.message.reply_text(
        "الخطوة 3/5 — أرسل *اسم الخدمة بالإنجليزي*:",
        parse_mode="Markdown", reply_markup=back_cancel_kb("wiz_add_svc"))
    return SVC_NAME_EN


async def svc_name_en(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["wiz"]["name_en"] = update.message.text
    await update.message.reply_text(
        "الخطوة 4/5 — أرسل *وصف الخدمة* (أو `-` لتخطي):",
        parse_mode="Markdown", reply_markup=back_cancel_kb("wiz_add_svc"))
    return SVC_DESC


async def svc_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data["wiz"]["desc"] = "" if text == "-" else text
    await update.message.reply_text(
        "الخطوة 5/5 — أرسل *الحد الأدنى للطلب* (رقم، أو `0` بدون حد):",
        parse_mode="Markdown", reply_markup=back_cancel_kb("wiz_add_svc"))
    return SVC_MIN


async def svc_min(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        min_val = float(update.message.text)
    except Exception:
        await update.message.reply_text("❌ أرسل رقماً صحيحاً مثل: 5 أو 0")
        return SVC_MIN
    w = context.user_data["wiz"]
    db.add_service(w["name_ar"], w["name_en"], w["desc"], "", "digital", w["type_id"], min_val)
    context.user_data.pop("wiz", None)
    await update.message.reply_text(
        f"✅ *تم إضافة الخدمة!*\n\n🔵 {w['name_ar']}\n"
        f"الآن أضف أنواعاً لها من /admin ← 🗂️ أنواع الخدمة\n"
        f"أو أضف خطة مباشرة من /admin ← ➕ خطة جديدة",
        parse_mode="Markdown")
    return ConversationHandler.END


# ══════════════════════════════════════════
#   ② إضافة خطة
# ══════════════════════════════════════════

async def wiz_add_plan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return ConversationHandler.END
    services = db.get_services()
    sub_services = [s for s in (services or []) if s.get("type_name") == "subscription"]
    if not sub_services:
        await q.edit_message_text("❌ أضف خدمة اشتراكات أولاً")
        return ConversationHandler.END
    context.user_data["wiz"] = {}
    btns = [[InlineKeyboardButton(s["name_ar"], callback_data=f"plansvc_{s['id']}")] for s in sub_services]
    btns.append([InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")])
    await q.edit_message_text(
        "➕ *خطة جديدة*\n\nاختر الخدمة:",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))
    return PLAN_SVC


async def plan_svc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    svc_id = int(q.data.split("_")[1])
    context.user_data["wiz"]["svc_id"]     = svc_id
    context.user_data["wiz"]["variant_id"] = None
    variants = db.get_variants(svc_id)
    if variants:
        btns = [[InlineKeyboardButton(v["name_ar"], callback_data=f"planvar_{v['id']}")] for v in variants]
        btns.append([InlineKeyboardButton("⏭️ بدون نوع", callback_data="planvar_0")])
        btns.append([InlineKeyboardButton("❌ إلغاء",    callback_data="wizard_cancel")])
        await q.edit_message_text("اختر *نوع الخطة*:", parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(btns))
        return PLAN_NAME_AR
    await q.edit_message_text(
        "أرسل *اسم الخطة بالعربي*:\nمثال: شهر واحد، شحن 500 ل.س",
        parse_mode="Markdown", reply_markup=cancel_kb())
    return PLAN_NAME_AR


async def plan_variant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    val = q.data.split("_")[1]
    context.user_data["wiz"]["variant_id"] = None if val == "0" else int(val)
    await q.edit_message_text(
        "أرسل *اسم الخطة بالعربي*:\nمثال: شهر واحد، 3 أشهر",
        parse_mode="Markdown", reply_markup=cancel_kb())
    return PLAN_NAME_AR


async def plan_name_ar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["wiz"]["name_ar"] = update.message.text
    await update.message.reply_text(
        "أرسل *اسم الخطة بالإنجليزي*:",
        parse_mode="Markdown", reply_markup=back_cancel_kb("wiz_add_plan"))
    return PLAN_NAME_EN


async def plan_name_en(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["wiz"]["name_en"] = update.message.text
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("30 يوم",  callback_data="pdays_30"),
         InlineKeyboardButton("90 يوم",  callback_data="pdays_90"),
         InlineKeyboardButton("365 يوم", callback_data="pdays_365")],
        [InlineKeyboardButton("لا ينطبق (رصيد/تحويل)", callback_data="pdays_0")],
        [InlineKeyboardButton("✏️ أدخل يدوياً", callback_data="pdays_custom")],
        [InlineKeyboardButton("◀️ رجوع", callback_data="wiz_add_plan"),
         InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")],
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
    await q.edit_message_text(
        "أرسل *السعر بالـ USDT*:\nمثال: 5.99",
        parse_mode="Markdown", reply_markup=cancel_kb())
    return PLAN_PRICE


async def plan_days_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data["wiz"].get("_custom_days"):
        try:
            context.user_data["wiz"]["days"] = int(update.message.text)
            context.user_data["wiz"].pop("_custom_days", None)
        except Exception:
            await update.message.reply_text("❌ أرسل رقماً صحيحاً:")
            return PLAN_DAYS
        await update.message.reply_text(
            "أرسل *السعر بالـ USDT*:", parse_mode="Markdown", reply_markup=cancel_kb())
        return PLAN_PRICE
    return PLAN_DAYS


async def plan_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["wiz"]["price"] = float(update.message.text)
    except Exception:
        await update.message.reply_text("❌ أرسل رقماً مثل: 5.99")
        return PLAN_PRICE
    await update.message.reply_text(
        "أرسل *مميزات الخطة* (كل ميزة في سطر)\nأو `-` لتخطي:",
        parse_mode="Markdown", reply_markup=back_cancel_kb("wiz_add_plan"))
    return PLAN_FEATS


async def plan_feats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data["wiz"]["features"] = (
        [] if text == "-" else [l.strip() for l in text.split("\n") if l.strip()]
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ نعم، أضف خيارات", callback_data="plan_add_opts"),
         InlineKeyboardButton("⏭️ تخطي",            callback_data="plan_skip_opts")],
        [InlineKeyboardButton("◀️ رجوع", callback_data="wiz_add_plan"),
         InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")],
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
    i = 0
    while i < len(lines):
        line = lines[i]
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
            "*خيارات أزرار:*\n`السؤال: كيف تريد؟`\n`خيار1: على إيميلك`\n`خيار2: إيميل من عندنا`\n\n"
            "*حقل نص:*\n`حقل: رقم هاتفك`\n`مفتاح: phone`",
            parse_mode="Markdown")
    return PLAN_OPTS_Q


async def _save_plan(q, context, options):
    w = context.user_data["wiz"]
    db.add_plan_full(
        w["svc_id"], w["name_ar"], w["name_en"],
        w.get("days", 0), w["price"],
        w.get("features", []), options,
        variant_id=w.get("variant_id")
    )
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
    db.add_plan_full(
        w["svc_id"], w["name_ar"], w["name_en"],
        w.get("days", 0), w["price"],
        w.get("features", []), options,
        variant_id=w.get("variant_id")
    )
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
    await q.edit_message_text(
        "✏️ *تعديل خدمة*\n\nاختر الخدمة:",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))
    return EDIT_SVC


async def edit_svc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    svc_id = int(q.data.split("_")[1])
    svc    = db.get_service(svc_id)
    plans  = db.get_plans(svc_id)
    context.user_data["wiz"]["svc_id"] = svc_id
    btns = [
        [InlineKeyboardButton("الاسم العربي",    callback_data="ef_name_ar"),
         InlineKeyboardButton("الاسم الإنجليزي", callback_data="ef_name_en")],
        [InlineKeyboardButton("الوصف",           callback_data="ef_description_ar"),
         InlineKeyboardButton("الحد الأدنى",     callback_data="ef_min_amount")],
        [InlineKeyboardButton("🔴 إخفاء",        callback_data="ef_hide"),
         InlineKeyboardButton("🟢 إظهار",        callback_data="ef_show")],
    ]
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
            f"أو `حذف` لإزالة كل الخيارات.",
            parse_mode="Markdown", reply_markup=cancel_kb())
        return EDIT_PLAN_OPTS

    LABELS = {
        "name_ar": "الاسم العربي", "name_en": "الاسم الإنجليزي",
        "description_ar": "الوصف", "min_amount": "الحد الأدنى"
    }
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
        try:
            value = float(value)
        except Exception:
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

    lines   = [l.strip() for l in text.split("\n") if l.strip()]
    options = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("حقل:"):
            question = line.replace("حقل:", "").strip()
            key = lines[i+1].replace("مفتاح:", "").strip() if i+1 < len(lines) and lines[i+1].startswith("مفتاح:") else question
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
    await update.message.reply_text(
        f"✅ *تم تحديث الخيارات!*\n\n{summary}", parse_mode="Markdown")
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
                btns.append([InlineKeyboardButton(
                    f"{svc['name_ar']} — {p['name_ar']}",
                    callback_data=f"delitem_{p['id']}"
                )])
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
    exchange = [s for s in services if s.get("type_name") == "exchange"] or services
    btns = [[InlineKeyboardButton(s["name_ar"], callback_data=f"ratesvc_{s['id']}")] for s in exchange]
    btns.append([InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")])
    await q.edit_message_text(
        "💱 *تحديث سعر الصرف*\n\nاختر الخدمة:",
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
        parse_mode="Markdown", reply_markup=back_cancel_kb("wiz_rate"))
    return RATE_VALUE


async def rate_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rate = float(update.message.text.replace(",", ""))
    except Exception:
        await update.message.reply_text("❌ أرسل رقماً صحيحاً مثل: 14500")
        return RATE_VALUE
    svc_id = context.user_data["wiz"]["svc_id"]
    db.set_exchange_rate(svc_id, rate)
    context.user_data.pop("wiz", None)
    await update.message.reply_text(
        f"✅ تم تحديث السعر: 1 USDT = *{rate:,.0f}* ل.س",
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
    except Exception:
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
    db.create_subscription(
        user["id"], w["plan_id"], order_id,
        plan["service_id"], plan["duration_days"], json.dumps(creds))
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
            parse_mode="Markdown")
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

# ══════════════════════════════════════════
#   إدارة الطلبات
# ══════════════════════════════════════════
(ORD_MAIN, ORD_SEARCH, ORD_DETAIL, ORD_CONFIRM) = range(100, 104)

PER_PAGE = 5

def _order_status_label(status):
    return {
        "awaiting_approval": "⏳ معلق",
        "paid":              "✅ منجز",
        "completed":         "✅ منجز",
        "rejected":          "❌ مرفوض",
        "pending":           "⏳ معلق",
    }.get(status, status)


def _build_orders_kb(orders, total, page, order_type, status_filter, search=None):
    btns = []
    for o in orders:
        label = (
            "#" + str(o["id"]) + " | " +
            (o.get("full_name") or "—") + " | " +
            f"{o.get('amount_local') or o.get('amount', 0):,.0f}" +
            (" ل.س" if o.get("order_type") == "recharge" else " USDT") +
            " | " + _order_status_label(o["status"])
        )
        btns.append([InlineKeyboardButton(label, callback_data="orddetail_" + str(o["id"]))])

    # pagination
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ السابق", callback_data=f"ordpage_{order_type}_{status_filter}_{page-1}"))
    total_pages = (total + PER_PAGE - 1) // PER_PAGE
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if (page + 1) * PER_PAGE < total:
        nav.append(InlineKeyboardButton("التالي ▶️", callback_data=f"ordpage_{order_type}_{status_filter}_{page+1}"))
    if nav:
        btns.append(nav)

    # فلاتر
    filters_row = []
    for s, label in [("all", "الكل"), ("awaiting_approval", "⏳ معلقة"), ("paid", "✅ منجزة"), ("rejected", "❌ مرفوضة")]:
        mark = "•" if s == status_filter else ""
        filters_row.append(InlineKeyboardButton(mark + label, callback_data=f"ordfilter_{order_type}_{s}"))
    btns.append(filters_row[:2])
    btns.append(filters_row[2:])

    btns.append([InlineKeyboardButton("🔍 بحث", callback_data=f"ordsearch_{order_type}")])
    btns.append([InlineKeyboardButton("◀️ رجوع", callback_data="wiz_orders")])
    return InlineKeyboardMarkup(btns)


async def cb_orders_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    pending_sub = db.get_subscription_orders(status="awaiting_approval")[1]
    pending_rch = db.get_recharge_orders(status="pending")[1]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "📦 طلبات الاشتراكات" + (f" ({pending_sub} معلق)" if pending_sub else ""),
            callback_data="ordtype_subscription_awaiting_approval_0")],
        [InlineKeyboardButton(
            "📱 طلبات التعبئة" + (f" ({pending_rch} معلق)" if pending_rch else ""),
            callback_data="ordtype_recharge_pending_0")],
        [InlineKeyboardButton("◀️ رجوع", callback_data="admin_back")],
    ])
    await q.edit_message_text("⏳ *إدارة الطلبات*\n\nاختر نوع الطلب:", parse_mode="Markdown", reply_markup=kb)


async def cb_orders_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    parts       = q.data.split("_")
    order_type  = parts[1]
    status      = parts[2]
    page        = int(parts[3])
    context.user_data["ord"] = {"type": order_type, "status": status, "page": page, "search": None}
    await _show_orders(q, context, order_type, status, page)


async def cb_orders_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    parts      = q.data.split("_")
    order_type = parts[1]
    status     = parts[2]
    page       = int(parts[3])
    search     = (context.user_data.get("ord") or {}).get("search")
    context.user_data["ord"] = {"type": order_type, "status": status, "page": page, "search": search}
    await _show_orders(q, context, order_type, status, page, search)


async def cb_orders_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    parts      = q.data.split("_")
    order_type = parts[1]
    status     = parts[2]
    search     = (context.user_data.get("ord") or {}).get("search")
    context.user_data["ord"] = {"type": order_type, "status": status, "page": 0, "search": search}
    await _show_orders(q, context, order_type, status, 0, search)


async def _show_orders(q, context, order_type, status, page, search=None):
    status_param = None if status == "all" else status
    if order_type == "recharge":
        orders, total = db.get_recharge_orders(status=status_param, page=page, per_page=PER_PAGE, search=search)
    else:
        orders, total = db.get_subscription_orders(status=status_param, page=page, per_page=PER_PAGE, search=search)

    type_label = "التعبئة" if order_type == "recharge" else "الاشتراكات"
    if not orders:
        await q.edit_message_text(
            "لا توجد طلبات.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ رجوع", callback_data="wiz_orders")]]))
        return

    header = f"📋 طلبات {type_label} | {total} طلب"
    if search:
        header += f" | بحث: {search}"
    await q.edit_message_text(
        header,
        parse_mode="Markdown",
        reply_markup=_build_orders_kb(orders, total, page, order_type, status, search))


async def cb_orders_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    order_type = q.data.split("_")[1]
    context.user_data["ord_search_type"] = order_type
    db.set_user_state(q.from_user.id, "ADMIN_ORD_SEARCH")
    await q.edit_message_text(
        "🔍 ابحث باسم المستخدم، @username، رقم الطلب، أو رقم الهاتف:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="wiz_orders")]]))


async def cb_order_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    order_id = int(q.data.split("_")[1])
    order    = db.get_order_by_id(order_id)
    if not order:
        await q.answer("الطلب غير موجود", show_alert=True); return

    is_rch = order.get("order_type") == "recharge"
    lines  = [
        f"🔖 *طلب #{order['id']}*",
        f"👤 {order['full_name']} (@{order.get('username') or '—'})",
        f"🛍️ {order['svc_ar']}",
    ]
    if is_rch:
        lines += [
            f"💵 {order.get('amount_local', 0):,.0f} ل.س",
            f"💳 {order['amount']} USDT",
            f"📞 `{order.get('phone_number') or '—'}`",
        ]
    else:
        lines += [
            f"📦 {order.get('plan_name_ar') or '—'}",
            f"💳 {order['amount']} USDT",
        ]
    lines.append(f"📊 {_order_status_label(order['status'])}")
    lines.append(f"🕐 {order['created_at'].strftime('%Y-%m-%d %H:%M') if order.get('created_at') else '—'}")

    # خيارات المستخدم
    try:
        opts = {**(json.loads(order.get("user_options") or "{}")), **(json.loads(order.get("user_inputs") or "{}"))}
        if opts:
            lines.append("\n📋 خيارات:")
            for k, v in opts.items():
                lines.append(f"  • {k}: {v}")
    except Exception:
        pass

    btns = []
    status = order["status"]
    pending = status in ("awaiting_approval", "pending")
    if pending:
        btns.append([
            InlineKeyboardButton("✅ قبول",  callback_data=f"ordconfirm_approve_{order_id}"),
            InlineKeyboardButton("❌ رفض",   callback_data=f"ordconfirm_reject_{order_id}"),
        ])

    # صورة الإشعار إن وجدت
    try:
        proof = json.loads(order.get("user_inputs") or "{}").get("proof_file_id")
        if proof:
            btns.append([InlineKeyboardButton("🖼️ عرض الإشعار", callback_data=f"ordproof_{order_id}")])
    except Exception:
        pass

    ord_ctx = context.user_data.get("ord", {})
    back_data = f"ordtype_{ord_ctx.get('type','subscription')}_{ord_ctx.get('status','all')}_{ord_ctx.get('page',0)}"
    btns.append([InlineKeyboardButton("◀️ رجوع", callback_data=back_data)])

    await q.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))


async def cb_order_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    parts    = q.data.split("_")
    action   = parts[1]
    order_id = int(parts[2])
    order    = db.get_order_by_id(order_id)
    if not order:
        await q.answer("الطلب غير موجود", show_alert=True); return

    action_label = "قبول" if action == "approve" else "رفض"
    await q.edit_message_text(
        f"⚠️ هل أنت متأكد من *{action_label}* طلب #{order_id}؟\n\n"
        f"👤 {order['full_name']}\n"
        f"💳 {order['amount']} USDT",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"✅ نعم، {action_label}", callback_data=f"ordexec_{action}_{order_id}"),
             InlineKeyboardButton("◀️ لا، رجوع",             callback_data=f"orddetail_{order_id}")]
        ]))


async def cb_order_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    parts    = q.data.split("_")
    action   = parts[1]
    order_id = int(parts[2])
    order    = db.get_order_by_id(order_id)
    if not order:
        await q.answer("الطلب غير موجود", show_alert=True); return

    is_rch = order.get("order_type") == "recharge"

    if action == "approve":
        if is_rch:
            db.complete_recharge_order(order_id)
            msg = f"✅ تمت التعبئة\nالمبلغ: {order.get('amount_local', 0):,.0f} ل.س\nالرقم: {order.get('phone_number') or '—'}"
        else:
            db.approve_subscription_order(order_id)
            # إنشاء الاشتراك
            plan = db.get_plan(order["plan_id"]) if order.get("plan_id") else None
            if plan:
                db.create_subscription(
                    order["user_id"], order["plan_id"], order_id,
                    order["service_id"], plan["duration_days"])
            msg = f"✅ تم تفعيل اشتراكك!\n📦 {order.get('plan_name_ar') or '—'}"
        # إشعار المستخدم
        try:
            await context.bot.send_message(chat_id=order["user_id"], text=msg)
        except Exception:
            pass
        await q.edit_message_text(f"✅ تم قبول الطلب #{order_id}")
    else:
        db.reject_order(order_id)
        try:
            await context.bot.send_message(
                chat_id=order["user_id"],
                text=f"❌ تم رفض طلبك #{order_id}\nللاستفسار تواصل مع الدعم.")
        except Exception:
            pass
        await q.edit_message_text(f"❌ تم رفض الطلب #{order_id}")


async def cb_order_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    order_id = int(q.data.split("_")[1])
    order    = db.get_order_by_id(order_id)
    try:
        file_id = json.loads(order.get("user_inputs") or "{}").get("proof_file_id")
        if file_id:
            await context.bot.send_photo(
                chat_id=q.from_user.id, photo=file_id,
                caption=f"إشعار دفع طلب #{order_id}")
        else:
            await q.answer("لا توجد صورة إشعار", show_alert=True)
    except Exception:
        await q.answer("تعذر عرض الصورة", show_alert=True)



async def cb_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tickets = db.get_open_tickets()
    if not tickets:
        await q.edit_message_text(
            "✅ لا توجد تذاكر مفتوحة",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ رجوع", callback_data="admin_back")]]))
        return
    for t in tickets[:5]:
        await context.bot.send_message(
            chat_id=q.from_user.id,
            text=f"🎫 *تذكرة #{t['id']}*\n👤 {t['full_name']}\n\n💬 {t['message']}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💬 رد", callback_data=f"replyticket_{t['id']}_{t['user_id']}")
            ]]))


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
        except Exception:
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
#   أنواع الخدمة (Variants)
# ══════════════════════════════════════════

async def wiz_variants_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return ConversationHandler.END
    services = db.get_services()
    # فلترة الاشتراكات الرقمية فقط
    sub_services = [s for s in (services or []) if s.get("type_name") == "subscription"]
    if not sub_services:
        await q.edit_message_text(
            "❌ لا توجد خدمات اشتراكات رقمية\n\nأضف خدمة من نوع *اشتراك رقمي* أولاً.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ رجوع", callback_data="admin_back")]]))
        return ConversationHandler.END
    btns = [[InlineKeyboardButton("📺 " + s["name_ar"], callback_data=f"varsvc_{s['id']}")] for s in sub_services]
    btns.append([InlineKeyboardButton("◀️ رجوع", callback_data="admin_back")])
    await q.edit_message_text(
        "🗂️ *أنواع الخدمة — الاشتراكات الرقمية*\n\nاختر الخدمة لإدارة أنواعها:",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))
    return VAR_SVC


async def var_svc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    svc_id   = int(q.data.split("_")[1])
    context.user_data["wiz"] = {"svc_id": svc_id}
    svc      = db.get_service(svc_id)
    variants = db.get_variants(svc_id)

    lines = [f"🗂️ *أنواع {svc['name_ar']}*\n"]
    btns  = []
    if variants:
        for v in variants:
            opts = db.get_variant_options(v["id"])
            lines.append(f"• *{v['name_ar']}* — {len(opts)} خيارات")
            btns.append([InlineKeyboardButton(
                f"🗑️ حذف: {v['name_ar']}",
                callback_data=f"vardelete_{v['id']}"
            )])
    else:
        lines.append("_لا توجد أنواع بعد_")

    btns.append([InlineKeyboardButton("➕ نوع جديد", callback_data=f"varadd_{svc_id}")])
    btns.append([InlineKeyboardButton("◀️ رجوع",    callback_data="wiz_variants")])
    await q.edit_message_text(
        "\n".join(lines),
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))
    return VAR_SVC


async def var_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    svc_id = int(q.data.split("_")[1])
    context.user_data["wiz"]["svc_id"] = svc_id
    await q.edit_message_text(
        "أرسل *اسم النوع بالعربي*:\nمثال: حساب مشترك، Business، عائلي",
        parse_mode="Markdown", reply_markup=back_cancel_kb(f"varsvc_{svc_id}"))
    return VAR_NAME_AR


async def var_name_ar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["wiz"]["var_name_ar"] = update.message.text.strip()
    await update.message.reply_text(
        "أرسل *اسم النوع بالإنجليزي*:",
        parse_mode="Markdown", reply_markup=back_cancel_kb("wiz_variants"))
    return VAR_NAME_EN


async def var_name_en(update: Update, context: ContextTypes.DEFAULT_TYPE):
    w = context.user_data["wiz"]
    w["var_name_en"] = update.message.text.strip()
    w["var_options"] = []
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ نعم، أضف خيارات", callback_data="varopts_yes"),
         InlineKeyboardButton("⏭️ تخطي",            callback_data="varopts_skip")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="wizard_cancel")],
    ])
    await update.message.reply_text(
        "هل تريد إضافة خيارات لهذا النوع؟\n\n"
        "مثال: على إيميلك / إيميل من عندنا\n"
        "أو حقل نصي: رقم هاتف، إيميل...",
        reply_markup=kb)
    return VAR_OPTS


async def var_opts_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    w   = context.user_data["wiz"]
    svc = db.get_service(w["svc_id"])
    db.add_variant(w["svc_id"], w["var_name_ar"], w["var_name_en"], options=[])
    context.user_data.pop("wiz", None)
    await q.edit_message_text(
        f"✅ تم إضافة النوع *{w['var_name_ar']}* لخدمة {svc['name_ar']}\n\n"
        f"الآن أضف خططاً له من /admin ← ➕ خطة جديدة",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ لوحة الأدمن", callback_data="admin_back")
        ]]))
    return ConversationHandler.END


async def var_opts_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(
        "🔘 *إضافة خيارات للنوع*\n\n"
        "*خيارات أزرار:*\n"
        "`السؤال: كيف تريد الاشتراك؟`\n"
        "`خيار1: على إيميلك`\n"
        "`خيار2: إيميل من عندنا`\n\n"
        "*حقل نص:*\n"
        "`حقل: الإيميل`\n"
        "`مفتاح: email`\n\n"
        "أرسل `تم` لما تخلص.",
        parse_mode="Markdown", reply_markup=cancel_kb())
    return VAR_OPTS


async def var_collect_opts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    w    = context.user_data["wiz"]

    if text == "تم":
        svc = db.get_service(w["svc_id"])
        db.add_variant(w["svc_id"], w["var_name_ar"], w["var_name_en"], options=w.get("var_options", []))
        context.user_data.pop("wiz", None)
        await update.message.reply_text(
            f"✅ تم إضافة النوع *{w['var_name_ar']}* بـ {len(w.get('var_options', []))} خيارات\n\n"
            f"الآن أضف خططاً له من /admin ← ➕ خطة جديدة",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ لوحة الأدمن", callback_data="admin_back")
            ]]))
        return ConversationHandler.END

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    added = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("السؤال:"):
            question = line.replace("السؤال:", "").strip()
            choices  = []
            i += 1
            while i < len(lines) and lines[i].startswith("خيار"):
                choices.append(lines[i].split(":", 1)[-1].strip())
                i += 1
            if question and choices:
                w["var_options"].append({"type": "choice", "question": question, "choices": choices})
                added.append(f"🔘 {question}: " + " | ".join(choices))
        elif line.startswith("حقل:"):
            question = line.replace("حقل:", "").strip()
            key = question
            if i + 1 < len(lines) and lines[i+1].startswith("مفتاح:"):
                key = lines[i+1].replace("مفتاح:", "").strip()
                i += 1
            if question:
                w["var_options"].append({"type": "input", "question": question, "key": key})
                added.append(f"📝 {question}")
            i += 1
        else:
            i += 1

    if added:
        await update.message.reply_text(
            "\n".join(f"✅ {a}" for a in added) + "\n\nأرسل خياراً آخر أو `تم`",
            parse_mode="Markdown")
    else:
        await update.message.reply_text(
            "❌ الصيغة غلط. مثال:\n"
            "`السؤال: كيف تريد؟`\n`خيار1: ...`\n`خيار2: ...`\n\n"
            "أو:\n`حقل: الإيميل`\n`مفتاح: email`",
            parse_mode="Markdown")
    return VAR_OPTS


async def var_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return ConversationHandler.END
    var_id = int(q.data.split("_")[1])
    db.delete_variant(var_id)
    await q.edit_message_text(
        "✅ تم حذف النوع.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ لوحة الأدمن", callback_data="admin_back")
        ]]))
    return ConversationHandler.END


# ══════════════════════════════════════════
#   تسجيل الـ Handlers
# ══════════════════════════════════════════

# ══════════════════════════════════════════
#   إعدادات خدمة التعبئة / سيرياتيل كاش
# ══════════════════════════════════════════

async def wiz_recharge_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return ConversationHandler.END
    services = db.get_services()
    recharge = [s for s in services if s.get("type_name") == "recharge"] or services
    btns = [[InlineKeyboardButton(s["name_ar"], callback_data="rchsvc_" + str(s["id"]))] for s in recharge]
    btns.append([InlineKeyboardButton("الغاء", callback_data="wizard_cancel")])
    await q.edit_message_text("اعدادات التعبئة\n\nاختر الخدمة:", reply_markup=InlineKeyboardMarkup(btns))
    return RCH_SVC


async def rch_svc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    svc_id  = int(q.data.split("_")[1])
    svc     = db.get_service(svc_id)
    context.user_data["wiz"] = {"svc_id": svc_id}
    limits  = db.get_service_limits(svc_id)
    rate    = db.get_recharge_rate(svc_id)
    presets = db.get_recharge_presets(svc_id)

    lines = [svc["name_ar"] + "\n"]
    if rate:
        lines.append("سعر الصرف: " + f"{rate:,.0f}" + " ل.س / USDT")
    else:
        lines.append("سعر الصرف: غير محدد")
    if limits:
        if limits.get("min_amount"):
            lines.append("الحد الادنى: " + f"{limits['min_amount']:,.0f}" + " ل.س")
        if limits.get("max_amount"):
            lines.append("الحد الاقصى: " + f"{limits['max_amount']:,.0f}" + " ل.س")
        if limits.get("daily_limit"):
            lines.append("الحد اليومي: " + str(limits["daily_limit"]) + " طلب")
    if presets:
        lines.append("\nالمبالغ الجاهزة:")
        for p in presets:
            lines.append("  - " + f"{p['rate']:,.0f}" + " ل.س")

    btns = [
        [InlineKeyboardButton("تحديث سعر الصرف",    callback_data="rch_setrate")],
        [InlineKeyboardButton("تحديث المبالغ الجاهزة", callback_data="rch_setpresets")],
        [InlineKeyboardButton("تحديث الحدود",        callback_data="rch_setlimits")],
        [InlineKeyboardButton("الغاء",               callback_data="wizard_cancel")],
    ]
    await q.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(btns))
    return RCH_RATE


async def rch_set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["wiz"]["rch_action"] = "rate"
    await q.edit_message_text(
        "ارسل سعر الصرف الجديد\n\nكم ليرة سورية = 1 USDT؟\nمثال: 14500",
        reply_markup=cancel_kb())
    return RCH_RATE


async def rch_set_presets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["wiz"]["rch_action"] = "presets"
    await q.edit_message_text(
        "ارسل المبالغ الجاهزة بالليرة السورية\n\nكل مبلغ في سطر:\n500\n1000\n2000\n5000",
        reply_markup=cancel_kb())
    return RCH_PRESETS


async def rch_set_limits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["wiz"]["rch_action"] = "limits"
    await q.edit_message_text(
        "ارسل الحدود بهذا الشكل:\n\nادنى: 500\nاقصى: 50000\nyomiy: 3\n\nيمكن ارسال سطر او اكثر.",
        reply_markup=cancel_kb())
    return RCH_LIMITS


async def rch_collect_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    svc_id = context.user_data["wiz"]["svc_id"]
    text   = update.message.text.strip().replace(",", "")
    try:
        rate = float(text)
    except Exception:
        await update.message.reply_text("خطأ — ارسل رقما صحيحا مثل: 14500")
        return RCH_RATE
    db.set_exchange_rate(svc_id, rate)
    context.user_data.pop("wiz", None)
    await update.message.reply_text(
        "تم تحديث سعر الصرف: 1 USDT = " + f"{rate:,.0f}" + " ل.س",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("لوحة الادمن", callback_data="admin_back")]]))
    return ConversationHandler.END


async def rch_collect_presets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    svc_id = context.user_data["wiz"]["svc_id"]
    lines  = [l.strip().replace(",", "") for l in update.message.text.strip().split("\n") if l.strip()]
    rate   = db.get_recharge_rate(svc_id)
    added  = []
    for line in lines:
        try:
            amount = float(line)
            usdt   = round(amount / rate, 4) if rate else 0
            db.set_recharge_preset(svc_id, amount, usdt)
            added.append(str(int(amount)) + " ل.س = " + str(usdt) + " USDT")
        except Exception:
            pass
    if not added:
        await update.message.reply_text("صيغة غلط — ارسل ارقاما فقط كل رقم في سطر")
        return RCH_PRESETS
    context.user_data.pop("wiz", None)
    await update.message.reply_text(
        "تم تحديث المبالغ:\n" + "\n".join(added),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("لوحة الادمن", callback_data="admin_back")]]))
    return ConversationHandler.END


async def rch_collect_limits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    svc_id = context.user_data["wiz"]["svc_id"]
    lines  = [l.strip() for l in update.message.text.strip().split("\n") if l.strip()]
    mn = mx = daily = None
    for line in lines:
        if line.startswith("ادنى:") or line.startswith("أدنى:"):
            try: mn = float(line.split(":", 1)[1].strip().replace(",", ""))
            except Exception: pass
        elif line.startswith("اقصى:") or line.startswith("أقصى:"):
            try: mx = float(line.split(":", 1)[1].strip().replace(",", ""))
            except Exception: pass
        elif line.startswith("يومي:"):
            try: daily = int(line.split(":", 1)[1].strip())
            except Exception: pass
    if mn is None and mx is None and daily is None:
        await update.message.reply_text("صيغة غلط. مثال:\nادنى: 500\nاقصى: 50000\nيومي: 3")
        return RCH_LIMITS
    db.update_service_limits(svc_id, mn, mx, daily)
    context.user_data.pop("wiz", None)
    parts = []
    if mn    is not None: parts.append("الحد الادنى: " + f"{mn:,.0f}" + " ل.س")
    if mx    is not None: parts.append("الحد الاقصى: " + f"{mx:,.0f}" + " ل.س")
    if daily is not None: parts.append("الحد اليومي: " + str(daily) + " طلب")
    await update.message.reply_text(
        "تم التحديث:\n" + "\n".join(parts),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("لوحة الادمن", callback_data="admin_back")]]))
    return ConversationHandler.END





# ══════════════════════════════════════════════════════
#   إدارة الاشتراكات — Admin Subscriptions Management
# ══════════════════════════════════════════════════════

def _sub_status_label(row) -> str:
    from datetime import datetime
    if row["status"] == "cancelled":
        return "❌ ملغى"
    expires = row["expires_at"]
    if expires and expires.replace(tzinfo=None) > datetime.now():
        return "✅ نشط"
    return "⏰ منتهي"


async def cb_subs_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    status = context.user_data.get("sub_status", "all")
    page   = context.user_data.get("sub_page", 0)
    search = context.user_data.get("sub_search", "")
    context.user_data.pop("sub_search_active", None)

    rows, total = db.get_subscriptions_admin(status=status, page=page, per_page=PER_PAGE, search=search)
    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)

    filters_row = [
        InlineKeyboardButton("الكل"   + (" ✓" if status == "all"     else ""), callback_data="subfilter_all"),
        InlineKeyboardButton("نشطة"   + (" ✓" if status == "active"  else ""), callback_data="subfilter_active"),
        InlineKeyboardButton("منتهية" + (" ✓" if status == "expired" else ""), callback_data="subfilter_expired"),
    ]

    kbd = [filters_row]
    for row in rows:
        label = f"{_sub_status_label(row)} #{row['id']} — {row['username'] or row['full_name'] or row['user_id']} | {row['service_name']}"
        kbd.append([InlineKeyboardButton(label, callback_data=f"subdetail_{row['id']}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ السابق", callback_data=f"subpage_{page-1}"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton("التالي ▶️", callback_data=f"subpage_{page+1}"))
    if nav:
        kbd.append(nav)

    kbd.append([InlineKeyboardButton("🔍 بحث", callback_data="subsearch_start")])
    kbd.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")])

    search_note = (f"\n🔍 بحث: `{search}`") if search else ""
    text = f"📋 *الاشتراكات* — {total} إجمالي{search_note}\nالصفحة {page+1}/{pages}"
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")
    return SUB_MAIN


async def cb_subs_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    status = q.data.replace("subfilter_", "")
    context.user_data["sub_status"] = status
    context.user_data["sub_page"]   = 0
    context.user_data.pop("sub_search", None)
    return await cb_subs_main(update, context)


async def cb_subs_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["sub_page"] = int(q.data.replace("subpage_", ""))
    return await cb_subs_main(update, context)


async def cb_subs_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["sub_search_active"] = True
    await q.edit_message_text("🔍 أرسل اسم المستخدم أو ID المستخدم أو رقم الاشتراك:")
    return SUB_SEARCH


async def cb_subs_search_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["sub_search"] = text
    context.user_data["sub_page"]   = 0

    class _FakeQuery:
        async def answer(self): pass
        async def edit_message_text(self, *a, **kw):
            await update.message.reply_text(*a, **kw)
        data = "wiz_subs"

    update.callback_query = _FakeQuery()
    return await cb_subs_main(update, context)


async def cb_sub_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    sub_id = int(q.data.replace("subdetail_", ""))
    context.user_data["sub_id"] = sub_id

    sub = db.get_subscription_by_id(sub_id)
    if not sub:
        await q.edit_message_text("❌ الاشتراك غير موجود.")
        return SUB_MAIN

    import json
    creds = {}
    try:
        creds = json.loads(sub.get("credentials") or "{}")
    except Exception:
        pass

    status_label = _sub_status_label(sub)
    expires = sub["expires_at"].strftime("%Y-%m-%d %H:%M") if sub["expires_at"] else "—"
    started = sub["started_at"].strftime("%Y-%m-%d") if sub["started_at"] else "—"

    creds_text = ""
    if creds:
        creds_text = "\n".join([f"• {k}: `{v}`" for k, v in creds.items()])
        creds_text = f"\n\n🔑 *بيانات الدخول:*\n{creds_text}"

    text = (
        f"📋 *اشتراك #{sub_id}*\n"
        f"👤 المستخدم: @{sub['username'] or '—'} (`{sub['user_id']}`)\n"
        f"📦 الخدمة: {sub['service_name']}\n"
        f"📅 الخطة: {sub['plan_name']} ({sub['duration_days']} يوم)\n"
        f"🟢 الحالة: {status_label}\n"
        f"📆 بدء: {started}\n"
        f"⏳ انتهاء: {expires}"
        f"{creds_text}"
    )

    kbd = [
        [InlineKeyboardButton("⏳ تمديد", callback_data=f"subextend_{sub_id}"),
         InlineKeyboardButton("❌ إلغاء", callback_data=f"subcancel_{sub_id}")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="wiz_subs")],
    ]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")
    return SUB_DETAIL


async def cb_sub_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("✅ تم إلغاء الاشتراك", show_alert=True)
    sub_id = int(q.data.replace("subcancel_", ""))
    db.cancel_subscription(sub_id)
    q.data = f"subdetail_{sub_id}"
    return await cb_sub_detail(update, context)


async def cb_sub_extend_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    sub_id = int(q.data.replace("subextend_", ""))
    context.user_data["sub_id"] = sub_id
    kbd = [[InlineKeyboardButton("🔙 رجوع", callback_data=f"subdetail_{sub_id}")]]
    await q.edit_message_text(
        f"⏳ كم يوم تريد تمديد الاشتراك #{sub_id}؟\nأرسل عدد الأيام (مثال: 7):",
        reply_markup=InlineKeyboardMarkup(kbd)
    )
    return SUB_EXTEND


async def cb_sub_extend_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    sub_id = context.user_data.get("sub_id")

    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("❌ أرسل عدد أيام صحيح (مثال: 7)")
        return SUB_EXTEND

    days = int(text)
    db.extend_subscription(sub_id, days)
    await update.message.reply_text(f"✅ تم تمديد الاشتراك #{sub_id} بمقدار {days} يوم.")

    class _FakeQuery:
        async def answer(self): pass
        async def edit_message_text(self, *a, **kw):
            await update.message.reply_text(*a, **kw)
        data = f"subdetail_{sub_id}"

    update.callback_query = _FakeQuery()
    return await cb_sub_detail(update, context)


# ══════════════════════════════════════════════════════
#   إدارة المستخدمين — Admin Users Management
# ══════════════════════════════════════════════════════

async def cb_users_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    status = context.user_data.get("usr_status", "all")
    page   = context.user_data.get("usr_page", 0)
    search = context.user_data.get("usr_search", "")

    rows, total = db.get_users_admin(status=status, page=page, per_page=PER_PAGE, search=search)
    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)

    filters_row = [
        InlineKeyboardButton("الكل"   + (" ✓" if status == "all"    else ""), callback_data="usrfilter_all"),
        InlineKeyboardButton("نشطون"  + (" ✓" if status == "active" else ""), callback_data="usrfilter_active"),
        InlineKeyboardButton("محظور"  + (" ✓" if status == "banned" else ""), callback_data="usrfilter_banned"),
    ]

    kbd = [filters_row]
    for row in rows:
        icon = "🚫" if row["is_banned"] else "👤"
        name = row["username"] or row["full_name"] or str(row["id"])
        kbd.append([InlineKeyboardButton(f"{icon} {name}", callback_data=f"usrdetail_{row['id']}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ السابق", callback_data=f"usrpage_{page-1}"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton("التالي ▶️", callback_data=f"usrpage_{page+1}"))
    if nav:
        kbd.append(nav)

    kbd.append([InlineKeyboardButton("🔍 بحث", callback_data="usrsearch_start")])
    kbd.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")])

    search_note = (f"\n🔍 بحث: `{search}`") if search else ""
    text = f"👥 *المستخدمون* — {total} إجمالي{search_note}\nالصفحة {page+1}/{pages}"
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")
    return USR_MAIN


async def cb_users_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["usr_status"] = q.data.replace("usrfilter_", "")
    context.user_data["usr_page"]   = 0
    context.user_data.pop("usr_search", None)
    return await cb_users_main(update, context)


async def cb_users_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["usr_page"] = int(q.data.replace("usrpage_", ""))
    return await cb_users_main(update, context)


async def cb_users_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("🔍 أرسل اسم المستخدم أو ID:")
    return USR_SEARCH


async def cb_users_search_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["usr_search"] = update.message.text.strip()
    context.user_data["usr_page"]   = 0

    class _FakeQuery:
        async def answer(self): pass
        async def edit_message_text(self, *a, **kw):
            await update.message.reply_text(*a, **kw)
        data = "wiz_users"

    update.callback_query = _FakeQuery()
    return await cb_users_main(update, context)


async def cb_user_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = int(q.data.replace("usrdetail_", ""))
    context.user_data["usr_uid"] = uid

    user = db.get_user(uid)
    if not user:
        await q.edit_message_text("❌ المستخدم غير موجود.")
        return USR_MAIN

    stats = db.get_user_stats(uid)
    active_sub = stats["active_sub"]

    joined = user["joined_at"].strftime("%Y-%m-%d") if user.get("joined_at") else "—"
    ban_icon = "🚫 محظور" if user["is_banned"] else "✅ نشط"

    sub_line = "لا يوجد"
    if active_sub:
        exp = active_sub["expires_at"].strftime("%Y-%m-%d") if active_sub.get("expires_at") else "—"
        sub_line = f"{active_sub['service_name']} — {active_sub['plan_name']} (حتى {exp})"

    text = (
        f"👤 *المستخدم #{uid}*\n"
        f"📛 الاسم: {user.get('full_name') or '—'}\n"
        f"🔗 يوزر: @{user.get('username') or '—'}\n"
        f"🌍 الدولة: {user.get('country') or '—'}\n"
        f"🗣️ اللغة: {user.get('lang', 'ar')}\n"
        f"📅 انضم: {joined}\n"
        f"🟢 الحالة: {ban_icon}\n"
        f"📦 الطلبات: {stats['total_orders']}\n"
        f"📋 الاشتراكات: {stats['total_subs']}\n"
        f"🔑 الاشتراك الحالي: {sub_line}"
    )

    if user["is_banned"]:
        ban_btn = InlineKeyboardButton("✅ رفع الحظر", callback_data=f"usrunban_{uid}")
    else:
        ban_btn = InlineKeyboardButton("🚫 حظر", callback_data=f"usrban_{uid}")

    kbd = [
        [ban_btn],
        [InlineKeyboardButton("🔙 رجوع", callback_data="wiz_users")],
    ]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")
    return USR_DETAIL


async def cb_user_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = int(q.data.replace("usrban_", ""))
    db.ban_user(uid)
    await q.answer("🚫 تم حظر المستخدم", show_alert=True)
    q.data = f"usrdetail_{uid}"
    return await cb_user_detail(update, context)


async def cb_user_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = int(q.data.replace("usrunban_", ""))
    db.unban_user(uid)
    await q.answer("✅ تم رفع الحظر", show_alert=True)
    q.data = f"usrdetail_{uid}"
    return await cb_user_detail(update, context)


# ══════════════════════════════════════════════════════
#   الإحصائيات — Admin Statistics
# ══════════════════════════════════════════════════════

async def cb_stats_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    period = context.user_data.get("stats_period", "month")
    return await _show_stats(update, context, period)


async def cb_stats_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    period = q.data.replace("statsperiod_", "")
    context.user_data["stats_period"] = period
    return await _show_stats(update, context, period)


async def _show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE, period: str):
    q = update.callback_query

    period_labels = {"day": "اليوم", "week": "الأسبوع", "month": "الشهر"}
    label = period_labels.get(period, "الشهر")

    summary  = db.get_summary_stats(period)
    by_svc   = db.get_revenue_by_service(period)
    by_time  = db.get_revenue_by_period(period)

    # --- نص الملخص ---
    lines = [
        f"📊 *إحصائيات {label}*",
        f"",
        f"💰 الإيرادات: `{summary['revenue']} USDT`",
        f"📦 الطلبات المنجزة: `{summary['orders']}`",
        f"👤 مستخدمون جدد: `{summary['new_users']}`",
        f"📋 اشتراكات جديدة: `{summary['new_subs']}`",
    ]

    if by_svc:
        lines.append("")
        lines.append("📈 *الإيرادات حسب الخدمة:*")
        for row in by_svc:
            lines.append(f"• {row['service_name']}: `{round(row['revenue'],2)} USDT` ({row['orders']} طلب)")

    if by_time:
        lines.append("")
        lines.append("🕐 *التوزيع الزمني:*")
        for row in by_time:
            p = row["period"]
            if period == "day":
                p_str = p.strftime("%H:00") if p else "—"
            else:
                p_str = p.strftime("%Y-%m-%d") if p else "—"
            lines.append(f"• {p_str}: `{round(row['revenue'],2)} USDT` ({row['orders']} طلب)")

    text = "\n".join(lines)

    # --- الأزرار ---
    period_row = [
        InlineKeyboardButton("اليوم"   + (" ✓" if period == "day"   else ""), callback_data="statsperiod_day"),
        InlineKeyboardButton("الأسبوع" + (" ✓" if period == "week"  else ""), callback_data="statsperiod_week"),
        InlineKeyboardButton("الشهر"   + (" ✓" if period == "month" else ""), callback_data="statsperiod_month"),
    ]
    kbd = [period_row, [InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")]]

    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")
    return STATS_MAIN


# ══════════════════════════════════════════════════════
#   التذاكر — Admin Tickets Management
# ══════════════════════════════════════════════════════

async def cb_tickets_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    status = context.user_data.get("tkt_status", "open")
    page   = context.user_data.get("tkt_page", 0)
    search = context.user_data.get("tkt_search", "")

    rows, total = db.get_tickets_admin(status=status, page=page, per_page=PER_PAGE, search=search)
    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)

    filters_row = [
        InlineKeyboardButton("مفتوحة" + (" ✓" if status == "open"   else ""), callback_data="tktfilter_open"),
        InlineKeyboardButton("مغلقة"  + (" ✓" if status == "closed" else ""), callback_data="tktfilter_closed"),
        InlineKeyboardButton("الكل"   + (" ✓" if status == "all"    else ""), callback_data="tktfilter_all"),
    ]

    kbd = [filters_row]
    for row in rows:
        icon = "🟢" if row["status"] == "open" else "🔴"
        name = row["username"] or row["full_name"] or str(row["user_id"])
        preview = row["message"][:30] + ("..." if len(row["message"]) > 30 else "")
        kbd.append([InlineKeyboardButton(f"{icon} #{row['id']} {name} — {preview}", callback_data=f"tktdetail_{row['id']}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ السابق", callback_data=f"tktpage_{page-1}"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton("التالي ▶️", callback_data=f"tktpage_{page+1}"))
    if nav:
        kbd.append(nav)

    kbd.append([InlineKeyboardButton("🔍 بحث", callback_data="tktsearch_start")])
    kbd.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")])

    search_note = (f"\n🔍 بحث: `{search}`") if search else ""
    text = f"🎫 *التذاكر* — {total} إجمالي{search_note}\nالصفحة {page+1}/{pages}"
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")
    return TKT_MAIN


async def cb_tickets_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["tkt_status"] = q.data.replace("tktfilter_", "")
    context.user_data["tkt_page"]   = 0
    context.user_data.pop("tkt_search", None)
    return await cb_tickets_main(update, context)


async def cb_tickets_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["tkt_page"] = int(q.data.replace("tktpage_", ""))
    return await cb_tickets_main(update, context)


async def cb_tickets_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("🔍 أرسل اسم المستخدم أو رقم التذكرة:")
    return TKT_SEARCH


async def cb_tickets_search_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tkt_search"] = update.message.text.strip()
    context.user_data["tkt_page"]   = 0

    class _FakeQuery:
        async def answer(self): pass
        async def edit_message_text(self, *a, **kw):
            await update.message.reply_text(*a, **kw)
        data = "wiz_tickets"

    update.callback_query = _FakeQuery()
    return await cb_tickets_main(update, context)


async def cb_ticket_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    tkt_id = int(q.data.replace("tktdetail_", ""))
    context.user_data["tkt_id"] = tkt_id

    ticket = db.get_ticket_by_id(tkt_id)
    if not ticket:
        await q.edit_message_text("❌ التذكرة غير موجودة.")
        return TKT_MAIN

    messages = db.get_ticket_messages(tkt_id) or []
    status_label = "🟢 مفتوحة" if ticket["status"] == "open" else "🔴 مغلقة"
    created = ticket["created_at"].strftime("%Y-%m-%d %H:%M") if ticket.get("created_at") else "—"
    name = ticket["username"] or ticket["full_name"] or str(ticket["user_id"])

    lines = [
        f"🎫 *تذكرة #{tkt_id}*",
        f"👤 المستخدم: @{ticket['username'] or '—'} (`{ticket['user_id']}`)",
        f"📅 تاريخ: {created}",
        f"🟢 الحالة: {status_label}",
        f"",
        f"💬 *المحادثة:*",
    ]

    if messages:
        for msg in messages:
            sender_icon = "👤" if msg["sender"] == "user" else "🛡️"
            time_str = msg["sent_at"].strftime("%H:%M") if msg.get("sent_at") else ""
            lines.append(f"{sender_icon} [{time_str}] {msg['message']}")
    else:
        lines.append(f"👤 {ticket['message']}")

    text = "\n".join(lines)

    kbd = []
    if ticket["status"] == "open":
        kbd.append([
            InlineKeyboardButton("✏️ رد", callback_data=f"tktreply_{tkt_id}"),
            InlineKeyboardButton("🔒 إغلاق", callback_data=f"tktclose_{tkt_id}"),
        ])
    else:
        kbd.append([
            InlineKeyboardButton("✏️ رد", callback_data=f"tktreply_{tkt_id}"),
            InlineKeyboardButton("🔓 إعادة فتح", callback_data=f"tktreopen_{tkt_id}"),
        ])
    kbd.append([InlineKeyboardButton("🔙 رجوع", callback_data="wiz_tickets")])

    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")
    return TKT_DETAIL


async def cb_ticket_reply_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    tkt_id = int(q.data.replace("tktreply_", ""))
    context.user_data["tkt_id"] = tkt_id
    kbd = [[InlineKeyboardButton("🔙 رجوع", callback_data=f"tktdetail_{tkt_id}")]]
    await q.edit_message_text(
        f"✏️ أرسل ردك على التذكرة #{tkt_id}:",
        reply_markup=InlineKeyboardMarkup(kbd)
    )
    return TKT_REPLY


async def cb_ticket_reply_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_text = update.message.text.strip()
    tkt_id = context.user_data.get("tkt_id")

    ticket = db.get_ticket_by_id(tkt_id)
    if not ticket:
        await update.message.reply_text("❌ التذكرة غير موجودة.")
        return TKT_MAIN

    # حفظ الرد في قاعدة البيانات
    db.add_ticket_message(tkt_id, "admin", reply_text)

    # إرسال الرد للمستخدم
    try:
        await update.get_bot().send_message(
            chat_id=ticket["user_id"],
            text=f"📩 *رد من الدعم على تذكرتك #{tkt_id}:*\n\n{reply_text}",
            parse_mode="Markdown"
        )
        await update.message.reply_text(f"✅ تم إرسال الرد للمستخدم.")
    except Exception:
        await update.message.reply_text("⚠️ تم حفظ الرد لكن لم يتمكن البوت من إرساله للمستخدم.")

    # العودة لتفاصيل التذكرة
    class _FakeQuery:
        async def answer(self): pass
        async def edit_message_text(self, *a, **kw):
            await update.message.reply_text(*a, **kw)
        data = f"tktdetail_{tkt_id}"

    update.callback_query = _FakeQuery()
    return await cb_ticket_detail(update, context)


async def cb_ticket_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    tkt_id = int(q.data.replace("tktclose_", ""))
    db.close_ticket(tkt_id)
    await q.answer("🔒 تم إغلاق التذكرة", show_alert=True)
    q.data = f"tktdetail_{tkt_id}"
    return await cb_ticket_detail(update, context)


async def cb_ticket_reopen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    tkt_id = int(q.data.replace("tktreopen_", ""))
    db.reopen_ticket(tkt_id)
    await q.answer("🔓 تم إعادة فتح التذكرة", show_alert=True)
    q.data = f"tktdetail_{tkt_id}"
    return await cb_ticket_detail(update, context)


# ══════════════════════════════════════════════════════
#   إعدادات تصريف العملات — Admin Exchange Rates
# ══════════════════════════════════════════════════════

EXC_RATE_KEYS = {
    "buy_normal":    ("buy",  "normal",    "شراء USDT — عادي"),
    "buy_syriatel":  ("buy",  "syriatel",  "شراء USDT — سيرياتيل"),
    "sell_normal":   ("sell", "normal",    "بيع USDT — عادي"),
    "sell_syriatel": ("sell", "syriatel",  "بيع USDT — سيرياتيل"),
}

(EXC_PICK, EXC_VALUE) = range(150, 152)


async def wiz_exchange_rates_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rates = db.get_exchange_rates_all()

    lines = ["💱 *أسعار تصريف العملات*\n"]
    for key, (op, method, label) in EXC_RATE_KEYS.items():
        lines.append(f"• {label}: `{rates.get(key, 0):,.0f}` ل.س")

    kbd = []
    for key, (op, method, label) in EXC_RATE_KEYS.items():
        kbd.append([InlineKeyboardButton(f"✏️ {label}", callback_data=f"excrate_{key}")])
    kbd.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")])

    await q.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(kbd),
        parse_mode="Markdown"
    )
    return EXC_PICK


async def exc_pick_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    key = q.data.replace("excrate_", "")
    context.user_data["exc_rate_key"] = key
    label = EXC_RATE_KEYS[key][2]
    rates = db.get_exchange_rates_all()
    current = rates.get(key, 0)

    kbd = [[InlineKeyboardButton("🔙 رجوع", callback_data="wiz_exc_rates")]]
    await q.edit_message_text(
        f"✏️ *{label}*\nالسعر الحالي: `{current:,.0f}` ل.س\n\nأرسل السعر الجديد بالليرة:",
        reply_markup=InlineKeyboardMarkup(kbd),
        parse_mode="Markdown"
    )
    return EXC_VALUE


async def exc_set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", "")
    key  = context.user_data.get("exc_rate_key")

    try:
        rate = float(text)
    except Exception:
        await update.message.reply_text("❌ أرسل رقماً صحيحاً مثل: 14500")
        return EXC_VALUE

    op, method, label = EXC_RATE_KEYS[key]
    db.set_exchange_rate(op, method, rate)
    await update.message.reply_text(f"✅ تم تحديث {label} إلى `{rate:,.0f}` ل.س", parse_mode="Markdown")

    # نعود للقائمة
    class _FakeQuery:
        async def answer(self): pass
        async def edit_message_text(self, *a, **kw):
            await update.message.reply_text(*a, **kw)
        data = "wiz_exc_rates"

    update.callback_query = _FakeQuery()
    return await wiz_exchange_rates_start(update, context)

def get_wizard_handlers():
    CANCEL = [CallbackQueryHandler(wizard_cancel, pattern="^wizard_cancel$")]

    ORDER_HANDLERS = [
        CallbackQueryHandler(cb_orders_main,        pattern="^wiz_orders$"),
        CallbackQueryHandler(cb_orders_type,        pattern="^ordtype_"),
        CallbackQueryHandler(cb_orders_page,        pattern="^ordpage_"),
        CallbackQueryHandler(cb_orders_filter,      pattern="^ordfilter_"),
        CallbackQueryHandler(cb_orders_search_start,pattern="^ordsearch_"),
        CallbackQueryHandler(cb_order_detail,       pattern="^orddetail_"),
        CallbackQueryHandler(cb_order_confirm,      pattern="^ordconfirm_"),
        CallbackQueryHandler(cb_order_execute,      pattern="^ordexec_"),
        CallbackQueryHandler(cb_order_proof,        pattern="^ordproof_"),
        CallbackQueryHandler(lambda u,c: u.callback_query.answer(), pattern="^noop$"),
    ]

    return ORDER_HANDLERS + [
        ConversationHandler(
            entry_points=[CallbackQueryHandler(wiz_variants_start, pattern="^wiz_variants$")],
            states={
                VAR_SVC:     [
                    CallbackQueryHandler(var_svc,       pattern="^varsvc_"),
                    CallbackQueryHandler(var_add_start, pattern="^varadd_"),
                    CallbackQueryHandler(var_delete,    pattern="^vardelete_"),
                ],
                VAR_NAME_AR: [MessageHandler(filters.TEXT & ~filters.COMMAND, var_name_ar)],
                VAR_NAME_EN: [MessageHandler(filters.TEXT & ~filters.COMMAND, var_name_en)],
                VAR_OPTS: [
                    CallbackQueryHandler(var_opts_skip,  pattern="^varopts_skip$"),
                    CallbackQueryHandler(var_opts_start, pattern="^varopts_yes$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, var_collect_opts),
                ],
            }, fallbacks=CANCEL, per_message=False, allow_reentry=True),

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
                PLAN_NAME_AR: [
                    CallbackQueryHandler(plan_variant, pattern="^planvar_"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, plan_name_ar),
                ],
                PLAN_NAME_EN: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_name_en)],
                PLAN_DAYS:    [
                    CallbackQueryHandler(plan_days, pattern="^pdays_"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, plan_days_text),
                ],
                PLAN_PRICE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_price)],
                PLAN_FEATS:   [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_feats)],
                PLAN_OPTS_Q:  [
                    CallbackQueryHandler(plan_skip_opts, pattern="^plan_skip_opts$"),
                    CallbackQueryHandler(plan_add_opts,  pattern="^plan_add_opts$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, plan_collect_opts),
                ],
            }, fallbacks=CANCEL, per_message=False, allow_reentry=True),

        ConversationHandler(
            entry_points=[CallbackQueryHandler(wiz_edit_start, pattern="^wiz_edit_svc$")],
            states={
                EDIT_SVC:       [CallbackQueryHandler(edit_svc,       pattern="^editsvc_")],
                EDIT_FIELD:     [CallbackQueryHandler(edit_field,      pattern="^ef_")],
                EDIT_VALUE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value)],
                EDIT_PLAN_OPTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_plan_opts)],
            }, fallbacks=CANCEL, per_message=False),

        ConversationHandler(
            entry_points=[CallbackQueryHandler(wiz_delete_start, pattern="^wiz_delete$")],
            states={
                DEL_TYPE:    [CallbackQueryHandler(del_type,    pattern="^deltype_")],
                DEL_ITEM:    [CallbackQueryHandler(del_item,    pattern="^delitem_")],
                DEL_CONFIRM: [CallbackQueryHandler(del_confirm, pattern="^delconfirm_yes$")],
            }, fallbacks=CANCEL, per_message=False),

        ConversationHandler(
            entry_points=[CallbackQueryHandler(wiz_rate_start, pattern="^wiz_rate$")],
            states={
                RATE_SVC:   [CallbackQueryHandler(rate_svc,   pattern="^ratesvc_")],
                RATE_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, rate_value)],
            }, fallbacks=CANCEL, per_message=False),

        ConversationHandler(
            entry_points=[CallbackQueryHandler(wiz_mansub_start, pattern="^wiz_mansub$")],
            states={
                MANSUB_USER:  [MessageHandler(filters.TEXT & ~filters.COMMAND, mansub_user)],
                MANSUB_PLAN:  [CallbackQueryHandler(mansub_plan, pattern="^mansubplan_")],
                MANSUB_CREDS: [MessageHandler(filters.TEXT & ~filters.COMMAND, mansub_creds)],
            }, fallbacks=CANCEL, per_message=False),

        ConversationHandler(
            entry_points=[CallbackQueryHandler(wiz_broadcast_start, pattern="^wiz_broadcast$")],
            states={
                BROADCAST_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)],
            }, fallbacks=CANCEL, per_message=False),

        ConversationHandler(
            entry_points=[CallbackQueryHandler(wiz_recharge_start, pattern="^wiz_recharge$")],
            states={
                RCH_SVC: [
                    CallbackQueryHandler(rch_svc,         pattern="^rchsvc_"),
                    CallbackQueryHandler(rch_set_rate,    pattern="^rch_setrate$"),
                    CallbackQueryHandler(rch_set_presets, pattern="^rch_setpresets$"),
                    CallbackQueryHandler(rch_set_limits,  pattern="^rch_setlimits$"),
                ],
                RCH_RATE: [
                    CallbackQueryHandler(rch_svc,         pattern="^rchsvc_"),
                    CallbackQueryHandler(rch_set_rate,    pattern="^rch_setrate$"),
                    CallbackQueryHandler(rch_set_presets, pattern="^rch_setpresets$"),
                    CallbackQueryHandler(rch_set_limits,  pattern="^rch_setlimits$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, rch_collect_rate),
                ],
                RCH_PRESETS: [MessageHandler(filters.TEXT & ~filters.COMMAND, rch_collect_presets)],
                RCH_LIMITS:  [MessageHandler(filters.TEXT & ~filters.COMMAND, rch_collect_limits)],
            }, fallbacks=CANCEL, per_message=False, allow_reentry=True),

        ConversationHandler(
            entry_points=[CallbackQueryHandler(cb_subs_main, pattern="^wiz_subs$")],
            states={
                SUB_MAIN: [
                    CallbackQueryHandler(cb_subs_filter,       pattern="^subfilter_"),
                    CallbackQueryHandler(cb_subs_page,         pattern="^subpage_"),
                    CallbackQueryHandler(cb_sub_detail,        pattern="^subdetail_"),
                    CallbackQueryHandler(cb_subs_search_start, pattern="^subsearch_"),
                ],
                SUB_SEARCH: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, cb_subs_search_handle),
                ],
                SUB_DETAIL: [
                    CallbackQueryHandler(cb_subs_main,         pattern="^wiz_subs$"),
                    CallbackQueryHandler(cb_subs_filter,       pattern="^subfilter_"),
                    CallbackQueryHandler(cb_sub_detail,        pattern="^subdetail_"),
                    CallbackQueryHandler(cb_sub_cancel,        pattern="^subcancel_"),
                    CallbackQueryHandler(cb_sub_extend_ask,    pattern="^subextend_"),
                ],
                SUB_EXTEND: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, cb_sub_extend_do),
                    CallbackQueryHandler(cb_sub_detail,        pattern="^subdetail_"),
                ],
            }, fallbacks=CANCEL, per_message=False, allow_reentry=True),

        ConversationHandler(
            entry_points=[CallbackQueryHandler(cb_users_main, pattern="^wiz_users$")],
            states={
                USR_MAIN: [
                    CallbackQueryHandler(cb_users_filter,       pattern="^usrfilter_"),
                    CallbackQueryHandler(cb_users_page,         pattern="^usrpage_"),
                    CallbackQueryHandler(cb_user_detail,        pattern="^usrdetail_"),
                    CallbackQueryHandler(cb_users_search_start, pattern="^usrsearch_start$"),
                ],
                USR_SEARCH: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, cb_users_search_handle),
                ],
                USR_DETAIL: [
                    CallbackQueryHandler(cb_users_main,   pattern="^wiz_users$"),
                    CallbackQueryHandler(cb_user_detail,  pattern="^usrdetail_"),
                    CallbackQueryHandler(cb_user_ban,     pattern="^usrban_"),
                    CallbackQueryHandler(cb_user_unban,   pattern="^usrunban_"),
                ],
            }, fallbacks=CANCEL, per_message=False, allow_reentry=True),

        ConversationHandler(
            entry_points=[CallbackQueryHandler(cb_stats_main, pattern="^wiz_stats$")],
            states={
                STATS_MAIN: [
                    CallbackQueryHandler(cb_stats_period, pattern="^statsperiod_"),
                ],
            }, fallbacks=CANCEL, per_message=False, allow_reentry=True),

        ConversationHandler(
            entry_points=[CallbackQueryHandler(cb_tickets_main, pattern="^wiz_tickets$")],
            states={
                TKT_MAIN: [
                    CallbackQueryHandler(cb_tickets_filter,       pattern="^tktfilter_"),
                    CallbackQueryHandler(cb_tickets_page,         pattern="^tktpage_"),
                    CallbackQueryHandler(cb_ticket_detail,        pattern="^tktdetail_"),
                    CallbackQueryHandler(cb_tickets_search_start, pattern="^tktsearch_start$"),
                ],
                TKT_SEARCH: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, cb_tickets_search_handle),
                ],
                TKT_DETAIL: [
                    CallbackQueryHandler(cb_tickets_main,      pattern="^wiz_tickets$"),
                    CallbackQueryHandler(cb_ticket_detail,     pattern="^tktdetail_"),
                    CallbackQueryHandler(cb_ticket_reply_ask,  pattern="^tktreply_"),
                    CallbackQueryHandler(cb_ticket_close,      pattern="^tktclose_"),
                    CallbackQueryHandler(cb_ticket_reopen,     pattern="^tktreopen_"),
                ],
                TKT_REPLY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, cb_ticket_reply_send),
                    CallbackQueryHandler(cb_ticket_detail,     pattern="^tktdetail_"),
                ],
            }, fallbacks=CANCEL, per_message=False, allow_reentry=True),

        ConversationHandler(
            entry_points=[CallbackQueryHandler(wiz_exchange_rates_start, pattern="^wiz_exc_rates$")],
            states={
                EXC_PICK: [
                    CallbackQueryHandler(exc_pick_rate,              pattern="^excrate_"),
                    CallbackQueryHandler(wiz_exchange_rates_start,   pattern="^wiz_exc_rates$"),
                ],
                EXC_VALUE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, exc_set_rate),
                    CallbackQueryHandler(wiz_exchange_rates_start,   pattern="^wiz_exc_rates$"),
                ],
            }, fallbacks=CANCEL, per_message=False, allow_reentry=True),
    ]

