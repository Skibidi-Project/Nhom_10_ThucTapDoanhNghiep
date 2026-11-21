# Demo MiniStay tích hợp

```powershell
cd C:\Users\nmthu\Documents\MiniStay_US20_New\MiniStay_Unified\Project_BE
.\START_DEMO.ps1
```

Script kiểm tra .venv, chỉ dùng SQLite tại `%TEMP%\ministay_us25_us27_demo.sqlite3`, chuẩn bị schema demo và yêu cầu mật khẩu cho `landlord.us25.demo@example.com`. Nếu cổng 8025 bận, trước khi chạy đặt `$env:MINISTAY_DEMO_PORT='18145'` và dùng cổng đó. Mở URL đăng nhập được script in ra, sau đó dùng menu chính. Từ Quản lý phòng chọn Lịch sử điện/nước; Hóa đơn & Thanh toán cho US-24/25; Tổng quan cho US-27. Dừng bằng Ctrl+C. Mật khẩu không được ghi vào script.

Dữ liệu demo được giữ giữa các lần chạy; nếu account đã tồn tại, nhập đúng mật khẩu đã tạo. Lần đầu có ba phòng, hóa đơn nhiều trạng thái và hai chỉ số mẫu. Các giao dịch mới làm thay đổi số liệu.

Không kết nối products_db để test. MySQL cũ cần migration `migrations/us25_due_date_mysql.sql` được duyệt trước startup; backup, kiểm tra schema trước khi áp dụng một lần vì MySQL DDL tự commit. Rollback `migrations/us25_due_date_mysql_rollback.sql` xóa cột và lịch sử nên cần sao lưu, duyệt và lưu trữ trước. Cài dependencies bằng `.venv\Scripts\python.exe -m pip install -r requirements.txt` nếu thiếu. Xem INTEGRATION_STATUS.md để biết phần chưa tích hợp.
