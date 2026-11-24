"""Explicit, one-shot migration runner. Never invoked by application startup.

Supply DATABASE_URL via the environment, then specify --execute and the exact
database name. A partially applied or externally managed schema is refused.
MySQL DDL commits implicitly: STARTED means operator recovery is required.
"""
import argparse
import hashlib
import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

FILES = ('us26_expenses_payment_note_mysql.sql', 'us20_dated_prices_mysql.sql',
         'us24_payment_idempotency_mysql.sql', 'us25_due_date_mysql.sql',
         'us30_contract_renewal_mysql.sql')
NEW_TABLES = {'expenses', 'utility_price_history', 'invoice_utility_snapshots',
              'invoice_service_snapshots', 'invoice_due_date_history',
              'contract_renewal_histories'}
NEW_COLUMNS = {'payments': {'note', 'idempotency_key', 'request_fingerprint'},
               'invoices': {'due_date'}}
TRACK = 'ministay_migration_batches'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-database', required=True)
    args = parser.parse_args()
    raw = os.environ.get('DATABASE_URL')
    if not raw:
        raise SystemExit('DATABASE_URL is required; no default database is used')
    url = make_url(raw)
    if url.get_backend_name() != 'mysql' or not url.database or args.confirm_database != url.database:
        raise SystemExit('Require an explicit matching MySQL database name')
    scripts = [(name, (Path(__file__).parent / name).read_text(encoding='utf-8-sig')) for name in FILES]
    digest = hashlib.sha256('\n'.join(s for _, s in scripts).encode()).hexdigest()
    engine = create_engine(url)
    with engine.connect() as conn:
        actual = conn.scalar(text('SELECT DATABASE()'))
        if actual != args.confirm_database:
            raise SystemExit('Connected database does not match confirmation')
        lock_name = 'ministay_migrate_' + hashlib.sha256(actual.encode()).hexdigest()[:32]
        if conn.scalar(text('SELECT GET_LOCK(:name, 0)'), {'name': lock_name}) != 1:
            raise SystemExit('Another migration holds the database lock')
        try:
            inspector = inspect(conn)
            tables = set(inspector.get_table_names())
            if TRACK in tables:
                row = conn.execute(text(f'SELECT status, checksum FROM `{TRACK}` WHERE id=1')).first()
                if row and row.status == 'complete' and row.checksum == digest:
                    print('Already recorded as complete; verify schema independently before deployment.')
                    return
                raise SystemExit('Migration tracking exists but is incomplete or differs; stop and investigate')
            if not {'payments', 'invoices', 'users', 'properties', 'rooms', 'rental_contracts'} <= tables:
                raise SystemExit('Required baseline tables missing')
            conflicts = sorted(NEW_TABLES & tables)
            for table, names in NEW_COLUMNS.items():
                columns = {item['name'] for item in inspector.get_columns(table)}
                conflicts.extend(f'{table}.{name}' for name in sorted(names & columns))
            if conflicts:
                raise SystemExit('Existing or partially migrated objects require manual review: ' + ', '.join(conflicts))
            if not args.execute:
                print('Preflight: target objects absent. No changes made; inspect full schema and take a verified backup.')
                return
            conn.execute(text(f'CREATE TABLE `{TRACK}` (id INT PRIMARY KEY, status VARCHAR(20) NOT NULL, checksum CHAR(64) NOT NULL) ENGINE=InnoDB'))
            conn.execute(text(f"INSERT INTO `{TRACK}` (id,status,checksum) VALUES (1,'started',:checksum)"), {'checksum': digest})
            conn.commit()
            for name, content in scripts:
                content = '\n'.join(line for line in content.splitlines() if not line.strip().startswith('--'))
                for statement in content.split(';'):
                    if statement.strip():
                        conn.execute(text(statement))
                conn.commit()
                print('Applied', name)
            conn.execute(text(f"UPDATE `{TRACK}` SET status='complete' WHERE id=1"))
            conn.commit()
            print('Migration batch recorded; verify schema and data before deployment.')
        finally:
            conn.execute(text('SELECT RELEASE_LOCK(:name)'), {'name': lock_name})
    engine.dispose()


if __name__ == '__main__':
    main()
