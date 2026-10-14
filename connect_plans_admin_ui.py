from pathlib import Path
import shutil

p = Path("admin.html")
s = p.read_text()
backup = Path("admin.html.pre-plans-js")
marker = "function renderAvailableTasks(tasks){"

if s.count(marker) != 1:
    raise SystemExit("STOP: JavaScript marker mismatch.")
if backup.exists():
    raise SystemExit("STOP: backup already exists.")
if "async function loadPlans()" in s:
    raise SystemExit("STOP: Plans JavaScript already exists.")

js = r'''
function resetPlanForm(){
  document.getElementById('planForm').reset();
  document.getElementById('planId').value='';
  document.getElementById('planSaveButton').textContent='Add Plan';
  document.getElementById('planCancelButton').hidden=true;
}
document.getElementById('planCancelButton').addEventListener('click',resetPlanForm);

async function loadPlans(){
  const box=document.getElementById('plansList');
  try{
    const d=await api('/api/admin/plans');
    box.replaceChildren();
    (d.plans||[]).forEach(x=>{
      const card=document.createElement('div');
      card.className='card';
      const title=document.createElement('h3');
      title.textContent=x.name;
      const meta=document.createElement('p');
      meta.textContent='Price: Rs. '+(Number(x.price_paisa)/100).toFixed(2)
        +' · Duration: '+x.duration_days+' days · '+(x.active?'Active':'Inactive');
      const edit=document.createElement('button');
      edit.textContent='Edit';
      edit.onclick=()=>{
        document.getElementById('planId').value=x.id;
        document.getElementById('planName').value=x.name;
        document.getElementById('planPrice').value=(Number(x.price_paisa)/100).toFixed(2);
        document.getElementById('planDuration').value=x.duration_days;
        document.getElementById('planSaveButton').textContent='Save Changes';
        document.getElementById('planCancelButton').hidden=false;
        document.getElementById('planMessage').textContent='Editing plan #'+x.id;
        document.getElementById('planForm').scrollIntoView({behavior:'smooth',block:'center'});
      };
      const toggle=document.createElement('button');
      toggle.textContent=x.active?'Deactivate':'Activate';
      toggle.onclick=async()=>{
        try{
          await api('/api/admin/plans/'+x.id+'/toggle',{method:'POST',body:'{}'});
          await loadPlans();
        }catch(e){alert(e.message);}
      };
      card.append(title,meta,edit,document.createTextNode(' '),toggle);
      box.append(card);
    });
    if(!(d.plans||[]).length) box.textContent='No plans yet.';
  }catch(e){box.textContent='Could not load plans: '+e.message;}
}

document.getElementById('planForm').addEventListener('submit',async e=>{
  e.preventDefault();
  const msg=document.getElementById('planMessage');
  msg.textContent='Saving...';
  const id=document.getElementById('planId').value;
  const payload={
    name:document.getElementById('planName').value.trim(),
    price:document.getElementById('planPrice').value,
    duration_days:document.getElementById('planDuration').value
  };
  try{
    await api(id?'/api/admin/plans/'+id:'/api/admin/plans',{
      method:'POST',body:JSON.stringify(payload)
    });
    resetPlanForm();
    msg.textContent=id?'Plan updated.':'Plan added.';
    await loadPlans();
  }catch(err){msg.textContent=err.message;}
});
'''

shutil.copy2(p, backup)
s = s.replace(marker, js + "\n" + marker, 1)

# Add plan loading to the existing loadAll() without replacing other work.
old = "async function loadAll(){"
if s.count(old) != 1:
    raise SystemExit("STOP: loadAll marker mismatch.")
s = s.replace(old, old + "\n  loadPlans();", 1)

p.write_text(s)
print("Plans UI JavaScript connected. Backup:", backup)
