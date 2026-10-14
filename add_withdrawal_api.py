from pathlib import Path
import shutil

p = Path("app.py")
s = p.read_text()

marker = "\ndef admin_required(fn):"
if "@app.get(\"/api/withdrawal-account\")" in s:
    print("API پہلے سے موجود ہے؛ کوئی تبدیلی نہیں کی۔")
    raise SystemExit(0)

if marker not in s or "def login_required(fn):" not in s:
    raise SystemExit("STOP: متوقع جگہ نہیں ملی؛ کوئی تبدیلی نہیں کی۔")

routes = r'''

@app.get("/api/withdrawal-account")
@login_required
def get_withdrawal_account():
    with get_db() as db:
        row = db.execute("""
            SELECT method, account_name, account_number, created_at
            FROM withdrawal_accounts WHERE user_id = ?
        """, (session["user_id"],)).fetchone()
    return jsonify(account=dict(row) if row else None)


@app.post("/api/withdrawal-account")
@login_required
def save_withdrawal_account():
    data = request.get_json(silent=True) or {}
    method = str(data.get("method", "")).strip()
    name = str(data.get("account_name", "")).strip()
    number = str(data.get("account_number", "")).strip()

    if method not in ("JazzCash", "Easypaisa"):
        return jsonify(error="JazzCash یا Easypaisa منتخب کریں۔"), 400
    if not name or len(name) > 100:
        return jsonify(error="درست اکاؤنٹ ہولڈر کا نام درج کریں۔"), 400
    if not number or len(number) > 40:
        return jsonify(error="درست اکاؤنٹ نمبر درج کریں۔"), 400

    # Normalize for duplicate detection; preserve original number for display.
    key = "".join(ch for ch in number if ch.isdigit())
    if len(key) < 8 or len(key) > 20:
        return jsonify(error="اکاؤنٹ نمبر 8 سے 20 ہندسوں کا ہونا چاہیے۔"), 400

    # Treat common Pakistan mobile-number formats as the same number.
    if key.startswith("0092"):
        key = "0" + key[4:]
    elif key.startswith("92") and len(key) == 12:
        key = "0" + key[2:]

    db = get_db()
    try:
        existing = db.execute("""
            SELECT user_id FROM withdrawal_accounts WHERE user_id = ?
        """, (session["user_id"],)).fetchone()
        if existing:
            return jsonify(error="آپ کا اکاؤنٹ پہلے ہی محفوظ ہے اور تبدیل نہیں ہو سکتا۔"), 409

        db.execute("""
            INSERT INTO withdrawal_accounts
                (user_id, method, account_name, account_number, account_number_key)
            VALUES (?, ?, ?, ?, ?)
        """, (session["user_id"], method, name, number, key))
        db.commit()
        return jsonify(message="Withdrawal اکاؤنٹ مستقل طور پر محفوظ ہوگیا۔"), 201
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify(error="یہ اکاؤنٹ نمبر پہلے ہی کسی دوسرے یوزر کے ساتھ محفوظ ہے۔"), 409
    finally:
        db.close()
'''

shutil.copy2(p, "app.py.before-withdrawal-api")
p.write_text(s.replace(marker, routes + marker, 1))
print("OK: Withdrawal account APIs شامل ہوگئیں۔")
print("Backup: app.py.before-withdrawal-api")
