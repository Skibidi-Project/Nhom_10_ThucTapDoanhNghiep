# Demo US-25 và US-27

Chạy trong PowerShell:

```powershell
cd C:\Users\nmthu\Documents\MiniStay_US20_New\MiniStay_US25_US27\Project_BE
.\START_DEMO.ps1
```

Script chỉ dùng SQLite tại `%TEMP%\ministay_us25_us27_demo.sqlite3`, kiểm tra schema, yêu cầu nhập mật khẩu mới tối thiểu 8 ký tự (và xác nhận khi tạo tài khoản). Lần sau nhập cùng mật khẩu. Dữ liệu demo được giữ lại sau mỗi lần chạy. Dừng bằng Ctrl+C; mỗi lần khởi động tạo JWT secret mới, vì vậy cần đăng nhập lại.

- Đăng nhập: http://127.0.0.1:8025/register/login.html
- Tài khoản: `landlord.us25.demo@example.com`; mật khẩu do người chạy nhập, không in trong log.
- API: http://127.0.0.1:8025/docs
- US-27: từ Quản lý cơ sở chọn Thống kê, hoặc http://127.0.0.1:8025/register/dashboard.html.
- US-25: mở giao diện thanh toán/hóa đơn, chọn hóa đơn và bấm Cập nhật trạng thái; thao tác này đối chiếu các giao dịch, không cho chọn trạng thái tùy ý.
- Dữ liệu ban đầu: một khu trọ, ba phòng (một đang thuê, một trống, một bảo trì), một hóa đơn kỳ hiện tại 1.000.000 đ và một khoản thu 300.000 đ. Dashboard kỳ hiện tại thể hiện số đã lập 1.000.000 đ, đã thu 300.000 đ và nợ 700.000 đ. Sau khi thêm thanh toán, các số sẽ thay đổi theo dữ liệu thật.

Giới hạn: backlog yêu cầu trạng thái quá hạn nhưng main chưa có hạn thanh toán và tài liệu chưa định nghĩa quy tắc tính hạn. Không tự gán quá hạn. Chi tiết acceptance criteria, quy tắc cập nhật thủ công, phạm vi thời gian và quyền admin cần nhóm xác nhận. Chrome headless đã kiểm tra một luồng thanh toán và dashboard trên desktop/mobile; chưa bao phủ mọi role và quá hạn.

Phương án lưu hạn và chứng từ chưa áp dụng: xem OVERDUE_DESIGN.md.
