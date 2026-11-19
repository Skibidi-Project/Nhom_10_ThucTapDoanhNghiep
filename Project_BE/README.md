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

### Lập hợp đồng thuê

`POST /api/contracts` tạo hợp đồng (201) cho phòng đang trống. Body yêu cầu
`room_id`, `tenant_id`, `start_date`, `end_date`, `monthly_rent`; `deposit`
mặc định 0 và `payment_cycle_months` mặc định 1. Kỳ thanh toán chỉ nhận 1, 2, 3,
6 hoặc 12 tháng. Ngày kết thúc phải sau ngày bắt đầu; ngày bắt đầu không được
quá một năm trong quá khứ và thời hạn không vượt quá 10 năm. Tiền thuê phải lớn
hơn 0; tiền cọc không âm và tối đa bằng 3 tháng tiền thuê.

Landlord chỉ lập hợp đồng cho khu trọ mình sở hữu; manager chỉ cho khu trọ được
giao. Khách thuê đại diện phải thuộc cùng landlord sở hữu khu trọ. Phòng phải
đang trống; hợp đồng active có khoảng ngày giao với hợp đồng mới gây HTTP 409.
Việc tạo hợp đồng và chuyển phòng sang `occupied` được lưu trong cùng transaction.
`GET /api/contracts`, `GET /api/contracts/{id}` và response tạo mới bao gồm số
phòng, mã/tên khu trọ và tên khách thuê. `rental_contracts.payment_cycle_months`
được ứng dụng tự bổ sung an toàn khi khởi động; có thể áp dụng script tương ứng
trong `sql.sql` thủ công nếu cần.

### Gia hạn hợp đồng thuê

- `POST /api/contracts/{id}/extend` gia hạn một hợp đồng hiện có. Body:
  `{"new_end_date":"2027-12-31","new_monthly_rent":3500000,"note":"Gia hạn 1 năm"}`
  `new_monthly_rent` tùy chọn và bỏ trống để giữ nguyên giá; `note` tối đa 255 ký
  tự. Dữ liệu ngoài schema bị từ chối.
- `GET /api/contracts/{id}/extensions` trả lịch sử gia hạn của hợp đồng, sắp xếp
  mới nhất trước.

Gia hạn được phép cho hợp đồng `active` hoặc `created`. Hợp đồng `pending_liquidation`
do hết hạn tự nhiên mới được gia hạn nếu ngày hết hạn cũ nhỏ hơn hôm nay, tiền cọc
chưa hoàn trả hoặc khấu trừ; hợp đồng chấm dứt sớm bị chặn. Hợp đồng `expired`
không thể gia hạn. Ngày hết hạn mới phải sau hạn cũ, hợp đồng quá hạn phải gia hạn
đến từ hôm nay trở đi, và thời hạn không được vượt quá 10 năm kể từ ngày bắt đầu.
Gia hạn không được làm trùng khoảng thời gian với hợp đồng `active`/`created`
khác của cùng phòng.

Giá thuê mới ghi thẳng vào hợp đồng và bảng lịch sử. Các hóa đơn đã tạo giữ nguyên
`rent_amount`; giá mới chỉ áp dụng cho hóa đơn được tạo sau thời điểm gia hạn.
Gia hạn không thay đổi tiền cọc, trạng thái cọc hoặc các trường thanh lý.

Bảng `contract_extensions` được tạo tự động cùng `Base.metadata.create_all`; không
cần thêm cột nào vào `rental_contracts`.

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
| `/api/contracts/{id}/extend`, `/api/contracts/{id}/extensions` | `landlord` sở hữu khu trọ hoặc `manager` được giao khu trọ |
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

## US-18 - Gán dịch vụ cho phòng và hợp đồng

- Giao diện: `/register/services.html`. Chọn khu trọ, chọn phòng hoặc hợp đồng chưa kết thúc, rồi gán dịch vụ trong danh mục hệ thống. US-18 không cấu hình đơn giá.
- Giao diện lấy tên và mã danh mục qua `GET /api/properties/{property_id}/service-prices`; đơn giá không được hiển thị hoặc chỉnh sửa trên trang này.
- `GET/POST /api/service-assignments` và `PUT/DELETE /api/service-assignments/{id}` xem, gán, đổi dịch vụ hoặc gỡ assignment. `POST` cần `service_code` cùng một trong `room_id` hoặc `contract_id`; `quantity` mặc định là 1.
- `GET /api/contracts/{id}/services` trả danh sách dịch vụ hiệu lực, ưu tiên gán trực tiếp cho hợp đồng so với dịch vụ kế thừa từ phòng.
- Các endpoint yêu cầu đăng nhập và quyền `UTILITY_MANAGE`; landlord/manager chỉ thao tác trong phạm vi khu trọ được phép.
- Test: `pytest -q tests/test_service_assignments.py` (SQLite bộ nhớ).

## US-24 - Ghi nhận thanh toán hóa đơn

- `POST /api/invoices/{invoice_id}/payments`: landlord/manager ghi nhận một khoản thanh toán.
- `GET /api/invoices/{invoice_id}/payments`: xem lịch sử thanh toán, mới nhất trước.
- `GET /api/invoices`: bổ sung bộ lọc tùy chọn `status`, `period=YYYY-MM`, `contract_id`.
- `GET /api/invoices/{invoice_id}`: trả thêm `paid_amount`, `remaining_amount`, tên phòng/khu trọ/khu vực khách thuê.
- Trang giao diện: mở `/register/payments.html` bằng server đang chạy.

Body ghi nhận thanh toán:

```json
{
  "amount": 150000,
  "method": "cash",
  "paid_at": "2026-11-18T00:00:00",
  "note": "Thanh toan tien dien nuoc"
}
```

`method` chỉ nhận `cash` hoặc `bank_transfer`. `paid_at` tùy chọn, không được nằm trong tương lai.
`note` tùy chọn, tối đa 255 ký tự. Extra field bị từ chối bằng HTTP 422.

Hệ thống chặn thanh toán vượt số còn nợ và trả HTTP 409 kèm số còn thiếu. Không ghi nhận tiền thừa;
hoàn tiền được xử lý ngoài hệ thống. Khi tổng đã thu bằng tổng hóa đơn, trạng thái là `paid`.
Không có chức năng hủy hoặc xóa khoản thanh toán đã ghi.

| API / nghiệp vụ US-24 | Vai trò được phép |
|---|---|
| Ghi nhận thanh toán | `landlord`/`manager` trong phạm vi khu trọ; tenant không được ghi |
| Xem hóa đơn/lịch sử thanh toán | `landlord`/`manager` trong phạm vi; tenant chỉ hóa đơn của chính mình |
| Admin | Không có quyền quản lý/xem hóa đơn theo RBAC hiện tại |

Ứng dụng tự thêm cột `payments.note` khi khởi động. Có thể áp dụng migration thủ công
bằng đoạn SQL tương ứng trong `sql.sql`. Seed demo nằm trong `seed_demo_payments.sql`,
không tự chạy lên database thật.
