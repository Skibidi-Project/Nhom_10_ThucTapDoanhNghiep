-- Apply once, after backup and review; MySQL DDL commits implicitly.
ALTER TABLE payments ADD COLUMN idempotency_key VARCHAR(128) NULL, ADD COLUMN request_fingerprint VARCHAR(64) NULL;
ALTER TABLE payments ADD CONSTRAINT uq_payment_idempotency UNIQUE (invoice_id, recorded_by, idempotency_key);
