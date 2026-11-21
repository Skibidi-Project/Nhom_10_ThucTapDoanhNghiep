import secrets,sqlite3,tempfile
from pathlib import Path
from datetime import datetime
from argon2 import PasswordHasher
from playwright.sync_api import sync_playwright
root=Path(tempfile.gettempdir()).resolve();db=root/'ministay_us25_us27_demo.sqlite3'
if root.name!='ministay_unified_test' or not db.is_file():raise SystemExit('Unsafe database')
pwd=secrets.token_urlsafe(24);nonce=secrets.token_hex(4);accounts={}
with sqlite3.connect(db) as c:
 for role in ['manager','tenant','admin']:
  email=f'{role}.{nonce}@example.com';accounts[role]=email
  c.execute('insert into users(full_name,email,password_hash,role,created_at) values(?,?,?,?,?)',(role,email,PasswordHasher().hash(pwd),role,datetime.now().isoformat()))
  if role=='manager':c.execute('insert into property_managers(property_id,user_id) values (?,?)',(1,c.execute('select last_insert_rowid()').fetchone()[0]))
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True,args=['--no-sandbox'])
 for role,email in accounts.items():
  page=b.new_page(viewport={'width':390,'height':844});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto('http://127.0.0.1:18145/register/login.html');page.locator('#identifier').fill(email);page.locator('#password').fill(pwd);page.locator('#loginForm button[type=submit]').click()
  target={'manager':'properties.html','tenant':'account.html','admin':'admin-users.html'}[role];page.wait_for_url('**/'+target)
  if role=='manager':page.locator('.unified-nav a[href="payments.html"]').wait_for()
  else:assert page.locator('.unified-nav').count()==0
  token=page.evaluate("sessionStorage.getItem('us05_access_token')");result=page.request.get('http://127.0.0.1:18145/api/dashboard/summary',headers={'Authorization':'Bearer '+token})
  assert result.status==(200 if role=='manager' else 403);assert not errors,errors
  print('PASS role',role,'login route menu and dashboard RBAC');page.close()
 b.close()
