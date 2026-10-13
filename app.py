
import os
from pathlib import Path
import sqlite3
import uuid

_env_file = Path(__file__).with_name(".env")
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        if "=" in _line and not _line.lstrip().startswith("#"):
            _key, _value = _line.split("=", 1)
            os.environ.setdefault(_key.strip(), _value.strip())
from functools import wraps
from flask import Flask, request, jsonify, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image, UnidentifiedImageError

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
app.secret_key = os.environ.get("PROFITZONE_SECRET")

if not app.secret_key:
    raise RuntimeError(
        "Set PROFITZONE_SECRET before starting the app."
    )

DB = os.environ.get("PROFITZONE_DB", os.path.join(os.path.dirname(__file__), "users.db"))


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_available_tasks():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS available_tasks (
                task_key TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                reward_paisa INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.executemany("""
            INSERT OR IGNORE INTO available_tasks
            (task_key, title, description, reward_paisa)
            VALUES (?, ?, ?, ?)
        """, [
            ("daily_checkin", "Daily check-in",
             "Open your dashboard and review your account.", 0),
            ("explore_site", "Explore ProfitZone",
             "Visit the Tasks and Account sections.", 0)
        ])




with get_db() as db:
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL COLLATE NOCASE UNIQUE,
            email TEXT NOT NULL COLLATE NOCASE UNIQUE,
            phone TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            invitation_code TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)


# Referral system migration (safe for existing accounts).
with get_db() as db:
    cols = {row[1] for row in db.execute("PRAGMA table_info(users)")}
    if "avatar" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN avatar TEXT DEFAULT ''")
    if "referral_code" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN referral_code TEXT")
    if "referred_by" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")
    import secrets
    for row in db.execute(
        "SELECT id FROM users WHERE referral_code IS NULL OR referral_code=''"
    ).fetchall():
        while True:
            code = secrets.token_hex(4).upper()
            if not db.execute(
                "SELECT 1 FROM users WHERE referral_code=?", (code,)
            ).fetchone():
                db.execute(
                    "UPDATE users SET referral_code=? WHERE id=?",
                    (code, row["id"])
                )
                break
    db.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_referral_code
        ON users(referral_code)
    """)



init_available_tasks()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify(error="Please log in first"), 401
        return fn(*args, **kwargs)
    return wrapper



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

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        admin_name = os.environ.get("PROFITZONE_ADMIN_LOGIN_USER")
        if (
            session.get("admin_authenticated") is not True
            or not admin_name
            or session.get("admin_username") != admin_name
        ):
            return jsonify(error="Admin login required"), 401
        return fn(*args, **kwargs)
    return wrapper


@app.get("/")
def home():
    from flask import send_from_directory
    return send_from_directory(os.path.dirname(__file__), "login.html")

@app.post("/api/signup")
def signup():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip()
    phone = str(data.get("phone", "")).strip()
    password = str(data.get("password", ""))
    invitation = str(data.get("invitation_code", "")).strip()

    if not all([username, email, phone, password]):
        return jsonify(error="All required fields must be filled"), 400
    if len(username) < 3 or len(username) > 30:
        return jsonify(error="Username must be 3-30 characters"), 400
    if len(password) < 10 or len(password) > 128:
        return jsonify(error="Password must be 10-128 characters"), 400
    if len(email) > 254 or "@" not in email:
        return jsonify(error="Enter a valid email"), 400
    if len(phone) > 30 or len(invitation) > 50:
        return jsonify(error="Input is too long"), 400

    inviter_id = None
    if invitation:
        with get_db() as db:
            inviter = db.execute(
                "SELECT id FROM users WHERE referral_code=?",
                (invitation.upper(),)
            ).fetchone()
        if not inviter:
            return jsonify(error="Invalid invitation code."), 400
        inviter_id = inviter["id"]
    try:
        with get_db() as db:
            while True:
                new_referral_code = __import__("secrets").token_hex(8).upper()
                exists = db.execute(
                    "SELECT 1 FROM users WHERE referral_code=?",
                    (new_referral_code,)
                ).fetchone()
                if not exists:
                    break

            cur = db.execute("""
                INSERT INTO users
                (username, email, phone, password_hash, invitation_code,
                 referral_code, referred_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                username, email, phone,
                generate_password_hash(password), invitation,
                new_referral_code, inviter_id
            ))
            user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        return jsonify(error="Username, email or phone already registered"), 409

    session.clear()
    session["user_id"] = user_id
    return jsonify(message="Account created", username=username), 201


