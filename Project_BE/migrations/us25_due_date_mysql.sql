-- Apply only after backup and approval, once, to the selected MySQL database.
-- MySQL DDL commits implicitly. Old invoices retain NULL due_date.
ALTER TABLE invoices ADD COLUMN due_date DATE NULL;
CREATE TABLE invoice_due_date_history (
 id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 invoice_id INT NOT NULL,
 old_due_date DATE NULL,
 new_due_date DATE NOT NULL,
 reason VARCHAR(500) NOT NULL,
 changed_by INT NOT NULL,
 changed_at DATETIME NOT NULL,
 INDEX ix_invoice_due_date_history_invoice_id (invoice_id),
 FOREIGN KEY (invoice_id) REFERENCES invoices(id),
 FOREIGN KEY (changed_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
