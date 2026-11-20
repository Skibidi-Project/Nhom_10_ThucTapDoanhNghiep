-- US-24 - Seed demo tùy chọn cho thanh toán hóa đơn.
-- Chạy thủ công trong MySQL Workbench/phpMyAdmin sau khi các bảng đã tồn tại.
-- Script không ghi danh sách thanh toán và không thay đổi dữ liệu hiện có.
-- Lệnh mở: mysql -u <user> -p products_db < seed_demo_payments.sql

USE products_db;

INSERT INTO invoices (
    contract_id,
    period,
    rent_amount,
    utility_amount,
    total_amount,
    status,
    created_at
)
SELECT
    c.id,
    '2026-11',
    c.monthly_rent,
    150000,
    c.monthly_rent + 150000,
    'unpaid',
    CURRENT_TIMESTAMP
FROM rental_contracts c
WHERE c.status = 'active'
  AND NOT EXISTS (
      SELECT 1
      FROM invoices i
      WHERE i.contract_id = c.id
        AND i.period = '2026-11'
  );
