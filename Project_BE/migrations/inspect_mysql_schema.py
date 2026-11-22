"""Read-only mapped schema inventory; does not certify compatibility."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from app.db.database import Base
import app.models
import app.models.room_type

url = make_url(os.environ["DATABASE_URL"])
if url.get_backend_name() != "mysql" or not url.database or len(sys.argv) != 2 or sys.argv[1] != url.database:
    raise SystemExit("Specify the exact MySQL database name")
engine = create_engine(url)
with engine.connect() as conn:
    print("Target:", conn.execute(text("SELECT DATABASE(), @@hostname, @@port, @@version")).one())
    inspector = inspect(conn)
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            print("MISSING TABLE", table.name)
            continue
        existing = {c["name"] for c in inspector.get_columns(table.name)}
        for name in sorted(set(table.columns.keys()) - existing):
            print("MISSING COLUMN", table.name + "." + name)
        actual_fk = {(tuple(f["constrained_columns"]), f["referred_table"], tuple(f["referred_columns"])) for f in inspector.get_foreign_keys(table.name)}
        for fk in table.foreign_key_constraints:
            expected = (tuple(e.parent.name for e in fk.elements), fk.referred_table.name, tuple(e.column.name for e in fk.elements))
            if expected not in actual_fk:
                print("MISSING FK", table.name, expected)
    print("Inventory only: review types, indexes, constraints, engines and data independently.")
engine.dispose()
