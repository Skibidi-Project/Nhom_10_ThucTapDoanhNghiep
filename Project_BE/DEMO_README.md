# Demo US-25 và US-27

```powershell
cd C:\Users\nmthu\Documents\MiniStay_US20_New\MiniStay_US25_US27\Project_BE
.\START_DEMO.ps1
```

Script dùng SQLite riêng `%TEMP%\ministay_us25_us27_demo.sqlite3`; nhập mật khẩu cho tài khoản `landlord.us25.demo@example.com` (nhập lại khi tạo). Nếu cổng 8025 đã được sử dụng, chạy `$env:MINISTAY_DEMO_PORT='8026'` trước lệnh trên và dùng cổng đó. Script không sử dụng products_db.

Mở http://127.0.0.1:8025/register/login.html rồi đến trang thanh toán. Demo có hóa đơn chưa trả, trả một phần, đã trả và quá hạn. Nút đặt hạn yêu cầu ngày và căn cứ; các thay đổi được lưu lịch sử. Lọc trạng thái Quá hạn để xem các khoản còn nợ sau ngày hạn theo giờ Việt Nam. Mở Thống kê từ trang cơ sở để xem dashboard. Dừng server bằng Ctrl+C. Dữ liệu demo đã thao tác được giữ lại khi khởi động lại.

Khi chạy với MySQL đã có schema, phải sao lưu và áp dụng migration `migrations/us25_due_date_mysql.sql` theo quy trình của nhóm trước khi khởi động. SQL chỉ chạy một lần, không tự kết nối. Kiểm tra cột và bảng hiện có trước khi áp dụng; MySQL DDL tự commit, cần kế hoạch khôi phục backup nếu chạy lỗi giữa chừng. `migrations/us25_due_date_mysql_rollback.sql` xóa cột và toàn bộ lịch sử hạn, chỉ dùng sau sao lưu và phê duyệt. Startup main còn DDL cũ và có thể tạo bảng, nên không chạy thử với products_db. Chạy `pip install -r requirements.txt` nếu thiếu tzdata.
