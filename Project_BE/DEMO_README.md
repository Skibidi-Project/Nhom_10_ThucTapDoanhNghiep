# Demo MiniStay tích hợp

```powershell
cd C:\Users\nmthu\Documents\MiniStay_US20_New\MiniStay_Unified\Project_BE
.\START_DEMO.ps1
```

Script chỉ dùng SQLite `%TEMP%\ministay_us25_us27_demo.sqlite3` và yêu cầu mật khẩu cho `landlord.us25.demo@example.com`. Nếu cổng 8025 bận, đặt `$env:MINISTAY_DEMO_PORT='18145'` rồi chạy script. Mở URL đăng nhập được in ra. Dừng bằng Ctrl+C.

Chọn **Điện/nước**, hợp đồng Demo D01 và kỳ tháng sau. Dữ liệu thử có giá khu trọ và chỉ số tổng hợp rõ ràng cho kỳ này. Xem preview rồi chọn Chốt hóa đơn. Khi kỳ đã chốt, chọn kỳ thử nghiệm khác có dữ liệu hợp lệ; không seed lại hóa đơn. Nhập lịch sử giá có chứng cứ trong mục trên trang; hệ thống không tự chuyển giá hiện tại thành giá lịch sử. Giá không có đủ hiệu lực cả tháng, chỉ số bị thiếu, hoặc giá thay đổi giữa tháng sẽ chặn tính và lập hóa đơn. Hiện chỉ dùng chỉ số đã ghi bằng quy trình sẵn có; chưa tích hợp chỉnh sửa US-19.

Chọn **Hóa đơn & Thanh toán** để thanh toán và đối chiếu, **Tổng quan** để xem dashboard. Dữ liệu demo được giữ giữa các lần chạy và sẽ thay đổi sau thao tác. Không kết nối products_db để kiểm thử.

## Migration trước production

Nhóm phải review, backup, kiểm tra schema và phê duyệt trước khi áp dụng một lần: `migrations/us25_due_date_mysql.sql`, `migrations/us24_payment_idempotency_mysql.sql` và `migrations/us20_dated_prices_mysql.sql` theo trạng thái schema hiện tại. US-20 tạo bảng lịch sử giá và snapshot, không tự nhập giá cũ. MySQL DDL tự commit; rollback `us20_dated_prices_mysql_rollback.sql` xóa lịch sử và snapshot, chỉ chạy sau lưu trữ, backup và phê duyệt. Không chạy migration tự động trên products_db. Startup main còn DDL cũ, và chặn MySQL đã có invoices nếu thiếu schema US-20.

US-24: giao diện dùng Idempotency-Key; client cũ không gửi khóa không được bảo vệ retry. Nếu thiếu dependency chạy `.venv\Scripts\python.exe -m pip install -r requirements.txt`.
