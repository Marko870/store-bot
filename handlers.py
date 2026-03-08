"""
🤖 بوت تلجرام - المعالجات الرئيسية (دفع يدوي USDT)
"""

import json
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from database import Database
from config import Config
from i18n import t

logger = logging.getLogger(__name__)
db = Database()
cfg = Config()

# ——— حالات انتظار ———
AWAITING_PROOF   = "awaiting_proof"
AWAITING_SUPPORT = "awaiting_support"


def is_admin(uid): return uid in cfg.ADMIN_IDS
def get_lang(uid):
    u = db.get_user(uid)
    return u["lang"] if u else "ar"
def fmt_date(dt_str):
    if not dt_str: return "—"
    try: return datetime.fromisoformat(dt_str).strftime("%Y/%m/%d")
    except: return dt_str


# ═══════════════════════════════════════════
#               القائمة الرئيسية
# ═══════════════════════════════════════════

def main_menu_kb(lang):
    if lang == "ar":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 الخدمات",     callback_data="services"),
             InlineKeyboardButton("📋 اشتراكاتي",   callback_data="my_subs")],
            [InlineKeyboardButton("👤 ملفي",         callback_data="profile"),
             InlineKeyboardButton("📨 الدعم",        callback_data="support")],
            [InlineKeyboardButton("🌐 English",      callback_data="lang_en")],
        ])
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Services",          callback_data="services"),
             InlineKeyboardButton("📋 My Subscriptions",  callback_data="my_subs")],
            [InlineKeyboardButton("👤 Profile",           callback_data="profile"),
             InlineKeyboardButton("📨 Support",           callback_data="support")],
            [InlineKeyboardButton("🌐 عربي",             callback_data="lang_ar")],
        ])


# ═══════════════════════════════════════════
#                   /start
# ═══════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.ensure_user(user.id, user.username or "", user.full_name)
    u = db.get_user(user.id)
    if u and u.get("is_banned"):
        await update.message.reply_text("🚫 تم حظر حسابك.")
        return
    context.user_data.clear()
    lang = get_lang(user.id)
    sub = db.get_active_subscription(user.id)
    extra = ""
    if sub:
        sn = sub["plan_name"] if lang == "ar" else sub["plan_name_en"]
        extra = (f"\n\n✅ اشتراكك النشط: *{sn}*\n📅 ينتهي: {fmt_date(sub['expires_at'])}"
                 if lang == "ar" else
                 f"\n\n✅ Active Plan: *{sn}*\n📅 Expires: {fmt_date(sub['expires_at'])}")
    text = t("welcome", lang, name=user.first_name) + extra
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_kb(lang))


# ═══════════════════════════════════════════
#               تغيير اللغة
# ═══════════════════════════════════════════

async def cb_set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang = "en" if q.data == "lang_en" else "ar"
    db.set_user_lang(q.from_user.id, lang)
    sub = db.get_active_subscription(q.from_user.id)
    extra = ""
    if sub:
        sn = sub["plan_name"] if lang == "ar" else sub["plan_name_en"]
        extra = (f"\n\n✅ اشتراكك النشط: *{sn}*\n📅 ينتهي: {fmt_date(sub['expires_at'])}"
                 if lang == "ar" else
                 f"\n\n✅ Active Plan: *{sn}*\n📅 Expires: {fmt_date(sub['expires_at'])}")
    await q.edit_message_text(
        t("welcome", lang, name=q.from_user.first_name) + extra,
        parse_mode="Markdown", reply_markup=main_menu_kb(lang)
    )


# ═══════════════════════════════════════════
#               الخدمات والخطط
# ═══════════════════════════════════════════

async def cb_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang = get_lang(q.from_user.id)
    services = db.get_services()
    if not services:
        await q.edit_message_text(t("no_services", lang), reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(t("back", lang), callback_data="main_menu")]]))
        return
    EMOJI = {"streaming": "🎬", "security": "🔒", "bot": "🤖", "digital": "💻"}
    btns = [[InlineKeyboardButton(
        f"{EMOJI.get(s['category'],'⭐')} {s['name_ar'] if lang=='ar' else s['name_en']}",
        callback_data=f"svc_{s['id']}")] for s in services]
    btns.append([InlineKeyboardButton(t("back", lang), callback_data="main_menu")])
    await q.edit_message_text(t("services_title", lang), parse_mode="Markdown",
                               reply_markup=InlineKeyboardMarkup(btns))


