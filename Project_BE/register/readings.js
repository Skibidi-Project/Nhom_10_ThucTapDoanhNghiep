const token = sessionStorage.getItem('us05_access_token');
const $ = id => document.getElementById(id);
let rows = [], editing = null;
const notify = text => { $('notice').textContent = text; $('notice').className = 'notice show'; };
async function api(path, options = {}) {
    const response = await fetch('/api' + path, {...options, headers: {Authorization: `Bearer ${token}`, 'Content-Type': 'application/json'}});
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : `HTTP ${response.status}`);
    return data;
}
function reset() { editing = null; $('period').disabled = false; $('type').disabled = false; $('room').disabled = false; $('property').disabled = false; $('save').textContent = 'Lưu chỉ số'; $('cancel').hidden = true; }
function consumption() { const a=$('previous').value,b=$('current').value; $('consumption').textContent='Tiêu thụ: '+(a!=='' && b!=='' && Number(b)>=Number(a) ? Number(b)-Number(a) : '—'); }
function suggestPrevious() {
    if (editing) return;
    const prior=rows.filter(r=>r.utility_type===$('type').value && r.period<$('period').value).sort((a,b)=>b.period.localeCompare(a.period))[0];
    $('previous').value=prior ? prior.current_reading : '';
    consumption();
}
async function load() {
    $('history').replaceChildren(); if (!$('room').value) return;
    rows = await api(`/rooms/${$('room').value}/readings`);
    suggestPrevious();
    for (const r of rows) {
        if (!['electricity','water'].includes(r.utility_type)) continue;
        const tr=document.createElement('tr');
        for (const value of [r.period,r.utility_type === 'electricity' ? 'Điện' : r.utility_type === 'water' ? 'Nước' : r.utility_type,r.previous_reading,r.current_reading]) { const td=document.createElement('td');td.textContent=value;tr.append(td); }
        const td=document.createElement('td'), button=document.createElement('button'); button.type='button';button.className='room-action';button.textContent='Sửa';
        button.onclick=async()=>{try { const v=await api(`/rooms/${r.room_id}/readings/${r.id}/version`);editing={...r,version:v.version};$('period').value=r.period;$('type').value=r.utility_type;$('previous').value=r.previous_reading;$('current').value=r.current_reading;for(const id of ['period','type','room','property'])$(id).disabled=true;$('save').textContent='Cập nhật';$('cancel').hidden=false;consumption();}catch(e){notify(e.message);}};
        td.append(button);tr.append(td);$('history').append(tr);
    }
}
async function loadRooms(preferred) { $('room').replaceChildren(new Option('Chọn phòng','')); if (!$('property').value) return; for(const r of await api(`/properties/${$('property').value}/rooms`)) $('room').add(new Option(r.room_number,r.id));if(preferred)$('room').value=preferred;await load(); }
$('readingForm').onsubmit=async e=>{e.preventDefault();if(!$('room').value||!$('period').value){notify('Chọn phòng và kỳ ghi.');return;}const previous=Number($('previous').value),current=Number($('current').value);if(current<previous){notify('Chỉ số mới phải lớn hơn hoặc bằng chỉ số cũ.');return;}$('save').disabled=true;try {const url=editing?`/rooms/${editing.room_id}/readings/${editing.id}`:`/rooms/${$('room').value}/readings`;const body=editing?{previous_reading:previous,current_reading:current,expected_version:editing.version}:{utility_type:$('type').value,period:$('period').value,previous_reading:previous,current_reading:current};await api(url,{method:editing?'PUT':'POST',body:JSON.stringify(body)});reset();await load();notify('Đã lưu chỉ số.');}catch(error){notify(error.message);}finally{$('save').disabled=false;}};
$('property').onchange=()=>loadRooms().catch(e=>notify(e.message));$('room').onchange=()=>load().catch(e=>notify(e.message));$('period').onchange=suggestPrevious;$('type').onchange=suggestPrevious;$('cancel').onclick=()=>{reset();suggestPrevious();};$('previous').oninput=consumption;$('current').oninput=consumption;
(async()=>{if(!token){location.href='login.html';return;}$('period').value=new Date().toLocaleDateString('en-CA').slice(0,7);const properties=await api('/properties');$('property').add(new Option('Chọn khu trọ',''));for(const p of properties)$('property').add(new Option(p.name,p.id));const selected=new URLSearchParams(location.search).get('room_id');if(selected){const room=await api(`/rooms/${encodeURIComponent(selected)}`);$('property').value=room.property_id;await loadRooms(selected);}})().catch(e=>notify(e.message));
