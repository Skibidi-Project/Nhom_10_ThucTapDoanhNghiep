CREATE DATABASE IF NOT EXISTS products_db
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE products_db;

SELECT DATABASE();
SHOW TABLES;

	USE products_db;

	SHOW TABLES;

	-- Bổ sung kỳ thanh toán cho rental_contracts trên database đã tồn tại.
	-- Ứng dụng cũng tự kiểm tra/thêm cột này khi khởi động.
	SET @rental_contracts_table_exists := (
	    SELECT COUNT(*)
	    FROM information_schema.tables
	    WHERE table_schema = DATABASE()
	      AND table_name = 'rental_contracts'
	);
	SET @payment_cycle_column_exists := (
	    SELECT COUNT(*)
	    FROM information_schema.columns
	    WHERE table_schema = DATABASE()
	      AND table_name = 'rental_contracts'
	      AND column_name = 'payment_cycle_months'
	);
	SET @payment_cycle_migration := IF(
	    @rental_contracts_table_exists > 0 AND @payment_cycle_column_exists = 0,
	    'ALTER TABLE rental_contracts ADD COLUMN payment_cycle_months INT NOT NULL DEFAULT 1',
	    'SELECT 1'
	);
	PREPARE payment_cycle_statement FROM @payment_cycle_migration;
	EXECUTE payment_cycle_statement;
	DEALLOCATE PREPARE payment_cycle_statement;
    
    USE products_db;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(20) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'tenant',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

SHOW TABLES;