# US-32: QA checklist và demo script

## Phạm vi và kết quả

Ngày chạy: 23/11/2026. Mỗi kịch bản dưới đây đi qua HTTP endpoint của FastAPI, service và SQLite trong bộ nhớ; fixture tạo database mới cho từng test. Đã chạy 12 kịch bản được chọn và toàn bộ bộ pytest.

| # | Kịch bản nghiệm thu | Kết quả | Test bảo vệ |
|---|---|---|---|
| 1 | Đăng ký, đăng nhập, token hết hạn và truy cập theo vai trò | PASS | `test_register_login_expired_token_and_role_access` |
| 2 | Chủ nhà/quản lý thao tác trong phạm vi; tenant và tài khoản không đủ quyền bị từ chối | PASS | `test_landlord_manager_can_assign_and_forbidden_roles` |
| 3 | Danh mục dịch vụ, cấu hình đơn giá và validation | PASS | `test_service_price_catalog_lists_six_services_and_validates_configuration` |
| 4 | Gán dịch vụ, chặn gán trùng, tính dịch vụ hiệu lực và override hợp đồng | PASS | `test_validation_duplicate_and_effective_services` |
| 5 | Cổng khách thuê tải được; chỉ hiện hợp đồng và hóa đơn của tài khoản đã liên kết | PASS | `test_us32_tenant_portal_shows_only_linked_tenant_data` |
| 6 | Ghi chỉ số điện/nước, đọc lịch sử, chặn ghi trùng và sai phạm vi | PASS | `test_us21_reading_history_scope_and_periods` |
| 7 | Chọn lịch sử giá theo thứ tự ưu tiên, fallback và giá 0 | PASS | `test_approved_precedence_and_fallback` |
| 8 | Preview tính đúng nguồn giá; phát hành hóa đơn, lưu snapshot và chặn trùng | PASS | `test_us20_history_preview_missing_overlap_and_access` |
| 9 | Giá thay đổi giữa kỳ bị chặn; không tạo hóa đơn/snapshot một phần | PASS | `test_us20_midmonth_change_blocks_invoice_without_partial_write` |
| 10 | Cập nhật hạn có lý do, ghi audit, tính quá hạn; thu một phần và tất toán | PASS | `test_due_date_authorization_audit_and_effective_status` |
| 11 | Ghi thanh toán idempotent; retry trả lại giao dịch cũ, khác nội dung bị chặn | PASS | `test_payment_idempotency_replay_conflict_and_authorization` |
| 12 | CRUD chi phí, phân quyền và tổng chi phí trên dashboard | PASS | `test_us26_expense_crud_scope_validation_and_dashboard` |

Chạy riêng 12 kịch bản:

```powershell
python -m pytest -q `
  tests/test_us25_us27.py::test_register_login_expired_token_and_role_access `
  tests/test_service_assignments.py::test_landlord_manager_can_assign_and_forbidden_roles `
  tests/test_service_assignments.py::test_service_price_catalog_lists_six_services_and_validates_configuration `
  tests/test_service_assignments.py::test_validation_duplicate_and_effective_services `
  tests/test_us25_us27.py::test_us32_tenant_portal_shows_only_linked_tenant_data `
  tests/test_us25_us27.py::test_us21_reading_history_scope_and_periods `
  tests/test_dated_utility_pricing.py::test_approved_precedence_and_fallback `
  tests/test_us25_us27.py::test_us20_history_preview_missing_overlap_and_access `
  tests/test_us25_us27.py::test_us20_midmonth_change_blocks_invoice_without_partial_write `
  tests/test_us25_us27.py::test_due_date_authorization_audit_and_effective_status `
  tests/test_us25_us27.py::test_payment_idempotency_replay_conflict_and_authorization `
  tests/test_us25_us27.py::test_us26_expense_crud_scope_validation_and_dashboard
```

Kết quả lần chạy này: **12 passed**. Toàn bộ suite: **30 passed**. Pytest có warning về khóa JWT ngắn trong cấu hình test và `datetime.utcnow()` deprecated; không có test nào thất bại.

