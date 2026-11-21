-- Only after explicit approval: rolling back removes the ability to detect retries.
ALTER TABLE payments DROP INDEX uq_payment_idempotency;
ALTER TABLE payments DROP COLUMN idempotency_key, DROP COLUMN request_fingerprint;