async def cb_service_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang = get_lang(q.from_user.id)
    svc_id = int(q.data.split("_")[1])
    svc   = db.get_service(svc_id)
    plans = db.get_plans(svc_id)
    name  = svc["name_ar"] if lang == "ar" else svc["name_en"]
    desc  = svc.get("description_ar" if lang == "ar" else "description_en", "")
    DUR   = {30:"شهر" if lang=="ar" else "1 Month",
             90:"3 أشهر" if lang=="ar" else "3 Months",
             180:"6 أشهر" if lang=="ar" else "6 Months",
             365:"سنة" if lang=="ar" else "1 Year"}
    btns = [[InlineKeyboardButton(
        f"📦 {DUR.get(p['duration_days'], str(p['duration_days'])+'d')} — {p['price']} USDT",
        callback_data=f"plan_{p['id']}")] for p in plans]
    btns.append([InlineKeyboardButton(t("back", lang), callback_data="services")])
    await q.edit_message_text(
        f"*{name}*\n{desc}\n\n{'📦 الخطط المتاحة:' if lang=='ar' else '📦 Available Plans:'}",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))


async def cb_plan_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang    = get_lang(q.from_user.id)
    plan_id = int(q.data.split("_")[1])
    plan    = db.get_plan(plan_id)
    if not plan:
        await q.answer("❌ الخطة غير موجودة", show_alert=True); return

    feats_raw = json.loads(plan.get("features", "[]"))
    feats = [f for f in feats_raw if (lang=="ar") == any('\u0600'<=c<='\u06ff' for c in f)]
    if not feats: feats = feats_raw
    feats_text = "\n".join(f"  ✔️ {f}" for f in feats)

    svc_name  = plan["service_name_ar"] if lang=="ar" else plan["service_name_en"]
    plan_name = plan["name_ar"]         if lang=="ar" else plan["name_en"]

    text = t("plan_details", lang,
             service=svc_name, plan=plan_name,
             days=plan["duration_days"], price=plan["price"],
             features=feats_text)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "💳 اشترِ الآن | Buy Now",
            callback_data=f"checkout_{plan_id}")],
        [InlineKeyboardButton(t("back", lang), callback_data=f"svc_{plan['service_id']}")]
    ])
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)


# ═══════════════════════════════════════════
#         عرض معلومات الدفع (USDT يدوي)
# ═══════════════════════════════════════════

async def cb_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang    = get_lang(q.from_user.id)
    plan_id = int(q.data.split("_")[1])
    plan    = db.get_plan(plan_id)

    # احفظ الطلب في قاعدة البيانات بحالة "pending"
    order_id = db.create_order(q.from_user.id, plan_id, plan["price"])

    plan_name = plan["name_ar"] if lang=="ar" else plan["name_en"]
    svc_name  = plan["service_name_ar"] if lang=="ar" else plan["service_name_en"]

    text = (
        f"💳 *تفاصيل الدفع | Payment Details*\n\n"
        f"🛍️ {'الخدمة' if lang=='ar' else 'Service'}: *{svc_name}*\n"
        f"📦 {'الخطة'   if lang=='ar' else 'Plan'}:    *{plan_name}*\n"
        f"💰 {'المبلغ'   if lang=='ar' else 'Amount'}:  *{plan['price']} USDT*\n"
        f"🌐 {'الشبكة'   if lang=='ar' else 'Network'}: `{cfg.USDT_NETWORK}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📤 {'أرسل المبلغ لهذا العنوان:' if lang=='ar' else 'Send the amount to this address:'}\n\n"
        f"`{cfg.USDT_ADDRESS}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{'⚠️ بعد الإرسال، أرفق لقطة شاشة للتحويل هنا وسيتم تفعيل اشتراكك خلال دقائق.' if lang=='ar' else '⚠️ After sending, upload a screenshot of the transfer here and your subscription will be activated within minutes.'}\n\n"
        f"🔖 {'رقم الطلب' if lang=='ar' else 'Order ID'}: `#{order_id}`"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "📸 أرسل إثبات الدفع | Send Proof",
            callback_data=f"sendproof_{order_id}_{plan_id}")],
        [InlineKeyboardButton(t("back", lang), callback_data=f"plan_{plan_id}")]
    ])
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)


