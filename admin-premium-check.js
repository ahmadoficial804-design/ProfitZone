async function adminLogout(){
  try {
    await fetch('/api/admin/logout', {
      method:'POST', credentials:'same-origin'
    });
  } finally {
    location.href='/admin/login';
  }
}

async function api(url, options={}) {
  const r=await fetch(url,{credentials:'same-origin',...options,
    headers:{'Content-Type':'application/json',...(options.headers||{})}});
  const raw=await r.text();
  let d;
  try { d=JSON.parse(raw); }
  catch { throw Error('API '+url+' returned HTTP '+r.status+
    ' ('+(r.headers.get('content-type')||'unknown content type')+'): '+
    raw.slice(0,160)); }
  if(!r.ok) throw Error(d.error||('HTTP '+r.status));
  return d;
}
function el(id, text){document.getElementById(id).textContent=text;}
function cardText(x){return JSON.stringify(x,null,2);}

async function loadPaymentSettings(){
  try{
    const d = await api('/api/admin/payment-settings');
    const x = d.settings || {};
    document.getElementById('payMethod').value =
      x.method === 'Easypaisa' ? 'Easypaisa' : 'JazzCash';
    document.getElementById('payName').value = x.account_name || '';
    document.getElementById('payNumber').value = x.account_number || '';
    document.getElementById('payInstructions').value = x.instructions || '';
    el('paymentSettingsMessage', x.enabled ? 'Payment details are enabled.' : 'No active payment details.');
  }catch(e){
    el('paymentSettingsMessage', e.message);
  }
}
document.getElementById('paymentSettingsForm').addEventListener('submit', async e=>{
  e.preventDefault();
  try{
    await api('/api/admin/payment-settings', {
      method:'POST',
      body:JSON.stringify({
        method:document.getElementById('payMethod').value,
        account_name:document.getElementById('payName').value,
        account_number:document.getElementById('payNumber').value,
        instructions:document.getElementById('payInstructions').value
      })
    });
    el('paymentSettingsMessage','Payment settings saved successfully.');
  }catch(err){
    el('paymentSettingsMessage',err.message);
  }
});
document.getElementById('clearPaymentSettings').addEventListener('click', async ()=>{
  if(!confirm('Hide and clear the current payment details?')) return;
  try{
    await api('/api/admin/payment-settings',{method:'DELETE'});
    document.getElementById('paymentSettingsForm').reset();
    el('paymentSettingsMessage','Payment details cleared.');
  }catch(err){
    el('paymentSettingsMessage',err.message);
  }
});

