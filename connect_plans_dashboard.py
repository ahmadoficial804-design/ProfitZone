from pathlib import Path

p = Path("index.html")
s = p.read_text()

show_old = """  if (id === 'withdraw') loadWithdrawalAccount();
}"""
show_new = """  if (id === 'withdraw') loadWithdrawalAccount();
  if (id === 'plans') loadPlans();
}"""

if s.count(show_old) != 1:
    raise SystemExit("STOP: showPage marker mismatch; index.html unchanged.")

if "async function loadPlans()" in s:
    raise SystemExit("STOP: Plans JavaScript already exists; index.html unchanged.")

js = r"""
async function loadPlans() {
  const message = document.getElementById('plans-message');
  const list = document.getElementById('plans-list');
  const history = document.getElementById('my-plans-list');
  if (!message || !list || !history) return;

  message.textContent = 'Loading plans…';
  list.replaceChildren();
  history.textContent = 'Loading purchase history…';

  try {
    const response = await fetch('/api/plans', { credentials: 'same-origin' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Plans load nahi ho sake.');

    message.textContent = data.plans.length ? 'Available plans' : 'Abhi koi active plan available nahi hai.';
    for (const plan of data.plans) {
      const card = document.createElement('div');
      card.className = 'panel';

      const title = document.createElement('h3');
      title.textContent = plan.name;
      const price = document.createElement('p');
      price.textContent = 'Price: Rs. ' + (Number(plan.price_paisa) / 100).toFixed(2);
      const duration = document.createElement('p');
      duration.textContent = 'Duration: ' + plan.duration_days + ' days';
      const buy = document.createElement('button');
      buy.className = 'action';
      buy.textContent = 'Buy Plan';

      buy.addEventListener('click', async () => {
        if (!confirm('Buy "' + plan.name + '" for Rs. ' +
          (Number(plan.price_paisa) / 100).toFixed(2) + '?')) return;

        buy.disabled = true;
        message.textContent = 'Purchase request bheji ja rahi hai…';
        try {
          const key = (typeof crypto !== 'undefined' && crypto.randomUUID)
            ? crypto.randomUUID()
            : Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);

          const result = await fetch('/api/plans/' + encodeURIComponent(plan.id) + '/buy', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ idempotency_key: key })
          });
          const resultData = await result.json();
          if (!result.ok) throw new Error(resultData.error || 'Purchase complete nahi hui.');

          message.textContent = resultData.message || 'Plan purchase successful.';
          await loadWalletBalance();
          await loadPlans();
        } catch (error) {
          message.textContent = error.message;
        } finally {
          buy.disabled = false;
        }
      });

      card.append(title, price, duration, buy);
      list.append(card);
    }

    history.replaceChildren();
    if (!data.purchases.length) {
      history.textContent = 'Abhi koi plan purchase history nahi hai.';
    } else {
      for (const purchase of data.purchases) {
        const item = document.createElement('div');
        item.className = 'panel';
        const title = document.createElement('h3');
        title.textContent = purchase.plan_name;
        const details = document.createElement('p');
        details.textContent = 'Price: Rs. ' +
          (Number(purchase.price_paisa) / 100).toFixed(2) +
          ' · Duration: ' + purchase.duration_days + ' days · Status: ' + purchase.status;
        const dates = document.createElement('p');
        dates.textContent = 'Purchased: ' + purchase.purchased_at +
          ' · Expires: ' + purchase.expires_at;
        item.append(title, details, dates);
        history.append(item);
      }
    }
  } catch (error) {
    message.textContent = error.message;
    history.textContent = 'Purchase history load nahi ho saki.';
  }
}
"""

s = s.replace(show_old, show_new, 1)
s = s.replace("</script>", js + "\n</script>", 1)
p.write_text(s)
print("Plans dashboard JavaScript added.")
