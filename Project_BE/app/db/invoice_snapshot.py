"""Invoice evidence is migrated explicitly, not created by app startup."""
from sqlalchemy import Column, Integer, MetaData, String, Table, Text

metadata = MetaData()
invoice_snapshot = Table(
    'invoice_snapshots', metadata,
    Column('invoice_id', Integer, primary_key=True),
    Column('payload', Text, nullable=False),
    Column('sha256', String(64), nullable=False),
)
