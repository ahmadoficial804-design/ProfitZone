from pathlib import Path
import shutil

p = Path("admin.html")
s = p.read_text()
backup = Path("admin.html.pre-plans-ui")
marker = '<div class="card">\n<h2>Deposit Payment Settings</h2>'

if s.count(marker) != 1:
    raise SystemExit("STOP: expected HTML marker not found exactly once.")
if backup.exists():
    raise SystemExit("STOP: backup already exists.")
if 'id="planForm"' in s:
    raise SystemExit("STOP: Plans form appears to exist already.")

card = """
<div class="card">
<h2>Investment Plans</h2>
<form id="planForm">
<label>Plan name</label>
<input id="planName" required maxlength="100" style="display:block;width:100%;padding:10px;margin:8px 0;box-sizing:border-box">
<label>Price (PKR)</label>
<input id="planPrice" type="number" min="0.01" max="1000000" step="0.01" required style="display:block;width:100%;padding:10px;margin:8px 0;box-sizing:border-box">
<label>Duration (days)</label>
<input id="planDuration" type="number" min="1" max="36500" step="1" required style="display:block;width:100%;padding:10px;margin:8px 0;box-sizing:border-box">
<input id="planId" type="hidden">
<button id="planSaveButton" type="submit">Add Plan</button>
<button id="planCancelButton" type="button" hidden>Cancel Edit</button>
</form>
<p id="planMessage"></p>
<div id="plansList">Loading plans…</div>
</div>
"""

shutil.copy2(p, backup)
p.write_text(s.replace(marker, card + "\n" + marker, 1))
print("Plans form added. Backup:", backup)
