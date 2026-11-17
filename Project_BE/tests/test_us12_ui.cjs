// Real Edge + real localhost FastAPI. No API mocks or dependency bypasses.
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const BASE = 'http://127.0.0.1:8012';
const delay = ms => new Promise(resolve => setTimeout(resolve,ms));
const out = path.resolve(__dirname,'../.us12-demo');
const edge = spawn('C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',[
    '--headless=new','--disable-gpu','--no-first-run','--remote-debugging-port=9124',
    '--remote-allow-origins=http://127.0.0.1:9124',`--user-data-dir=${path.join(out,'browser-profile')}`,
    '--window-size=1440,1100','about:blank'
],{windowsHide:true,stdio:'ignore'});
let ws, seq=0; const calls=new Map();
function send(method,params={}) {
    return new Promise((resolve,reject)=>{
        const id=++seq; calls.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));
    });
}
async function evaluate(expression) {
    const result=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});
    if(result.exceptionDetails) throw new Error(result.exceptionDetails.text+' '+(result.exceptionDetails.exception?.description||''));
    return result.result.value;
}
async function until(expression) {
    for(let i=0;i<400;i++){if(await evaluate(expression))return;await delay(50);}
    throw new Error('UI condition timed out: '+expression);
}
async function navigate(url,condition) {
    await send('Page.navigate',{url});
    await until(`location.href === ${JSON.stringify(url)} && document.readyState === 'complete'`);
    if(condition)await until(condition);
}
async function login(email) {
    await navigate(BASE+'/register/login.html',`!!document.getElementById('loginBtn')`);
    const status = await evaluate(`(async () => {
        sessionStorage.removeItem('us05_access_token');
        const response = await fetch('/api/auth/login', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({identifier: ${JSON.stringify(email)}, password: 'DemoOnly!2026'})
        });
        const data = await response.json();
        if (response.ok) sessionStorage.setItem('us05_access_token', data.access_token);
        return response.status;
    })()`);
    assert.equal(status, 200, 'Existing login API must authenticate the demo account');
}
const page=BASE+'/register/contract-members.html?contract_id=1';
const ready=`!document.getElementById('workspace').hidden && document.getElementById('loading').hidden`;
async function add(id){
    await evaluate(`document.getElementById('tenantId').value='${id}';document.getElementById('tenantId').dispatchEvent(new Event('change'));document.getElementById('memberForm').requestSubmit()`);
    await until(`document.getElementById('notice').textContent.includes('Đã thêm') && document.getElementById('loading').hidden`);
}
async function remove(id){
    await evaluate(`Array.from(document.querySelectorAll('.person')).find(e=>e.textContent.includes('#${id}')).querySelector('button').click()`);
    await until(`document.getElementById('removeDialog').open`);
    await evaluate(`document.getElementById('confirmRemove').click()`);
    await until(`document.getElementById('notice').textContent.includes('Đã xóa') && document.getElementById('loading').hidden`);
}
(async()=>{
    try {
        let target;
        for(let i=0;i<100;i++){
            try{target=(await(await fetch('http://127.0.0.1:9124/json/list')).json()).find(t=>t.type==='page');if(target)break;}catch{}
            await delay(100);
        }
        assert(target,'Headless Edge did not start');
        ws=new WebSocket(target.webSocketDebuggerUrl);
        await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
        ws.onmessage=e=>{const r=JSON.parse(e.data);if(r.id&&calls.has(r.id)){const c=calls.get(r.id);calls.delete(r.id);r.error?c.reject(new Error(r.error.message)):c.resolve(r.result);}};
        await send('Page.enable');
        await navigate(page,`document.getElementById('notice').textContent.includes('Vui lòng đăng nhập')`);
        console.log('PASS unauthenticated UI');
        await login('landlord@example.com');await navigate(page,ready);
        assert(await evaluate(`document.getElementById('workspace').textContent.includes('Nguyễn Minh An')`));
        assert.equal(await evaluate(`document.querySelector('#workspace .person button')?.textContent`),'Xóa');
        assert.equal(await evaluate(`Array.from(document.querySelectorAll('.person')).find(e=>e.textContent.includes('#1')).querySelector('button')===null`),true);
        await add(3);
        console.log('PASS landlord add via real API');
        const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});
        fs.writeFileSync(path.join(out,'us12-desktop.png'),Buffer.from(shot.data,'base64'));
        await evaluate(`Array.from(document.querySelectorAll('.person')).find(e=>e.textContent.includes('#3')).querySelector('button').click();document.getElementById('cancelRemove').click()`);
        assert(await evaluate(`document.getElementById('workspace').textContent.includes('#3')`));
        await remove(3); console.log('PASS cancel and confirm removal');
        await remove(2);assert.equal(await evaluate(`document.querySelectorAll('.person').length`),1);
        assert(await evaluate(`document.querySelector('.empty')!==null`));
        await add(2);console.log('PASS empty state and restore initial member');
        await navigate(BASE+'/register/contract-members.html?contract_id=2',ready);
        assert(await evaluate(`document.getElementById('addBtn').disabled && document.querySelectorAll('.remove').length===0`));
        console.log('PASS expired contract is read-only');
        await login('manager@example.com');await navigate(page,ready);await add(3);await remove(3);
        console.log('PASS assigned manager add/remove');
        for(const email of ['other@example.com','outsider@example.com','tenant@example.com']){
            await login(email);await navigate(page,`document.getElementById('notice').textContent.includes('không có quyền')`);
            assert(await evaluate(`!!sessionStorage.getItem('us05_access_token') && document.getElementById('workspace').hidden`));
        }
        console.log('PASS 403 preserves session for wrong landlord/manager/tenant');
        await evaluate(`sessionStorage.setItem('us05_access_token','invalid-test-token')`);
        await navigate(page,`document.getElementById('notice').textContent.includes('Phiên không hợp lệ')`);
        assert(await evaluate(`!sessionStorage.getItem('us05_access_token')`));
        console.log('PASS 401 requests login');
        await login('landlord@example.com');await navigate(page,ready);
        await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
        assert(await evaluate(`document.documentElement.scrollWidth <= innerWidth`));
        const mobile=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});fs.writeFileSync(path.join(out,'us12-mobile.png'),Buffer.from(mobile.data,'base64'));
        console.log('PASS mobile layout; screenshots saved in .us12-demo');
    } finally {
        if(ws?.readyState===1){await Promise.race([send('Browser.close').catch(()=>{}),delay(1500)]);ws.close();}
        edge.kill();
    }
})().catch(e=>{console.error(e.message);process.exitCode=1;});
