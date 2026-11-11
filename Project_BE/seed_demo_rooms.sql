-- Seed tùy chọn cho MySQL local. Chạy thủ công sau khi có ít nhất một landlord.
-- Tạo 1 khu trọ, 4 phòng (đủ ba trạng thái), một khách thuê và một hợp đồng active.
USE products_db;

SET @landlord_id := (SELECT id FROM users WHERE role = 'landlord' ORDER BY id LIMIT 1);
START TRANSACTION;

INSERT INTO properties (
    owner_id, name, address, electricity_unit_price, water_unit_price, service_unit_price
)
SELECT @landlord_id, 'Khu trọ demo US-09', 'Địa chỉ demo', 3500, 15000, 0
WHERE @landlord_id IS NOT NULL;
SET @property_id := LAST_INSERT_ID();

INSERT INTO rooms (property_id, room_number, area_sqm, base_rent, status)
VALUES (@property_id, 'D101', 18.00, 2500000, 'available');
INSERT INTO rooms (property_id, room_number, area_sqm, base_rent, status)
VALUES (@property_id, 'D102', 22.50, 3000000, 'occupied');
INSERT INTO rooms (property_id, room_number, area_sqm, base_rent, status)
VALUES (@property_id, 'D103', 16.00, 2200000, 'maintenance');
INSERT INTO rooms (property_id, room_number, area_sqm, base_rent, status)
VALUES (@property_id, 'D104', 20.00, 2700000, 'available');

INSERT INTO tenants (landlord_id, created_by, full_name, phone, id_number)
VALUES (
    @landlord_id, @landlord_id, 'Khách thuê demo US-09', '0999990109',
    CONCAT('9', LPAD(@property_id, 11, '0'))
);
SET @tenant_id := LAST_INSERT_ID();

INSERT INTO rental_contracts (
    room_id, tenant_id, created_by, start_date, end_date, deposit, monthly_rent, status
)
SELECT id, @tenant_id, @landlord_id, '2026-01-01', '2027-01-01', 3000000, 3000000, 'active'
FROM rooms
WHERE property_id = @property_id AND room_number = 'D102';

COMMIT;