# ═══════════════════════════════════════════
#         استقبال إثبات الدفع (صورة)
# ═══════════════════════════════════════════

async def cb_send_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang = get_lang(q.from_user.id)
    parts = q.data.split("_")          # sendproof_<order_id>_<plan_id>
    order_id = int(parts[1])
    plan_id  = int(parts[2])

    context.user_data[AWAITING_PROOF] = {"order_id": order_id, "plan_id": plan_id}

    text = (
        "📸 *أرسل صورة إثبات التحويل الآن*\n\n"
        "أرفق screenshot أو صورة من محفظتك تُظهر عملية التحويل.\n\n"
        "📸 *Send your transfer screenshot now*\n"
        "Attach a screenshot from your wallet showing the transaction."
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ إلغاء | Cancel", callback_data=f"checkout_{plan_id}")
    ]])
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)


async def handle_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """المستخدم يرسل صورة إثبات الدفع"""
    proof_data = context.user_data.get(AWAITING_PROOF)
    if not proof_data:
        # تحقق إذا كان ينتظر رسالة دعم
        await handle_support_message(update, context)
        return

    order_id = proof_data["order_id"]
    plan_id  = proof_data["plan_id"]
    lang     = get_lang(update.effective_user.id)
    u        = db.get_user(update.effective_user.id)
    plan     = db.get_plan(plan_id)

    # تحديث الطلب كـ "awaiting_approval"
    db.update_order_status(order_id, "awaiting_approval")
    context.user_data.pop(AWAITING_PROOF, None)

    # إشعار المستخدم
    await update.message.reply_text(
        (
            "✅ *تم استلام إثبات الدفع!*\n\n"
            "⏳ سيتم مراجعته وتفعيل اشتراكك خلال دقائق.\n"
            f"🔖 رقم الطلب: `#{order_id}`\n\n"
            "✅ *Payment proof received!*\n"
            "⏳ It will be reviewed and your subscription activated within minutes.\n"
            f"🔖 Order ID: `#{order_id}`"
        ),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 القائمة | Menu", callback_data="main_menu")
        ]])
    )

    # إشعار الأدمن مع الصورة + أزرار تفعيل/رفض
    plan_name = plan["name_ar"]
    svc_name  = plan["service_name_ar"]
    caption = (
        f"🔔 *طلب دفع جديد يحتاج موافقة!*\n\n"
        f"👤 المستخدم: {u['full_name']}\n"
        f"🆔 ID: `{update.effective_user.id}`\n"
        f"📦 الخطة: {svc_name} — {plan_name}\n"
        f"💰 المبلغ: {plan['price']} USDT\n"
        f"🔖 رقم الطلب: `#{order_id}`"
    )
    approve_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"✅ تفعيل #{ order_id}",
                             callback_data=f"admin_approve_{order_id}_{update.effective_user.id}_{plan_id}"),
        InlineKeyboardButton(f"❌ رفض #{order_id}",
                             callback_data=f"admin_reject_{order_id}_{update.effective_user.id}")
    ]])

    for admin_id in cfg.ADMIN_IDS:
        try:
            if update.message.photo:
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=update.message.photo[-1].file_id,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=approve_kb
                )
            elif update.message.document:
                await context.bot.send_document(
                    chat_id=admin_id,
                    document=update.message.document.file_id,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=approve_kb
                )
            else:
                # نص فقط
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=caption + f"\n\n📝 ملاحظة المستخدم: {update.message.text or '—'}",
                    parse_mode="Markdown",
                    reply_markup=approve_kb
                )
        except Exception as e:
            logger.error(f"Admin notify failed: {e}")


# ═══════════════════════════════════════════
#          أزرار الأدمن: تفعيل / رفض
# ═══════════════════════════════════════════

