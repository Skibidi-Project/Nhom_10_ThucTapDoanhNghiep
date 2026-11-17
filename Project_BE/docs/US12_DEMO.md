# Demo giao diện US-12

Chạy trong worktree `.release-us12`, nhánh `feature/thuc-us12`. Không cần MySQL,
không sửa `database.py`, `DATABASE_URL`, JWT/RBAC hoặc backend nghiệp vụ.

## PowerShell

```powershell
cd C:\Users\nmthu\Documents\Project_BE\Nhom_10_ThucTapDoanhNghiep\.release-us12\Project_BE
python -B demos/us12_demo.py
```

Cần các dependency backend hiện có (FastAPI, uvicorn, SQLAlchemy, PyMySQL,
argon2-cffi, PyJWT, email-validator). Frontend được phục vụ cùng backend,
không mở HTML bằng `file://` và không cần server frontend riêng.

1. Mở http://127.0.0.1:8012/register/login.html.
2. Đăng nhập `landlord@example.com`, mật khẩu demo công khai `DemoOnly!2026`.
3. Trang đăng nhập cũ chuyển sang properties.html; mở tiếp
   http://127.0.0.1:8012/register/contract-members.html?contract_id=1
   trong **cùng tab**. Không sửa cơ chế chuyển trang của đăng nhập.
4. Chụp trang có người đại diện Nguyễn Minh An và thành viên Trần Thu Hà.
5. Chọn Lê Hoàng Nam hoặc Phạm Ngọc Linh rồi thêm; xóa bằng nút Xóa và xác nhận.
6. Xóa hết thành viên để chụp empty state; người đại diện luôn được giữ.
7. Đổi mã hợp đồng thành 2 để xem hợp đồng hết hạn, không có nút thêm/xóa.

Các tài khoản giả dùng cùng mật khẩu demo, không dùng cho hệ thống thật:

| Email | Quyền trên hợp đồng 1 |
| --- | --- |
| landlord@example.com | Chủ trọ sở hữu: xem/thêm/xóa |
| manager@example.com | Quản lý được giao: xem/thêm/xóa |
| other@example.com | Chủ trọ khác: 403 |
| outsider@example.com | Quản lý cơ sở khác: 403 |
| tenant@example.com | Khách thuê: 403 |

Đăng nhập lại bằng trang cũ để đổi tài khoản. 403 giữ phiên, 401 xóa token
không hợp lệ và yêu cầu đăng nhập lại. Không hiển thị JWT trên trang demo.

## Dữ liệu và API thật

Entry point demo đăng ký **các router hiện có** và thay dependency `get_db`
bằng session SQLite riêng; không override người dùng/quyền hoặc cấp token giả.
Login thật xác minh mật khẩu Argon2, phát JWT bằng code hiện có. JWT secret
ngẫu nhiên chỉ trong tiến trình demo; khởi động lại cần đăng nhập lại.
Engine database ứng dụng bị chặn kết nối trong tiến trình demo.
Không khởi động lifespan `app.main`, không chạy SQL trên `products_db`.

SQLite `.us12-demo/demo.sqlite3` được seed lần đầu, giữ thay đổi sau khi thêm/xóa.
Thư mục có `.gitignore` riêng, chỉ chứa dữ liệu giả. Không tự reset hay xóa DB.
Để xem endpoint thật: http://127.0.0.1:8012/docs.

Trang gọi GET hợp đồng, GET tenants và ba API US-12 bằng Bearer JWT hiện có.
Danh sách lấy trực tiếp từ API; không mock hoặc lưu thành viên trong localStorage.
SQLite demo không kiểm chứng row locking InnoDB.

## Kiểm thử và ảnh minh chứng

Giữ server demo chạy trong cửa sổ PowerShell đầu tiên. Mở cửa sổ thứ hai,
vào cùng thư mục `Project_BE`, rồi chạy (đã thử với Node 26 và Microsoft Edge):

```powershell
node tests/test_us12_ui.cjs
```

Test dùng Edge headless và API localhost thật: chưa đăng nhập, Chủ trọ thêm,
hủy/xác nhận xóa, danh sách rỗng, hợp đồng hết hạn, Quản lý thêm/xóa,
403 giữ phiên cho ba tài khoản sai quyền, 401 yêu cầu đăng nhập lại và giao diện mobile.
Fixture UI mong đợi dữ liệu demo ban đầu có thành viên #2, chưa có #3.
Test thêm/xóa để khôi phục trạng thái ban đầu; không dùng database thật.
Không chạy đồng thời với thao tác thêm/xóa thủ công trên cùng database demo.

Ảnh được lưu tại `.us12-demo/us12-desktop.png` và `.us12-demo/us12-mobile.png`.
Database, profile trình duyệt và ảnh đều được bỏ qua bởi `.us12-demo/.gitignore`.
Test đăng nhập bằng API `/api/auth/login` hiện có, dùng JWT nhận từ backend
và mở thẳng US-12 để tránh bộ hẹn giờ chuyển sang trang cơ sở cũ.
Không thay code đăng nhập, không giả token hoặc bỏ qua kiểm tra quyền.

Trang này cũng được phục vụ tại `/register/contract-members.html` khi chạy
FastAPI hiện có với database **đã được người vận hành cấu hình an toàn**.
Không chạy ứng dụng chính bằng cấu hình database thật để thử demo này.
