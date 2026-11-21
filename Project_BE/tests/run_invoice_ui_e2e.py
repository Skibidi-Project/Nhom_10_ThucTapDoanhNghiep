import os,sqlite3,tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(tempfile.gettempdir()).resolve();db=root/'ministay_us25_us27_demo.sqlite3'
if root.name!='ministay_unified_test' or not db.is_file():raise SystemExit('Unsafe database')
with sqlite3.connect(db) as c:
 contract=c.execute('select id from rental_contracts order by id limit 1').fetchone()[0]
 c.execute("update rental_contracts set end_date='2045-12-31' where id=?",(contract,))
 used={r[0] for r in c.execute('select period from invoices where contract_id=?',(contract,))}
 periods=[f'{y}-{m:02}' for y in range(2030,2040) for m in range(1,13) if f'{y}-{m:02}' not in used][:3]
base='http://127.0.0.1:'+os.environ.get('MINISTAY_DEMO_PORT','18145');password=os.environ['MINISTAY_BROWSER_PASSWORD']
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True,args=['--no-sandbox'])
 for (label,width),period in zip([('desktop',1366),('tablet',768),('mobile',390)],periods):
  page=browser.new_page(viewport={'width':width,'height':850});errors=[];bad=[]
  page.on('pageerror',lambda e:errors.append(str(e)));page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None);page.on('response',lambda r:bad.append((r.status,r.url)) if r.status>=400 else None)
  page.goto(base+'/register/login.html');page.locator('#identifier').fill('landlord.us25.demo@example.com');page.locator('#password').fill(password);page.locator('#loginForm button[type=submit]').click();page.wait_for_url('**/properties.html')
  page.locator('.unified-nav').get_by_role('link',name='Chốt hóa đơn').click();page.wait_for_url('**/invoices.html');page.locator('#invoiceForm').wait_for();page.locator('#contract').select_option(str(contract));page.locator('#period').fill(period);page.locator('#invoiceForm button').click();page.locator('#notice').get_by_text('Đã chốt hóa đơn',exact=False).wait_for()
  page.locator('.unified-nav').get_by_role('link',name='Hóa đơn & Thanh toán').click();page.wait_for_url('**/payments.html');row=page.locator('#paymentRows tr').filter(has_text=period);row.wait_for();assert 'Chưa thanh toán' in row.inner_text();row.get_by_role('button',name='Ghi nhận thanh toán').click();page.locator('#paymentAmount').fill('400');page.locator('#savePaymentBtn').click();page.locator('#paymentDialog').wait_for(state='hidden');assert 'Thanh toán một phần' in row.inner_text();page.reload();page.locator('#paymentRows tr').filter(has_text=period).get_by_text('Thanh toán một phần').wait_for()
  assert not errors,errors;assert not bad,bad;print('PASS',label,'US22 UI -> US24 -> US25 -> refresh');page.close()
 browser.close()
