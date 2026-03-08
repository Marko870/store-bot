"""
🌐 نظام الترجمة الثنائية - Bilingual Translation System (AR/EN)
"""

TEXTS = {
    # ——— عام ———
    "welcome": {
        "ar": (
            "👋 *أهلاً وسهلاً {name}!*\n\n"
            "🛍️ مرحباً بك في متجر الخدمات الرقمية\n"
            "نقدم لك أفضل الخدمات الرقمية بأسعار تنافسية 💎\n\n"
            "اختر من القائمة أدناه:"
        ),
        "en": (
            "👋 *Welcome {name}!*\n\n"
            "🛍️ Welcome to the Digital Services Store\n"
            "We offer the best digital services at competitive prices 💎\n\n"
            "Choose from the menu below:"
        )
    },
    "choose_lang": {
        "ar": "🌐 اختر لغتك المفضلة:\nChoose your preferred language:",
        "en": "🌐 اختر لغتك المفضلة:\nChoose your preferred language:"
    },
    "main_menu": {
        "ar": "🏠 *القائمة الرئيسية*\nاختر ما تريد:",
        "en": "🏠 *Main Menu*\nChoose what you need:"
    },
    "services_title": {
        "ar": "🛒 *خدماتنا المتاحة*\nاختر الخدمة التي تريدها:",
        "en": "🛒 *Our Available Services*\nChoose the service you want:"
    },
    "no_services": {
        "ar": "❌ لا توجد خدمات متاحة حالياً",
        "en": "❌ No services available currently"
    },
    "plans_title": {
        "ar": "📦 *خطط {service}*\nاختر الخطة المناسبة لك:",
        "en": "📦 *{service} Plans*\nChoose the right plan for you:"
    },
    "plan_details": {
        "ar": (
            "📋 *تفاصيل الخطة*\n\n"
            "🏷️ الخدمة: {service}\n"
            "📦 الخطة: {plan}\n"
            "⏳ المدة: {days} يوم\n"
            "💰 السعر: {price} USDT\n\n"
            "✨ *المميزات:*\n{features}\n\n"
            "هل تريد المتابعة للدفع؟"
        ),
        "en": (
            "📋 *Plan Details*\n\n"
            "🏷️ Service: {service}\n"
            "📦 Plan: {plan}\n"
            "⏳ Duration: {days} days\n"
            "💰 Price: {price} USDT\n\n"
            "✨ *Features:*\n{features}\n\n"
            "Do you want to proceed to payment?"
        )
    },
    "generating_invoice": {
        "ar": "⏳ جاري إنشاء فاتورة الدفع...",
        "en": "⏳ Generating payment invoice..."
    },
    "invoice_ready": {
        "ar": (
            "💳 *فاتورة الدفع جاهزة!*\n\n"
            "📦 الخطة: {plan}\n"
            "💰 المبلغ: {amount} USDT\n"
            "⏰ صالحة لمدة: ساعة واحدة\n\n"
            "اضغط على الزر أدناه لإتمام الدفع بالكريبتو 👇"
        ),
        "en": (
            "💳 *Payment Invoice Ready!*\n\n"
            "📦 Plan: {plan}\n"
            "💰 Amount: {amount} USDT\n"
            "⏰ Valid for: 1 hour\n\n"
            "Click the button below to pay with crypto 👇"
        )
    },
    "pay_now": {"ar": "💳 ادفع الآن", "en": "💳 Pay Now"},
    "check_payment": {"ar": "🔄 تحقق من الدفع", "en": "🔄 Check Payment"},
    "payment_success": {
        "ar": "✅ *تم الدفع بنجاح!*\nتم تفعيل اشتراكك. اضغط /start",
        "en": "✅ *Payment Successful!*\nYour subscription is now active. Press /start"
    },
    "payment_pending": {
        "ar": "⏳ لم يتم تأكيد الدفع بعد. حاول مجدداً بعد دقيقة.",
        "en": "⏳ Payment not confirmed yet. Try again in a minute."
    },
    "payment_failed": {
        "ar": "❌ فشل إنشاء الفاتورة. تواصل مع الدعم.",
        "en": "❌ Failed to create invoice. Contact support."
    },
    "my_subscriptions": {
        "ar": "📋 *اشتراكاتي*",
        "en": "📋 *My Subscriptions*"
    },
    "no_subscriptions": {
        "ar": "😔 ليس لديك أي اشتراكات نشطة حالياً.\n\nاضغط على 🛒 الخدمات لتصفح خدماتنا",
        "en": "😔 You have no active subscriptions.\n\nPress 🛒 Services to browse our offerings"
    },
    "subscription_card": {
        "ar": (
            "━━━━━━━━━━━━━━━━\n"
            "🔵 {service} - {plan}\n"
            "📅 ينتهي: {expires}\n"
            "📊 الحالة: {status}\n"
            "{credentials}"
            "━━━━━━━━━━━━━━━━"
        ),
        "en": (
            "━━━━━━━━━━━━━━━━\n"
            "🔵 {service} - {plan}\n"
            "📅 Expires: {expires}\n"
            "📊 Status: {status}\n"
            "{credentials}"
            "━━━━━━━━━━━━━━━━"
        )
    },
    "support_prompt": {
        "ar": "📨 *الدعم الفني*\n\nأرسل رسالتك وسيرد عليك فريقنا في أقرب وقت:",
        "en": "📨 *Technical Support*\n\nSend your message and our team will reply shortly:"
    },
    "ticket_created": {
        "ar": "✅ تم إرسال رسالتك! سنرد عليك قريباً.\nرقم التذكرة: #{ticket_id}",
        "en": "✅ Your message has been sent! We'll reply soon.\nTicket #: #{ticket_id}"
    },
    "back": {"ar": "◀️ رجوع", "en": "◀️ Back"},
    "cancel": {"ar": "❌ إلغاء", "en": "❌ Cancel"},
    "profile": {
        "ar": (
            "👤 *ملفك الشخصي*\n\n"
            "🆔 المعرف: `{uid}`\n"
            "👤 الاسم: {name}\n"
            "🌐 المقبض: @{username}\n"
            "📅 تاريخ الانضمام: {joined}\n\n"
            "📦 الاشتراك النشط: {sub_status}"
        ),
        "en": (
            "👤 *Your Profile*\n\n"
            "🆔 ID: `{uid}`\n"
            "👤 Name: {name}\n"
            "🌐 Handle: @{username}\n"
            "📅 Joined: {joined}\n\n"
            "📦 Active Subscription: {sub_status}"
        )
    },
    "banned": {
        "ar": "🚫 تم حظر حسابك. تواصل مع الدعم.",
        "en": "🚫 Your account has been banned. Contact support."
    },
    # ——— أدمن ———
    "admin_panel": {
        "ar": (
            "⚙️ *لوحة الإدارة*\n\n"
            "👥 المستخدمون: {users}\n"
            "✅ الاشتراكات النشطة: {subs}\n"
            "💰 الإيرادات: {revenue} USDT\n"
            "⏳ الطلبات المعلقة: {pending}\n"
            "🎫 التذاكر المفتوحة: {tickets}"
        ),
        "en": (
            "⚙️ *Admin Panel*\n\n"
            "👥 Users: {users}\n"
            "✅ Active Subscriptions: {subs}\n"
            "💰 Revenue: {revenue} USDT\n"
            "⏳ Pending Orders: {pending}\n"
            "🎫 Open Tickets: {tickets}"
        )
    },
}


def t(key: str, lang: str = "ar", **kwargs) -> str:
    """جلب النص المترجم"""
    entry = TEXTS.get(key, {})
    text = entry.get(lang, entry.get("ar", f"[{key}]"))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text

