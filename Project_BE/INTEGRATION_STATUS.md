# Trạng thái tích hợp MiniStay

- Base `origin/main` 1185342765db60937d588c94058d2229fe1ba149, merge nhánh US-25/27 giữ các commit f7139c1, 890551c, 31318d7.
- US-21 backlog: tra cứu bảng/biểu đồ chỉ số điện/nước theo phòng và tháng. Commit 1185342 nằm trực tiếp trên origin/main, không tìm thấy PR riêng trong danh sách PR. Giao diện trong trang phòng, dùng API đọc chỉ số hiện có. API và Chrome đã kiểm tra luồng chính; chưa xác nhận toàn bộ AC không có trong backlog.
- US-20 backlog: tiêu thụ = chỉ số mới - cũ, tiền = tiêu thụ × đơn giá. Nhánh origin/feature/us-20-tinh-luong-tieu-thu-dien-nuoc tại cbe4cd2981b73d75f3280d660fad825e12da6ac9 đã push, chưa phải ancestor main. Giao diện nhánh dùng giá trên properties, trong khi billing có thể dùng service assignments, giá catalog hoặc giá riêng. Chưa tích hợp giao diện tính tiền này vì rủi ro khác số hóa đơn; cần nhóm duyệt nguồn giá. US-20 chưa được nghiệm thu.
- US-24 được tích hợp qua PR #14 https://github.com/Skibidi-Project/Nhom_10_ThucTapDoanhNghiep/pull/14 và commit 8431555; PR #12 vẫn mở. Đã test một phần/toàn phần và hai thanh toán đồng thời; chưa chứng minh toàn bộ AC.
- US-16/19 chưa tích hợp; không sửa các worktree cũ.
- US-25 migration `migrations/us25_due_date_mysql.sql` phải được sao lưu và nhóm phê duyệt trước khi chạy production; không áp dụng vào products_db. Startup code main có DDL, nhánh này kiểm tra schema US-25 MySQL trước init_db. Xem DEMO_README.md về rollback.
- Nguyên nhân xác nhận: main mới US-06 chuyển toàn bộ role sang account.html sau login; sửa chuyển hướng theo role. Static /register/ trả Cache-Control no-cache để trình duyệt xác thực lại; chưa có chứng cứ chứng minh cache là nguyên nhân duy nhất trong môi trường người dùng.
- Còn hạn chế: chưa có US-19 an toàn trong bản này, US-20 chưa duyệt nguồn giá; chưa nghiệm thu toàn bộ US-20/21/24/26; chưa chứng minh toàn bộ màn hình và RBAC trên mọi viewport. Không tuyên bố ready for main.

## Đợt kiểm thử hồi quy tiếp theo

Đã sửa biểu đồ lịch sử khi thiếu một loại điện/nước và sửa tràn ngang trên desktop/mobile. Thêm đường menu đến trang chốt hóa đơn US-22 và hiển thị trạng thái hiệu lực tại trang đó. Chrome và MySQL đã chạy trên môi trường test riêng; xem TEST_RESULTS.md. Các điểm US-20, nghiệp vụ trùng thanh toán và regression chưa bao phủ vẫn cần review trước production.

## US-20 và US-24 sau đợt ổn định

- Backlog yêu cầu tiêu thụ = mới − cũ và tiền = tiêu thụ × đơn giá. SRS nêu đơn giá theo bất động sản, áp dụng cho mọi phòng trừ khi được ghi đè; SDD đặt đơn giá tiện ích trong bảng riêng. Tài liệu chưa quy định rõ thứ tự khi đồng thời có giá khu trọ, gán theo phòng, gán theo hợp đồng và giá riêng, cũng chưa xác định hiệu lực lịch sử theo kỳ. Cần nhóm xác nhận thứ tự và thời điểm áp dụng trước khi đưa giao diện tính tiền US-20 vào Billing. Hóa đơn lịch sử không bị thay đổi.
- `Idempotency-Key` là header tùy chọn, phạm vi `(invoice_id, recorded_by, key)`; SHA-256 của khóa và nội dung đã chuẩn hóa được lưu cùng giao dịch. Cùng khóa/nội dung trả lại giao dịch hiện có, số dư trong phản hồi phản ánh thời điểm gửi lại; cùng khóa/nội dung khác trả 409. Quyền được kiểm tra trước khi tra cứu. MySQL khóa hóa đơn và unique constraint bảo vệ hai request đồng thời. Giao diện giữ khóa trong sessionStorage đến khi nhận thành công để thử lại sau lỗi mạng. Client cũ không gửi header vẫn hoạt động nhưng không có bảo vệ retry; cần cập nhật client để được bảo vệ.
- Migration `migrations/us24_payment_idempotency_mysql.sql` chỉ áp dụng một lần sau sao lưu, kiểm tra schema và phê duyệt; cột nullable giữ lịch sử cũ. MySQL DDL tự commit, chuẩn bị khôi phục backup nếu lỗi từng bước. Rollback xóa dữ liệu khóa và làm mất khả năng phát hiện retry, chỉ chạy khi được duyệt. Startup MySQL từ chối schema payments chưa migrate; không chạy trên products_db.
