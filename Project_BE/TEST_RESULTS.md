# Kết quả kiểm thử tích hợp

- Pytest SQLite cô lập: 38 passed, 1 skipped; MySQL được chạy riêng.
- MySQL InnoDB test: 2 passed. Có luồng thật dùng duyệt thủ công, chỉ số, Wi-Fi, snapshot, thanh toán và hoàn cọc; kiểm tra hai request đồng thời, revision/ABA, deadlock và rollback. Một số test bổ sung vẫn mô phỏng chứng cứ; luồng hoàn cọc chính không mock.
- Chrome headless + SQLite tạm: PASS hai lượt luồng login → chỉ số → duyệt → hóa đơn → đối soát → thanh toán → hoàn cọc, mỗi lượt dùng viewport desktop rồi mobile. Không phải hai lượt E2E riêng biệt cho từng viewport hoặc Chrome trên MySQL.
- Demo setup: tạo và chạy lại idempotent trên SQLite tạm cô lập; chưa kiểm tra tương tác nhập mật khẩu thực trong mọi terminal Windows.

Chưa chứng minh toàn bộ regression US-26, hợp đồng tự động theo ngày/nguyên kỳ, thay/reset công tơ, điều chỉnh hóa đơn và lịch sử giá. Không test ghi hoặc chạy migration trên `products_db`. Tài liệu migration và các giới hạn còn lại: `migrations/INTEGRATION_REVIEW.md`, `migrations/FINAL_PERIOD_DESIGN_REVIEW.md`.
