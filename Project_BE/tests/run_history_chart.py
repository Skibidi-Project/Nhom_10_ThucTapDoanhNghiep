import os,sqlite3,tempfile,subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
base='http://127.0.0.1:'+os.environ.get('MINISTAY_DEMO_PORT','18145'); password=os.environ['MINISTAY_BROWSER_PASSWORD']; temp=Path(tempfile.gettempdir()).resolve();db=temp/'ministay_us25_us27_demo.sqlite3'
if temp.name!='ministay_unified_test' or not db.is_file():raise SystemExit('Unsafe database')
with sqlite3.connect(db) as c:
 room=c.execute("select id from rooms where room_number='D01'").fetchone()[0];user=c.execute("select id from users where email='landlord.us25.demo@example.com'").fetchone()[0]
 if not c.execute("select id from utility_readings where room_id=? and utility_type='electricity' and period='2000-01'",(room,)).fetchone():c.execute("insert into utility_readings(room_id,utility_type,period,previous_reading,current_reading,recorded_by) values (?,'electricity','2000-01',10,30,?)",(room,user))
 if c.execute("select count(*) from utility_readings where room_id=? and utility_type='water' and period='2000-01'",(room,)).fetchone()[0]:raise SystemExit('Expected missing water data')
old=subprocess.check_output(['git','show','HEAD:Project_BE/register/rooms.js'],encoding='utf-8')
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True,args=['--no-sandbox'])
 for variant in ['before','after']:
  page=browser.new_page(viewport={'width':1366,'height':900});errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  if variant=='before':page.route('**/register/rooms.js',lambda route:route.fulfill(status=200,content_type='application/javascript',body=old))
  page.goto(base+'/register/login.html');page.locator('#identifier').fill('landlord.us25.demo@example.com');page.locator('#password').fill(password);page.locator('#loginForm button[type=submit]').click();page.wait_for_url('**/properties.html');page.locator('.unified-nav').get_by_role('link',name='Quản lý phòng').click()
  page.locator('#roomRows tr').filter(has_text='D01').get_by_role('button',name='Lịch sử điện/nước').click();page.locator('#utilityMonthFilter').select_option('2000-01')
  bars=page.locator('#utilityChart .utility-bar');assert bars.count()==(2 if variant=='before' else 1);assert not errors,errors
  page.locator('#utilityHistoryDialog').screenshot(path=str(temp/('us21-'+variant+'.png')))
  print(variant,'bars',bars.count(),'screenshot',str(temp/('us21-'+variant+'.png')));page.close()
 browser.close()
