"""
💸 اختبار السحب — Syriatel Cash API Test
"""

import asyncio
import aiohttp
import os
from aiohttp import web

API_KEY  = os.getenv("APISYRIA_KEY", "")
FROM_GSM = os.getenv("SYRIATEL_GSM", "")
PIN_CODE = os.getenv("SYRIATEL_PIN", "")
BASE_URL = "https://apisyria.com/api/v1"
PORT     = int(os.getenv("PORT", 8080))

# مستخدم وهمي للاختبار
FAKE_USER = {"name": "أحمد (اختبار)", "balance": 50.0}  # رصيد وهمي 50 USDT

HTML = """<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>اختبار السحب</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: Arial, sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; }
h1 { color: #22c55e; margin-bottom: 8px; font-size: 20px; }
.badge { background: #1e293b; color: #94a3b8; font-size: 12px; padding: 4px 10px;
         border-radius: 20px; display: inline-block; margin-bottom: 20px; }
.card { background: #1e293b; border-radius: 12px; padding: 20px; margin-bottom: 16px; }
h2 { color: #94a3b8; font-size: 14px; margin-bottom: 14px; text-transform: uppercase; letter-spacing: 1px; }
.balance-box { background: #0f172a; border-radius: 10px; padding: 16px; text-align: center; margin-bottom: 16px; }
.balance-val { font-size: 32px; font-weight: bold; color: #22c55e; }
.balance-label { font-size: 13px; color: #64748b; margin-top: 4px; }
input { width: 100%; padding: 10px 12px; border-radius: 8px; border: 1px solid #334155;
        background: #0f172a; color: #e2e8f0; font-size: 15px; margin-bottom: 10px; }
button { width: 100%; padding: 12px; border-radius: 8px; border: none; background: #22c55e;
         color: #000; font-size: 15px; font-weight: bold; cursor: pointer; margin-bottom: 8px; }
button:hover { background: #16a34a; }
button.sec { background: #334155; color: #e2e8f0; }
button.sec:hover { background: #475569; }
.result { margin-top: 12px; padding: 14px; border-radius: 8px; background: #0f172a;
          font-size: 14px; white-space: pre-wrap; line-height: 1.6; display: none; }
.ok  { border-right: 3px solid #22c55e; }
.err { border-right: 3px solid #ef4444; }
.row { display: flex; gap: 8px; }
.row button { flex: 1; }
</style>
</head>
<body>
<h1>💸 اختبار السحب</h1>
<span class="badge">⚠️ بيئة اختبار — مستخدم وهمي</span>

<div class="card">
  <h2>المستخدم الوهمي</h2>
  <div class="balance-box">
    <div class="balance-val" id="bal_display">50.00 USDT</div>
    <div class="balance-label">الرصيد المتاح</div>
  </div>
  <div class="row">
    <button class="sec" onclick="addBalance()">➕ إضافة رصيد</button>
    <button class="sec" onclick="resetBalance()">🔄 إعادة تعيين</button>
  </div>
</div>

<div class="card">
  <h2>طلب السحب</h2>
  <input id="to_gsm" placeholder="رقم سيرياتيل كاش المستفيد">
  <input id="amount" placeholder="المبلغ بالليرة السورية" type="number">
  <input id="pin" placeholder="PIN الحساب المصدر" type="password">
  <button onclick="doWithdraw()">💸 تنفيذ السحب</button>
  <div id="result" class="result"></div>
</div>

<script>
let balance = 50.0;

function updateDisplay() {
  document.getElementById('bal_display').textContent = balance.toFixed(2) + ' USDT';
}

function addBalance() {
  balance += 10;
  updateDisplay();
  alert('تمت إضافة 10 USDT — الرصيد الآن: ' + balance.toFixed(2));
}

function resetBalance() {
  balance = 50.0;
  updateDisplay();
}

function show(text, ok) {
  const el = document.getElementById('result');
  el.style.display = 'block';
  el.className = 'result ' + (ok ? 'ok' : 'err');
  el.textContent = text;
}

async function doWithdraw() {
  const to_gsm = document.getElementById('to_gsm').value.trim();
  const amount = parseFloat(document.getElementById('amount').value);
  const pin    = document.getElementById('pin').value.trim();

  if (!to_gsm) { show('❌ أدخل رقم المستفيد', false); return; }
  if (!amount || amount <= 0) { show('❌ أدخل مبلغاً صحيحاً', false); return; }
  if (!pin) { show('❌ أدخل رمز PIN', false); return; }
  if (amount > balance * 15000) {
    show('❌ الرصيد غير كافٍ\\nالرصيد المتاح: ' + (balance * 15000).toLocaleString() + ' ل.س', false);
    return;
  }

  if (!confirm('تأكيد السحب؟\\nإلى: ' + to_gsm + '\\nالمبلغ: ' + amount.toLocaleString() + ' ل.س')) return;

  show('⏳ جاري التنفيذ...', true);

  const r = await fetch('/withdraw', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ to_gsm, amount, pin })
  });
  const data = await r.json();

  if (data.ok) {
    balance -= amount / 15000;
    updateDisplay();
  }
  show(data.text, data.ok);
}
</script>
</body>
</html>
"""


async def handle_index(request):
    return web.Response(text=HTML, content_type="text/html")


async def handle_withdraw(request):
    body     = await request.json()
    to_gsm   = body.get("to_gsm", "")
    amount   = int(float(body.get("amount", 0)))
    pin      = body.get("pin", PIN_CODE)

    if not to_gsm or not amount:
        return web.json_response({"ok": False, "text": "❌ بيانات ناقصة"})

    headers = {
        "X-Api-Key": API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "gsm":      FROM_GSM,
        "to_gsm":   to_gsm,
        "amount":   str(amount),
        "pin_code": pin,
    }

    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"{BASE_URL}?resource=syriatel&action=transfer_cash",
                headers=headers, data=data,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as r:
                result = await r.json()

        if result.get("success"):
            d = result["data"]
            text = (
                f"✅ تم التحويل بنجاح!\n"
                f"إلى: {to_gsm}\n"
                f"المبلغ: {d.get('amount')} ل.س\n"
                f"الرسوم: {d.get('fee')} ل.س\n"
                f"كود العملية: {d.get('billcode')}\n"
                f"الرسالة: {d.get('message')}"
            )
            return web.json_response({"ok": True, "text": text})
        else:
            return web.json_response({"ok": False, "text": f"❌ {result.get('error', 'خطأ غير معروف')}"})

    except Exception as e:
        return web.json_response({"ok": False, "text": f"❌ خطأ في الاتصال: {e}"})


app = web.Application()
app.router.add_get("/",        handle_index)
app.router.add_post("/withdraw", handle_withdraw)

if __name__ == "__main__":
    print(f"🚀 Server running on port {PORT}")
    web.run_app(app, port=PORT)
