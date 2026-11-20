-- REVIEW ONLY: backups, schema checks and permission review required before deployment.
CREATE TABLE invoice_snapshots (
 invoice_id INT NOT NULL PRIMARY KEY,
 payload TEXT NOT NULL,
 sha256 CHAR(64) NOT NULL,
 CONSTRAINT fk_invoice_snapshot_invoice FOREIGN KEY (invoice_id) REFERENCES invoices(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TRIGGER invoice_snapshots_no_update BEFORE UPDATE ON invoice_snapshots FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Invoice snapshot is immutable';
CREATE TRIGGER invoice_snapshots_no_delete BEFORE DELETE ON invoice_snapshots FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Invoice snapshot is immutable';
