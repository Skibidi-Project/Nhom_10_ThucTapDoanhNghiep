import os,sqlite3,tempfile
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(tempfile.gettempdir()).resolve();db=root/'ministay_us25_us27_demo.sqlite3'
if root.name!='ministay_unified_test' or not db.is_file():raise SystemExit('Unsafe database')
with sqlite3.connect(db) as c:
 contract=c.execute('select id from rental_contracts order by id limit 1').fetchone()[0];used={x[0] for x in c.execute('select period from invoices where contract_id=?',(contract,))};period=next(f'{y}-{m:02}' for y in range(2010,2020) for m in range(1,13) if f'{y}-{m:02}' not in used)
 c.execute("insert into invoices(contract_id,period,rent_amount,utility_amount,total_amount,status,created_at) values (?,?,1000,0,1000,'unpaid',?)",(contract,period,datetime.now().isoformat()));iid=c.execute('select last_insert_rowid()').fetchone()[0]
base='http://127.0.0.1:'+os.environ.get('MINISTAY_DEMO_PORT','18145');password=os.environ['MINISTAY_BROWSER_PASSWORD'];keys=[]
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True,args=['--no-sandbox']);page=b.new_page()
 page.goto(base+'/register/login.html');page.locator('#identifier').fill('landlord.us25.demo@example.com');page.locator('#password').fill(password);page.locator('#loginForm button[type=submit]').click();page.wait_for_url('**/properties.html');page.locator('.unified-nav a[href="payments.html"]').click();row=page.locator('#paymentRows tr').filter(has_text=period);row.wait_for()
 def lose_response(route):
  keys.append(route.request.headers.get('idempotency-key'));response=route.fetch();assert response.status==201;route.abort('failed')
 page.route(f'**/api/invoices/{iid}/payments',lose_response,times=1);row.get_by_role('button',name='Ghi nhận thanh toán').click();page.locator('#paymentAmount').fill('400');page.locator('#savePaymentBtn').click();page.locator('#paymentFormError').wait_for(state='visible');assert page.locator('#paymentFormError').inner_text()
 def capture(request):
  if request.url.endswith(f'/api/invoices/{iid}/payments') and request.method=='POST':keys.append(request.headers.get('idempotency-key'))
 page.on('request',capture);page.locator('#savePaymentBtn').click();page.locator('#paymentDialog').wait_for(state='hidden');assert len(keys)==2 and keys[0] and keys[0]==keys[1];assert 'Thanh toán một phần' in row.inner_text()
 with sqlite3.connect(db) as c:assert c.execute('select count(*),sum(amount) from payments where invoice_id=?',(iid,)).fetchone()==(1,400)
 print('PASS Chrome retry after lost HTTP response: same idempotency key, one payment');b.close()
