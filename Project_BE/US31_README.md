# US-31 — Bộ dữ liệu mẫu

## Phạm vi

Seed riêng cho test/demo theo bảng phân công:
- 2 khu trọ, 5 phòng (3 đang thuê, 2 trống).
- 3 hồ sơ người thuê và 3 hợp đồng đang hiệu lực.
- 20 bản ghi chỉ số: 5 phòng × 2 loại điện/nước × 2 tháng liên tiếp.
- 1 tài khoản chủ trọ; thông tin người thuê đều giả lập.
- Giá điện 3.500 đ/kWh, nước 15.000 đ/m³, có lịch sử giá bao phủ hai tháng.
- Phòng đang thuê dùng 50 kWh + 5 m³ mỗi tháng, tổng điện nước 250.000 đ.
- Phòng trống có chỉ số không đổi. Chỉ số cuối tháng trước bằng đầu tháng sau.

Không tạo sẵn hóa đơn để người demo tự thử US-22. Seed không thay đổi giao diện.

## Chạy trên PowerShell

Mở terminal tại thư mục Project_BE của nhánh feature/us-31-seed-data:

```powershell
python -m pip install -r requirements.txt
python seed_us31.py --month 2026-11
$env:DATABASE_URL = 'sqlite:///./us31_demo.db'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Lần đầu script yêu cầu đặt mật khẩu ít nhất 8 ký tự (không hiện ký tự khi nhập).
Đăng nhập tại http://127.0.0.1:8000/register/html/login.html:
- Email: landlord.us31@example.com
- Mật khẩu: mật khẩu vừa nhập.

Tham số trên tạo chỉ số tháng 2026-10 và 2026-11. Bỏ --month để lấy tháng hiện tại
và tháng trước. Hợp đồng bắt đầu từ tháng trước, kết thúc một năm sau tháng thứ hai.

Xem mục Khu trọ, Phòng, Người thuê và Hợp đồng. Tạo hóa đơn cho một hợp đồng
với kỳ 2026-10 hoặc 2026-11; tổng tiền phải bằng tiền phòng + 250.000 đ.
Có thể dùng Swagger tại http://127.0.0.1:8000/docs để đăng nhập và gọi
POST /api/contracts/{contract_id}/invoices với {"period": "2026-11"}.

## Chạy lại và dữ liệu

Mặc định ghi file us31_demo.db ngay cạnh script. Script không dùng database
được cấu hình trong .env hay DATABASE_URL để ghi dữ liệu.
Dữ liệu được ghi trong một transaction; lỗi ghi sẽ rollback toàn bộ bản ghi seed.

Nếu tài khoản seed đã tồn tại, chạy lại giữ nguyên tất cả dữ liệu, mật khẩu
và các tháng cũ, kể cả khi truyền --month khác. Không tự sửa lại dữ liệu đã demo.
Nếu muốn bộ mới, dùng tên database khác:
```powershell
python seed_us31.py --database us31_demo_new.db --month 2026-12
$env:DATABASE_URL = 'sqlite:///./us31_demo_new.db'
```
Database có dữ liệu khác nhưng chưa có tài khoản seed sẽ bị từ chối.
Chỉ dùng file SQLite demo riêng. Không commit file database hay mật khẩu.

## Kiểm thử

```powershell
$env:DATABASE_URL = 'sqlite://'
python -m pytest tests/test_us31_seed.py -q
```

5 bài kiểm thử: số lượng và liên tục chỉ số qua năm mới; chạy lại giữ chỉnh sửa;
từ chối database có dữ liệu khác; rollback khi lỗi và chạy lại; đăng nhập rồi
tạo 6 hóa đơn cho 3 hợp đồng × 2 tháng, kiểm tra tổng tiền và chặn hóa đơn trùng.
Sau khi test, đặt lại DATABASE_URL thành file demo trước khi chạy server.
