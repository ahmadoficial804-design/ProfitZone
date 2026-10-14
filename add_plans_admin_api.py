from pathlib import Path

p = Path("app.py")
s = p.read_text()
marker = '@app.get("/api/admin/users")'

if s.count(marker) != 1:
    raise SystemExit("STOP: app.py marker mismatch; no changes made.")

routes = '''

@app.get("/api/admin/plans")
@admin_required
def admin_list_plans():
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM investment_plans ORDER BY id DESC"
        ).fetchall()
    return jsonify(plans=[dict(r) for r in rows])


@app.post("/api/admin/plans")
@admin_required
def admin_create_plan():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    try:
        price_paisa = int(round(float(data.get("price", 0)) * 100))
        duration_days = int(data.get("duration_days", 0))
    except (TypeError, ValueError, OverflowError):
        return jsonify(error="Enter a valid price and duration."), 400

    if not name or len(name) > 100:
        return jsonify(error="Plan name is required (maximum 100 characters)."), 400
    if not 0 < price_paisa <= 100000000:
        return jsonify(error="Price must be greater than zero."), 400
    if not 1 <= duration_days <= 36500:
        return jsonify(error="Duration must be between 1 and 36500 days."), 400

    with get_db() as db:
        cur = db.execute(
            """INSERT INTO investment_plans
               (name, price_paisa, duration_days) VALUES (?, ?, ?)""",
            (name, price_paisa, duration_days)
        )
        row = db.execute(
            "SELECT * FROM investment_plans WHERE id = ?",
            (cur.lastrowid,)
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
    except (TypeError, ValueError, OverflowError):
        return jsonify(error="Enter a valid price and duration."), 400

    if not name or len(name) > 100:
        return jsonify(error="Invalid plan name."), 400
    if not 0 < price_paisa <= 100000000:
        return jsonify(error="Invalid plan price."), 400
    if not 1 <= duration_days <= 36500:
        return jsonify(error="Invalid duration."), 400

    with get_db() as db:
        cur = db.execute(
            """UPDATE investment_plans
               SET name=?, price_paisa=?, duration_days=?,
                   updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (name, price_paisa, duration_days, plan_id)
        )
        if cur.rowcount != 1:
            return jsonify(error="Plan not found."), 404
        row = db.execute(
            "SELECT * FROM investment_plans WHERE id=?",
            (plan_id,)
        ).fetchone()
    return jsonify(message="Plan updated.", plan=dict(row))


@app.post("/api/admin/plans/<int:plan_id>/toggle")
@admin_required
def admin_toggle_plan(plan_id):
    with get_db() as db:
        cur = db.execute(
            """UPDATE investment_plans
               SET active=CASE WHEN active=1 THEN 0 ELSE 1 END,
                   updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (plan_id,)
        )
        if cur.rowcount != 1:
            return jsonify(error="Plan not found."), 404
        row = db.execute(
            "SELECT * FROM investment_plans WHERE id=?",
            (plan_id,)
        ).fetchone()
    return jsonify(message="Plan status updated.", plan=dict(row))

'''

Path("app.py.add-plans-admin.patch").write_text(routes)
print("Patch text saved.")

