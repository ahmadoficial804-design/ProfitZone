from pathlib import Path
import shutil

p = Path("app.py")
s = p.read_text()

old = '''            SELECT p.id, p.user_id, u.username, p.request_type,
                   p.amount_paisa, p.method, p.reference, p.status, p.created_at,
                   p.screenshot_filename
            FROM payment_requests p LEFT JOIN users u ON u.id = p.user_id
            ORDER BY p.id DESC LIMIT 200
'''

new = '''            SELECT p.id, p.user_id, u.username, p.request_type,
                   p.amount_paisa, p.method, p.reference, p.status, p.created_at,
                   p.screenshot_filename,
                   w.account_name AS withdrawal_account_name,
                   w.account_number AS withdrawal_account_number
            FROM payment_requests p
            LEFT JOIN users u ON u.id = p.user_id
            LEFT JOIN withdrawal_accounts w ON w.user_id = p.user_id
            ORDER BY p.id DESC LIMIT 200
'''

if s.count(old) != 1:
    raise SystemExit("STOP: متوقع SQL نہیں ملی؛ کوئی تبدیلی نہیں کی گئی۔")

shutil.copy2(p, "app.py.before-admin-withdrawals")
p.write_text(s.replace(old, new, 1))
print("OK: Admin API میں محفوظ اکاؤنٹ کی تفصیلات شامل ہوگئیں۔")
