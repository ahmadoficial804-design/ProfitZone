from pathlib import Path

p = Path("app.py")
s = p.read_text()

if "def profitzone_payment_request_api():" not in s:
    raise SystemExit("Payment API not found; app.py unchanged.")

if "/api/admin/payment-receipts/" not in s:
    s = s.replace(
        "import sqlite3",
        "import sqlite3\nimport uuid",
        1
    )

    s = s.replace(
        "from flask import Flask, request, jsonify, session",
        "from flask import Flask, request, jsonify, session, send_from_directory",
        1
    )

    s = s.replace(
        "app.secret_key = os.environ.get",
        "app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024\napp.secret_key = os.environ.get",
        1
    )

    route = r'''
@app.get("/api/admin/payment-receipts/<filename>")
@admin_required
def admin_payment_receipt(filename):
    import re
    if not re.fullmatch(r"[0-9a-f]{32}\.(jpg|jpeg|png|webp)", filename):
        return jsonify(error="Invalid receipt name"), 400
    folder = Path(__file__).with_name("private_uploads") / "payment_receipts"
    return send_from_directory(folder, filename, as_attachment=False)

'''
    anchor = '@app.get("/api/admin/payments")'
    if anchor not in s:
        raise SystemExit("Admin payments route not found; app.py unchanged.")
    s = s.replace(anchor, route + anchor, 1)

start = s.find('@app.post("/api/payment-requests")')
end = s.find('@app.route("/payments"', start)
if start < 0 or end < 0:
    raise SystemExit("Payment API boundaries not found; app.py unchanged.")

new_api = r'''
@app.post("/api/payment-requests")
@login_required
def profitzone_payment_request_api():
    is_upload = not request.is_json
    data = request.form if is_upload else (request.get_json(silent=True) or {})
    kind = str(data.get("type", "")).strip()
    method = str(data.get("method", "")).strip()[:60]
    reference = str(data.get("reference", "")).strip()[:120]

    if kind not in ("deposit", "withdraw"):
        return jsonify(error="Invalid request type"), 400

    try:
        amount = round(float(data.get("amount", 0)) * 100)
    except (TypeError, ValueError):
        return jsonify(error="Enter a valid amount"), 400

    if amount < 100 or amount > 100000000:
        return jsonify(error="Amount must be between Rs. 1 and Rs. 1,000,000"), 400

    receipt_name = None
    if is_upload and kind == "deposit":
        upload = request.files.get("receipt")
        if not upload or not upload.filename:
            return jsonify(error="Please attach a receipt screenshot"), 400
        ext = Path(upload.filename).suffix.lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            return jsonify(error="Only JPG, PNG or WebP images are allowed"), 400
        raw = upload.read(5 * 1024 * 1024 + 1)
        if len(raw) > 5 * 1024 * 1024:
            return jsonify(error="Image must be 5 MB or smaller"), 400
        valid = (
            (ext in (".jpg", ".jpeg") and raw.startswith(b"\xff\xd8\xff")) or
            (ext == ".png" and raw.startswith(b"\x89PNG\r\n\x1a\n")) or
            (ext == ".webp" and len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP")
        )
        if not valid:
            return jsonify(error="File content does not match an allowed image type"), 400

        folder = Path(__file__).with_name("private_uploads") / "payment_receipts"
        folder.mkdir(parents=True, exist_ok=True)
        receipt_name = uuid.uuid4().hex + ext
        (folder / receipt_name).write_bytes(raw)

    db = get_db()
    try:
        if kind == "deposit" and is_upload:
            setting = db.execute("""
                SELECT method FROM payment_settings
                WHERE id=1 AND enabled=1 AND account_number != ''
            """).fetchone()
            if not setting:
                if receipt_name:
                    (Path(__file__).with_name("private_uploads") / "payment_receipts" / receipt_name).unlink(missing_ok=True)
                return jsonify(error="Admin has not configured payment details yet"), 400
            if method != setting["method"]:
                if receipt_name:
                    (Path(__file__).with_name("private_uploads") / "payment_receipts" / receipt_name).unlink(missing_ok=True)
                return jsonify(error="Selected payment method does not match the configured method"), 400

        db.execute("""
            INSERT INTO payment_requests
                (user_id, request_type, amount_paisa, method, reference, screenshot_filename)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session["user_id"], kind, amount, method, reference, receipt_name))
        db.commit()
        return jsonify(message="Request submitted for admin review.", status="pending"), 201
    finally:
        db.close()

'''
s = s[:start] + new_api + s[end:]
p.write_text(s)
print("Private receipt upload API added.")
