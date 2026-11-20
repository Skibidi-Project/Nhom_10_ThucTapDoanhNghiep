"""Opt-in local InnoDB tests. Creates a unique database, never targets products_db."""
import os, subprocess, sys, uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app.db.database import DATABASE_URL
url=make_url(DATABASE_URL)
if url.get_backend_name()!='mysql' or url.host not in ('localhost','127.0.0.1') or (url.port or 3306)!=3306:
    raise SystemExit('Refusing non-local server')
name='ministay_business_test_'+uuid.uuid4().hex[:12]
assert name!='products_db'
engine=create_engine(url.set(database=None))
with engine.begin() as c: c.execute(text('CREATE DATABASE `'+name+'` CHARACTER SET utf8mb4'))
engine.dispose()
env=os.environ.copy();env['MINISTAY_MYSQL_TEST_URL']=url.set(database=name).render_as_string(hide_password=False);env['DATABASE_URL']=env['MINISTAY_MYSQL_TEST_URL'];env['PYTHONDONTWRITEBYTECODE']='1'
print('Isolated database:',name,flush=True)
raise SystemExit(subprocess.call([sys.executable,'-m','pytest','-q','-p','no:cacheprovider','tests/test_us19_mysql_concurrency.py'],env=env))
