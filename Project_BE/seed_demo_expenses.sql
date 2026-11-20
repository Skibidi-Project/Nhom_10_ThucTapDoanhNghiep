-- Chay thu cong trong MySQL Workbench/CLI sau khi ung dung da khoi dong.
-- Script khong tu dong chay, idempotent va chi lay khu tro dau tien cua landlord@gmail.com.
-- mysql -u root -p products_db < seed_demo_expenses.sql

INSERT INTO expenses (property_id, room_id, category, description, vendor, amount, expense_date, created_by)
SELECT p.id, r.id, 'repair', 'Sua voi nuoc phong 101', 'Thay Thep', 350000,
       CURDATE() - INTERVAL 18 DAY, u.id
FROM users u
JOIN properties p ON p.owner_id = u.id
LEFT JOIN rooms r ON r.property_id = p.id AND r.room_number = '101'
WHERE u.email = 'landlord@gmail.com'
  AND p.id = (SELECT MIN(p2.id) FROM properties p2 WHERE p2.owner_id = u.id)
  AND NOT EXISTS (
      SELECT 1 FROM expenses e
      WHERE e.property_id = p.id AND e.description = 'Sua voi nuoc phong 101'
  )
LIMIT 1;

INSERT INTO expenses (property_id, room_id, category, description, vendor, amount, expense_date, created_by)
SELECT p.id, NULL, 'repair', 'Thay bong den hanh lang', 'Dien Lan Anh', 180000,
       CURDATE() - INTERVAL 52 DAY, u.id
FROM users u JOIN properties p ON p.owner_id = u.id
WHERE u.email = 'landlord@gmail.com'
  AND p.id = (SELECT MIN(p2.id) FROM properties p2 WHERE p2.owner_id = u.id)
  AND NOT EXISTS (SELECT 1 FROM expenses e WHERE e.property_id = p.id AND e.description = 'Thay bong den hanh lang')
LIMIT 1;

INSERT INTO expenses (property_id, room_id, category, description, vendor, amount, expense_date, created_by)
SELECT p.id, NULL, 'supplies', 'Mua vat tu ve sinh', 'Sieuthi An Tam', 520000,
       CURDATE() - INTERVAL 35 DAY, u.id
FROM users u JOIN properties p ON p.owner_id = u.id
WHERE u.email = 'landlord@gmail.com'
  AND p.id = (SELECT MIN(p2.id) FROM properties p2 WHERE p2.owner_id = u.id)
  AND NOT EXISTS (SELECT 1 FROM expenses e WHERE e.property_id = p.id AND e.description = 'Mua vat tu ve sinh')
LIMIT 1;

INSERT INTO expenses (property_id, room_id, category, description, vendor, amount, expense_date, created_by)
SELECT p.id, NULL, 'operations', 'Bao tri may bom nuoc', 'Co Khi Minh', 900000,
       CURDATE() - INTERVAL 68 DAY, u.id
FROM users u JOIN properties p ON p.owner_id = u.id
WHERE u.email = 'landlord@gmail.com'
  AND p.id = (SELECT MIN(p2.id) FROM properties p2 WHERE p2.owner_id = u.id)
  AND NOT EXISTS (SELECT 1 FROM expenses e WHERE e.property_id = p.id AND e.description = 'Bao tri may bom nuoc')
LIMIT 1;

INSERT INTO expenses (property_id, room_id, category, description, vendor, amount, expense_date, created_by)
SELECT p.id, r.id, 'cleaning', 'Ve sinh phong 101 sau khi trao tra', 'Dich vu Sach Xanh', 300000,
       CURDATE() - INTERVAL 9 DAY, u.id
FROM users u JOIN properties p ON p.owner_id = u.id
LEFT JOIN rooms r ON r.property_id = p.id AND r.room_number = '101'
WHERE u.email = 'landlord@gmail.com'
  AND p.id = (SELECT MIN(p2.id) FROM properties p2 WHERE p2.owner_id = u.id)
  AND NOT EXISTS (SELECT 1 FROM expenses e WHERE e.property_id = p.id AND e.description = 'Ve sinh phong 101 sau khi trao tra')
LIMIT 1;

INSERT INTO expenses (property_id, room_id, category, description, vendor, amount, expense_date, created_by)
SELECT p.id, NULL, 'other', 'Phi xit muoi va khu khuan khu vuc chung', NULL, 250000,
       CURDATE() - INTERVAL 43 DAY, u.id
FROM users u JOIN properties p ON p.owner_id = u.id
WHERE u.email = 'landlord@gmail.com'
  AND p.id = (SELECT MIN(p2.id) FROM properties p2 WHERE p2.owner_id = u.id)
  AND NOT EXISTS (SELECT 1 FROM expenses e WHERE e.property_id = p.id AND e.description = 'Phi xit muoi va khu khuan khu vuc chung')
LIMIT 1;
