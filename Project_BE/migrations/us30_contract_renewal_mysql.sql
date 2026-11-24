-- Apply only after backup and approval, once, to the selected MySQL database.
-- MySQL DDL commits implicitly. Keeps full history of contract renewals.
CREATE TABLE contract_renewal_histories (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  contract_id INT NOT NULL,
  previous_end_date DATE NOT NULL,
  new_end_date DATE NOT NULL,
  previous_monthly_rent INT NOT NULL,
  new_monthly_rent INT NOT NULL,
  previous_payment_cycle_months INT NOT NULL,
  new_payment_cycle_months INT NOT NULL,
  renewal_note VARCHAR(500) NULL,
  renewed_by INT NOT NULL,
  renewed_at DATETIME NOT NULL,
  INDEX ix_contract_renewal_histories_contract_id (contract_id),
  FOREIGN KEY (contract_id) REFERENCES rental_contracts(id),
  FOREIGN KEY (renewed_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;