-- Apply only after schema preflight, backup and approval; MySQL DDL implicitly commits.
-- Stop if either object already exists; reconcile any partial migration manually.
ALTER TABLE payments ADD COLUMN note VARCHAR(255) NULL;
CREATE TABLE expenses (
 id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 property_id INT NOT NULL, room_id INT NULL,
 category VARCHAR(20) NOT NULL, description VARCHAR(255) NOT NULL,
 vendor VARCHAR(120) NULL, amount INT NOT NULL,
 expense_date DATE NOT NULL, created_by INT NOT NULL, created_at DATETIME NOT NULL,
 INDEX ix_expenses_property_date (property_id, expense_date),
 FOREIGN KEY (property_id) REFERENCES properties(id),
 FOREIGN KEY (room_id) REFERENCES rooms(id),
 FOREIGN KEY (created_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
