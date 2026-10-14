
function showPage(id){
  const target = document.getElementById(id);
  if (!target) {
    console.error('Page not found:', id);
    return;
  }
  document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'));
  target.classList.remove('hidden');
  document.querySelectorAll('.nav-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.page === id);
  });
  window.scrollTo(0, 0);
}
function demoMessage(){
const page=document.querySelector('.page:not(.hidden)');
const msg=page.querySelector('[id$="-msg"]');
if(msg)msg.textContent='Demo only: request was not sent or saved.';
}
function showExtra(type){
const box=document.getElementById('extra');
box.classList.remove('hidden');
const content={
referrals:'<h3>Referrals</h3><p>Your referral code and rewards will appear here after setup.</p>',
transactions:'<h3>Transactions</h3><p>No transactions recorded in this demo.</p>',
support:'<h3>Customer Support</h3><p>Support tickets are not connected yet.</p><textarea placeholder="Write your question"></textarea><button class="action" onclick="alert(\\'Demo only: message not sent.\\')">Send Demo Message</button>'
};
box.innerHTML=content[type];
}
async function loadWalletBalance() {
  try {
    const response = await fetch('/api/wallet');
    if (response.status === 401) return;
    if (!response.ok) throw new Error('Wallet load failed');

    const data = await response.json();
    const amount = document.querySelector('.balance .amount');

    if (amount) {
      amount.textContent = 'Rs. ' +
        (Number(data.balance_paisa || 0) / 100).toFixed(2);
    }
  } catch (error) {
    console.error('Wallet balance load nahi hua:', error);
  }
}

loadWalletBalance();