@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    identity = str(data.get("identity", "")).strip()
    password = str(data.get("password", ""))

    with get_db() as db:
        user = db.execute("""
            SELECT * FROM users
            WHERE username = ? OR email = ? OR phone = ?
        """, (identity, identity, identity)).fetchone()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify(error="Invalid login details"), 401

    session.clear()
    session["user_id"] = user["id"]
    return jsonify(message="Login successful", username=user["username"])



AVATAR_DIR = Path(__file__).with_name("avatars")

@app.post("/api/avatar-upload")
@login_required
def avatar_upload():
    file = request.files.get("avatar")
    if not file or not file.filename:
        return jsonify(error="Choose an image first"), 400

    try:
        image = Image.open(file.stream)
        image.verify()
    except Exception:
        return jsonify(error="Invalid image"), 400

    AVATAR_DIR.mkdir(parents=True, exist_ok=True)

    filename = uuid.uuid4().hex + ".png"
    file.stream.seek(0)
    image = Image.open(file.stream).convert("RGB")
    image.thumbnail((512, 512))
    image.save(AVATAR_DIR / filename, "PNG")

    with get_db() as db:
        old = db.execute(
            "SELECT avatar FROM users WHERE id=?",
            (session["user_id"],)
        ).fetchone()

        db.execute(
            "UPDATE users SET avatar=? WHERE id=?",
            (filename, session["user_id"])
        )
        db.commit()

    if old and old["avatar"]:
        (AVATAR_DIR / old["avatar"]).unlink(missing_ok=True)

    return jsonify(message="Avatar uploaded", avatar=filename)


@app.get("/avatar/<filename>")
def avatar_file(filename):
    if Path(filename).name != filename:
        return jsonify(error="Not found"), 404
    return send_from_directory(str(AVATAR_DIR), filename)

@app.get("/api/me")
@login_required
def me():
    with get_db() as db:
        user = db.execute("""
            SELECT u.username, u.email, u.phone, u.referral_code,
                   inviter.username AS inviter_username,
                   (SELECT COUNT(*) FROM users r WHERE r.referred_by=u.id)
                       AS referral_count
            FROM users u
            LEFT JOIN users inviter ON inviter.id=u.referred_by
            WHERE u.id=?
        """, (session["user_id"],)).fetchone()
    if not user:
        session.clear()
        return jsonify(error="Account not found"), 404
    return jsonify(dict(user))


@app.get("/api/my-referrals")
@login_required
def my_referrals():
    with get_db() as db:
        rows = db.execute("""
            SELECT username, created_at
            FROM users
            WHERE referred_by = ?
            ORDER BY id DESC
        """, (session["user_id"],)).fetchall()
    return jsonify(referrals=[dict(row) for row in rows])


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(message="Logged out")


@app.get("/dashboard")
@login_required
def dashboard():
    from flask import send_from_directory
    return send_from_directory(os.path.dirname(__file__), "index.html")

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
            SELECT id, name, price_paisa, duration_days, daily_profit_percent
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
            SELECT id, name, price_paisa, duration_days, daily_profit_percent
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


@app.get("/api/wallet")
@login_required
def wallet():
    db = get_db()
    wallet = db.execute(
        "SELECT balance_paisa FROM wallets WHERE user_id = ?",
        (session["user_id"],)
    ).fetchone()

    transactions = db.execute(
        """SELECT type, amount_paisa, status, created_at, id
           FROM transactions
           WHERE user_id = ?
           ORDER BY id DESC LIMIT 20""",
        (session["user_id"],)
    ).fetchall()

    history = [
        {
            "type": t["type"],
            "amount_paisa": t["amount_paisa"],
            "status": t["status"],
            "created_at": t["created_at"],
            "id": t["id"]
        }
        for t in transactions
    ]

    withdrawals = db.execute(
        """SELECT id, request_type AS type, amount_paisa, status, created_at
           FROM payment_requests
           WHERE user_id = ? AND request_type = 'withdraw'
           ORDER BY id DESC LIMIT 20""",
        (session["user_id"],)
    ).fetchall()

    known = {(t["type"], t["amount_paisa"], t["created_at"]) for t in history}
    for w in withdrawals:
        item = dict(w)
        item["status"] = {
            "pending": "Pending",
            "in_progress": "In Progress",
            "completed": "Completed",
            "approved": "Completed",
            "rejected": "Rejected"
        }.get(item["status"], item["status"].title())

        # Avoid showing an identical existing withdrawal twice.
        key = (item["type"], item["amount_paisa"], item["created_at"])
        if key not in known:
            history.append(item)
            known.add(key)

    history.sort(key=lambda t: (t["created_at"] or ""), reverse=True)

    return jsonify({
        "balance_paisa": wallet["balance_paisa"] if wallet else 0,
        "transactions": history[:20]
    })



