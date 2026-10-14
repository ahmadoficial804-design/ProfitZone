from pathlib import Path
import shutil

p = Path("index.html")
s = p.read_text()
backup = Path("index.html.pre-plans")
marker = '<section id="deposit" class="page hidden">'

if s.count(marker) != 1:
    raise SystemExit("STOP: deposit section marker mismatch.")
if 'id="plans"' in s:
    raise SystemExit("STOP: Plans section already exists.")

section = """
<section id="plans" class="page hidden">
  <div class="panel">
    <h2>Investment Plans</h2>
    <p>Choose an active plan. Your wallet balance will be checked before purchase.</p>
    <div id="plans-message" role="status">Loading plans…</div>
    <div id="plans-list"></div>
  </div>
  <div class="panel">
    <h2>My Plan Purchases</h2>
    <div id="my-plans-list">Loading purchase history…</div>
  </div>
</section>

"""

nav_old = """<button class="nav-btn" data-page="tasks" onclick="window.location.href='/tasks'"><span class="ico">☷</span>Tasks</button>"""
nav_new = """<button class="nav-btn" data-page="plans" onclick="showPage('plans')"><span class="ico">▣</span>Plans</button>"""

nav_new = """<button class="nav-btn" data-page="plans" onclick="showPage('plans')"><span class="ico">▣</span>Plans</button>"""

if s.count(nav_old) != 1:
    raise SystemExit("STOP: Tasks navigation marker mismatch.")

shutil.copy2(p, backup)
s = s.replace(marker, section + marker, 1)
s = s.replace(nav_old, nav_new, 1)
p.write_text(s)
print("Dashboard Plans section added; Tasks page and Explore Tasks link retained.")
print("Backup:", backup)
