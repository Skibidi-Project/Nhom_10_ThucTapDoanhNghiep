"""Revision table is deliberately outside Base.metadata; run reviewed migration explicitly."""
from sqlalchemy import Column, Integer, MetaData, Table

metadata = MetaData()
reading_revision = Table(
    "reading_revisions", metadata,
    Column("reading_id", Integer, primary_key=True),
    Column("version", Integer, nullable=False),
)
