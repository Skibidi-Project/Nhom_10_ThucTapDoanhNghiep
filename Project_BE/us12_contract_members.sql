-- US-12: Ch?y th? c?ng trong schema MySQL hi?n c?. Kh?ng thay ??i b?ng c?.
CREATE TABLE IF NOT EXISTS contract_members (
    contract_id INT NOT NULL,
    tenant_id INT NOT NULL,
    PRIMARY KEY (contract_id, tenant_id),
    INDEX ix_contract_members_tenant_id (tenant_id),
    CONSTRAINT fk_contract_members_contract FOREIGN KEY (contract_id)
        REFERENCES rental_contracts (id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_contract_members_tenant FOREIGN KEY (tenant_id)
        REFERENCES tenants (id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