async def cb_admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return

    # admin_approve_<order_id>_<user_id>_<plan_id>
    parts    = q.data.split("_")
    order_id = int(parts[2])
    user_id  = int(parts[3])
    plan_id  = int(parts[4])

    order = db.complete_order(order_id)
    if not order:
        await q.answer("⚠️ الطلب غير موجود أو تمت معالجته", show_alert=True)
        return

    plan = db.get_plan(plan_id)
    db.create_subscription(user_id, plan_id, order_id, plan["duration_days"])

    # إشعار المستخدم
    lang = get_lang(user_id)
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"🎉 *تم تفعيل اشتراكك!*\n\n"
                f"📦 الخطة: *{plan['name_ar']}*\n"
                f"⏳ المدة: {plan['duration_days']} يوم\n\n"
                f"🎉 *Subscription Activated!*\n"
                f"📦 Plan: *{plan['name_en']}*\n"
                f"⏳ Duration: {plan['duration_days']} days\n\n"
                f"اضغط /start لعرض اشتراكك ✅"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"User notify failed: {e}")

    # تعديل رسالة الأدمن
    await q.edit_message_caption(
        caption=(q.message.caption or "") + f"\n\n✅ *تم التفعيل بواسطة @{q.from_user.username}*",
        parse_mode="Markdown"
    )


async def cb_admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return

    # admin_reject_<order_id>_<user_id>
    parts    = q.data.split("_")
    order_id = int(parts[2])
    user_id  = int(parts[3])

    db.update_order_status(order_id, "rejected")

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "❌ *تم رفض طلبك*\n\n"
                "إذا أرسلت المبلغ بالفعل تواصل مع الدعم فوراً.\n\n"
                "❌ *Your order was rejected*\n"
                "If you already sent the amount, contact support immediately."
            ),
            parse_mode="Markdown"
        )
    except: pass

    await q.edit_message_caption(
        caption=(q.message.caption or "") + f"\n\n❌ *تم الرفض بواسطة @{q.from_user.username}*",
        parse_mode="Markdown"
    )


# ═══════════════════════════════════════════
#               اشتراكاتي
# ═══════════════════════════════════════════

async def cb_my_subs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang = get_lang(q.from_user.id)
    subs = db.get_all_subscriptions(q.from_user.id)
    if not subs:
        await q.edit_message_text(
            t("no_subscriptions", lang),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 الخدمات | Services", callback_data="services")],
                [InlineKeyboardButton(t("back", lang), callback_data="main_menu")]
            ])
        ); return

    STATUS = {"active": "✅ نشط", "expired": "❌ منتهي"}
    lines  = [t("my_subscriptions", lang) + "\n"]
    for sub in subs[:5]:
        creds = json.loads(sub.get("credentials", "{}"))
        creds_text = "".join(f"🔑 {k}: `{v}`\n" for k, v in creds.items())
        lines.append(
            f"━━━━━━━━━━━━\n"
            f"🔵 {sub['service_ar']} — {sub['plan_name']}\n"
            f"📅 {'ينتهي' if lang=='ar' else 'Expires'}: {fmt_date(sub['expires_at'])}\n"
            f"📊 {STATUS.get(sub['status'], sub['status'])}\n"
            f"{creds_text}"
        )
    await q.edit_message_text(
        "\n".join(lines), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("back", lang), callback_data="main_menu")]])
    )


# ═══════════════════════════════════════════
#               الملف الشخصي
# ═══════════════════════════════════════════

async def cb_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang = get_lang(q.from_user.id)
    u    = db.get_user(q.from_user.id)
    sub  = db.get_active_subscription(q.from_user.id)
    sub_status = "—"
    if sub:
        sn = sub["plan_name"] if lang=="ar" else sub["plan_name_en"]
        sub_status = f"{sn} ⟶ {fmt_date(sub['expires_at'])}"
    await q.edit_message_text(
        t("profile", lang,
          uid=q.from_user.id, name=u["full_name"],
          username=u["username"] or "—",
          joined=fmt_date(u["joined_at"]), sub_status=sub_status),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("back", lang), callback_data="main_menu")]])
    )


# ═══════════════════════════════════════════
#               الدعم الفني
# ═══════════════════════════════════════════