@app.get("/tasks")
@login_required
def profitzone_tasks_page():
    from flask import render_template_string
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS task_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, task_key)
            )
        """)
        tasks = db.execute("""
            SELECT a.task_key, a.title, a.description, a.reward_paisa,
                   CASE WHEN t.id IS NULL THEN 0 ELSE 1 END AS submitted
            FROM available_tasks a
            LEFT JOIN task_submissions t
              ON t.task_key = a.task_key AND t.user_id = ?
            WHERE a.active = 1
            ORDER BY a.created_at DESC
        """, (session["user_id"],)).fetchall()

    return render_template_string("""<!doctype html>
<html lang="en">
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ProfitZone Tasks</title>
<style>
:root{color-scheme:dark;--bg:#070b18;--panel:#10182b;--line:#243653;--cyan:#48e4ff;--purple:#9b7bff;--muted:#a7b5cc}
*{box-sizing:border-box}
body{font-family:Arial,sans-serif;background:radial-gradient(ellipse at top,#17274b 0%,#0a1022 42%,#060914 100%);margin:0;min-height:100vh;color:#f3f7ff}
header{padding:30px 20px 25px;background:linear-gradient(135deg,#111d38,#17264a 60%,#251b49);border-bottom:1px solid #34496d;box-shadow:0 12px 40px #02040b66}
header h1{margin:0;font-size:clamp(27px,6vw,36px);letter-spacing:.3px;background:linear-gradient(90deg,#fff,var(--cyan),#b8a3ff);-webkit-background-clip:text;background-clip:text;color:transparent}
header p{color:#b7c7e4;margin:10px 0 0;line-height:1.6}
main{padding:20px 16px 38px;max-width:700px;margin:auto}
a{color:var(--cyan);text-decoration:none;font-weight:600}
a:hover{text-decoration:underline}
main>p:first-child{margin:2px 0 22px}
.card{position:relative;overflow:hidden;background:linear-gradient(145deg,#141e34,#0d1426);border:1px solid var(--line);padding:21px;border-radius:20px;margin:16px 0;box-shadow:0 12px 30px #0003}
.card:before{content:"";position:absolute;left:0;top:0;width:4px;height:100%;background:linear-gradient(180deg,var(--cyan),var(--purple))}
.card h3{margin:0 0 12px;font-size:20px;color:#f4f7ff}
.card p{color:#c2cee2;line-height:1.7;overflow-wrap:anywhere}
small{display:inline-block;color:#a8c9e5;background:#13263b;border:1px solid #244563;padding:9px 11px;border-radius:10px;line-height:1.5}
button{background:linear-gradient(100deg,#20c8e8,#657dff 65%,#a16bff);color:#071020;font-weight:800;border:0;border-radius:12px;padding:13px 19px;min-height:45px;cursor:pointer;box-shadow:0 5px 20px #3c9fff25;transition:transform .15s,filter .15s}
button:hover:not(:disabled){transform:translateY(-2px);filter:brightness(1.12)}
button:disabled{background:#25354b;color:#b6c4d8;box-shadow:none;cursor:default;border:1px solid #3b506b}
#msg{padding:12px 14px;border-radius:12px;color:var(--cyan);overflow-wrap:anywhere}
@media(max-width:480px){header{padding:25px 17px}main{padding:17px 13px 30px}.card{padding:18px;border-radius:17px}.card h3{font-size:19px}button{width:100%}}
</style>
</head>
<body>
<header><h1>ProfitZone Tasks</h1><p>Complete tasks and submit for review</p></header>
<main>
<p><a href="/dashboard">← Back to dashboard</a></p>
{% for task in tasks %}
<div class="card">
<h3>{{ task['title'] }}</h3>
<p>{{ task['description'] }}</p>
<small>Reward: Rs. {{ "%.2f"|format(task['reward_paisa'] / 100) }} · Subject to review</small>
<p><button id='btn-{{ task["task_key"] }}'
       {% if task["submitted"] %}disabled{% endif %}
       onclick='{% if task["task_key"] == "join_whatsapp" %}startWhatsAppTask({{ task["task_key"]|tojson }}){% else %}submitTask({{ task["task_key"]|tojson }}){% endif %}'>{{ "Submitted ✓" if task["submitted"] else ("Join WhatsApp" if task["task_key"] == "join_whatsapp" else "Submit task") }}</button></p>
</div>
{% else %}
<div class="card"><p>No active tasks available right now.</p></div>
{% endfor %}
<p id="msg"></p>
<script>
const whatsappChannel = 'https://whatsapp.com/channel/0029VbBbr4CDDmFV2RnQ0S21';

function startWhatsAppTask(key){
  sessionStorage.setItem('profitzone_return_task', key);
  window.open(whatsappChannel, '_blank');
}

document.addEventListener('visibilitychange', async ()=>{
  if(document.visibilityState !== 'visible') return;
  const key = sessionStorage.getItem('profitzone_return_task');
  if(!key) return;
  sessionStorage.removeItem('profitzone_return_task');
  await submitTask(key);
});

async function submitTask(key){
 const msg=document.getElementById('msg');
 msg.textContent='Submitting...';
 try{
  const r=await fetch('/api/tasks/submit',{method:'POST',
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({task_key:key})});
  const d=await r.json();
  msg.textContent=d.message||d.error||'Request complete';
  if(r.ok && d.message && (
      d.message.includes('submitted for review') ||
      d.message.includes('already submitted')
  )){
    const btn=document.getElementById('btn-'+key);
    if(btn){btn.textContent='Submitted ✓';btn.disabled=true;}
  }
 }catch(e){msg.textContent='Request failed. Please try again.'}
}
</script>
</main></body></html>""", tasks=tasks)

@app.post("/api/tasks/submit")
@login_required
def profitzone_submit_task():
    data = request.get_json(silent=True) or {}
    key = str(data.get("task_key", "")).strip()

    with get_db() as db:
        task = db.execute(
            "SELECT task_key FROM available_tasks WHERE task_key = ? AND active = 1",
            (key,)
        ).fetchone()
        if not task:
            return jsonify(error="Task not found or inactive"), 400

        db.execute("""
            CREATE TABLE IF NOT EXISTS task_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, task_key)
            )
        """)
        try:
            db.execute(
                "INSERT INTO task_submissions(user_id, task_key) VALUES (?, ?)",
                (session["user_id"], key)
            )
            db.commit()
            return jsonify(message="Task submitted for review.")
        except sqlite3.IntegrityError:
            return jsonify(message="You have already submitted this task.")

@app.get("/api/admin/tasks")
@admin_required
def profitzone_admin_tasks_api():
    from flask import jsonify
    db = get_db()
    try:
        rows = db.execute("""
            SELECT t.id, t.user_id, u.username,
                   t.task_key, COALESCE(a.title, t.task_key) AS title,
                   t.status, t.created_at
            FROM task_submissions t
            LEFT JOIN users u ON u.id = t.user_id
            LEFT JOIN available_tasks a ON a.task_key = t.task_key
            ORDER BY t.id DESC LIMIT 100
        """).fetchall()
        return jsonify({"tasks": [dict(row) for row in rows]})
    finally:
        db.close()







@app.get("/api/admin/available-tasks")
@admin_required
def profitzone_admin_available_tasks():
    with get_db() as db:
        rows = db.execute("""
            SELECT task_key, title, description, reward_paisa, active
            FROM available_tasks ORDER BY created_at DESC
        """).fetchall()
    return jsonify(tasks=[dict(r) for r in rows])


@app.post("/api/admin/available-tasks")
@admin_required
def profitzone_admin_create_task():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()
    key = str(data.get("task_key", "")).strip().lower()
    try:
        reward = round(float(data.get("reward", 0)) * 100)
    except (TypeError, ValueError):
        return jsonify(error="Enter a valid reward"), 400
    if not key or not key.replace("_", "").isalnum() or len(key) > 40:
        return jsonify(error="Task key must use letters, numbers, underscores"), 400
    if not title or len(title) > 100 or not description or len(description) > 500:
        return jsonify(error="Enter a title (max 100) and description (max 500)"), 400
    if reward < 0 or reward > 100000000:
        return jsonify(error="Reward must be between Rs. 0 and Rs. 1,000,000"), 400
    with get_db() as db:
        try:
            db.execute("""
                INSERT INTO available_tasks
                (task_key, title, description, reward_paisa)
                VALUES (?, ?, ?, ?)
            """, (key, title, description, reward))
            db.commit()
        except sqlite3.IntegrityError:
            return jsonify(error="That task key already exists"), 409
    return jsonify(message="Task created", task_key=key), 201


@app.post("/api/admin/available-tasks/<task_key>/toggle")
@admin_required
def profitzone_admin_toggle_task(task_key):
    with get_db() as db:
        cur = db.execute("""
            UPDATE available_tasks SET active = CASE active WHEN 1 THEN 0 ELSE 1 END
            WHERE task_key = ?
        """, (task_key,))
        if cur.rowcount != 1:
            return jsonify(error="Task not found"), 404
        db.commit()
        row = db.execute(
            "SELECT active FROM available_tasks WHERE task_key = ?", (task_key,)
        ).fetchone()
    return jsonify(message="Task status updated", active=row["active"])


@app.get("/admin/login")
def admin_login_page():
    from flask import send_from_directory
    return send_from_directory(os.path.dirname(__file__), "admin_login.html")


@app.post("/api/admin/login")
def admin_login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    configured_user = os.environ.get("PROFITZONE_ADMIN_LOGIN_USER", "")
    password_hash = os.environ.get("PROFITZONE_ADMIN_PASSWORD_HASH", "")

    if (
        not configured_user
        or not password_hash
        or username != configured_user
        or not check_password_hash(password_hash, password)
    ):
        return jsonify(error="Invalid admin login details"), 401

    session.clear()
    session["admin_authenticated"] = True
    session["admin_username"] = configured_user
    return jsonify(message="Admin login successful")


@app.post("/api/admin/logout")
def admin_logout():
    session.clear()
    return jsonify(message="Admin logged out")


@app.get("/admin")
@admin_required
def profitzone_admin_dashboard():
    from flask import send_from_directory
    return send_from_directory(os.path.dirname(__file__), "admin.html")




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



@app.get("/api/admin/users")
@admin_required
def profitzone_admin_users_api():
    with get_db() as db:
        rows = db.execute("""
            SELECT u.id, u.username, u.email, u.phone, u.created_at,
                   COALESCE(w.balance_paisa, 0) AS balance_paisa
            FROM users u LEFT JOIN wallets w ON w.user_id = u.id
            ORDER BY u.id DESC LIMIT 200
        """).fetchall()
    return jsonify(users=[dict(r) for r in rows])



@app.get("/api/admin/transactions")
@admin_required
def admin_transactions_api():
    with get_db() as db:
        rows = db.execute("""
            SELECT t.id, t.user_id, u.username, t.type,
                   t.amount_paisa, t.status, t.created_at,
                   t.task_submission_id
            FROM transactions t
            LEFT JOIN users u ON u.id = t.user_id
            ORDER BY t.id DESC
            LIMIT 500
        """).fetchall()
    return jsonify(transactions=[dict(r) for r in rows])


@app.get("/api/admin/wallets")
@admin_required
def admin_wallets_api():
    with get_db() as db:
        rows = db.execute("""
            SELECT w.user_id, u.username, w.balance_paisa
            FROM wallets w
            LEFT JOIN users u ON u.id = w.user_id
            ORDER BY w.user_id DESC
            LIMIT 500
        """).fetchall()
    return jsonify(wallets=[dict(r) for r in rows])



@app.post("/api/admin/add-balance")
@admin_required
def admin_add_balance():
    data = request.get_json(silent=True) or {}

    username = str(data.get("username", "")).strip()
    amount = int(data.get("amount", 0))

    if not username:
        return jsonify(error="Username required"), 400

    if amount <= 0:
        return jsonify(error="Invalid amount"), 400

    amount_paisa = amount * 100

    with get_db() as db:
        user = db.execute(
            "SELECT id FROM users WHERE username=?",
            (username,)
        ).fetchone()

        if not user:
            return jsonify(error="Member not found"), 404

        user_id = user["id"]

        wallet = db.execute(
            "SELECT balance_paisa FROM wallets WHERE user_id=?",
            (user_id,)
        ).fetchone()

        if wallet:
            db.execute(
                "UPDATE wallets SET balance_paisa = balance_paisa + ? WHERE user_id=?",
                (amount_paisa, user_id)
            )
        else:
            db.execute(
                "INSERT INTO wallets (user_id, balance_paisa) VALUES (?, ?)",
                (user_id, amount_paisa)
            )

        db.execute("""
            INSERT INTO transactions
            (user_id, type, amount_paisa, status)
            VALUES (?, 'deposit', ?, 'approved')
        """, (user_id, amount_paisa))

        db.commit()

    return jsonify(
        message="Balance added successfully",
        username=username,
        amount=amount
    )

@app.get("/api/admin/payment-receipts/<filename>")
@admin_required
def admin_payment_receipt(filename):
    import re
    if not re.fullmatch(r"[0-9a-f]{32}\.(jpg|jpeg|png|webp)", filename):
        return jsonify(error="Invalid receipt name"), 400
    folder = Path(__file__).with_name("private_uploads") / "payment_receipts"
    return send_from_directory(folder, filename, as_attachment=False)

@app.get("/api/admin/payments")
@admin_required
def profitzone_admin_payments_api():
    with get_db() as db:
        rows = db.execute("""
            SELECT p.id, p.user_id, u.username, p.request_type,
                   p.amount_paisa, p.method, p.reference, p.status, p.created_at,
                   p.screenshot_filename,
                   w.account_name AS withdrawal_account_name,
                   w.account_number AS withdrawal_account_number
            FROM payment_requests p
            LEFT JOIN users u ON u.id = p.user_id
            LEFT JOIN withdrawal_accounts w ON w.user_id = p.user_id
            ORDER BY p.id DESC LIMIT 200
        """).fetchall()
    return jsonify(requests=[dict(r) for r in rows])




PAYMENT_QR_DIR = Path(__file__).with_name("payment_qr")
PAYMENT_QR_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}

def ensure_payment_qr_column():
    with get_db() as db:
        cols = {r["name"] for r in db.execute("PRAGMA table_info(payment_settings)")}
        if "qr_image" not in cols:
            db.execute('ALTER TABLE payment_settings ADD COLUMN qr_image TEXT NOT NULL DEFAULT ""')
            db.commit()

@app.post("/api/admin/payment-qr")
@admin_required
def payment_qr_upload():
    ensure_payment_qr_column()
    uploaded = request.files.get("qr_image")
    if not uploaded or not uploaded.filename:
        return jsonify(error="Choose a QR image first"), 400
    try:
        uploaded.stream.seek(0)
        image = Image.open(uploaded.stream)
        fmt = image.format
        if fmt not in PAYMENT_QR_FORMATS:
            return jsonify(error="Only JPG, PNG, or WEBP images are allowed"), 400
        if image.width < 1 or image.height < 1 or image.width * image.height > 16000000:
            return jsonify(error="Image dimensions are too large"), 400
        image.verify()
        uploaded.stream.seek(0)
        image = Image.open(uploaded.stream)
        image.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return jsonify(error="Invalid image"), 400

    PAYMENT_QR_DIR.mkdir(parents=True, exist_ok=True)
    filename = uuid.uuid4().hex + PAYMENT_QR_FORMATS[fmt]
    destination = PAYMENT_QR_DIR / filename
    old = ""
    try:
        if fmt == "JPEG":
            image = image.convert("RGB")
        image.save(destination, format=fmt)
        with get_db() as db:
            row = db.execute("SELECT qr_image FROM payment_settings WHERE id=1").fetchone()
            if not row:
                destination.unlink(missing_ok=True)
                return jsonify(error="Save payment settings before uploading a QR image"), 400
            old = row["qr_image"]
            db.execute("UPDATE payment_settings SET qr_image=? WHERE id=1", (filename,))
            db.commit()
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    if old and old != filename and Path(old).name == old:
        (PAYMENT_QR_DIR / old).unlink(missing_ok=True)
    return jsonify(message="QR image uploaded", qr_image=filename)

@app.get("/payment-qr/<filename>")
def payment_qr_file(filename):
    if Path(filename).name != filename:
        return jsonify(error="Not found"), 404
    ensure_payment_qr_column()
    with get_db() as db:
        row = db.execute(
            "SELECT qr_image FROM payment_settings WHERE id=1 AND enabled=1"
        ).fetchone()
    if not row or row["qr_image"] != filename:
        return jsonify(error="Not found"), 404
    return send_from_directory(str(PAYMENT_QR_DIR), filename)

@app.get("/api/admin/payment-settings")
@admin_required
def admin_get_payment_settings():
    ensure_payment_qr_column()
    with get_db() as db:
        row = db.execute("""
            SELECT method, account_name, account_number, instructions, enabled, qr_image
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
    ensure_payment_qr_column()
    with get_db() as db:
        row = db.execute("""
            SELECT method, account_name, account_number, instructions, qr_image
            FROM payment_settings
            WHERE id=1 AND enabled=1 AND account_number != ''
        """).fetchone()
    return jsonify(settings=dict(row) if row else None)

@app.post("/api/admin/payments/<int:request_id>")
@admin_required
def profitzone_admin_review_payment(request_id):
    data = request.get_json(silent=True) or {}
    status = str(data.get("status", "")).strip()

    if status not in ("pending", "in_progress", "completed", "approved", "rejected"):
        return jsonify(error="Invalid status"), 400

    with get_db() as db:
        row = db.execute("""
            SELECT user_id, request_type, amount_paisa, status
            FROM payment_requests WHERE id = ?
        """, (request_id,)).fetchone()

        if not row:
            return jsonify(error="Request not found"), 404

        kind = row["request_type"]
        old_status = row["status"]

        if kind == "deposit":
            if status not in ("approved", "rejected"):
                return jsonify(error="Deposits can only be approved or rejected"), 400
            if old_status in ("approved", "rejected") and status != old_status:
                return jsonify(error="Finalized deposits cannot be changed"), 409

        elif kind == "withdraw":
            if status not in ("pending", "in_progress", "completed", "rejected"):
                return jsonify(error="Invalid withdrawal status"), 400
        else:
            return jsonify(error="Invalid payment type"), 400

        if kind == "deposit" and status == "approved":
            columns = {
                r["name"] for r in db.execute("PRAGMA table_info(transactions)")
            }
            if "payment_request_id" not in columns:
                db.execute(
                    "ALTER TABLE transactions ADD COLUMN payment_request_id INTEGER"
                )

            db.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                idx_transactions_payment_request_type
                ON transactions(payment_request_id, type)
                WHERE payment_request_id IS NOT NULL
            """)

            user_id = row["user_id"]
            amount = int(row["amount_paisa"])
            if amount <= 0:
                return jsonify(error="Invalid deposit amount"), 400

            db.execute("""
                INSERT INTO wallets (user_id, balance_paisa)
                VALUES (?, 0) ON CONFLICT(user_id) DO NOTHING
            """, (user_id,))

            result = db.execute("""
                INSERT OR IGNORE INTO transactions
                    (user_id, type, amount_paisa, status, payment_request_id)
                VALUES (?, 'deposit', ?, 'approved', ?)
            """, (user_id, amount, request_id))

            if result.rowcount == 1:
                db.execute("""
                    UPDATE wallets SET balance_paisa = balance_paisa + ?
                    WHERE user_id = ?
                """, (amount, user_id))

            member = db.execute(
                "SELECT referred_by FROM users WHERE id = ?", (user_id,)
            ).fetchone()

            if member and member["referred_by"] is not None:
                referrer_id = member["referred_by"]
                commission = amount * 20 // 100

                if commission > 0:
                    db.execute("""
                        INSERT INTO wallets (user_id, balance_paisa)
                        VALUES (?, 0) ON CONFLICT(user_id) DO NOTHING
                    """, (referrer_id,))

                    reward = db.execute("""
                        INSERT OR IGNORE INTO transactions
                            (user_id, type, amount_paisa, status, payment_request_id)
                        VALUES (?, 'referral_commission', ?, 'approved', ?)
                    """, (referrer_id, commission, request_id))

                    if reward.rowcount == 1:
                        db.execute("""
                            UPDATE wallets
                            SET balance_paisa = balance_paisa + ?
                            WHERE user_id = ?
                        """, (commission, referrer_id))

        db.execute(
            "UPDATE payment_requests SET status = ? WHERE id = ?",
            (status, request_id)
        )

    return jsonify(message="Request status updated", status=status)


@app.post("/api/admin/tasks/<int:task_id>")
@admin_required
def profitzone_admin_review_task(task_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in ("approved", "rejected"):
        return jsonify(error="Status must be approved or rejected"), 400

    with get_db() as db:
        submission = db.execute("""
            SELECT ts.id, ts.user_id, ts.status,
                   COALESCE(at.reward_paisa, 0) AS reward_paisa
            FROM task_submissions ts
            LEFT JOIN available_tasks at ON at.task_key = ts.task_key
            WHERE ts.id = ?
        """, (task_id,)).fetchone()

        if not submission or submission["status"] != "pending":
            return jsonify(error="Task not found or already reviewed"), 409

        cur = db.execute("""
            UPDATE task_submissions SET status = ?
            WHERE id = ? AND status = 'pending'
        """, (status, task_id))
        if cur.rowcount != 1:
            return jsonify(error="Task not found or already reviewed"), 409

        if status == "approved" and submission["reward_paisa"] > 0:
            columns = {
                row["name"] for row in db.execute(
                    "PRAGMA table_info(transactions)"
                )
            }
            if "task_submission_id" not in columns:
                db.execute(
                    "ALTER TABLE transactions ADD COLUMN task_submission_id INTEGER"
                )

            db.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                idx_transactions_task_submission
                ON transactions(task_submission_id)
                WHERE task_submission_id IS NOT NULL
            """)

            db.execute("""
                INSERT INTO wallets (user_id, balance_paisa)
                VALUES (?, 0)
                ON CONFLICT(user_id) DO NOTHING
            """, (submission["user_id"],))

            result = db.execute("""
                INSERT OR IGNORE INTO transactions
                    (user_id, type, amount_paisa, status, task_submission_id)
                VALUES (?, 'task_reward', ?, 'approved', ?)
            """, (
                submission["user_id"],
                submission["reward_paisa"],
                task_id
            ))

            if result.rowcount == 1:
                db.execute("""
                    UPDATE wallets
                    SET balance_paisa = balance_paisa + ?
                    WHERE user_id = ?
                """, (submission["reward_paisa"], submission["user_id"]))

        db.commit()

    return jsonify(message="Task status updated", status=status)


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

            wallet = db.execute(
                "SELECT balance_paisa FROM wallets WHERE user_id = ?",
                (session["user_id"],)
            ).fetchone()
            balance = wallet["balance_paisa"] if wallet else 0

            if amount > balance:
                return jsonify(
                    error="Insufficient Balance: آپ کا بیلنس اس رقم کے لیے کافی نہیں۔"
                ), 400

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

@app.route("/payments", methods=["GET"])
@login_required
def profitzone_payments_page():
    return """
<!doctype html>
<html lang="en">
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ProfitZone Payments</title>
</head>
<body style="font-family:Arial;max-width:420px;margin:30px auto;padding:16px">
  <h2>ProfitZone</h2>
  <h3>Deposit / Withdraw</h3>

  <form id="paymentForm">
    <label>Request type</label>
    <select id="type" required style="width:100%;padding:12px;margin:8px 0">
      <option value="deposit">Deposit</option>
      <option value="withdraw">Withdraw</option>
    </select>

    <label>Amount (PKR)</label>
    <input id="amount" type="number" min="1" max="1000000"
      step="1" required placeholder="Enter amount"
      style="width:100%;padding:12px;margin:8px 0">

    <label>Payment method</label>
    <input id="method" required placeholder="Easypaisa / JazzCash"
      style="width:100%;padding:12px;margin:8px 0">

    <label>Reference number (optional)</label>
    <input id="reference" placeholder="Transaction reference"
      style="width:100%;padding:12px;margin:8px 0">

    <button type="submit" style="width:100%;padding:12px">
      Submit Request
    </button>
  </form>

  <p id="result"></p>

  <script>
  document.getElementById("paymentForm").addEventListener("submit", async function(e) {
    e.preventDefault();
    const result = document.getElementById("result");
    result.textContent = "Submitting...";

    try {
      const response = await fetch("/api/payment-requests", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          type: document.getElementById("type").value,
          amount: document.getElementById("amount").value,
          method: document.getElementById("method").value,
          reference: document.getElementById("reference").value
        })
      });

      const data = await response.json();
      result.textContent = response.ok
        ? "Request submitted. Status: pending."
        : (data.error || data.message || "Request failed.");
    } catch (error) {
      result.textContent = "Connection error. Check the server.";
    }
  });
  </script>
</body>
</html>
    """




if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)


