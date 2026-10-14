from pathlib import Path
import shutil

p = Path("app.py")
s = p.read_text()

old = '''    db = get_db()
    try:
        if kind == "deposit" and is_upload:
'''

new = '''    db = get_db()
    try:
        if kind == "withdraw":
            account = db.execute("""
                SELECT method, account_name, account_number
                FROM withdrawal_accounts
                WHERE user_id = ?
            """, (session["user_id"],)).fetchone()

            if not account:
                return jsonify(
                    error="Withdrawal سے پہلے اپنا اکاؤنٹ محفوظ کریں۔"
                ), 400

            # Never trust a payment method supplied by the browser.
            method = account["method"]

        if kind == "deposit" and is_upload:
'''

if s.count(old) != 1:
    raise SystemExit(
        "STOP: متوقع کوڈ کی ایک جگہ نہیں ملی۔ کوئی تبدیلی نہیں کی گئی۔"
    )

shutil.copy2(p, "app.py.before-withdrawal-security")
p.write_text(s.replace(old, new, 1))
print("OK: Withdrawal server-side account check added.")
