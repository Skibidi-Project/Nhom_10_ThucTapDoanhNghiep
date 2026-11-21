import os, sqlite3, tempfile
from pathlib import Path
from datetime import date
from playwright.sync_api import sync_playwright

password=os.environ['MINISTAY_BROWSER_PASSWORD']
db=(Path(tempfile.gettempdir())/'ministay_us25_us27_demo.sqlite3').resolve()
if db.name!='ministay_us25_us27_demo.sqlite3' or 'ministay_us25_browser_final' not in str(db): raise SystemExit('Unsafe database')
with sqlite3.connect(db) as c:
 contract=c.execute('select id from rental_contracts order by id limit 1').fetchone()[0]
 baseline=c.execute("select coalesce(sum(amount),0) from payments where substr(paid_at,1,7)=?",(date.today().strftime('%Y-%m'),)).fetchone()[0]
 periods={x[0] for x in c.execute('select period from invoices where contract_id=?',(contract,))}
 period=next(f'{y}-{m:02}' for y in range(2010,2020) for m in range(1,13) if f'{y}-{m:02}' not in periods)
 c.execute('insert into invoices(contract_id,period,rent_amount,utility_amount,total_amount,status,created_at) values (?,?,?,?,?,?,CURRENT_TIMESTAMP)',(contract,period,1000,0,1000,'unpaid'))

with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':1440,'height':900})
 errors=[]; bad=[]
 page.on('pageerror',lambda e: errors.append(str(e)))
 page.on('console',lambda m: errors.append(m.text) if m.type=='error' else None)
 page.on('response',lambda r: bad.append((r.status,r.url)) if '/api/' in r.url and r.status>=400 else None)
 page.goto('http://127.0.0.1:8025/register/login.html',wait_until='networkidle')
 page.locator('#identifier').fill('landlord.us25.demo@example.com');page.locator('#password').fill(password);page.locator('#loginForm button[type=submit]').click()
 page.wait_for_url('**/properties.html');page.goto('http://127.0.0.1:8025/register/payments.html')
 row=page.locator('#paymentRows tr').filter(has_text=period);row.wait_for();assert 'Chưa thanh toán' in row.inner_text()
 row.get_by_role('button',name='Ghi nhận thanh toán').click();page.locator('#paymentAmount').fill('400');page.locator('#savePaymentBtn').click();page.locator('#paymentDialog').wait_for(state='hidden');assert 'Thanh toán một phần' in row.inner_text()
 row.get_by_role('button',name='Ghi nhận thanh toán').click();page.locator('#fillRemainingBtn').click();page.locator('#savePaymentBtn').click();page.locator('#paymentDialog').wait_for(state='hidden');assert 'Đã thanh toán' in row.inner_text()
 row.get_by_role('button',name='Cập nhật trạng thái').click();page.get_by_text('Đã cập nhật trạng thái theo thanh toán.').wait_for()
 page.goto('http://127.0.0.1:8025/register/dashboard.html',wait_until='networkidle');page.locator('.stat').first.wait_for();cards=page.locator('.stat strong');assert cards.nth(1).inner_text()=='3';assert cards.nth(3).inner_text()=='1';assert cards.nth(8).inner_text().startswith(f'{baseline+1000:,}'.replace(',','.'));assert cards.nth(9).inner_text().startswith('700.000')
 page.locator('#period').fill(period);page.locator('#filters button').click();page.wait_for_timeout(500);cards=page.locator('.stat strong');assert cards.nth(7).inner_text().startswith('1.000');assert cards.nth(9).inner_text().startswith('0')
 options=page.locator('#property option').count();assert options>=2;page.locator('#property').select_option(index=1);page.locator('#filters button').click();page.wait_for_timeout(500)
 page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(300);assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
 assert not errors, errors;assert not bad,bad
 print('PASS Chrome desktop/mobile: login, unpaid, partial, paid, reconcile, dashboard, filters, console/API')
 browser.close()
