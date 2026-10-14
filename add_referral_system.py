from pathlib import Path

p = Path("app.py")
s = p.read_text()

# Add a safe, repeatable migration after the existing users table setup.
marker = 'init_available_tasks()'
migration = '''
# Referral system migration (safe for existing accounts).
with get_db() as db:
    cols = {row[1] for row in db.execute("PRAGMA table_info(users)")}
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
            exists = db.execute(
                "SELECT 1 FROM users WHERE referral_code=?", (code,)
            ).fetchone()
            if not exists:
                db.execute(
                    "UPDATE users SET referral_code=? WHERE id=?",
                    (code, row["id"])
                )
                break
    db.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_referral_code
        ON users(referral_code)
    """)

'''
if "idx_users_referral_code" not in s:
    if marker not in s:
        raise SystemExit("STOP: app.py startup marker not found; unchanged.")
    s = s.replace(marker, migration + marker, 1)

old_insert = '''                INSERT INTO users
                (username, email, phone, password_hash, invitation_code)
                VALUES (?, ?, ?, ?, ?)
            """, (
                username, email, phone,
                generate_password_hash(password), invitation
            ))
            user_id = cur.lastrowid'''
new_insert = '''                INSERT INTO users
                (username, email, phone, password_hash, invitation_code,
                 referral_code, referred_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                username, email, phone,
                generate_password_hash(password), invitation,
                __import__("secrets").token_hex(4).upper(), inviter_id
            ))
            user_id = cur.lastrowid'''
if new_insert not in s:
    if old_insert not in s:
        raise SystemExit("STOP: signup insert did not match; app.py not saved.")
    validation = '''    inviter_id = None
    if invitation:
        with get_db() as db:
            inviter = db.execute(
                "SELECT id FROM users WHERE referral_code=?",
                (invitation.upper(),)
            ).fetchone()
        if not inviter:
            return jsonify(error="Invalid invitation code."), 400
        inviter_id = inviter["id"]
'''
    signup_marker = '    try:\n        with get_db() as db:'
    # Insert validation only once, within signup.
    start = s.find('@app.post("/api/signup")')
    pos = s.find(signup_marker, start)
    if pos < 0:
        raise SystemExit("STOP: signup validation location not found; app.py not saved.")
    s = s[:pos] + validation + s[pos:]
    s = s.replace(old_insert, new_insert, 1)

old_me = '''        user = db.execute(
            "SELECT username, email, phone FROM users WHERE id = ?",
            (session["user_id"],)
        ).fetchone()'''
new_me = '''        user = db.execute("""
            SELECT u.username, u.email, u.phone, u.referral_code,
                   inviter.username AS inviter_username,
                   (SELECT COUNT(*) FROM users r WHERE r.referred_by=u.id)
                       AS referral_count
            FROM users u
            LEFT JOIN users inviter ON inviter.id=u.referred_by
            WHERE u.id=?
        """, (session["user_id"],)).fetchone()'''
if new_me not in s:
    if old_me not in s:
        raise SystemExit("STOP: /api/me query did not match; app.py not saved.")
    s = s.replace(old_me, new_me, 1)

p.write_text(s)
print("Referral backend patched.")

p = Path("index.html")
s = p.read_text()
old_card = '<p>Referral rewards: Not activated</p>'
new_card = '''<p>Referral rewards: Not activated</p>
<div class="panel" id="referral-panel">
  <h3>Your invite code</h3>
  <p id="referral-code">Loading…</p>
  <button class="action" id="referral-copy-code" type="button">Copy code</button>
  <p id="referral-link" style="overflow-wrap:anywhere"></p>
  <button class="action" id="referral-share" type="button">Share invite link</button>
  <p id="referral-count">Referrals: 0</p>
  <p id="referral-inviter"></p>
  <p class="note">Referral rewards are not enabled.</p>
</div>'''
if 'id="referral-panel"' not in s:
    if old_card not in s:
        raise SystemExit("STOP: dashboard referral insertion point not found; index.html unchanged.")
    s = s.replace(old_card, new_card, 1)

js = '''
async function loadReferralInfo() {
  try {
    const response = await fetch('/api/me');
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not load referral details.');
    const code = data.referral_code || '';
    const link = window.location.origin + '/?ref=' + encodeURIComponent(code);
    document.getElementById('referral-code').textContent = code || 'Not available';
    document.getElementById('referral-link').textContent = link;
    document.getElementById('referral-count').textContent = 'Referrals: ' + (data.referral_count || 0);
    document.getElementById('referral-inviter').textContent =
      data.inviter_username ? 'Invited by: ' + data.inviter_username : 'Invited by: —';
    document.getElementById('referral-copy-code').onclick = async () => {
      try { await navigator.clipboard.writeText(code); alert('Invite code copied.'); }
      catch (_) { alert('Your invite code: ' + code); }
    };
    document.getElementById('referral-share').onclick = async () => {
      try {
        if (navigator.share) await navigator.share({title:'Join ProfitZone', url:link, text:'Use my invite code: ' + code});
        else { await navigator.clipboard.writeText(link); alert('Invite link copied.'); }
      } catch (error) {
        if (error.name !== 'AbortError') alert('Invite link: ' + link);
      }
    };
  } catch (error) {
    const el = document.getElementById('referral-code');
    if (el) el.textContent = 'Could not load referral details.';
  }
}
'''
if 'async function loadReferralInfo()' not in s:
    close = s.rfind('</script>')
    if close < 0:
        raise SystemExit("STOP: dashboard script closing tag not found; index.html unchanged.")
    s = s[:close] + js + "\nloadReferralInfo();\n" + s[close:]
p.write_text(s)
print("Referral dashboard patched.")

p = Path("login.html")
s = p.read_text()
snippet = '''
const referralFromUrl = new URLSearchParams(window.location.search).get('ref');
if (referralFromUrl) {
  const invitationInput = document.querySelector('#signupForm [name="invitation_code"]');
  if (invitationInput) invitationInput.value = referralFromUrl;
}
'''
if 'referralFromUrl' not in s:
    close = s.rfind('</script>')
    if close < 0:
        raise SystemExit("STOP: login script closing tag not found; login.html unchanged.")
    s = s[:close] + snippet + "\n" + s[close:]
p.write_text(s)
print("Signup invite-link support patched.")
