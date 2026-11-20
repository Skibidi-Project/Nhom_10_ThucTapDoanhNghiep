-- REVIEW ONLY. Trial policy is not approved for real financial operations.
CREATE TABLE us16_trial_settlements (
 contract_id INT NOT NULL PRIMARY KEY,
 handover_date DATE NOT NULL,
 reason VARCHAR(500) NOT NULL,
 created_by INT NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 refund_amount INT NULL,
 damage_shortfall INT NOT NULL DEFAULT 0,
 refunded_by INT NULL,
 refunded_at DATETIME NULL,
 refund_method VARCHAR(20) NULL,
 refund_reference VARCHAR(255) NULL,
 FOREIGN KEY (contract_id) REFERENCES rental_contracts(id),
 FOREIGN KEY (created_by) REFERENCES users(id),
 FOREIGN KEY (refunded_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE us16_trial_receivables (
 contract_id INT NOT NULL PRIMARY KEY,
 amount INT NOT NULL,
 status VARCHAR(20) NOT NULL,
 created_by INT NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (contract_id) REFERENCES rental_contracts(id),
 FOREIGN KEY (created_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE us16_trial_invoice_reviews (
 invoice_id INT NOT NULL PRIMARY KEY,
 contract_id INT NOT NULL,
 snapshot_sha256 CHAR(64) NOT NULL,
 reviewed_by INT NOT NULL,
 reviewed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (invoice_id) REFERENCES invoices(id),
 FOREIGN KEY (contract_id) REFERENCES rental_contracts(id),
 FOREIGN KEY (reviewed_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE us16_trial_final_approvals (
 id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 contract_id INT NOT NULL,
 period CHAR(7) NOT NULL,
 period_start DATE NOT NULL,
 period_end DATE NOT NULL,
 charge_type VARCHAR(40) NOT NULL,
 inputs TEXT NOT NULL,
 input_sha256 CHAR(64) NOT NULL,
 reason VARCHAR(500) NOT NULL,
 proposed_method VARCHAR(500) NOT NULL,
 proposed_amount INT NOT NULL,
 reference VARCHAR(500) NULL,
 created_by INT NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 status VARCHAR(20) NOT NULL,
 reviewed_by INT NULL,
 reviewed_at DATETIME NULL,
 decision_reason VARCHAR(500) NULL,
 invoice_id INT NULL,
 FOREIGN KEY (contract_id) REFERENCES rental_contracts(id),
 FOREIGN KEY (created_by) REFERENCES users(id),
 FOREIGN KEY (reviewed_by) REFERENCES users(id),
 FOREIGN KEY (invoice_id) REFERENCES invoices(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE us16_trial_meter_handovers (
 contract_id INT NOT NULL PRIMARY KEY,
 handover_at DATETIME NOT NULL,
 electricity_reading_id INT NOT NULL,
 water_reading_id INT NOT NULL,
 electricity_version INT NOT NULL,
 water_version INT NOT NULL,
 recorded_by INT NOT NULL,
 confirmed_by INT NOT NULL,
 confirmed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (contract_id) REFERENCES rental_contracts(id),
 FOREIGN KEY (electricity_reading_id) REFERENCES utility_readings(id),
 FOREIGN KEY (water_reading_id) REFERENCES utility_readings(id),
 FOREIGN KEY (recorded_by) REFERENCES users(id),
 FOREIGN KEY (confirmed_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE us16_trial_input_revisions (
 property_id INT NOT NULL PRIMARY KEY,
 version INT NOT NULL,
 FOREIGN KEY (property_id) REFERENCES properties(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE us16_trial_damages (
 id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 contract_id INT NOT NULL,
 description VARCHAR(500) NOT NULL,
 amount INT NOT NULL,
 created_by INT NOT NULL,
 confirmed_by INT NULL,
 confirmed_at DATETIME NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (contract_id) REFERENCES rental_contracts(id),
 FOREIGN KEY (created_by) REFERENCES users(id),
 FOREIGN KEY (confirmed_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
