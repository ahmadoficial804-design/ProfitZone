import sqlite3
from pathlib import Path

db_path = Path("users.db")
if not db_path.exists():
    raise SystemExit("STOP: users.db nahi mili.")

db = sqlite3.connect(str(db_path))
try:
    columns = {
        row[1]
        for row in db.execute("PRAGMA table_info(investment_plans)")
    }

    if "daily_profit_percent" in columns:
        print("Column pehle se maujood hai; koi change nahi kiya.")
    else:
        db.execute("""
            ALTER TABLE investment_plans
            ADD COLUMN daily_profit_percent REAL NOT NULL DEFAULT 0
        """)
        db.commit()
        print("daily_profit_percent column safely add ho gaya.")
finally:
    db.close()
