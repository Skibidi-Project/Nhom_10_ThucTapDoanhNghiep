# Demo US-19 — Điện / nước theo tháng

## Chạy bằng PowerShell

```powershell
cd C:\Users\nmthu\Documents\Project_BE\Nhom_10_ThucTapDoanhNghiep\.release-us19\Project_BE
python -B demos/us19_demo.py
```

Dùng dependency backend hiện có: FastAPI, uvicorn, SQLAlchemy, PyMySQL,
argon2-cffi, PyJWT và email-validator. Không thay `DATABASE_URL` hoặc database.py.
Frontend phục vụ cùng origin FastAPI, không cần server frontend riêng.

- Đăng nhập: http://127.0.0.1:8019/register/login.html
- Giao diện: http://127.0.0.1:8019/register/utility-readings.html?room_id=1
- Swagger: http://127.0.0.1:8019/docs

Đăng nhập bằng form hiện có rồi mở giao diện trong **cùng tab**.
Trang login cũ chuyển sang properties.html; giữ nguyên hành vi code cũ.

Mật khẩu công khai cho tất cả tài khoản **giả trong SQLite demo**: `DemoOnly!2026`.

| Email | Quyền với phòng 1 |
| --- | --- |
| landlord@example.com | Chủ trọ sở hữu, xem và ghi |
| manager@example.com | Quản lý được giao, xem và ghi |
| other@example.com | Chủ trọ khác, 403 |
| outsider@example.com | Quản lý cơ sở khác, 403 |
| tenant@example.com | Khách thuê, 403 |
| admin@example.com | Admin chưa được cấp UTILITY_MANAGE, 403 |

Không dùng tài khoản demo cho hệ thống thật. Không hardcode hoặc hiển thị JWT.
403 giữ phiên trên trang US-19; 401 xóa token không hợp lệ và yêu cầu login lại.
Trang properties cũ có thể từ chối tenant/admin. Test đăng nhập qua API
`/api/auth/login` hiện có và mở thẳng US-19 bằng JWT do backend cấp để tránh
bộ hẹn giờ điều hướng của trang login cũ. Không giả token hoặc bỏ qua quyền.

## Dữ liệu và thao tác minh chứng

SQLite `.us19-demo/demo.sqlite3` độc lập, bật FK, chỉ chứa dữ liệu mẫu.
Seed lần đầu: phòng 1 có điện 2026-01 (1000→1120), 2026-02 (1120→1255),
nước 2026-01 (100→112), 2026-02 (112→126). Phòng 3 cùng chủ chưa có chỉ số.
Khởi động lại giữ nguyên dữ liệu đã ghi, không reset/xóa database.

1. Mở phòng 1 và chụp bảng chỉ số đầu/cuối kỳ, lượng tiêu thụ và form.
2. Chọn điện. Nhập kỳ mới lớn hơn kỳ gần nhất, đầu kỳ đúng chỉ số cuối gần nhất,
   cuối kỳ lớn hơn đầu kỳ (ví dụ seed mới: 2026-03, 1255, 1390). Bấm Ghi chỉ số.
3. Ghi lại tháng đó để chụp lỗi 409 trùng kỳ.
4. Nhập 2025-12 để chụp lỗi 409 tháng lùi.
5. Chọn kỳ lớn hơn kỳ gần nhất nhưng sửa đầu kỳ lệch 1 để chụp lỗi 409 liên tục.
6. Cuối kỳ nhỏ hơn đầu kỳ sẽ được API từ chối 422. Trường bắt buộc, số nguyên,
   số âm và định dạng tháng có validation trình duyệt cơ bản; API vẫn kiểm tra.
7. Đổi sang nước để thấy chuỗi độc lập. Tháng mới có thể bỏ cách tháng.
8. Mở `?room_id=3` để xem empty state (trước lần ghi đầu tiên).

Trang gọi GET/POST `/api/rooms/{room_id}/readings` thật. Gợi ý đầu kỳ/tháng
được tính từ response API; không giả lập lưu hoặc thành công bằng JavaScript.
Tiêu thụ hiển thị bằng cuối kỳ trừ đầu kỳ, không tính tiền hoặc tạo hóa đơn.
Lỗi nghiệp vụ hiển thị mã HTTP và nội dung trả từ backend.

Demo đăng ký nguyên các router hiện có và chỉ override session `get_db` sang
SQLite riêng. Login Argon2, JWT và kiểm tra quyền/scope dùng code thật nguyên vẹn.
Signing secret ngẫu nhiên chỉ trong tiến trình demo; restart cần login lại.
Engine ứng dụng bị chặn kết nối trong tiến trình demo, không chạy lifespan
`app.main`, không đọc/ghi `products_db`. Không có OTP/SMTP hoặc US-12.
SQLite không kiểm chứng row locking/đồng thời InnoDB.

## Test UI và ảnh

Giữ server chạy, mở PowerShell thứ hai trong `Project_BE`:

```powershell
node tests/test_us19_ui.cjs
```

Dùng Node 26 và Edge headless, API thật, không mock. Test ghi một kỳ mới nên
chỉ chạy trên database demo này; không thao tác thủ công đồng thời.
Ảnh desktop lưu `.us19-demo/us19-desktop.png`.
Toàn bộ database, ảnh và browser profile được bỏ qua bởi `.us19-demo/.gitignore`.
