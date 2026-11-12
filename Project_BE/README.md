# FastAPI + MySQL: Register và Login

Backend local cho Windows: đăng ký, đăng nhập bằng email/SĐT và phân quyền theo vai trò.
Đăng nhập cấp JWT (hết hạn 24 giờ). Quyền được kiểm tra theo vai trò lưu ở server, không theo dữ liệu client.

## Cấu trúc

```text
app/
  __init__.py
  main.py
  core/       (__init__.py, config.py)
  db/         (__init__.py, database.py)
  models/     (__init__.py, user.py)
  schemas/    (__init__.py, user.py)
  routers/    (__init__.py, auth.py)
  services/   (__init__.py, user_service.py)
.env
.gitignore
requirements.txt
README.md
```

## Cài đặt và chạy

```powershell
python --version
python -m pip --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Get-Service *mysql*
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

`.env` chứa DATABASE_URL cho MySQL local theo cấu hình yêu cầu. Không đưa
file này lên Git hoặc dùng tài khoản root local cho môi trường production.
Ứng dụng đọc `.env` từ gốc dự án; biến môi trường hiện có được ưu tiên.
Startup kết nối server, chạy CREATE DATABASE IF NOT EXISTS với utf8mb4,
rồi tạo bảng users còn thiếu. Không sửa schema, xóa hoặc ghi đè dữ liệu cũ.

Swagger UI: http://127.0.0.1:8000/docs

## API

POST `/api/auth/register` → 201:

```json
{"full_name":"Nguyen Van A","email":"user@example.com","phone":"0912345678","password":"Password123"}
```

Họ tên được bỏ khoảng trắng ở hai đầu, dài 1–120 ký tự; email hợp lệ tối đa
255 ký tự; SĐT đúng 10 chữ số ASCII bắt đầu bằng 0. Mật khẩu dài 8–128 ký tự,
không chỉ gồm khoảng trắng; lưu dưới dạng Argon2.

POST `/api/auth/login` → 200:

```json
{"identifier":"user@example.com","password":"Password123"}
```

Có thể thay identifier bằng số điện thoại. Kết quả gồm message, access_token,
token_type và user (id, full_name, email, phone, role, created_at), không chứa
mật khẩu/hash. Gửi token ở header `Authorization: Bearer <access_token>` cho API
cần đăng nhập. Thời gian created_at là giờ local của server, không kèm múi giờ.

Đăng ký công khai luôn tạo vai trò `tenant`. Trường role, owner_id hoặc các trường
gán quyền trong body bị từ chối với HTTP 403. Chỉ admin đổi vai trò qua
`PUT /api/users/{id}/role`. Tài khoản admin đầu tiên được gán trực tiếp trong
database (`UPDATE users SET role='admin' WHERE email='...';`), không tự nâng qua API.

Vai trò: `admin`, `landlord` (chủ trọ), `manager` (người quản lý được giao khu trọ),
`tenant` (người thuê). Chưa đăng nhập: 401. Đã đăng nhập nhưng sai quyền hoặc ngoài
phạm vi dữ liệu: 403.

### Quản lý phòng

Các endpoint phòng yêu cầu quyền `PROPERTY_OPERATE`: landlord thao tác trên phòng
thuộc khu trọ mình sở hữu; manager thao tác trên khu trọ được gán. Tenant và tài
khoản chưa đăng nhập lần lượt nhận 403 và 401.

- `GET /api/properties/{property_id}/rooms` giữ nguyên danh sách phòng của một khu trọ.
- `POST /api/properties/{property_id}/rooms` tạo phòng (201), body gồm
  `room_number`, `base_rent` và `area_sqm` tùy chọn. Phòng mới luôn ở trạng thái
  `available`.
- `GET /api/rooms?page=1&page_size=10&search=P101&property_id=1&status=available`
  trả `{items, total, page, page_size}`. `page_size` tối đa 100; status nhận
  `available`, `occupied` hoặc `maintenance`.
- `GET /api/rooms/{room_id}` trả chi tiết phòng, tên khu trọ và thông tin hợp đồng
  hiện ở trạng thái `active` (nếu có).
- `PUT /api/rooms/{room_id}` nhận một phần các trường `room_number`, `area_sqm`,
  `base_rent`, `status`. Chỉ được đặt trạng thái thủ công thành `available` hoặc
  `maintenance`; phòng có hợp đồng `active` không được đổi trạng thái.
- `DELETE /api/rooms/{room_id}` trả 204. Phòng có hợp đồng hoạt động hoặc lịch sử
  hợp đồng/chỉ số điện nước không thể xóa.

Số phòng phải duy nhất trong một khu trọ; diện tích (m²) phải lớn hơn 0 và tối đa
2 chữ số thập phân; giá thuê là số nguyên không âm theo VNĐ. Cột diện tích mới
được bổ sung an toàn khi ứng dụng khởi động, không ghi đè dữ liệu phòng hiện có.
Seed demo tùy chọn nằm trong `seed_demo_rooms.sql`; script này không được ứng dụng
tự chạy.

## Phân quyền API

| API / nghiệp vụ | Vai trò được phép |
|---|---|
| `POST /api/auth/register`, `POST /api/auth/login` | Công khai; đăng ký luôn tạo `tenant` |
| `GET /api/users`, `PUT /api/users/{id}/role` | `admin` |
| `GET /api/users/{id}` | `admin` hoặc chính tài khoản đó |
| `/api/users/me` và `/api/users/me/contracts`, `/api/users/me/invoices` | Người dùng đã đăng nhập; chỉ dữ liệu cá nhân/thuê gắn với tài khoản |
| `/api/properties` | `landlord` xem/tạo khu trọ của mình; `manager` chỉ xem khu trọ được giao |
| `/api/properties/{id}` và `/api/properties/{id}/managers` | `landlord` sở hữu khu trọ; `manager` không sửa thông tin khu trọ hoặc gán quản lý |
| `/api/properties/{id}/rooms`, `/api/rooms`, `/api/rooms/{id}` (GET/PUT/DELETE) | `landlord` sở hữu hoặc `manager` được giao khu trọ |
| `/api/tenants`, `/api/contracts` | `landlord` hoặc `manager`, giới hạn theo phạm vi khu trọ |
| `/api/rooms/{id}/readings` | `landlord` sở hữu hoặc `manager` được giao khu trọ |
| `/api/invoices`, `/api/contracts/{id}/invoices`, `/api/invoices/{id}/payments` | `landlord`/`manager` trong phạm vi được phép; `tenant` chỉ xem hóa đơn của mình |

Lỗi: 422 khi dữ liệu không hợp lệ; 409 khi trùng email/SĐT, trùng số phòng hoặc
xung đột nghiệp vụ; 401 khi thông tin đăng nhập sai; 503 khi database gặp sự cố.
Không trả chi tiết SQL cho client.
Chỉ thử đăng ký tài khoản khi đã xác nhận database là môi trường thử nghiệm an toàn.

## Xử lý lỗi MySQL

- 2003: kiểm tra dịch vụ MySQL80 đang chạy, localhost và cổng 3306.
- 1045: kiểm tra thông tin đăng nhập trong `.env` bằng tài khoản MySQL hiện có.
- 1044/1142: nhờ quản trị viên cấp quyền truy cập database, CREATE DATABASE,
  CREATE TABLE và SELECT/INSERT cần thiết.
- Nếu bảng users đã tồn tại với schema khác, ứng dụng không tự thay đổi bảng;
  cần quản trị viên kiểm tra schema trước khi dùng.

Không tự đổi mật khẩu root, sửa MySQL Server hoặc xóa dữ liệu để xử lý lỗi.


## US-07 - Quản lý tòa nhà và tầng

- `GET/POST /api/properties/{property_id}/buildings`: danh sách và tạo tòa nhà.
- `GET/PUT/DELETE /api/buildings/{id}`: xem, sửa, xóa tòa nhà.
- `PUT /api/buildings/{id}/floors/{floor_id}`: đổi tên một tầng.
- Body tạo mới: `{"name":"Block A","floor_count":3,"floor_names":["Trệt","Lầu 1","Lầu 2"]}`.
- `floor_names` tùy chọn; mặc định tạo `Tầng 1`, `Tầng 2`, ...
- Tất cả endpoint yêu cầu `PROPERTY_OPERATE` và quyền trên khu trọ.
- Giao diện: `/register/properties.html` → nút Quản lý tòa nhà.
- Lưu ý: US-07 chưa gán `rooms` vào `floors`; thao tác đó thuộc US-09.
- Test: `pytest -q tests/test_us07_buildings.py` (SQLite bộ nhớ).
