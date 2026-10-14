from pathlib import Path

p = Path("app.py")
s = p.read_text()

if "/api/admin/payment-settings" in s:
    print("Payment settings API already exists; no changes made.")
    raise SystemExit(0)

anchor = '@app.post("/api/admin/payments/<int:request_id>")'
if anchor not in s:
    print("ERROR: Expected code location not found. app.py unchanged.")
    raise SystemExit(1)

addition = r'''
@app.get("/api/admin/payment-settings")
@admin_required
def admin_get_payment_settings():
    with get_db() as db:
        row = db.execute("""
            SELECT method, account_name, account_number, instructions, enabled
            FROM payment_settings WHERE id = 1
        """).fetchone()
    return jsonify(settings=dict(row) if row else {})


@app.post("/api/admin/payment-settings")
@admin_required
def admin_save_payment_settings():
    data = request.get_json(silent=True) or {}
    method = str(data.get("method", "")).strip()
    account_name = str(data.get("account_name", "")).strip()[:100]
    account_number = str(data.get("account_number", "")).strip()[:50]
    instructions = str(data.get("instructions", "")).strip()[:500]

    if method not in ("JazzCash", "Easypaisa"):
        return jsonify(error="Choose JazzCash or Easypaisa"), 400
    if not account_name or not account_number:
        return jsonify(error="Account name and number are required"), 400

    with get_db() as db:
        db.execute("""
            INSERT INTO payment_settings
                (id, method, account_name, account_number, instructions, enabled)
            VALUES (1, ?, ?, ?, ?, 1)
            ON CONFLICT(id) DO UPDATE SET
                method=excluded.method,
                account_name=excluded.account_name,
                account_number=excluded.account_number,
                instructions=excluded.instructions,
                enabled=1
        """, (method, account_name, account_number, instructions))
        db.commit()
    return jsonify(message="Payment settings saved")


@app.delete("/api/admin/payment-settings")
@admin_required
def admin_delete_payment_settings():
    with get_db() as db:
        db.execute("""
            UPDATE payment_settings
            SET method='', account_name='', account_number='',
                instructions='', enabled=0
            WHERE id=1
        """)
        db.commit()
    return jsonify(message="Payment settings cleared")


@app.get("/api/payment-settings")
@login_required
def member_get_payment_settings():
    with get_db() as db:
        row = db.execute("""
            SELECT method, account_name, account_number, instructions
            FROM payment_settings
            WHERE id=1 AND enabled=1 AND account_number != ''
        """).fetchone()
    return jsonify(settings=dict(row) if row else None)

'''

s = s.replace(anchor, addition + anchor, 1)
p.write_text(s)
print("Payment settings API added.")
