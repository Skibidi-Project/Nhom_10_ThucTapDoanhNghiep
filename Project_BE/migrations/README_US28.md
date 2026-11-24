# US-28: Service configured utility prices

Utility invoice snapshots can now use electricity and water prices from
`property_service_prices`. Their `price_id` is nullable for these snapshots;
existing snapshots that reference `utility_price_history` keep their values.

For an existing MySQL database, apply `us28_service_price_snapshots_mysql.sql`
once before restarting the application. SQLite databases receive the updated
nullable column from the SQLAlchemy model when initialized.

## US-29 (đồng bộ giá điện/nước)

Apply `us29_property_utility_price_sync_mysql.sql` một lần trên cơ sở dữ liệu MySQL
hiện có, sau khi đã sao lưu, để đồng bộ cột `properties.electricity_unit_price` /
`properties.water_unit_price` với bảng `property_service_prices` (dịch vụ electricity
đơn vị kwh và water đơn vị m3). File này idempotent, không bắt buộc cho việc khởi
động ứng dụng và ứng dụng KHÔNG tự chạy nó.
