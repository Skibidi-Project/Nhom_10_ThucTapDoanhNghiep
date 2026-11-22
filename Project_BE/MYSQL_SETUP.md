# MySQL setup cho nhóm

Backend dùng MySQL, không tự chuyển sang SQLite. Cài Python, MySQL client và `python -m pip install -r requirements.txt`. Cấu hình `DATABASE_URL` cho đúng máy chủ và database, cùng bí mật JWT theo cấu hình dự án. Không commit mật khẩu. Ví dụ PowerShell: `$env:DATABASE_URL = 'mysql+pymysql://USER:PASSWORD@HOST:3306/products_db'` (mã hóa URL các ký tự đặc biệt trong mật khẩu).

Chạy trong `Project_BE`:

```powershell
.\MYSQL_TEAM.ps1 -Action check
.\MYSQL_TEAM.ps1 -Action preflight
.\MYSQL_TEAM.ps1 -Action start
```

Nhập chính xác tên database mỗi lần. `check` kiểm tra kết nối và liệt kê bảng, cột, khóa ngoại theo model còn thiếu; đây không phải chứng nhận đầy đủ kiểu dữ liệu, index, quyền hay tính toàn vẹn. `preflight` chỉ đọc; xem thêm `MIGRATION_PREFLIGHT_REVIEW.md`. Sau khi chạy, đăng nhập tại http://127.0.0.1:8000/register/login.html. Trạng thái khởi động thành công được uvicorn in ra; lỗi schema sẽ làm ứng dụng dừng.

## Người quản lý database

Với database chung, chỉ một người phụ trách chạy migration; những người khác chỉ cấu hình kết nối và khởi động. Xác định host, database, phiên bản MySQL và cửa sổ bảo trì; ngừng ghi và DDL đồng thời. Kiểm tra đầy đủ schema, index, foreign key, engine, quyền và tình trạng migration trước khi phê duyệt.

Tạo backup nhất quán theo quy trình của tổ chức, gồm schema, dữ liệu, triggers, routines và events. Ví dụ dùng `mysqldump --single-transaction --routines --triggers --events --no-tablespaces --databases products_db` ghi vào tệp được bảo vệ; cấp thông tin đăng nhập qua cơ chế bảo mật của MySQL, không đưa mật khẩu vào dòng lệnh. Kiểm tra mã thoát, khôi phục vào server/database thử nghiệm riêng và đối chiếu dữ liệu trước khi xác nhận backup. Điều phối DDL và ghi đồng thời vì chúng có thể làm backup không nhất quán.

Sau preflight, backup đã khôi phục kiểm tra và phê duyệt của người quản lý, chạy ` .\MYSQL_TEAM.ps1 -Action migrate`. Script yêu cầu nhập tên database hai lần và xác nhận riêng backup cùng phê duyệt. Không chạy lên `products_db` nếu thiếu các điều kiện này. Runner chạy theo thứ tự US-26, US-20, US-24, US-25 và ghi checksum; lần chạy lại cùng batch được bỏ qua. Nó dừng khi có đối tượng đã tồn tại không được theo dõi hoặc migration dở dang: cần điều tra thủ công, không chạy lại mù quáng. MySQL DDL tự commit; lỗi giữa chừng không tự rollback. Các file rollback có thể xóa dữ liệu mới và không được chạy tự động.

Sau migration đối chiếu dữ liệu, index, foreign key và kiểm thử đăng nhập, hóa đơn, thanh toán, hạn thanh toán. Lịch sử giá cũ không được tạo giả; cần bằng chứng và nhập giá hợp lệ cho kỳ cần lập hóa đơn. Xem `MIGRATION_PREFLIGHT_REVIEW.md` để biết chi tiết và phục hồi.
