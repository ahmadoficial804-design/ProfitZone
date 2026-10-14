from pathlib import Path
import shutil

p = Path("app.py")
s = p.read_text()
backup = Path("app.py.pre-user-plans-api-patch")
marker = '@app.get("/api/wallet")'

if s.count(marker) != 1:
    raise SystemExit("STOP: wallet route marker mismatch.")
if backup.exists():
    raise SystemExit("STOP: patch backup already exists.")
if 'def user_list_plans()' in s or 'def buy_plan(' in s:
    raise SystemExit("STOP: user Plans API appears to exist already.")

routes = r'''
@app.get("/api/plans")
@login_required
def user_list_plans():
    user_id = session["user_id"]
    now = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).isoformat(timespec="seconds")

    with get_db() as db:
        db.execute("""
            UPDATE plan_purchases
            SET status='expired'
            WHERE user_id=? AND status='active' AND expires_at<=?
        """, (user_id, now))

        plans = db.execute("""
            SELECT id, name, price_paisa, duration_days
            FROM investment_plans
            WHERE active=1
            ORDER BY price_paisa ASC, id ASC
        """).fetchall()

        purchases = db.execute("""
            SELECT id, plan_id, plan_name, price_paisa, duration_days,
                   status, purchased_at, activated_at, expires_at
            FROM plan_purchases
            WHERE user_id=?
            ORDER BY id DESC LIMIT 50
        """, (user_id,)).fetchall()

    return jsonify(
        plans=[dict(r) for r in plans],
        purchases=[dict(r) for r in purchases]
    )


@app.post("/api/plans/<int:plan_id>/buy")
@login_required
def buy_plan(plan_id):
    data = request.get_json(silent=True) or {}
    key = str(data.get("idempotency_key", "")).strip()

    if not 8 <= len(key) <= 100:
        return jsonify(error="A valid purchase request key is required."), 400

    from datetime import datetime, timedelta, timezone

    user_id = session["user_id"]
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat(timespec="seconds")
    db = get_db()

    try:
        db.execute("BEGIN IMMEDIATE")

        # Repeated request with the same key must never charge twice.
        previous = db.execute("""
            SELECT * FROM plan_purchases
            WHERE user_id=? AND idempotency_key=?
        """, (user_id, key)).fetchone()

        if previous:
            balance = db.execute(
                "SELECT balance_paisa FROM wallets WHERE user_id=?",
                (user_id,)
            ).fetchone()
            db.commit()
            return jsonify(
                message="This purchase request was already processed.",
                purchase=dict(previous),
                balance_paisa=balance["balance_paisa"] if balance else 0,
                replayed=True
            )

        plan = db.execute("""
            SELECT id, name, price_paisa, duration_days
            FROM investment_plans
            WHERE id=? AND active=1
        """, (plan_id,)).fetchone()

        if not plan:
            db.rollback()
            return jsonify(error="This plan is unavailable."), 404

        cur = db.execute("""
            UPDATE wallets
            SET balance_paisa=balance_paisa-?
            WHERE user_id=? AND balance_paisa>=?
        """, (plan["price_paisa"], user_id, plan["price_paisa"]))

        if cur.rowcount != 1:
            db.rollback()
            return jsonify(error="Insufficient wallet balance."), 400

        expires = (
            now_dt + timedelta(days=plan["duration_days"])
        ).isoformat(timespec="seconds")

        cur = db.execute("""
            INSERT INTO plan_purchases
                (user_id, plan_id, plan_name, price_paisa,
                 duration_days, status, purchased_at, activated_at,
                 expires_at, idempotency_key)
            VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
        """, (
            user_id, plan["id"], plan["name"], plan["price_paisa"],
            plan["duration_days"], now, now, expires, key
        ))

        purchase = db.execute(
            "SELECT * FROM plan_purchases WHERE id=?",
            (cur.lastrowid,)
        ).fetchone()

        balance = db.execute(
            "SELECT balance_paisa FROM wallets WHERE user_id=?",
            (user_id,)
        ).fetchone()

        db.commit()
        return jsonify(
            message="Plan purchased and activated.",
            purchase=dict(purchase),
            balance_paisa=balance["balance_paisa"],
            replayed=False
        ), 201

    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify(error="Purchase request could not be processed."), 409
    except Exception:
        db.rollback()
        app.logger.exception("Plan purchase failed")
        return jsonify(error="Purchase failed; no changes were committed."), 500
    finally:
        db.close()


'''

shutil.copy2(p, backup)
p.write_text(s.replace(marker, routes + marker, 1))
print("User Plans API added. Backup:", backup)
