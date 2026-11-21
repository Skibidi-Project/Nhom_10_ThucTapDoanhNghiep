-- Apply only after backup and review, once; does not infer old prices.
CREATE TABLE utility_price_history (
 id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 property_id INT NOT NULL, room_id INT NULL, contract_id INT NULL,
 utility VARCHAR(20) NOT NULL, unit_price INT NOT NULL,
 valid_from DATE NOT NULL, valid_to DATE NOT NULL, evidence VARCHAR(500) NOT NULL,
 created_by INT NOT NULL, created_at DATETIME NOT NULL,
 FOREIGN KEY (property_id) REFERENCES properties(id), FOREIGN KEY (room_id) REFERENCES rooms(id),
 FOREIGN KEY (contract_id) REFERENCES rental_contracts(id), FOREIGN KEY (created_by) REFERENCES users(id),
 CHECK (unit_price >= 0), CHECK (valid_to >= valid_from), CHECK (room_id IS NULL OR contract_id IS NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE invoice_utility_snapshots (
 id INT NOT NULL AUTO_INCREMENT PRIMARY KEY, invoice_id INT NOT NULL, utility VARCHAR(20) NOT NULL,
 price_id INT NOT NULL, source VARCHAR(20) NOT NULL, previous_reading INT NOT NULL,
 current_reading INT NOT NULL, unit_price INT NOT NULL, amount INT NOT NULL,
 CONSTRAINT uq_invoice_utility_snapshot UNIQUE (invoice_id,utility),
 FOREIGN KEY (invoice_id) REFERENCES invoices(id), FOREIGN KEY (price_id) REFERENCES utility_price_history(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE invoice_service_snapshots (
 id INT NOT NULL AUTO_INCREMENT PRIMARY KEY, invoice_id INT NOT NULL, service_code VARCHAR(20) NOT NULL,
 source VARCHAR(20) NOT NULL, quantity INT NOT NULL, unit_price INT NOT NULL, billing_unit VARCHAR(20) NOT NULL,
 amount INT NOT NULL, CONSTRAINT uq_invoice_service_snapshot UNIQUE (invoice_id,service_code),
 FOREIGN KEY (invoice_id) REFERENCES invoices(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
