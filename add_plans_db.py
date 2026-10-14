import sqlite3

db = sqlite3.connect("users.db")
db.execute("""
CREATE TABLE IF NOT EXISTS investment_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price_paisa INTEGER NOT NULL CHECK(price_paisa > 0),
    duration_days INTEGER NOT NULL CHECK(duration_days > 0),
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
    daily_profit_percent REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
""")
db.execute("""
CREATE TABLE IF NOT EXISTS plan_purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plan_id INTEGER NOT NULL,
    plan_name TEXT NOT NULL,
    price_paisa INTEGER NOT NULL CHECK(price_paisa > 0),
    duration_days INTEGER NOT NULL CHECK(duration_days > 0),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK(status IN ('active', 'expired')),
    purchased_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    activated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    UNIQUE(user_id, idempotency_key),
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(plan_id) REFERENCES investment_plans(id)
)
""")
columns = {row[1] for row in db.execute("PRAGMA table_info(investment_plans)")}
if "daily_profit_percent" not in columns:
    db.execute("ALTER TABLE investment_plans ADD COLUMN daily_profit_percent REAL NOT NULL DEFAULT 0")

db.commit()
db.close()
print("Plans tables created successfully.")