Đây là kiểm thử tích hợp HTTP/service/database, chưa tự động hóa thao tác trên trình duyệt. Kịch bản #5 kiểm tra endpoint của cổng khách thuê và tải HTML; demo script bên dưới hướng dẫn kiểm tra giao diện bằng trình duyệt. Chưa chạy Chrome E2E tự động trong lần QA này.

## Demo script (8-12 phút)

### Chuẩn bị

Mở PowerShell tại thư mục `Project_BE`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\START_DEMO.ps1
```

Nhập mật khẩu demo landlord khi được hỏi và nhập lại để xác nhận. Script dùng SQLite riêng tại `%TEMP%\ministay_us25_us27_demo.sqlite3`; không kết nối MySQL hay `products_db`. Giữ cửa sổ server mở, truy cập URL đăng nhập mà script in ra (mặc định `http://127.0.0.1:8025/register/login.html`). Nếu cổng 8025 đang bận, chạy lại với `$env:MINISTAY_DEMO_PORT='18145'`.

Tài khoản landlord demo:

- Email: `landlord@gmail.com`
- Mật khẩu: mật khẩu vừa nhập lúc chạy script

### Trình tự demo

1. Đăng nhập landlord. Mở danh sách cơ sở và phòng; giới thiệu cơ sở `MiniStay Dashboard Demo`, phòng D01-D03 và hợp đồng mẫu.
2. Mở **Khách thuê**. Tạo tài khoản khách thuê riêng qua trang đăng ký tại cửa sổ ẩn danh/thu hai, rồi quay lại tài khoản landlord và dùng **Liên kết tài khoản** trên hồ sơ `Người thuê Demo` với email vừa đăng ký.
3. Mở cửa sổ thứ hai, đăng nhập bằng tài khoản tenant mới và vào `http://127.0.0.1:8025/register/html/tenant-portal.html` (thay cổng nếu đã đổi). Xem hợp đồng, chỉ số điện/nước và hóa đơn; đổi bộ lọc hợp đồng nếu có nhiều hợp đồng.
4. Quay lại landlord, mở **Điện/nước**. Chọn hợp đồng D01 và kỳ demo tháng kế tiếp. Xem preview: chỉ số điện tăng 50 kWh, nước tăng 6 m³; đơn giá demo tương ứng 3.500 và 15.000 VND. Kiểm tra tổng preview rồi phát hành hóa đơn.
5. Mở **Hóa đơn & Thanh toán**. Lọc hóa đơn vừa tạo, ghi nhận một khoản thanh toán một phần. Xác nhận trạng thái và số dư còn lại; ghi tiếp phần còn lại và xác nhận trạng thái đã thanh toán. Refresh trang để kiểm tra dữ liệu được lưu.
6. Mở **Tổng quan**. Đối chiếu doanh thu/dư nợ với hóa đơn và thanh toán vừa thao tác. Kết thúc bằng đăng xuất và xác nhận token bị xóa.

### Lời thoại demo ngắn

“MiniStay tách quyền chủ nhà và khách thuê. Chủ nhà có thể lập hợp đồng, ghi chỉ số, xem preview hóa đơn và thu tiền. Khách thuê chỉ thấy hợp đồng, chỉ số và hóa đơn liên kết với tài khoản của mình. Hóa đơn lưu snapshot giá lúc phát hành; lịch sử giá thiếu hoặc thay đổi giữa kỳ sẽ bị chặn. Sau thanh toán, số dư và dashboard cập nhật theo giao dịch.”

### Lưu ý khi lặp lại demo

Database demo được giữ giữa các lần chạy. Không phát hành lại hóa đơn cho cùng một hợp đồng và kỳ đã chốt; chọn kỳ chưa có hóa đơn. Nếu đã thanh toán tất cả, dùng một hóa đơn chưa thanh toán khác hoặc tạo database demo mới sau khi đóng server và tự xóa file demo trong `%TEMP%`.
