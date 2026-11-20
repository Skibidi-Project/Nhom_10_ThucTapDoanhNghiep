const {spawn}=require('node:child_process'), crypto=require('node:crypto'), path=require('node:path'), os=require('node:os'), assert=require('node:assert/strict');
const port=19342, base='http://127.0.0.1:18342';
const chrome=spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',['--headless=new','--disable-gpu','--no-first-run','--disable-extensions','--remote-allow-origins=*',`--remote-debugging-port=${port}`,`--user-data-dir=${path.join(os.tmpdir(),'ministay-e2e-'+crypto.randomUUID())}`,'about:blank'],{windowsHide:true,stdio:'ignore'});
const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function wait(fn,label){for(let i=0;i<100;i++){try{const x=await fn();if(x)return x;}catch{}await delay(100)}throw Error('Timeout: '+label)}
async function main(){
 await wait(async()=>(await fetch(`http://127.0.0.1:${port}/json/version`)).ok,'browser');
 const target=await(await fetch(`http://127.0.0.1:${port}/json/new?about:blank`,{method:'PUT'})).json();const ws=new WebSocket(target.webSocketDebuggerUrl);await new Promise((ok,bad)=>{ws.onopen=ok;ws.onerror=bad});let id=0;const pending=new Map(),errors=[];
 ws.onmessage=e=>{const x=JSON.parse(e.data);if(x.id&&pending.has(x.id)){const [resolve,reject]=pending.get(x.id);pending.delete(x.id);x.error?reject(Error(x.error.message)):resolve(x.result)}else if(x.method==='Runtime.exceptionThrown')errors.push(x.params.exceptionDetails.text);else if(x.method==='Page.javascriptDialogOpening')send('Page.handleJavaScriptDialog',{accept:true});};
 function send(method,params={}){return new Promise((resolve,reject)=>{const n=++id;pending.set(n,[resolve,reject]);ws.send(JSON.stringify({id:n,method,params}));})}
 async function js(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.text);return r.result.value}
 async function go(url){await send('Page.navigate',{url});await wait(async()=>await js('location.href')===url && await js('document.readyState')==='complete','page '+url)}
 await send('Page.enable');await send('Runtime.enable');
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false});
 await go(base+'/register/login.html');await js(`identifier.value=${JSON.stringify(process.env.MINISTAY_E2E_EMAIL)};password.value=${JSON.stringify(process.env.MINISTAY_E2E_PASSWORD)};loginForm.requestSubmit()`);await wait(async()=>String(await js('location.pathname')).endsWith('properties.html'),'login');
 await go(base+'/register/rooms.html');await wait(async()=>await js("[...document.querySelectorAll('button')].some(x=>x.textContent==='Ghi chỉ số điện/nước')"),'room action');await js("[...document.querySelectorAll('button')].find(x=>x.textContent==='Ghi chỉ số điện/nước').click()");await wait(async()=>String(await js('location.pathname')).endsWith('readings.html'),'readings page');await wait(async()=>await js("document.getElementById('room').value!==''"),'selected room');
 await js("document.getElementById('previous').value='0';document.getElementById('current').value='5';document.getElementById('readingForm').requestSubmit()");await wait(async()=>await js("document.getElementById('history').textContent.includes('5')"),'saved');
 await js("document.querySelector('#history button').click()");await wait(async()=>await js("!document.getElementById('cancel').hidden"),'edit mode');await js("document.getElementById('current').value='7';document.getElementById('readingForm').requestSubmit()");await wait(async()=>await js("document.getElementById('history').textContent.includes('7') && document.getElementById('cancel').hidden"),'updated');
 await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await go(base+'/register/rooms.html');await wait(async()=>await js("[...document.querySelectorAll('button')].some(x=>x.textContent==='Ghi chỉ số điện/nước')"),'mobile action');
 await js("[...document.querySelectorAll('button')].find(x=>x.textContent==='Ghi chỉ số điện/nước').scrollIntoView({block:'center',inline:'center'})");
 assert(await js("(()=>{const r=[...document.querySelectorAll('button')].find(x=>x.textContent==='Ghi chỉ số điện/nước').getBoundingClientRect();return r.width>0&&r.left>=0&&r.right<=innerWidth})()"),'mobile room action outside viewport');
 await js("[...document.querySelectorAll('button')].find(x=>x.textContent==='Ghi chỉ số điện/nước').click()");await wait(async()=>String(await js('location.pathname')).endsWith('readings.html'),'mobile navigation');
 await go(base+'/register/invoices.html');await wait(async()=>await js("document.getElementById('contract').options.length>0"),'invoice contract');
 await js("document.getElementById('invoiceForm').requestSubmit()");await wait(async()=>await js("document.getElementById('notice').textContent.includes('Đã chốt hóa đơn')"),'invoice created');
 assert(await js("document.getElementById('invoices').textContent.includes('170')"),'invoice total must include 100 rent and 70 electricity');
 await js("document.getElementById('invoiceForm').requestSubmit()");await wait(async()=>await js("document.getElementById('notice').textContent.includes('đã tồn tại')"),'duplicate invoice rejected');
 await go(base+'/register/contracts.html');await wait(async()=>await js("[...document.querySelectorAll('button')].some(x=>x.textContent.includes('Chờ thanh lý'))"),'contract');await js("[...document.querySelectorAll('button')].find(x=>x.textContent.includes('Chờ thanh lý')).click()");await wait(async()=>await js("[...document.querySelectorAll('button')].some(x=>x.textContent==='Thanh lý hợp đồng')"),'pending');await js("[...document.querySelectorAll('button')].find(x=>x.textContent==='Thanh lý hợp đồng').click()");await wait(async()=>await js("document.getElementById('liquidationDialog').open"),'settlement dialog');assert(await js("document.querySelector('#liquidationDialog button[disabled]')!==null"));
 await go(base+'/register/payments.html');await wait(async()=>await js("[...document.querySelectorAll('button')].some(x=>x.textContent==='Ghi nhận thanh toán' && !x.disabled)"),'payment action');
 await js("[...document.querySelectorAll('button')].find(x=>x.textContent==='Ghi nhận thanh toán' && !x.disabled).click()");
 await wait(async()=>await js("document.getElementById('paymentDialog').open"),'payment dialog');
 await js("document.getElementById('fillRemainingBtn').click();document.getElementById('paymentForm').requestSubmit()");
 await wait(async()=>await js("document.getElementById('notice').textContent.includes('Đã ghi nhận thanh toán thành công')"),'payment saved');
 assert.equal(errors.length,0,errors.join(';'));console.log('PASS login, readings, mobile action, US22 invoice and duplicate, US16 preview, US24 payment');ws.close();
}
main().catch(e=>{console.error(e.message);process.exitCode=1}).finally(()=>chrome.kill());
