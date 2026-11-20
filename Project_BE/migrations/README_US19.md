# US-19 reading revision migration — review required

`us19_reading_revisions.sql` adds only a revision counter referencing the existing `utility_readings` row. Existing rows need no backfill: missing revision means version 0; the first successful edit creates version 1. The table contains no separate meter reading data.

Application startup deliberately does not create this table. Until the reviewed migration has been applied, reading the revision or editing an existing reading returns HTTP 503; existing read/create routes still work subject to invoice locking rules. Do not run the migration on products_db without approval, a backup and a deployment plan.

Rollout must deploy the locking and revision-aware code to all writers together. Old application versions or external SQL updates do not update revision numbers or share the room lock, so mixed-version operation can break ABA protection and invoice consistency. Review the database user's privileges, check for an existing table and confirm table definitions and foreign keys before migration. The migration was run on isolated MySQL test databases only.

Rollback requires a reviewed plan: do not drop the revision table while newer application instances are running, and ensure no active reader expects the revision endpoint. The migration does not contain destructive rollback commands.
