from pathlib import Path

def patch(file, replacements):
    p = Path(file)
    text = p.read_text()
    for old, new in replacements:
        count = text.count(old)
        if count != 1:
            raise SystemExit(
                f"STOP: {file}: expected one match, found {count}:\n{old[:100]}"
            )
        text = text.replace(old, new, 1)
    p.write_text(text)
    print(f"Patched: {file}")

patch("admin.html", [
    (
        '<label>Duration (days)</label>',
        '<label>Daily Profit (%)</label>\n'
        '<input id="planDailyProfit" type="number" min="0" max="100000" '
        'step="0.01" required value="0" '
        'style="display:block;width:100%;padding:10px;margin:8px 0;box-sizing:border-box">\n'
        '<label>Duration (days)</label>'
    ),
    (
        "document.getElementById('planDuration').value=x.duration_days;",
        "document.getElementById('planDuration').value=x.duration_days;\n"
        "        document.getElementById('planDailyProfit').value=Number(x.daily_profit_percent||0);"
    ),
    (
        "duration_days:document.getElementById('planDuration').value",
        "duration_days:document.getElementById('planDuration').value,\n"
        "    daily_profit_percent:document.getElementById('planDailyProfit').value"
    ),
    (
        "+' · Duration: '+x.duration_days+' days · '+(x.active?'Active':'Inactive');",
        "+' · Duration: '+x.duration_days+' days · Daily profit: '\n"
        "+Number(x.daily_profit_percent||0).toFixed(2)+'% · '\n"
        "+(x.active?'Active':'Inactive');"
    )
])

patch("app.py", [
    (
        'duration_days = int(data.get("duration_days", 0))',
        'duration_days = int(data.get("duration_days", 0))\n'
        '        daily_profit_percent = float(data.get("daily_profit_percent", 0))',
    ),
    (
        'return jsonify(error="Enter a valid price and duration."), 400',
        'return jsonify(error="Enter a valid price, duration and daily profit rate."), 400',
    ),
    (
        'if not 1 <= duration_days <= 36500:',
        'if not 0 <= daily_profit_percent <= 100000:\n'
        '        return jsonify(error="Daily profit rate must be between 0 and 100000%."), 400\n'
        '    if not 1 <= duration_days <= 36500:',
    ),
    (
        '(name, price_paisa, duration_days) VALUES (?, ?, ?)',
        '(name, price_paisa, duration_days, daily_profit_percent) VALUES (?, ?, ?, ?)',
    ),
    (
        '(name, price_paisa, duration_days)\n        )',
        '(name, price_paisa, duration_days, daily_profit_percent)\n        )',
    ),
    (
        'SET name=?, price_paisa=?, duration_days=?,\n'
        '                   updated_at=CURRENT_TIMESTAMP',
        'SET name=?, price_paisa=?, duration_days=?, daily_profit_percent=?,\n'
        '                   updated_at=CURRENT_TIMESTAMP',
    ),
    (
        '(name, price_paisa, duration_days, plan_id)',
        '(name, price_paisa, duration_days, daily_profit_percent, plan_id)',
    ),
    (
        'SELECT id, name, price_paisa, duration_days\n'
        '            FROM investment_plans',
        'SELECT id, name, price_paisa, duration_days, daily_profit_percent\n'
        '            FROM investment_plans',
    )
])

patch("index.html", [
    (
        "const duration = document.createElement('p');\n"
        "      duration.textContent = 'Duration: ' + plan.duration_days + ' days';",
        "const duration = document.createElement('p');\n"
        "      duration.textContent = 'Duration: ' + plan.duration_days + ' days';\n"
        "      const rate = document.createElement('p');\n"
        "      rate.textContent = 'Daily Profit: ' + Number(plan.daily_profit_percent || 0).toFixed(2) + '%';"
    ),
    (
        'card.append(title, price, duration, buy);',
        'card.append(title, price, duration, rate, buy);'
    )
])

print("Daily rate feature patch complete.")