async function loadAll(){
  loadPaymentSettings();
  try{
    const [u,p,t,a]=await Promise.all([
      api('/api/admin/users'),api('/api/admin/payments'),
      api('/api/admin/tasks'),api('/api/admin/available-tasks')
    ]);
    renderAvailableTasks(a.tasks||[]);
    const ud=document.getElementById('users');
    ud.replaceChildren();
    (u.users||[]).forEach(x=>{
      const tr=document.createElement('tr');
      [
        x.id, x.username, x.email, x.phone,
        'Rs. '+((Number(x.balance_paisa)||0)/100).toFixed(2),
        x.created_at
      ].forEach(value=>{
        const td=document.createElement('td');
        td.style.padding='10px';
        td.style.borderBottom='1px solid #ddd';
        td.textContent=value ?? '—';
        tr.append(td);
      });
      ud.append(tr);
    });
    if(!(u.users||[]).length){
      const tr=document.createElement('tr');
      const td=document.createElement('td');
      td.colSpan=6;
      td.textContent='No users found.';
      tr.append(td);
      ud.append(tr);
    }
    const deposits=document.getElementById('deposits');
    const withdrawals=document.getElementById('withdrawals');
    deposits.replaceChildren();
    withdrawals.replaceChildren();

    (p.requests||[]).forEach(x=>{
      const isWithdrawal=x.request_type === 'withdraw';
      const target=isWithdrawal ? withdrawals : deposits;
      const tr=document.createElement('tr');

      const addCell=(value)=>{
        const td=document.createElement('td');
        td.style.padding='10px';
        td.style.borderBottom='1px solid #ddd';
        td.textContent=value ?? '—';
        tr.append(td);
        return td;
      };

      addCell(x.id);
      addCell((x.username || ('User '+x.user_id))+' (#'+x.user_id+')');
      addCell('Rs. '+((Number(x.amount_paisa)||0)/100).toFixed(2));
      addCell(x.method || '—');

      if(isWithdrawal){
        addCell(x.withdrawal_account_name
          ? x.withdrawal_account_name+' / '+(x.withdrawal_account_number||'')
          : (x.reference || '—'));
      } else {
        addCell(x.reference || '—');
      }

      const actionCell=document.createElement('td');
      actionCell.style.padding='10px';
      actionCell.style.borderBottom='1px solid #ddd';

      const status=document.createElement('p');
      status.textContent='Status: '+(x.status || '—');
      actionCell.append(status);

      const updateStatus=async(newStatus,label)=>{
        if(!confirm('Change status to '+label+'?')) return;
        try{
          await api('/api/admin/payments/'+x.id,{
            method:'POST',
            body:JSON.stringify({status:newStatus})
          });
          await loadAll();
        }catch(e){alert(e.message)}
      };

      if(isWithdrawal){
        if(!['completed','approved','rejected'].includes(x.status)){
          [
            ['pending','Pending'],
            ['in_progress','In Progress'],
            ['completed','Completed'],
            ['rejected','Rejected']
          ].forEach(([value,label])=>{
            const b=document.createElement('button');
            b.textContent=label;
            b.style.margin='4px';
            b.onclick=()=>updateStatus(value,label);
            actionCell.append(b);
          });
        }
      } else if(x.status === 'pending'){
        [['approved','Approve'],['rejected','Reject']].forEach(([value,label])=>{
          const b=document.createElement('button');
          b.textContent=label;
          b.style.margin='4px';
          b.onclick=()=>updateStatus(value,label);
          actionCell.append(b);
        });
      }
      tr.append(actionCell);

      const receiptCell=document.createElement('td');
      receiptCell.style.padding='10px';
      receiptCell.style.borderBottom='1px solid #ddd';
      if(x.screenshot_filename){
        const image=document.createElement('img');
        image.src='/api/admin/payment-receipts/'+encodeURIComponent(x.screenshot_filename);
        image.alt='Payment receipt';
        image.loading='lazy';
        image.style.maxWidth='180px';
        image.style.maxHeight='180px';
        image.style.objectFit='contain';
        image.onerror=()=>{image.alt='Receipt preview unavailable';};
        receiptCell.append(image);
      } else {
        receiptCell.textContent='No receipt image';
      }
      tr.append(receiptCell);
      target.append(tr);
    });

    if(!deposits.children.length){
      deposits.innerHTML='<tr><td colspan="7">No deposits found.</td></tr>';
    }
    if(!withdrawals.children.length){
      withdrawals.innerHTML='<tr><td colspan="7">No withdrawals found.</td></tr>';
    }
    const td=document.getElementById('tasks');
    td.replaceChildren();
    (t.tasks||[]).forEach(x=>{
      const tr=document.createElement('tr');
      const values=[
        x.username || ('User '+x.user_id),
        x.title || x.task_key,
        x.created_at || '—',
        x.status || '—'
      ];
      values.forEach(value=>{
        const cell=document.createElement('td');
        cell.style.padding='10px';
        cell.style.borderBottom='1px solid #ddd';
        cell.textContent=value;
        tr.append(cell);
      });
      const action=document.createElement('td');
      action.style.padding='10px';
      action.style.borderBottom='1px solid #ddd';
      if(x.status==='pending'){
        for(const status of ['approved','rejected']){
          const b=document.createElement('button');
          b.textContent=status==='approved'?'Approve':'Reject';
          b.onclick=async()=>{
            try{
              await api('/api/admin/tasks/'+x.id,{
                method:'POST',
                body:JSON.stringify({status})
              });
              await loadAll();
            }catch(e){alert(e.message)}
          };
          action.append(b,document.createTextNode(' '));
        }
      }else{
        action.textContent='—';
      }
      tr.append(action);
      td.append(tr);
    });
  }catch(e){alert(e.message)}
}

function renderAvailableTasks(tasks){
  const box=document.getElementById('availableTasks');
  box.replaceChildren();
  tasks.forEach(x=>{
    const d=document.createElement('div');d.className='card';
    const h=document.createElement('h3');h.textContent=x.title;d.append(h);
    const p=document.createElement('p');p.textContent=x.description;d.append(p);
    const meta=document.createElement('p');
    meta.textContent='Key: '+x.task_key+' · Reward: Rs. '+(Number(x.reward_paisa||0)/100).toFixed(2)+' · '+(x.active?'Active':'Inactive');
    d.append(meta);
    const b=document.createElement('button');b.textContent=x.active?'Deactivate':'Activate';
    b.onclick=async()=>{try{await api('/api/admin/available-tasks/'+encodeURIComponent(x.task_key)+'/toggle',{method:'POST',body:'{}'});await loadAll()}catch(e){alert(e.message)}};
    d.append(b);box.append(d);
  });
  if(!tasks.length) box.textContent='No tasks yet.';
}
document.getElementById('taskForm').addEventListener('submit',async e=>{
  e.preventDefault();
  const msg=document.getElementById('taskFormMessage');
  msg.textContent='Saving...';
  try{
    await api('/api/admin/available-tasks',{method:'POST',body:JSON.stringify({
      task_key:document.getElementById('taskKey').value.trim(),
      title:document.getElementById('taskTitle').value.trim(),
      description:document.getElementById('taskDescription').value.trim(),
      reward:document.getElementById('taskReward').value
    })});
    e.target.reset();document.getElementById('taskReward').value='0';
    msg.textContent='Task added.';await loadAll();
  }catch(err){msg.textContent=err.message}
});

loadAll();