async def cb_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang = get_lang(q.from_user.id)
    context.user_data[AWAITING_SUPPORT] = True
    await q.edit_message_text(
        t("support_prompt", lang), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("cancel", lang), callback_data="main_menu")]])
    )


async def handle_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get(AWAITING_SUPPORT):
        return
    lang      = get_lang(update.effective_user.id)
    ticket_id = db.create_ticket(update.effective_user.id, update.message.text)
    context.user_data.pop(AWAITING_SUPPORT, None)
    u = db.get_user(update.effective_user.id)
    for admin_id in cfg.ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"🎫 *تذكرة دعم جديدة #{ticket_id}*\n\n"
                    f"👤 {u['full_name']} (@{u['username']})\n"
                    f"🆔 `{update.effective_user.id}`\n\n"
                    f"📝 {update.message.text}\n\n"
                    f"للرد: `/reply {ticket_id} <ردك>`"
                ),
                parse_mode="Markdown"
            )
        except: pass
    await update.message.reply_text(
        t("ticket_created", lang, ticket_id=ticket_id),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 القائمة | Menu", callback_data="main_menu")]])
    )


# ═══════════════════════════════════════════
#               القائمة الرئيسية (callback)
# ═══════════════════════════════════════════

async def cb_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data.clear()
    lang = get_lang(q.from_user.id)
    sub  = db.get_active_subscription(q.from_user.id)
    extra = ""
    if sub:
        sn = sub["plan_name"] if lang=="ar" else sub["plan_name_en"]
        extra = (f"\n\n✅ اشتراكك النشط: *{sn}*\n📅 ينتهي: {fmt_date(sub['expires_at'])}"
                 if lang=="ar" else
                 f"\n\n✅ Active Plan: *{sn}*\n📅 Expires: {fmt_date(sub['expires_at'])}")
    await q.edit_message_text(
        t("welcome", lang, name=q.from_user.first_name) + extra,
        parse_mode="Markdown", reply_markup=main_menu_kb(lang)
    )


# ═══════════════════════════════════════════
#           لوحة الأدمن
# ═══════════════════════════════════════════

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    stats = db.get_stats()
    text  = t("admin_panel", "ar",
              users=stats["total_users"], subs=stats["active_subs"],
              revenue=stats["total_revenue"], pending=stats["pending_orders"],
              tickets=stats["open_tickets"])
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏳ الطلبات المعلقة", callback_data="admin_orders"),
         InlineKeyboardButton("🎫 التذاكر",          callback_data="admin_tickets")],
        [InlineKeyboardButton("📢 إذاعة",            callback_data="admin_broadcast_prompt")],
    ])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)


async def cb_admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    orders = db.get_pending_orders()
    if not orders:
        await q.edit_message_text("✅ لا توجد طلبات معلقة", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ رجوع", callback_data="admin_back")]])); return
    lines = ["⏳ *الطلبات المعلقة:*\n"]
    btns  = []
    for o in orders[:10]:
        lines.append(f"━━━━━━━━━\n📦 #{o['id']} | {o['full_name']} | {o['name_ar']} | {o['amount']} USDT\n")
        btns.append([
            InlineKeyboardButton(f"✅ تفعيل #{o['id']}",
                                 callback_data=f"admin_approve_{o['id']}_{o['user_id']}_{o['plan_id']}"),
            InlineKeyboardButton(f"❌ رفض #{o['id']}",
                                 callback_data=f"admin_reject_{o['id']}_{o['user_id']}")
        ])
    btns.append([InlineKeyboardButton("◀️ رجوع", callback_data="admin_back")])
    await q.edit_message_text("\n".join(lines), parse_mode="Markdown",
                               reply_markup=InlineKeyboardMarkup(btns))


async def cb_admin_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    tickets = db.get_open_tickets()
    if not tickets:
        await q.edit_message_text("✅ لا توجد تذاكر مفتوحة", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ رجوع", callback_data="admin_back")]])); return
    lines = ["🎫 *التذاكر المفتوحة:*\n"]
    for tk in tickets[:8]:
        lines.append(
            f"━━━━━━━\n🎫 #{tk['id']} | {tk['full_name']} (`{tk['user_id']}`)\n"
            f"📝 {tk['message'][:80]}\n"
            f"➡️ `/reply {tk['id']} <ردك>`\n"
        )
    await q.edit_message_text("\n".join(lines), parse_mode="Markdown",
                               reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ رجوع", callback_data="admin_back")]]))


async def cb_admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    stats = db.get_stats()
    text  = t("admin_panel", "ar",
              users=stats["total_users"], subs=stats["active_subs"],
              revenue=stats["total_revenue"], pending=stats["pending_orders"],
              tickets=stats["open_tickets"])
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏳ الطلبات المعلقة", callback_data="admin_orders"),
         InlineKeyboardButton("🎫 التذاكر",          callback_data="admin_tickets")],
        [InlineKeyboardButton("📢 إذاعة",            callback_data="admin_broadcast_prompt")],
    ])
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)


