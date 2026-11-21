import os,sqlite3,tempfile
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright
base='http://127.0.0.1:'+os.environ.get('MINISTAY_DEMO_PORT','18145');password=os.environ['MINISTAY_BROWSER_PASSWORD']
db=(Path(tempfile.gettempdir())/'ministay_us25_us27_demo.sqlite3').resolve()
if db.parent.name!='ministay_unified_test' or db.name!='ministay_us25_us27_demo.sqlite3': raise SystemExit('Unsafe database')
with sqlite3.connect(db) as c:
 contract=c.execute('SELECT id FROM rental_contracts ORDER BY id LIMIT 1').fetchone()[0]
 used={x[0] for x in c.execute('SELECT period FROM invoices WHERE contract_id=?',(contract,))}
 periods=[f'{y}-{m:02}' for y in range(2010,2020) for m in range(1,13) if f'{y}-{m:02}' not in used][:3]
 for period in periods:c.execute("INSERT INTO invoices(contract_id,period,rent_amount,utility_amount,total_amount,status,created_at) VALUES (?,?,1000,0,1000,'unpaid',?)",(contract,period,datetime.now().isoformat()))
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True,args=['--no-sandbox'])
 for (label,width),period in zip([('desktop',1366),('tablet',768),('mobile',390)],periods):
  page=browser.new_page(viewport={'width':width,'height':850}); errors=[];bad=[]
  page.on('pageerror',lambda e: errors.append(str(e)))
  page.on('console',lambda m: errors.append(m.text) if m.type=='error' else None)
  page.on('response',lambda r: bad.append((r.status,r.url)) if r.status>=400 else None)
  def fits():
   if page.evaluate('document.documentElement.scrollWidth > innerWidth'):
    page.screenshot(path=str(Path(tempfile.gettempdir())/('overflow-'+label+'.png')),full_page=True)
    raise AssertionError(f'Horizontal page overflow: {label} {page.url}')
  page.goto(base+'/register/login.html',wait_until='networkidle');page.locator('#identifier').fill('landlord.us25.demo@example.com');page.locator('#password').fill(password);page.locator('#loginForm button[type=submit]').click()
  page.wait_for_url('**/properties.html');nav=page.locator('.unified-nav');nav.get_by_role('link',name='Hóa đơn & Thanh toán').wait_for();token=page.evaluate("sessionStorage.getItem('us05_access_token')");assert token
  fits()
  assert page.locator('#invoicesLink').is_visible()
  nav.get_by_role('link',name='Quản lý phòng').click();page.wait_for_url('**/rooms.html');row=page.locator('#roomRows tr').filter(has_text='D01');row.wait_for();row.get_by_role('button',name='Lịch sử điện/nước').click();page.locator('#utilityHistoryRows tr').first.wait_for();history=page.locator('#utilityHistoryRows').inner_text();assert 'Điện' in history and 'Nước' in history;assert page.locator('#utilityChartSection').is_visible();page.locator('#closeUtilityHistoryBtn').click()
  page.locator('.unified-nav').get_by_role('link',name='Quản lý hợp đồng').click();page.wait_for_url('**/contracts.html');page.locator('#contractRows tr').filter(has_text='D01').wait_for()
  page.locator('.unified-nav').get_by_role('link',name='Hóa đơn & Thanh toán').click();page.wait_for_url('**/payments.html');row=page.locator('#paymentRows tr').filter(has_text=period);row.wait_for();row.get_by_role('button',name='Ghi nhận thanh toán').click();page.locator('#paymentAmount').fill('400');page.locator('#savePaymentBtn').click();page.locator('#paymentDialog').wait_for(state='hidden');assert 'Thanh toán một phần' in row.inner_text();row.get_by_role('button',name='Cập nhật trạng thái').click();page.get_by_text('Đã cập nhật trạng thái theo thanh toán.').wait_for()
  fits()
  page.locator('.unified-nav').get_by_role('link',name='Tổng quan').click();page.wait_for_url('**/dashboard.html');page.locator('.stat').first.wait_for();assert page.locator('.stat strong').nth(1).inner_text()=='3'
  page.go_back();page.wait_for_url('**/payments.html');page.locator('.unified-nav').get_by_role('link',name='Quản lý cơ sở').click();page.wait_for_url('**/properties.html');assert page.evaluate("sessionStorage.getItem('us05_access_token')")==token;page.locator('#logoutBtn').click();assert page.locator('.unified-nav').is_hidden();assert page.evaluate("sessionStorage.getItem('us05_access_token')") is None
  page.locator('#guestActions').get_by_role('link',name='Đăng nhập').click();page.wait_for_url('**/login.html');page.locator('#identifier').fill('landlord.us25.demo@example.com');page.locator('#password').fill(password);page.locator('#loginForm button[type=submit]').click();page.wait_for_url('**/properties.html');page.locator('.unified-nav').get_by_role('link',name='Hóa đơn & Thanh toán').wait_for()
  assert not errors,errors;assert not bad,bad
  print('PASS',label,'login, unified navigation, US21, US25, US27, back, logout, console/API')
  page.close()
 browser.close()
