import os
import pytest
from sqlalchemy.engine import make_url

os.environ.setdefault('DATABASE_URL','sqlite://')
url=make_url(os.environ['DATABASE_URL'])
if url.get_backend_name()=='sqlite':
    if url.database not in (None,'',':memory:'): raise pytest.UsageError('Only in-memory SQLite is allowed for pytest.')
elif url.get_backend_name()=='mysql':
    if url.host not in ('localhost','127.0.0.1') or (url.port or 3306)!=3306 or not (url.database or '').startswith('ministay_us25_test_'):
        raise pytest.UsageError('Refusing non-isolated MySQL database.')
else: raise pytest.UsageError('Unsupported test database.')
