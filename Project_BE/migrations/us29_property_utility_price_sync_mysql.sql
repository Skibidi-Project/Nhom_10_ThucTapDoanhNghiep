-- US-29: Đồng bộ giá điện/nước giữa cột properties và bảng property_service_prices.
-- Chạy MỘT LẦN trên cơ sở dữ liệu MySQL hiện có, SAU KHI ĐÃ SAO LƯU dữ liệu.
-- Không bắt buộc cho việc khởi động ứng dụng; ứng dụng KHÔNG tự chạy file này.
-- Idempotent: có thể chạy lại nhiều lần mà không gây tác dụng phụ (UPDATE an toàn, INSERT có NOT EXISTS).
--
-- (a) Với dòng property_service_prices electricity đơn vị kwh và water đơn vị m3 đã tồn tại,
--     cập nhật cột properties tương ứng theo giá cấu hình (giá cấu hình thắng vì hóa đơn đang tính theo đó).
-- (b) Với cơ sở có cột giá > 0 mà chưa có dòng cấu hình tương ứng, chèn dòng cấu hình (kwh / m3).

-- (a) Cập nhật electricity_unit_price từ cấu hình electricity/kwh đã tồn tại.
UPDATE properties p
JOIN property_service_prices esp
  ON esp.property_id = p.id
  AND esp.service_code = 'electricity'
  AND esp.billing_unit = 'kwh'
SET p.electricity_unit_price = esp.unit_price;

-- (a) Cập nhật water_unit_price từ cấu hình water/m3 đã tồn tại.
UPDATE properties p
JOIN property_service_prices wsp
  ON wsp.property_id = p.id
  AND wsp.service_code = 'water'
  AND wsp.billing_unit = 'm3'
SET p.water_unit_price = wsp.unit_price;

-- (b) Chèn cấu hình electricity/kwh cho cơ sở có giá điện > 0 chưa có dòng.
INSERT INTO property_service_prices (property_id, service_code, billing_unit, unit_price)
SELECT p.id, 'electricity', 'kwh', p.electricity_unit_price
FROM properties p
WHERE p.electricity_unit_price > 0
  AND NOT EXISTS (
    SELECT 1
    FROM property_service_prices esp
    WHERE esp.property_id = p.id
      AND esp.service_code = 'electricity'
      AND esp.billing_unit = 'kwh'
  );

-- (b) Chèn cấu hình water/m3 cho cơ sở có giá nước > 0 chưa có dòng.
INSERT INTO property_service_prices (property_id, service_code, billing_unit, unit_price)
SELECT p.id, 'water', 'm3', p.water_unit_price
FROM properties p
WHERE p.water_unit_price > 0
  AND NOT EXISTS (
    SELECT 1
    FROM property_service_prices wsp
    WHERE wsp.property_id = p.id
      AND wsp.service_code = 'water'
      AND wsp.billing_unit = 'm3'
  );