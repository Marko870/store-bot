"""
💸 سكريبت السحب — Syriatel Cash Transfer
ملف مستقل للاختبار — احذفه بعد الانتهاء
"""

import asyncio
import aiohttp
import os

# ══════════════════════════════════════════
#   الإعدادات — غيّرها قبل التشغيل
# ══════════════════════════════════════════

API_KEY  = os.getenv("APISYRIA_KEY", "")   # أو اكتبه مباشرة هنا
FROM_GSM = os.getenv("SYRIATEL_GSM", "")   # رقم الحساب المصدر
PIN_CODE = os.getenv("SYRIATEL_PIN", "")   # رمز PIN سيرياتيل كاش

BASE_URL = "https://apisyria.com/api/v1"


# ══════════════════════════════════════════
#   فحص الرصيد
# ══════════════════════════════════════════

async def check_balance(gsm: str = None) -> dict:
    gsm = gsm or FROM_GSM
    params  = {"resource": "syriatel", "action": "balance", "gsm": gsm}
    headers = {"X-Api-Key": API_KEY, "Accept": "application/json"}
    async with aiohttp.ClientSession() as s:
        async with s.get(BASE_URL, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as r:
            return await r.json()


# ══════════════════════════════════════════
#   تحويل كاش
# ══════════════════════════════════════════

async def transfer(to_gsm: str, amount: float, from_gsm: str = None, pin: str = None) -> dict:
    from_gsm = from_gsm or FROM_GSM
    pin      = pin      or PIN_CODE
    headers  = {"X-Api-Key": API_KEY, "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
    data     = {"gsm": from_gsm, "to_gsm": to_gsm, "amount": str(int(amount)), "pin_code": pin}
    async with aiohttp.ClientSession() as s:
        async with s.post(f"{BASE_URL}?resource=syriatel&action=transfer_cash", headers=headers, data=data, timeout=aiohttp.ClientTimeout(total=15)) as r:
            return await r.json()


# ══════════════════════════════════════════
#   عرض الحسابات المرتبطة
# ══════════════════════════════════════════

async def list_accounts() -> dict:
    params  = {"resource": "accounts", "action": "list"}
    headers = {"X-Api-Key": API_KEY, "Accept": "application/json"}
    async with aiohttp.ClientSession() as s:
        async with s.get(BASE_URL, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as r:
            return await r.json()


# ══════════════════════════════════════════
#   Main — واجهة سطر الأوامر
# ══════════════════════════════════════════

async def main():
    if not API_KEY:
        print("❌ API_KEY فارغ — عيّن APISYRIA_KEY")
        return

    print("=" * 45)
    print("💸 سكريبت السحب — Syriatel Cash")
    print("=" * 45)
    print("\n1. فحص الرصيد")
    print("2. تحويل كاش")
    print("3. عرض الحسابات المرتبطة")
    print("0. خروج")

    while True:
        print()
        choice = input("اختر: ").strip()

        if choice == "0":
            print("وداعاً!")
            break

        elif choice == "1":
            gsm = input(f"رقم الحساب [{FROM_GSM}]: ").strip() or FROM_GSM
            print("⏳ جاري الجلب...")
            result = await check_balance(gsm)
            if result.get("success"):
                d = result["data"]
                print(f"\n✅ الرصيد:")
                print(f"   الرقم: {d.get('gsm')}")
                print(f"   الرصيد: {float(d.get('balance', 0)):,.0f} ل.س")
            else:
                print(f"❌ خطأ: {result.get('error')}")

        elif choice == "2":
            to_gsm = input("رقم المستفيد: ").strip()
            if not to_gsm:
                print("❌ أدخل رقم المستفيد")
                continue
            amount_str = input("المبلغ (ل.س): ").strip()
            try:
                amount = float(amount_str.replace(",", ""))
            except ValueError:
                print("❌ مبلغ غير صحيح")
                continue
            from_gsm = input(f"رقم المصدر [{FROM_GSM}]: ").strip() or FROM_GSM
            pin      = input(f"PIN [{PIN_CODE or '****'}]: ").strip() or PIN_CODE

            print(f"\n⚠️  تأكيد التحويل:")
            print(f"   من: {from_gsm}")
            print(f"   إلى: {to_gsm}")
            print(f"   المبلغ: {amount:,.0f} ل.س")
            confirm = input("تأكيد؟ (y/n): ").strip().lower()
            if confirm != "y":
                print("❌ تم الإلغاء")
                continue

            print("⏳ جاري التحويل...")
            result = await transfer(to_gsm, amount, from_gsm, pin)
            if result.get("success"):
                d = result["data"]
                print(f"\n✅ تم التحويل بنجاح!")
                print(f"   المبلغ: {d.get('amount')} ل.س")
                print(f"   الرسوم: {d.get('fee')} ل.س")
                print(f"   كود العملية: {d.get('billcode')}")
                print(f"   الرسالة: {d.get('message')}")
            else:
                print(f"❌ فشل التحويل: {result.get('error')}")

        elif choice == "3":
            print("⏳ جاري الجلب...")
            result = await list_accounts()
            if result.get("success"):
                data = result.get("data", {})
                syriatel = data.get("syriatel", [])
                print(f"\n✅ حسابات Syriatel Cash ({len(syriatel)}):")
                for acc in syriatel:
                    print(f"   • {acc.get('gsm')} — كود: {acc.get('cash_code')}")
            else:
                print(f"❌ خطأ: {result.get('error')}")

        else:
            print("خيار غير صحيح")


if __name__ == "__main__":
    asyncio.run(main())
