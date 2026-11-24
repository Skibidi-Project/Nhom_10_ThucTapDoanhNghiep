-- Allow invoice utility snapshots to store prices from property service configuration.
-- Existing dated-price references remain intact.
ALTER TABLE invoice_utility_snapshots
    MODIFY COLUMN price_id INT NULL;
