# Kết quả kiểm thử US-25 / US-27

- `DATABASE_URL=sqlite://` và secret test, `python -m pytest -q -p no:cacheprovider`: **9 PASS, 0 FAIL**; gồm 2 test mới, không bao phủ đầy đủ mọi trường hợp backlog.
- MySQL InnoDB database riêng `ministay_us25_test_e2a7fa0cd284`: **PASS** hai HTTP thanh toán đồng thời 40/60, kiểm tra trạng thái, công nợ/dashboard và chặn trả vượt. Không test ghi products_db.
- Demo setup SQLite cô lập: **PASS** chạy hai lần và giữ idempotence.
- `node --check register/dashboard.js` và `node --check register/payments.js`: **PASS** cú pháp.
- Chrome E2E desktop/mobile: **PASS một luồng**: Chrome headless, backend thực qua START_DEMO.ps1, đăng nhập, chưa thanh toán → một phần → đủ, đối chiếu trạng thái, KPI, bộ lọc, desktop/mobile, console và API. Chưa kiểm thử quá hạn hoặc mọi vai trò trên Chrome.
- Regression US-22/US-24: **PARTIAL**, pytest hiện có và ca thanh toán MySQL ở trên; chưa kiểm thử tất cả luồng UI, rollback, deadlock và concurrency.
- Login qua Chrome: **PASS**; rooms và contracts: **SKIP** kiểm thử đầy đủ qua trình duyệt.
- Trạng thái quá hạn và quy tắc cập nhật thủ công đầy đủ: **BLOCKED** bởi đặc tả/schema thiếu; không tự suy diễn.
- Lỗi đã sửa: khi hai giao dịch thanh toán đồng thời trong MySQL repeatable-read, tính trạng thái dựa vào snapshot cũ có thể sai; nay khóa invoice và các khoản thanh toán, tính từ dữ liệu khóa hiện hành.

Các kiểm tra chưa chạy không được xem là PASS. Không có migration trong thay đổi này; startup main có DDL nên chỉ chạy server với SQLite demo riêng.
