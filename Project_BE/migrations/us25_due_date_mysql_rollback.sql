-- Destructive rollback: only after backup, explicit approval and archival of audit history.
DROP TABLE invoice_due_date_history;
ALTER TABLE invoices DROP COLUMN due_date;
