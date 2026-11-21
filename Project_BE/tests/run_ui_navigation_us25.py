import os, sqlite3, tempfile
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

base='http://127.0.0.1:'+os.environ.get('MINISTAY_DEMO_PORT','8026')
password=os.environ['MINISTAY_BROWSER_PASSWORD']
db=(Path(tempfile.gettempdir())/'ministay_us25_us27_demo.sqlite3').resolve()
if db.name!='ministay_us25_us27_demo.sqlite3' or db.parent.name!='ministay_us25_overdue_test': raise SystemExit('Unsafe database')
with sqlite3.connect(db) as c:
    first=c.execute('SELECT id FROM rental_contracts WHERE room_id=1').fetchone()[0]
    other=c.execute('SELECT id FROM rental_contracts WHERE room_id=2').fetchone()
    if other is None:
        c.execute('INSERT INTO rental_contracts(room_id,tenant_id,created_by,start_date,end_date,deposit,deposit_status,deposit_returned_amount,deposit_note,monthly_rent,payment_cycle_months,status) SELECT 2,tenant_id,created_by,start_date,end_date,deposit,deposit_status,deposit_returned_amount,deposit_note,monthly_rent,payment_cycle_months,status FROM rental_contracts WHERE id=?',(first,))
        other=c.execute('SELECT last_insert_rowid()').fetchone()
    other=other[0]
    if not c.execute("SELECT id FROM invoices WHERE contract_id=? AND period='2039-12'",(other,)).fetchone():
        c.execute("INSERT INTO invoices(contract_id,period,rent_amount,utility_amount,total_amount,status,created_at) VALUES (?,'2039-12',1000,0,1000,'unpaid',?)",(other,datetime.now().isoformat()))
    used={x[0] for x in c.execute('SELECT period FROM invoices WHERE contract_id=?',(first,))}
    periods=[f'{y}-{m:02}' for y in range(2020,2030) for m in range(1,13) if f'{y}-{m:02}' not in used][:2]
    for period in periods:
        c.execute("INSERT INTO invoices(contract_id,period,rent_amount,utility_amount,total_amount,status,created_at) VALUES (?,?,1000,0,1000,'unpaid',?)",(first,period,datetime.now().isoformat()))

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True,args=['--no-sandbox'])
    for (label,width,height),period in zip([('desktop',1440,900),('mobile',390,844)],periods):
        page=browser.new_page(viewport={'width':width,'height':height})
        errors=[]; bad=[]
        page.on('pageerror',lambda e: errors.append(str(e)))
        page.on('console',lambda m: errors.append(m.text) if m.type=='error' else None)
        page.on('response',lambda r: bad.append((r.status,r.url)) if '/api/' in r.url and r.status>=400 else None)
        page.goto(base+'/register/login.html',wait_until='networkidle')
        page.locator('#identifier').fill('landlord.us25.demo@example.com');page.locator('#password').fill(password);page.locator('#loginForm button[type=submit]').click()
        page.wait_for_url('**/properties.html');token=page.evaluate("sessionStorage.getItem('us05_access_token')");assert token
        page.get_by_role('link',name='Quản lý hóa đơn').click();page.wait_for_url('**/payments.html')
        assert page.evaluate("sessionStorage.getItem('us05_access_token')")==token
        row=page.locator('#paymentRows tr').filter(has_text=period);row.wait_for();assert 'Chưa thanh toán' in row.inner_text()
        row.get_by_role('button',name='Ghi nhận thanh toán').click();page.locator('#paymentAmount').fill('400');page.locator('#savePaymentBtn').click();page.locator('#paymentDialog').wait_for(state='hidden');assert 'Thanh toán một phần' in row.inner_text()
        row.get_by_role('button',name='Cập nhật trạng thái').click();page.get_by_text('Đã cập nhật trạng thái theo thanh toán.').wait_for()
        row.get_by_role('button',name='Ghi nhận thanh toán').click();page.locator('#fillRemainingBtn').click();page.locator('#savePaymentBtn').click();page.locator('#paymentDialog').wait_for(state='hidden');assert 'Đã thanh toán' in row.inner_text()
        page.locator('main').get_by_role('link',name='Quản lý cơ sở').click();page.wait_for_url('**/properties.html')
        page.get_by_role('link',name='Quản lý hợp đồng').click();page.wait_for_url('**/contracts.html')
        contract_row=page.locator('#contractRows tr').filter(has_text='D01');contract_row.wait_for();contract_row.get_by_role('button',name='Hóa đơn / Thanh toán').click();page.wait_for_url('**/payments.html?contract_id=*')
        assert page.url.endswith('contract_id='+str(first));page.locator('#contractScope').wait_for();page.locator('#paymentRows tr').filter(has_text=period).wait_for()
        assert page.locator('#paymentRows tr').filter(has_text='2039-12').count()==0
        assert page.evaluate("sessionStorage.getItem('us05_access_token')")==token
        assert not errors,errors;assert not bad,bad
        print('PASS',label,'login > properties > invoices > payments/reconcile > contract filter, token, console/API')
        page.close()
    browser.close()
