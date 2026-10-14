from pathlib import Path

p = Path("app.py")
s = p.read_text()

old = '''def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify(error="Please log in first"), 401
        admin_id = os.environ.get("PROFITZONE_ADMIN_USER_ID")
        if not admin_id or str(session["user_id"]) != admin_id:
            return jsonify(error="Admin access required"), 403
        return fn(*args, **kwargs)
    return wrapper
'''

new = '''def admin_required(fn):
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
'''

route_anchor = '@app.get("/admin")'
routes = '''@app.get("/admin/login")
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


'''

if s.count(old) != 1:
    raise SystemExit("STOP: admin_required block did not match exactly; app.py unchanged.")
if s.count(route_anchor) != 1:
    raise SystemExit('STOP: expected /admin route anchor not found uniquely; app.py unchanged.')
if 'def admin_login_page()' in s or 'PROFITZONE_ADMIN_PASSWORD_HASH' in s:
    raise SystemExit("STOP: admin login code may already exist; app.py unchanged.")

backup = Path("app.py.before_admin_auth")
if not backup.exists():
    raise SystemExit("STOP: expected backup app.py.before_admin_auth is missing.")

s = s.replace(old, new, 1)
s = s.replace(route_anchor, routes + route_anchor, 1)
p.write_text(s)
print("Admin authentication code added to app.py.")