async def cmd_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("الاستخدام: /reply <ticket_id> <ردك>"); return
    ticket_id  = int(args[0])
    reply_text = " ".join(args[1:])
    ticket     = db.reply_ticket(ticket_id, reply_text)
    try:
        await context.bot.send_message(
            chat_id=ticket["user_id"],
            text=(
                f"📨 *رد الدعم على تذكرتك #{ticket_id}*\n\n"
                f"{reply_text}\n\n"
                f"📨 *Support reply to ticket #{ticket_id}*\n{reply_text}"
            ),
            parse_mode="Markdown"
        )
        await update.message.reply_text(f"✅ تم الرد على التذكرة #{ticket_id}")
    except Exception as e:
        await update.message.reply_text(f"❌ فشل: {e}")


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("الاستخدام: /broadcast <رسالتك>"); return
    message = " ".join(context.args)
    users   = db.get_all_users()
    sent = failed = 0
    msg  = await update.message.reply_text(f"⏳ جاري الإرسال لـ {len(users)} مستخدم...")
    for user in users:
        try:
            await context.bot.send_message(chat_id=user["id"], text=message, parse_mode="Markdown")
            sent += 1
        except:
            failed += 1
    await msg.edit_text(f"📢 *تم!*\n✅ نجح: {sent}\n❌ فشل: {failed}", parse_mode="Markdown")


# ═══════════════════════════════════════════
#          Handler الرسائل الواردة (صور + نصوص)
# ═══════════════════════════════════════════

async def handle_incoming(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """موزّع مركزي لكل الرسائل الواردة"""
    if context.user_data.get(AWAITING_PROOF):
        await handle_payment_proof(update, context)
    elif context.user_data.get(AWAITING_SUPPORT):
        await handle_support_message(update, context)


# ═══════════════════════════════════════════
#           تسجيل جميع الـ Handlers
# ═══════════════════════════════════════════

def register_handlers(app: Application):
    # أوامر
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("admin",     cmd_admin))
    app.add_handler(CommandHandler("reply",     cmd_reply))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))

    # Callbacks المستخدم
    app.add_handler(CallbackQueryHandler(cb_main_menu,     pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(cb_set_lang,      pattern="^lang_(ar|en)$"))
    app.add_handler(CallbackQueryHandler(cb_services,      pattern="^services$"))
    app.add_handler(CallbackQueryHandler(cb_service_detail,pattern=r"^svc_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_plan_detail,   pattern=r"^plan_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_checkout,      pattern=r"^checkout_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_send_proof,    pattern=r"^sendproof_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_my_subs,       pattern="^my_subs$"))
    app.add_handler(CallbackQueryHandler(cb_profile,       pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(cb_support,       pattern="^support$"))

    # Callbacks الأدمن
    app.add_handler(CallbackQueryHandler(cb_admin_orders,  pattern="^admin_orders$"))
    app.add_handler(CallbackQueryHandler(cb_admin_approve, pattern=r"^admin_approve_\d+_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_reject,  pattern=r"^admin_reject_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_tickets, pattern="^admin_tickets$"))
    app.add_handler(CallbackQueryHandler(cb_admin_back,    pattern="^admin_back$"))

    # رسائل واردة (صور + نصوص)
    app.add_handler(MessageHandler(
        (filters.PHOTO | filters.Document.ALL | filters.TEXT) & ~filters.COMMAND,
        handle_incoming
    ))

