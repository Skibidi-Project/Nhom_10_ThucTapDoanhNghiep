-- Requires explicit approval and archival; destroys price history and invoice snapshots.
DROP TABLE invoice_service_snapshots;
DROP TABLE invoice_utility_snapshots;
DROP TABLE utility_price_history;
