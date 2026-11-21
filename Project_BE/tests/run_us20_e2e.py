import os,sqlite3,tempfile,calendar
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(tempfile.gettempdir()).resolve();db=root/'ministay_us25_us27_demo.sqlite3'
if root.name!='ministay_unified_test' or not db.is_file():raise SystemExit('Unsafe database')
with sqlite3.connect(db) as c:
 row=c.execute('select id,room_id from rental_contracts order by id limit 1').fetchone();cid,rid=row
 used={x[0] for x in c.execute('select period from invoices where contract_id=?',(cid,))}
 candidates=[f'{y}-{m:02}' for y in range(2038,2045) for m in range(1,13) if f'{y}-{m:02}' not in used and not c.execute('select 1 from utility_readings where room_id=? and period=?',(rid,f'{y}-{m:02}')).fetchone()]
 periods=candidates[:3]
base='http://127.0.0.1:'+os.environ.get('MINISTAY_DEMO_PORT','18145');password=os.environ['MINISTAY_BROWSER_PASSWORD']
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True,args=['--no-sandbox'])
 for (label,width),period in zip([('desktop',1366),('tablet',768),('mobile',390)],periods):
  page=browser.new_page(viewport={'width':width,'height':850});errors=[];bad=[]
  page.on('pageerror',lambda e:errors.append(str(e)));page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None);page.on('response',lambda r:bad.append((r.status,r.url)) if r.status>=400 else None)
  page.goto(base+'/register/login.html');page.locator('#identifier').fill('landlord.us25.demo@example.com');page.locator('#password').fill(password);page.locator('#loginForm button[type=submit]').click();page.wait_for_url('**/properties.html')
  token=page.evaluate("sessionStorage.getItem('us05_access_token')");headers={'Authorization':'Bearer '+token};last=calendar.monthrange(*map(int,period.split('-')))[1]
  for kind,unit in [('electricity',3500),('water',15000)]:
   result=page.request.post(base+'/api/utility-pricing/history',headers=headers,data={'property_id':1,'utility':kind,'unit_price':unit,'valid_from':period+'-01','valid_to':period+f'-{last:02}','evidence':'E2E agreement'});assert result.status==201,result.text()
   result=page.request.post(base+f'/api/rooms/{rid}/readings',headers=headers,data={'utility_type':kind,'period':period,'previous_reading':10,'current_reading':20});assert result.status==201,result.text()
  page.locator('.unified-nav a[href="utility-pricing.html"]').click();page.wait_for_url('**/utility-pricing.html');page.locator('#contract').select_option(str(cid));page.locator('#period').fill(period);page.locator('#previewForm button').click();page.locator('#result').wait_for();assert '185000' in page.locator('#result').inner_text()
  page.locator('.unified-nav a[href="invoices.html"]').click();page.locator('#invoiceForm').wait_for();page.locator('#contract').select_option(str(cid));page.locator('#period').fill(period);page.locator('#invoiceForm button').click();page.locator('#notice').get_by_text('Đã chốt hóa đơn',exact=False).wait_for()
  data=page.request.get(base+f'/api/invoices?contract_id={cid}&period={period}',headers=headers).json();assert len(data)==1 and data[0]['utility_amount']==185000
  page.locator('.unified-nav a[href="payments.html"]').click();row=page.locator('#paymentRows tr').filter(has_text=period);row.wait_for();row.get_by_role('button',name='Ghi nhận thanh toán').click();page.locator('#paymentAmount').fill('400');page.locator('#savePaymentBtn').click();page.locator('#paymentDialog').wait_for(state='hidden');assert 'Thanh toán một phần' in row.inner_text()
  page.locator('.unified-nav a[href="dashboard.html"]').click();page.locator('.stat').first.wait_for();assert not errors,errors;assert not bad,bad
  print('PASS',label,'history, readings, US20 preview -> invoice snapshot -> payment -> dashboard');page.close()
 browser.close()
