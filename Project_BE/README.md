# FastAPI + MySQL: Register và Login

Backend local cho Windows, chỉ có đăng ký và đăng nhập bằng email/SĐT.
Không phát hành token hoặc tạo phiên đăng nhập.

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

Có thể thay identifier bằng số điện thoại. Kết quả gồm message và user
(id, full_name, email, phone, created_at), không chứa mật khẩu/hash.
Thời gian created_at là giờ local của server, không kèm múi giờ.

Lỗi: 422 khi dữ liệu không hợp lệ; 409 khi trùng email/SĐT; 401 khi thông tin
đăng nhập sai; 503 khi database gặp sự cố. Không trả chi tiết SQL cho client.
Chỉ thử đăng ký tài khoản khi đã xác nhận database là môi trường thử nghiệm an toàn.

## Xử lý lỗi MySQL

- 2003: kiểm tra dịch vụ MySQL80 đang chạy, localhost và cổng 3306.
- 1045: kiểm tra thông tin đăng nhập trong `.env` bằng tài khoản MySQL hiện có.
- 1044/1142: nhờ quản trị viên cấp quyền truy cập database, CREATE DATABASE,
  CREATE TABLE và SELECT/INSERT cần thiết.
- Nếu bảng users đã tồn tại với schema khác, ứng dụng không tự thay đổi bảng;
  cần quản trị viên kiểm tra schema trước khi dùng.

Không tự đổi mật khẩu root, sửa MySQL Server hoặc xóa dữ liệu để xử lý lỗi.
