from pathlib import Path

p = Path("app.py")
s = p.read_text()

start = s.index('@app.post("/api/admin/plans")')
end = s.index('@app.post("/api/admin/plans/<int:plan_id>/toggle")')

new_api = '''@app.post("/api/admin/plans")
@admin_required
def admin_create_plan():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    try:
        price_paisa = int(round(float(data.get("price", 0)) * 100))
        duration_days = int(data.get("duration_days", 0))
        daily_profit_percent = float(data.get("daily_profit_percent", 0))
    except (TypeError, ValueError, OverflowError):
        return jsonify(error="Enter valid price, duration and daily rate."), 400

    if not name or len(name) > 100:
        return jsonify(error="Plan name is required (maximum 100 characters)."), 400
    if not 0 < price_paisa <= 100000000:
        return jsonify(error="Price must be greater than zero."), 400
    if not 0 <= daily_profit_percent <= 100000:
        return jsonify(error="Daily profit rate must be between 0 and 100000%."), 400
    if not 1 <= duration_days <= 36500:
        return jsonify(error="Duration must be between 1 and 36500 days."), 400

    with get_db() as db:
        cur = db.execute(
            """INSERT INTO investment_plans
               (name, price_paisa, duration_days, daily_profit_percent)
               VALUES (?, ?, ?, ?)""",
            (name, price_paisa, duration_days, daily_profit_percent)
        )
        row = db.execute(
            "SELECT * FROM investment_plans WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return jsonify(message="Plan created.", plan=dict(row)), 201


@app.post("/api/admin/plans/<int:plan_id>")
@admin_required
def admin_update_plan(plan_id):
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    try:
        price_paisa = int(round(float(data.get("price", 0)) * 100))
        duration_days = int(data.get("duration_days", 0))
        daily_profit_percent = float(data.get("daily_profit_percent", 0))
    except (TypeError, ValueError, OverflowError):
        return jsonify(error="Enter valid price, duration and daily rate."), 400

    if not name or len(name) > 100:
        return jsonify(error="Invalid plan name."), 400
    if not 0 < price_paisa <= 100000000:
        return jsonify(error="Invalid plan price."), 400
    if not 0 <= daily_profit_percent <= 100000:
        return jsonify(error="Daily profit rate must be between 0 and 100000%."), 400
    if not 1 <= duration_days <= 36500:
        return jsonify(error="Invalid duration."), 400

    with get_db() as db:
        cur = db.execute(
            """UPDATE investment_plans
               SET name=?, price_paisa=?, duration_days=?, daily_profit_percent=?,
                   updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (name, price_paisa, duration_days, daily_profit_percent, plan_id)
        )
        if cur.rowcount != 1:
            return jsonify(error="Plan not found."), 404
        row = db.execute(
            "SELECT * FROM investment_plans WHERE id=?", (plan_id,)
        ).fetchone()
    return jsonify(message="Plan updated.", plan=dict(row))


'''
s = s[:start] + new_api + s[end:]
p.write_text(s)
print("Admin API updated.")

p = Path("index.html")
s = p.read_text()
old = """const duration = document.createElement('p');
      duration.textContent = 'Duration: ' + plan.duration_days + ' days';"""
new = """const duration = document.createElement('p');
      duration.textContent = 'Duration: ' + plan.duration_days + ' days';
      const rate = document.createElement('p');
      rate.textContent = 'Daily Profit: ' + Number(plan.daily_profit_percent || 0).toFixed(2) + '%';"""
if s.count(old) != 1:
    raise SystemExit(f"STOP: dashboard rate insertion expected 1 match, found {s.count(old)}")
s = s.replace(old, new, 1)

old = "card.append(title, price, duration, buy);"
new = "card.append(title, price, duration, rate, buy);"
if s.count(old) != 1:
    raise SystemExit(f"STOP: dashboard card insertion expected 1 match, found {s.count(old)}")
s = s.replace(old, new, 1)
p.write_text(s)
print("User dashboard updated.")
