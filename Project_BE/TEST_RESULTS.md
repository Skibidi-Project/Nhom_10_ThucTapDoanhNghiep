# Kiểm thử hồi quy tích hợp

- Pytest trên SQLite cô lập: **18 PASS, 0 FAIL**, một cảnh báo `datetime.utcnow` deprecated. Bao gồm đăng ký/đăng nhập/JWT hết hạn; RBAC; US-21; US-22 lập hóa đơn, tiền phòng và điện/nước, chống trùng; US-24/25; US-26 CRUD/validation/phân quyền; US-27; rollback hạn thanh toán.
- MySQL InnoDB riêng: **PASS** migration, giữ dữ liệu cũ, foreign key, unique, rollback, deadlock hai transaction (một transaction rollback), thanh toán HTTP đồng thời, công nợ và dashboard. Database kiểm thử `ministay_us25_test_3c08598f128b` và `ministay_us25_test_82b1b83e7213`; không ghi products_db. Đây là kiểm thử deadlock InnoDB tổng quát, không chứng minh mọi deadlock của ứng dụng.
- Chrome thật desktop 1366, tablet 768, mobile 390: **PASS** đăng nhập landlord không reload, điều hướng, US-21, US-22 tạo hóa đơn, US-24 thanh toán, US-25, dashboard, back/logout/login lại; kiểm tra dữ liệu sau refresh, lỗi console và HTTP. Kiểm tra tràn ngang ở trang cơ sở và thanh toán. Chưa quét hết mọi phần tử hoặc mọi trang.
- Chrome mobile: **PASS** điều hướng đăng nhập và RBAC dashboard của manager, tenant, admin với tài khoản thử riêng.
- US-21: lỗi thiếu nước bị vẽ thành 0 đã sửa; so sánh Chrome với JS commit trước và API thật. Ảnh trước/sau trong `%TEMP%\ministay_unified_test\us21-before.png` và `us21-after.png`. Ảnh lỗi/đã sửa tràn ngang: `overflow-desktop.png`, `overflow-desktop-after.png`, `overflow-mobile.png`, `overflow-mobile-after.png` trong cùng thư mục.
- US-20: **BLOCKED** duyệt nguồn giá. Test xác nhận giá properties 2 và override hợp đồng 4 cho 10 đơn vị cho hai số khác nhau (20 và 40). Giao diện nhánh US-20 chưa tích hợp để tránh hiển thị số sai.
- **SKIP/PARTIAL:** AC đầy đủ US-20/21/24/26, thao tác trọn vẹn properties/rooms/contracts, toàn bộ API US-26 và mọi role/viewport, idempotency chống gửi lại giao dịch trùng không có khóa yêu cầu, mọi trường hợp đồng thời, US-16/19. Không coi là đã nghiệm thu.

## Kiểm thử US-24 idempotency

- Pytest: **20 PASS**, một cảnh báo deprecation; test replay, đổi nội dung, RBAC, trả đủ rồi replay và client cũ.
- MySQL InnoDB test riêng: **PASS** migration trên schema có dữ liệu, hai request đồng thời cùng khóa/cùng nội dung nhận cùng payment id và chỉ một dòng, khác nội dung trả 409; sau đó thanh toán tiếp, FK/unique/rollback/deadlock và dashboard. Không ghi products_db. Các request đồng thời chạy qua FastAPI TestClient trong tiến trình với MySQL thật.
- Chrome backend SQLite riêng: **PASS** giả lập mất phản hồi sau khi backend ghi thật; gửi lại cùng khóa và database chỉ có một thanh toán. Desktop/tablet/mobile PASS regression login, US-21/22/24/25/27; pytest kiểm tra US-26.
- **SKIP:** quyết định nguồn giá US-20; bảo vệ retry của client cũ không gửi khóa; toàn bộ kịch bản multi-process/MySQL qua mạng và mọi role/viewport.
