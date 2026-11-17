// Real Edge + real localhost FastAPI. No API mocks or dependency bypasses.
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const BASE = 'http://127.0.0.1:8019';
const delay = ms => new Promise(resolve => setTimeout(resolve,ms));
const out = path.resolve(__dirname,'../.us19-demo');
const edge = spawn('C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',[
    '--headless=new','--disable-gpu','--no-first-run','--remote-debugging-port=9129',
    '--remote-allow-origins=http://127.0.0.1:9129',`--user-data-dir=${path.join(out,'browser-profile')}`,
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

const page=BASE+'/register/utility-readings.html?room_id=1';
const ready=`!document.getElementById('workspace').hidden && document.getElementById('loading').hidden`;
async function submit(period,previous,current,expected,kind='electricity') {
    await evaluate(`document.getElementById('notice').hidden=true;document.getElementById('kind').value=${JSON.stringify(kind)};document.getElementById('kind').dispatchEvent(new Event('change'));document.getElementById('period').value=${JSON.stringify(period)};document.getElementById('previous').value=${previous};document.getElementById('current').value=${current};document.getElementById('readingForm').noValidate=true;document.getElementById('readingForm').requestSubmit()`);
    await until(`!document.getElementById('notice').hidden && document.getElementById('loading').hidden`);
    if(expected===201)assert(await evaluate(`document.getElementById('notice').className !== 'error'`));
    else assert(await evaluate(`document.getElementById('notice').textContent.includes('HTTP ${expected}')`));
}
async function suggested() {
    return evaluate(`({period:document.getElementById('period').value,previous:Number(document.getElementById('previous').value)})`);
}
(async()=>{
    try {
        let target;
        for(let i=0;i<100;i++){
            try{target=(await (await fetch('http://127.0.0.1:9129/json')).json()).find(t=>t.type==='page');if(target)break;}catch{}
            await delay(100);
        }
        assert(target,'Headless Edge did not start');ws=new WebSocket(target.webSocketDebuggerUrl);
        await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
        ws.onmessage=e=>{const r=JSON.parse(e.data);if(r.id&&calls.has(r.id)){const c=calls.get(r.id);calls.delete(r.id);r.error?c.reject(new Error(r.error.message)):c.resolve(r.result);}};
        await send('Page.enable');
        await navigate(page,`!document.getElementById('notice').hidden`);
        assert(await evaluate(`document.getElementById('workspace').hidden`));console.log('PASS unauthenticated UI');
        await login('landlord@example.com');await navigate(page,ready);
        const before=await evaluate(`document.querySelectorAll('#rows tr').length`);
        let next=await suggested();
        await submit(next.period,next.previous,next.previous+135,201);
        assert.equal(await evaluate(`document.querySelectorAll('#rows tr').length`),before+1);
        assert(await evaluate(`document.getElementById('rows').textContent.includes('135 kWh')`));
        console.log('PASS valid electricity, persisted list and consumption');
        const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});fs.writeFileSync(path.join(out,'us19-desktop.png'),Buffer.from(shot.data,'base64'));
        const validRows=await evaluate(`document.querySelectorAll('#rows tr').length`);
        await submit('2026-02',1255,1390,409);console.log('PASS duplicate period rejected by backend');
        await submit('2025-12',1255,1390,409);console.log('PASS backdated period rejected by backend');
        next=await suggested();await submit(next.period,next.previous-1,next.previous+5,409);console.log('PASS broken continuity rejected by backend');
        await submit(next.period,-1,5,422);await submit(next.period,next.previous,next.previous-1,422);await submit('',0,1,422);
        assert.equal(await evaluate(`document.querySelectorAll('#rows tr').length`),validRows);
        console.log('PASS negative, decreasing and invalid month rejected without adding rows');
        await evaluate(`document.getElementById('kind').value='water';document.getElementById('kind').dispatchEvent(new Event('change'))`);
        let water=await suggested();await submit(water.period,water.previous,water.previous+12,201,'water');
        console.log('PASS independent water continuity');
        await navigate(BASE+'/register/utility-readings.html?room_id=3',ready);
        assert(await evaluate(`!document.getElementById('empty').hidden`));console.log('PASS empty state');
        await login('manager@example.com');await navigate(page,ready);next=await suggested();await submit(next.period,next.previous,next.previous+5,201);
        console.log('PASS assigned manager can record');
        for(const email of ['other@example.com','outsider@example.com','tenant@example.com','admin@example.com']){
            await login(email);await navigate(page,`!document.getElementById('notice').hidden && document.getElementById('notice').className==='error'`);
            assert(await evaluate(`!!sessionStorage.getItem('us05_access_token') && document.getElementById('workspace').hidden`));
            const status=await evaluate(`fetch('/api/rooms/1/readings',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+sessionStorage.getItem('us05_access_token')},body:JSON.stringify({utility_type:'electricity',period:'2099-12',previous_reading:0,current_reading:1})}).then(r=>r.status)`);
            assert.equal(status,403);
        }
        console.log('PASS unauthorized landlord/manager/tenant/admin GET and POST 403; session preserved');
        await evaluate(`sessionStorage.setItem('us05_access_token','invalid-test-token')`);
        await navigate(page,`!document.getElementById('notice').hidden`);
        await until(`!sessionStorage.getItem('us05_access_token')`);console.log('PASS invalid JWT returns to login state');
        await login('landlord@example.com');await navigate(page,ready);
        await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
        assert(await evaluate(`document.documentElement.scrollWidth<=innerWidth`));console.log('PASS mobile layout');
    }finally{if(ws?.readyState===1){await Promise.race([send('Browser.close').catch(()=>{}),delay(1500)]);ws.close();}edge.kill();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
