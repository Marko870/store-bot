"""
💸 واجهة السحب — Syriatel Cash
تشغيل: python withdraw.py
ثم افتح: http://localhost:8080
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

HTML = """<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>💸 سكريبت السحب</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: Arial, sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; }
h1 { color: #22c55e; margin-bottom: 24px; font-size: 22px; }
.card { background: #1e293b; border-radius: 12px; padding: 20px; margin-bottom: 16px; }
h2 { color: #94a3b8; font-size: 15px; margin-bottom: 14px; }
input { width: 100%; padding: 10px 12px; border-radius: 8px; border: 1px solid #334155;
        background: #0f172a; color: #e2e8f0; font-size: 15px; margin-bottom: 10px; }
button { width: 100%; padding: 12px; border-radius: 8px; border: none; background: #22c55e;
         color: #000; font-size: 15px; font-weight: bold; cursor: pointer; }
button:hover { background: #16a34a; }
.result { margin-top: 14px; padding: 12px; border-radius: 8px; background: #0f172a;
          font-size: 14px; white-space: pre-wrap; word-break: break-all; }
.ok { border-left: 3px solid #22c55e; }
.err { border-left: 3px solid #ef4444; }
</style>
</head>
<body>
<h1>💸 سكريبت السحب — Syriatel Cash</h1>

<div class="card">
  <h2>1. فحص الرصيد</h2>
  <input id="bal_gsm" placeholder="رقم الحساب" value="{FROM_GSM}">
  <button onclick="checkBalance()">فحص الرصيد</button>
  <div id="bal_result" class="result" style="display:none"></div>
</div>

<div class="card">
  <h2>2. تحويل كاش</h2>
  <input id="tr_from" placeholder="رقم المصدر" value="{FROM_GSM}">
  <input id="tr_to" placeholder="رقم المستفيد">
  <input id="tr_amount" placeholder="المبلغ (ل.س)" type="number">
  <input id="tr_pin" placeholder="رمز PIN" type="password" value="{PIN_CODE}">
  <button onclick="transfer()">تنفيذ التحويل</button>
  <div id="tr_result" class="result" style="display:none"></div>
</div>

<div class="card">
  <h2>3. الحسابات المرتبطة</h2>
  <button onclick="listAccounts()">عرض الحسابات</button>
  <div id="acc_result" class="result" style="display:none"></div>
</div>

<script>
async function api(path, data=null) {
  const opts = { method: data ? 'POST' : 'GET',
                 headers: {'Content-Type':'application/json'} };
  if (data) opts.body = JSON.stringify(data);
  const r = await fetch(path, opts);
  return r.json();
}
function show(id, text, ok) {
  const el = document.getElementById(id);
  el.style.display = 'block';
  el.className = 'result ' + (ok ? 'ok' : 'err');
  el.textContent = text;
}
async function checkBalance() {
  show('bal_result', '⏳ جاري الجلب...', true);
  const r = await api('/balance?gsm=' + document.getElementById('bal_gsm').value);
  show('bal_result', r.text, r.ok);
}
async function transfer() {
  if (!confirm('تأكيد التحويل؟')) return;
  show('tr_result', '⏳ جاري التحويل...', true);
  const r = await api('/transfer', {
    from_gsm: document.getElementById('tr_from').value,
    to_gsm:   document.getElementById('tr_to').value,
    amount:   document.getElementById('tr_amount').value,
    pin_code: document.getElementById('tr_pin').value,
  });
  show('tr_result', r.text, r.ok);
}
async function listAccounts() {
  show('acc_result', '⏳ جاري الجلب...', true);
  const r = await api('/accounts');
  show('acc_result', r.text, r.ok);
}
</script>
</body>
</html>
""".replace("{FROM_GSM}", FROM_GSM).replace("{PIN_CODE}", PIN_CODE)


async def handle_index(request):
    return web.Response(text=HTML, content_type="text/html")


async def handle_balance(request):
    gsm = request.rel_url.query.get("gsm", FROM_GSM)
    headers = {"X-Api-Key": API_KEY, "Accept": "application/json"}
    params  = {"resource": "syriatel", "action": "balance", "gsm": gsm}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(BASE_URL, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as r:
                data = await r.json()
        if data.get("success"):
            d = data["data"]
            text = f"✅ الرصيد\nالرقم: {d.get('gsm')}\nالرصيد: {float(d.get('balance',0)):,.0f} ل.س"
            return web.json_response({"ok": True, "text": text})
        return web.json_response({"ok": False, "text": f"❌ {data.get('error')}"})
    except Exception as e:
        return web.json_response({"ok": False, "text": f"❌ خطأ: {e}"})


async def handle_transfer(request):
    body = await request.json()
    headers = {"X-Api-Key": API_KEY, "Accept": "application/json",
               "Content-Type": "application/x-www-form-urlencoded"}
    data = {"gsm": body.get("from_gsm", FROM_GSM),
            "to_gsm": body["to_gsm"],
            "amount": str(int(float(body["amount"]))),
            "pin_code": body.get("pin_code", PIN_CODE)}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{BASE_URL}?resource=syriatel&action=transfer_cash",
                              headers=headers, data=data, timeout=aiohttp.ClientTimeout(total=15)) as r:
                result = await r.json()
        if result.get("success"):
            d = result["data"]
            text = (f"✅ تم التحويل بنجاح!\n"
                    f"المبلغ: {d.get('amount')} ل.س\n"
                    f"الرسوم: {d.get('fee')} ل.س\n"
                    f"كود العملية: {d.get('billcode')}\n"
                    f"الرسالة: {d.get('message')}")
            return web.json_response({"ok": True, "text": text})
        return web.json_response({"ok": False, "text": f"❌ {result.get('error')}"})
    except Exception as e:
        return web.json_response({"ok": False, "text": f"❌ خطأ: {e}"})


async def handle_accounts(request):
    headers = {"X-Api-Key": API_KEY, "Accept": "application/json"}
    params  = {"resource": "accounts", "action": "list"}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(BASE_URL, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as r:
                data = await r.json()
        if data.get("success"):
            accs = data["data"].get("syriatel", [])
            lines = [f"✅ حسابات Syriatel ({len(accs)}):"]
            for a in accs:
                lines.append(f"• {a.get('gsm')} — كود: {a.get('cash_code')}")
            return web.json_response({"ok": True, "text": "\n".join(lines)})
        return web.json_response({"ok": False, "text": f"❌ {data.get('error')}"})
    except Exception as e:
        return web.json_response({"ok": False, "text": f"❌ خطأ: {e}"})


app = web.Application()
app.router.add_get("/",         handle_index)
app.router.add_get("/balance",  handle_balance)
app.router.add_post("/transfer",handle_transfer)
app.router.add_get("/accounts", handle_accounts)

if __name__ == "__main__":
    print(f"🚀 running on port {PORT}")
    web.run_app(app, port=PORT)
