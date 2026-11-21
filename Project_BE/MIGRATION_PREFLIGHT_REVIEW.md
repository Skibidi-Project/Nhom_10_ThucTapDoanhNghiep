# MySQL migration review: US-20, US-24 and US-25

This is a review and recovery plan, not authorization to execute DDL. The scripts are not idempotent and MySQL DDL implicitly commits. A failure can leave a partially migrated schema; do not blindly rerun a script.

## Before scheduling a migration

1. Identify the actual deployment, target server, database, MySQL version, service account and maintenance window. Confirm that writes are quiesced and that an operator has approved the change and recovery plan.
2. Capture a consistent backup using the site's approved procedure, including schema, data, triggers, routines and events. For InnoDB, an operator can use `mysqldump --single-transaction --routines --triggers --events --no-tablespaces --databases products_db > <protected-backup-file>` with credentials supplied securely outside the command line. Concurrent DDL invalidates the consistency assumptions; coordinate all DDL and writes. Check dump exit status and restore and verify it on a separate test server before relying on it.
3. Check the target explicitly with `SELECT DATABASE(), @@hostname, @@port, @@version;`. Inspect table engines, columns, indexes and foreign keys through `information_schema`. Check the three migrations against the exact current schema, including partially applied migrations. In particular verify `uq_payment_idempotency` is unique on `(invoice_id, recorded_by, idempotency_key)`; column names alone are insufficient. Check existing payments for valid invoice and user references and invoice history for valid invoice and user references.
4. Verify every dependent table exists with matching foreign-key column types, collations and InnoDB engine. Verify available storage, metadata-lock risk, backup restore time, privileges and the application version and its schema requirements. Test all scripts, interrupted execution, application startup, billing and payments against an isolated copy first.
5. Inventory the dated utility price evidence for each contract, room and property. US-20 does not backfill historic prices; invoices cannot safely be issued for periods without supported effective prices. A price change within a billing period remains blocked pending an approved allocation rule.

## Application order and verification

The local schema audit also found that `expenses` and `payments.note` are absent; the reviewed batch includes `migrations/us26_expenses_payment_note_mysql.sql`. The application does not create or alter MySQL objects at startup. All four migration scripts must be reviewed and applied before deploying the new application.

Set `DATABASE_URL` securely in the operator environment and run `python migrations/apply_mysql_migrations.py --confirm-database <exact-database-name>` for a non-mutating object preflight. After backup, full schema review and explicit operational approval, add `--execute`. The runner acquires a MySQL advisory lock and records a batch checksum and status. It applies US-26/note, US-20, US-24 and US-25 in that order. It refuses partially present objects or an unfinished/different tracked batch; it does not repair a partial migration. An exact recorded repeat is skipped, but still requires independent schema verification. It intentionally refuses untracked pre-existing objects even if they appear compatible. Its preflight checks object presence, not every type, foreign key, index, permission or data invariant; complete the independent checks above. Never manually execute the scripts alongside this runner.

On error, stop and reconcile the actual schema against the backup and each statement; do not assume transaction rollback reverted DDL. A `started` tracking row is a recovery stop, not permission to retry.

Verify all expected columns, tables, foreign keys and unique indexes, preserved row counts and historical invoice/payment totals, `NULL` legacy due dates and idempotency keys, and application health. On an isolated copy, test price snapshots and duplicate-period protection, same-key payment retry and conflicting request, partial payment and overdue status. Validate permissions and record the exact versions and results. Existing clients without an idempotency key remain outside retry protection.

## Rollback and recovery

The supplied `*_rollback.sql` scripts drop columns or tables and therefore can destroy dated-price evidence, invoice snapshots, due-date audit history or idempotency keys. A rollback after new writes can also permit payment retries to be recorded twice. Do not execute these scripts automatically. Stop writes, preserve and export all new data and transaction evidence, obtain explicit operational approval and reconcile payments before choosing a recovery method. A tested restore from the pre-change backup loses later writes unless they are separately recovered and reconciled. Rehearse restoration and application rollback on an isolated server; restoring production requires a separately approved operational plan.

## Current release blocker

The prepared merge fails startup on a schema-only copy of the current local `products_db`: the US-25 guard raises before the service starts. Removing the guard alone is unsafe because mapped invoice/payment columns and US-20 tables are queried by application paths. MySQL startup now refuses missing mapped tables and columns and does not run `init_db()`; migration and independent deployment coordination remain mandatory. An unknown deployment webhook is a release blocker until an authorized administrator verifies that a push cannot deploy against the old schema.
