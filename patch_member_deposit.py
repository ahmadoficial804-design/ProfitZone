from pathlib import Path

p = Path("index.html")
s = p.read_text()

start = s.find('<section id="deposit"')
end = s.find('</section>', start) + len('</section>')

if start < 0 or end < len('</section>'):
    raise SystemExit("Deposit section not found; index.html unchanged.")

section = """
<section id="deposit" class="page hidden">
<div class="panel">
<h2>Deposit Request</h2>
<div id="deposit-details" class="note">Loading payment details…</div>
<form id="deposit-form">
<label>Amount (PKR)</label>
<input id="deposit-amount" type="number" min="1" max="1000000"
step="0.01" required placeholder="Enter amount">
<label>Payment Method</label>
<select id="deposit-method" required>
<option value="">Choose method</option>
<option value="JazzCash">JazzCash</option>
<option value="Easypaisa">Easypaisa</option>
</select>
<label>Payment Reference / Transaction ID</label>
<input id="deposit-reference" maxlength="120" required
placeholder="Enter transaction reference">
<label>Receipt screenshot (JPG, PNG or WebP; max 5 MB)</label>
<input id="deposit-receipt" type="file"
accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" required>
<button class="action" type="submit">Submit Deposit Request</button>
</form>
<p id="deposit-msg" class="note"></p>
</div>
</section>
"""

s = s[:start] + section + s[end:]

js = r"""
async function loadDepositSettings(){
  const box = document.getElementById('deposit-details');
  const method = document.getElementById('deposit-method');
  if(!box || !method) return;
  try{
    const r = await fetch('/api/payment-settings', {credentials:'same-origin'});
    if(r.status === 401){
      box.textContent = 'Please log in to view payment details.';
      return;
    }
    const data = await r.json();
    const x = data.settings;
    if(!r.ok || !x){
      box.textContent = 'Payment details are not configured yet. Please contact the administrator.';
      method.disabled = true;
      return;
    }
    box.replaceChildren();
    [
      ['Payment Method', x.method],
      ['Account Name', x.account_name],
      ['Payment Number', x.account_number],
      ['Instructions', x.instructions || 'Follow the payment provider instructions.']
    ].forEach(([label,value])=>{
      const row = document.createElement('p');
      const strong = document.createElement('strong');
      strong.textContent = label + ': ';
      row.append(strong, document.createTextNode(value || '—'));
      box.append(row);
    });
    method.value = x.method;
    method.disabled = true;
  }catch(e){
    box.textContent = 'Could not load payment details. Please try again.';
  }
}

const depositForm = document.getElementById('deposit-form');
if(depositForm){
  depositForm.addEventListener('submit', async e=>{
    e.preventDefault();
    const msg = document.getElementById('deposit-msg');
    const file = document.getElementById('deposit-receipt').files[0];
    const method = document.getElementById('deposit-method').value;
    if(!file){ msg.textContent = 'Please attach your receipt screenshot.'; return; }
    if(file.size > 5 * 1024 * 1024){
      msg.textContent = 'Image must be 5 MB or smaller.'; return;
    }
    if(!['image/jpeg','image/png','image/webp'].includes(file.type)){
      msg.textContent = 'Use a JPG, PNG or WebP image.'; return;
    }
    const body = new FormData();
    body.append('type','deposit');
    body.append('amount',document.getElementById('deposit-amount').value);
    body.append('method',method);
    body.append('reference',document.getElementById('deposit-reference').value);
    body.append('receipt',file);
    msg.textContent = 'Submitting request…';
    try{
      const r = await fetch('/api/payment-requests',{
        method:'POST', credentials:'same-origin', body
      });
      const data = await r.json();
      if(!r.ok) throw new Error(data.error || 'Request failed');
      msg.textContent = data.message || 'Request submitted for admin review.';
      depositForm.reset();
      await loadDepositSettings();
    }catch(err){ msg.textContent = err.message; }
  });
}
"""

marker = "async function loadWalletBalance()"
if marker not in s:
    raise SystemExit("Wallet function not found; index.html unchanged.")

if "async function loadDepositSettings()" not in s:
    s = s.replace(marker, js + "\n" + marker, 1)

s = s.replace("loadWalletBalance();", "loadWalletBalance();\nloadDepositSettings();", 1)
p.write_text(s)
print("Member Deposit page updated.")
