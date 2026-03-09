"""
🌐 نظام الترجمة - i18n
"""

STRINGS = {
    "welcome": {
        "ar": "👋 أهلاً وسهلاً *{name}*!\n\n🛍️ مرحباً بك في *Nova Plus*\nنقدم لك أفضل الخدمات الرقمية بأسعار تنافسية\n\nاختر من القائمة أدناه:",
        "en": "👋 Welcome *{name}*!\n\n🛍️ Welcome to *Nova Plus*\nWe offer the best digital services at competitive prices\n\nChoose from the menu below:",
    },
    "services_title": {
        "ar": "🛍️ *خدماتنا*\n\nاختر الخدمة التي تريدها:",
        "en": "🛍️ *Our Services*\n\nChoose a service:",
    },
    "no_services": {
        "ar": "❌ لا توجد خدمات متاحة حالياً",
        "en": "❌ No services available right now",
    },
    "back": {
        "ar": "◀️ رجوع",
        "en": "◀️ Back",
    },
    "main_menu": {
        "ar": "🏠 القائمة الرئيسية",
        "en": "🏠 Main Menu",
    },
    "my_subs": {
        "ar": "📋 *اشتراكاتي*",
        "en": "📋 *My Subscriptions*",
    },
    "no_subs": {
        "ar": "📭 ليس لديك اشتراكات حتى الآن\n\nاضغط على الخدمات لتصفح ما نقدمه 👇",
        "en": "📭 You have no subscriptions yet\n\nBrowse our services 👇",
    },
    "sub_card": {
        "ar": "━━━━━━━━━━━━━━━━\n🔵 *{service}*\n📦 {plan}\n📅 بدأ: {started}\n📅 ينتهي: {expires}\n⏳ باقي: {remaining}\n{bar}\n{credentials}",
        "en": "━━━━━━━━━━━━━━━━\n🔵 *{service}*\n📦 {plan}\n📅 Started: {started}\n📅 Expires: {expires}\n⏳ Remaining: {remaining}\n{bar}\n{credentials}",
    },
    "support_prompt": {
        "ar": "📨 *تواصل مع الدعم*\n\nأرسل رسالتك وسيرد عليك فريقنا في أقرب وقت:",
        "en": "📨 *Contact Support*\n\nSend your message and our team will reply soon:",
    },
    "support_sent": {
        "ar": "✅ تم إرسال رسالتك بنجاح!\nسيتم الرد عليك قريباً.",
        "en": "✅ Your message was sent!\nWe'll reply soon.",
    },
    "cancel": {
        "ar": "❌ إلغاء",
        "en": "❌ Cancel",
    },
    "enter_amount": {
        "ar": "💰 أدخل الكمية (الحد الأدنى: {min}):",
        "en": "💰 Enter amount (minimum: {min}):",
    },
    "invalid_amount": {
        "ar": "❌ الكمية غير صحيحة. الحد الأدنى هو {min}",
        "en": "❌ Invalid amount. Minimum is {min}",
    },
    "rate_info": {
        "ar": "💱 *سعر الصرف الحالي:*\n1 {unit} = {rate} ليرة سورية\n\nأدخل الكمية التي تريدها:",
        "en": "💱 *Current Rate:*\n1 {unit} = {rate} SYP\n\nEnter the amount you want:",
    },
    "order_summary": {
        "ar": "📋 *ملخص الطلب*\n\n🛍️ الخدمة: *{service}*\n📦 الخطة: *{plan}*\n💰 المبلغ: *{amount} USDT*\n{extras}\n\nهل تريد المتابعة؟",
        "en": "📋 *Order Summary*\n\n🛍️ Service: *{service}*\n📦 Plan: *{plan}*\n💰 Amount: *{amount} USDT*\n{extras}\n\nContinue?",
    },
    "payment_details": {
        "ar": "💳 *تفاصيل الدفع*\n\n🛍️ الخدمة: *{service}*\n📦 الخطة: *{plan}*\n💰 المبلغ: *{amount} USDT*\n🌐 الشبكة: `{network}`\n\n━━━━━━━━━━━━━━━━\n📤 أرسل المبلغ لهذا العنوان:\n\n`{address}`\n\n━━━━━━━━━━━━━━━━\n⚠️ بعد الإرسال، أرفق لقطة شاشة للتحويل وسيتم تفعيل طلبك خلال دقائق\n\n🔖 رقم الطلب: `#{order_id}`",
        "en": "💳 *Payment Details*\n\n🛍️ Service: *{service}*\n📦 Plan: *{plan}*\n💰 Amount: *{amount} USDT*\n🌐 Network: `{network}`\n\n━━━━━━━━━━━━━━━━\n📤 Send to this address:\n\n`{address}`\n\n━━━━━━━━━━━━━━━━\n⚠️ After sending, attach a screenshot and your order will be activated within minutes\n\n🔖 Order ID: `#{order_id}`",
    },
    "proof_prompt": {
        "ar": "📸 أرسل صورة إثبات التحويل الآن:",
        "en": "📸 Send your transfer screenshot now:",
    },
    "proof_received": {
        "ar": "✅ تم استلام إثبات الدفع!\nسيتم مراجعة طلبك وتفعيله خلال دقائق.\n\n🔖 رقم الطلب: `#{order_id}`",
        "en": "✅ Payment proof received!\nYour order will be reviewed and activated within minutes.\n\n🔖 Order ID: `#{order_id}`",
    },
    "sub_activated": {
        "ar": "🎉 *تم تفعيل طلبك!*\n\n🛍️ الخدمة: *{service}*\n📦 الخطة: *{plan}*\n{credentials}\n\nاضغط /start لعرض اشتراكك ✅",
        "en": "🎉 *Your order is activated!*\n\n🛍️ Service: *{service}*\n📦 Plan: *{plan}*\n{credentials}\n\nPress /start to view your subscription ✅",
    },
    "order_rejected": {
        "ar": "❌ *تم رفض طلبك*\n\n🔖 رقم الطلب: `#{order_id}`\n\nإذا كان لديك استفسار تواصل مع الدعم.",
        "en": "❌ *Your order was rejected*\n\n🔖 Order ID: `#{order_id}`\n\nContact support if you have questions.",
    },
    "expiry_7d": {
        "ar": "⏰ *تذكير:* اشتراكك في *{service}* سينتهي خلال 7 أيام!\n\nاضغط لتجديده الآن 👇",
        "en": "⏰ *Reminder:* Your *{service}* subscription expires in 7 days!\n\nRenew now 👇",
    },
    "expiry_3d": {
        "ar": "⚠️ *تنبيه:* اشتراكك في *{service}* سينتهي خلال 3 أيام!\n\nجدد الآن قبل الانقطاع 👇",
        "en": "⚠️ *Alert:* Your *{service}* subscription expires in 3 days!\n\nRenew before it expires 👇",
    },
    "expiry_1d": {
        "ar": "🔴 *عاجل:* اشتراكك في *{service}* سينتهي غداً!\n\nجدد الآن فوراً 👇",
        "en": "🔴 *Urgent:* Your *{service}* subscription expires tomorrow!\n\nRenew immediately 👇",
    },
    "renew_btn": {
        "ar": "♻️ جدد اشتراكي",
        "en": "♻️ Renew Subscription",
    },
    "phone_prompt": {
        "ar": "📱 أدخل رقم هاتفك:",
        "en": "📱 Enter your phone number:",
    },
    "wallet_prompt": {
        "ar": "💼 أدخل رقم محفظتك / اسم المستخدم:",
        "en": "💼 Enter your wallet number / username:",
    },
    "profile": {
        "ar": "👤 *ملفي الشخصي*\n\n🆔 المعرف: `{uid}`\n👤 الاسم: {name}\n📅 تاريخ التسجيل: {joined}",
        "en": "👤 *My Profile*\n\n🆔 ID: `{uid}`\n👤 Name: {name}\n📅 Joined: {joined}",
    },
}


def t(key, lang="ar", **kwargs):
    s = STRINGS.get(key, {}).get(lang) or STRINGS.get(key, {}).get("ar", key)
    try:
        return s.format(**kwargs)
    except Exception:
        return s

