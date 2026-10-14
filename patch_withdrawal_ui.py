from pathlib import Path
import shutil

p = Path("index.html")
s = p.read_text()

old_section = '''<section id="withdraw" class="page hidden">
<div class="panel">
<h2>Withdraw</h2>
<p>Real withdrawals are not enabled in this demo.</p>
<label>Amount (PKR)</label>
<input type="number" min="1" placeholder="Enter amount">
<label>Payment Method</label>
<select><option>Choose method</option><option>JazzCash</option><option>Easypaisa</option></select>
<label>Account number</label>
<input type="tel" placeholder="03XXXXXXXXX">
<button class="action" onclick="demoMessage()">Submit Demo Request</button>
<p id="withdraw-msg" class="note"></p>
</div>
</section>'''

new_section = '''<section id="withdraw" class="page hidden">
<div class="panel">
<h2>Withdrawal Account</h2>
<p>Your first saved account cannot be changed. Each account number can belong to one user only.</p>

<div id="withdraw-account-loading">Loading account details…</div>

<form id="withdraw-account-form" class="hidden">
<label>Account holder name</label>
<input id="withdraw-account-name" maxlength="100" required
       autocomplete="name" placeholder="Name registered with wallet">
<label>Payment method</label>
<select id="withdraw-account-method" required>
<option value="">Choose method</option>
<option value="JazzCash">JazzCash</option>
<option value="Easypaisa">Easypaisa</option>
</select>
<label>Account number</label>
<input id="withdraw-account-number" type="tel" maxlength="40"
       required autocomplete="tel" placeholder="Enter wallet number">
<button class="action" type="submit">Save Account Permanently</button>
</form>

<div id="withdraw-account-saved" class="hidden"></div>
<p id="withdraw-account-msg" class="note"></p>
</div>

<div id="withdraw-request-panel" class="panel hidden">
<h2>Withdrawal Request</h2>
<p>Request submission does not itself transfer money or deduct your balance.</p>
<form id="withdraw-request-form">
<label>Amount (PKR)</label>
<input id="withdraw-amount" type="number" min="1" max="1000000"
       step="1" required placeholder="Enter amount">
<label>Reference (optional)</label>
<input id="withdraw-reference" maxlength="120"
       placeholder="Optional note for admin">
<button class="action" type="submit">Submit Withdrawal Request</button>
</form>
<p id="withdraw-msg" class="note"></p>
</div>
</section>'''

if s.count(old_section) != 1:
    raise SystemExit("STOP: Withdrawal HTML did not match; no changes made.")

old_show = '''  window.scrollTo(0, 0);
}'''
new_show = '''  window.scrollTo(0, 0);
  if (id === 'withdraw') loadWithdrawalAccount();
}'''
if s.count(old_show) != 1:
    raise SystemExit("STOP: showPage insertion point not unique; no changes made.")

js_marker = "async function loadWalletBalance() {"
withdraw_js = r'''
async function loadWithdrawalAccount() {
  const loading = document.getElementById('withdraw-account-loading');
  const form = document.getElementById('withdraw-account-form');
  const saved = document.getElementById('withdraw-account-saved');
  const requestPanel = document.getElementById('withdraw-request-panel');
  const msg = document.getElementById('withdraw-account-msg');

  if (!loading || !form || !saved || !requestPanel) return;

  loading.classList.remove('hidden');
  loading.textContent = 'Loading account details…';
  form.classList.add('hidden');
  saved.classList.add('hidden');
  requestPanel.classList.add('hidden');
  msg.textContent = '';

  try {
    const r = await fetch('/api/withdrawal-account', {
      credentials: 'same-origin'
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || 'Could not load account.');

    loading.classList.add('hidden');

    if (data.account) {
      const a = data.account;
      saved.replaceChildren();
      [
        ['Account holder', a.account_name],
        ['Payment method', a.method],
        ['Account number', a.account_number],
        ['Saved on', a.created_at]
      ].forEach(([label, value]) => {
        const row = document.createElement('p');
        const strong = document.createElement('strong');
        strong.textContent = label + ': ';
        row.append(strong, document.createTextNode(value || '—'));
        saved.append(row);
      });

      const lockNote = document.createElement('p');
      lockNote.textContent = 'This account is locked and cannot be changed.';
      saved.append(lockNote);
      saved.classList.remove('hidden');
      requestPanel.classList.remove('hidden');
    } else {
      form.classList.remove('hidden');
      loading.textContent = '';
    }
  } catch (e) {
    loading.textContent = e.message;
  }
}

const withdrawalAccountForm = document.getElementById('withdraw-account-form');
if (withdrawalAccountForm) {
  withdrawalAccountForm.addEventListener('submit', async e => {
    e.preventDefault();
    const msg = document.getElementById('withdraw-account-msg');
    const button = withdrawalAccountForm.querySelector('button[type="submit"]');
    button.disabled = true;
    msg.textContent = 'Saving account…';

    try {
      const r = await fetch('/api/withdrawal-account', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          account_name: document.getElementById('withdraw-account-name').value,
          method: document.getElementById('withdraw-account-method').value,
          account_number: document.getElementById('withdraw-account-number').value
        })
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || 'Could not save account.');
      msg.textContent = data.message || 'Account saved.';
      withdrawalAccountForm.reset();
      await loadWithdrawalAccount();
    } catch (err) {
      msg.textContent = err.message;
    } finally {
      button.disabled = false;
    }
  });
}

const withdrawalRequestForm = document.getElementById('withdraw-request-form');
if (withdrawalRequestForm) {
  withdrawalRequestForm.addEventListener('submit', async e => {
    e.preventDefault();
    const msg = document.getElementById('withdraw-msg');
    const button = withdrawalRequestForm.querySelector('button[type="submit"]');
    button.disabled = true;
    msg.textContent = 'Submitting request…';

    try {
      const r = await fetch('/api/payment-requests', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          type: 'withdraw',
          amount: document.getElementById('withdraw-amount').value,
          reference: document.getElementById('withdraw-reference').value
        })
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || 'Request failed.');
      msg.textContent = data.message || 'Request submitted for admin review.';
      withdrawalRequestForm.reset();
    } catch (err) {
      msg.textContent = err.message;
    } finally {
      button.disabled = false;
    }
  });
}

'''

if s.count(js_marker) != 1:
    raise SystemExit("STOP: JavaScript insertion point not unique; no changes made.")

shutil.copy2(p, "index.html.before-withdrawal-ui")
s = s.replace(old_section, new_section, 1)
s = s.replace(old_show, new_show, 1)
s = s.replace(js_marker, withdraw_js + js_marker, 1)
p.write_text(s)
print("OK: Withdrawal UI patched.")
print("Backup: index.html.before-withdrawal-ui")
