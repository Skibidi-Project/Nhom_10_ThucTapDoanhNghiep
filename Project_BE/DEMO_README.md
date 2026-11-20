# MiniStay US-16 / US-19 — demo cục bộ

Trong PowerShell trên Windows, tại `Project_BE`:

```powershell
powershell -ExecutionPolicy Bypass -File .\START_DEMO.ps1
```

Script dùng `.venv` trong workspace, tạo/kiểm tra SQLite riêng `%TEMP%\ministay_business_e2e_manual_demo.sqlite3`, nhập mật khẩu tài khoản demo bằng `getpass`, tạo JWT secret ngẫu nhiên trong tiến trình và mở server tại `http://127.0.0.1:8016/register/login.html`. Email: `landlord.final.demo@example.com`. Không dùng `products_db`. Chạy lại với đúng mật khẩu đã chọn; script không đổi mật khẩu hay xóa dữ liệu cũ. Hợp đồng đã quyết toán không được tự tạo lại; dùng môi trường thử mới nếu cần một kịch bản sạch.

1. Đăng nhập, vào **Quản lý phòng**, chọn `DEMO-01`, ghi chỉ số điện và nước trong kỳ hiện tại. Ghi chỉ số cũ là 0 cho kịch bản mới.
2. Vào **Quản lý hợp đồng**, chuyển hợp đồng sang chờ thanh lý và chọn **Thanh lý hợp đồng**. Xác nhận thời điểm bàn giao và hai chỉ số vừa ghi.
3. Trong phần thử nghiệm, tạo yêu cầu và landlord duyệt riêng tiền phòng, điện, nước và từng dịch vụ đã gán. Nhập phương pháp, số tiền và căn cứ; bản demo không tự áp giá lịch sử hoặc chia ngày. Phát hành hóa đơn cuối kỳ thử.
4. Xem snapshot và xác nhận đối soát, nhập lý do và xác nhận bàn giao. Khi còn nợ, hoàn cọc bị khóa.
5. Vào `http://127.0.0.1:8016/register/payments.html`, thanh toán hóa đơn bằng dữ liệu demo. Quay lại modal thanh lý và ghi nhận hoàn cọc.

Đây là demo cô lập, không phải triển khai production. Hợp đồng cũ thiếu điều khoản cần duyệt thủ công. Bản thử chưa hỗ trợ tự động tính theo điều khoản, lịch sử giá có hiệu lực, thay/reset công tơ hoặc điều chỉnh hóa đơn. Các writer cũ và truy cập database trực tiếp không tuân theo khóa/version thử nghiệm. Migration phải review và thử triển khai/rollback trước khi sử dụng trên môi trường thật. Khi demo server dừng, JWT secret tạm cũng mất hiệu lực.
