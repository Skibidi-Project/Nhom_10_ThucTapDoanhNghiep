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

## Audit giá và review migration

Ma trận nguồn giá, bằng chứng SRS/SDD/code, hiệu lực và các lựa chọn cần phê duyệt: xem `PRICING_DECISION.md`. Giá theo kỳ và thứ tự khi nhiều mức ghi đè cùng tồn tại chưa có đủ căn cứ; không tích hợp phép tính US-20 hoặc thay đổi hóa đơn cũ.

Khi kiểm tra migration US-24, đã tăng cường startup để xác thực cả tên và bộ cột unique index `(invoice_id, recorded_by, idempotency_key)`; chỉ trùng tên không đủ bảo đảm an toàn. Migration US-24/25 chưa chạy trên products_db; DDL MySQL tự commit, xem hướng dẫn backup, kiểm tra schema và rollback trong DEMO_README.md. Header idempotency tùy chọn; client cũ, khóa mới cho cùng giao dịch, hoặc giao dịch do người khác gửi lại không được tự nhận diện là trùng.

## Chấp thuận thử nghiệm US-20 và trạng thái thực thi

Người dùng đã chấp thuận thứ tự giá riêng hợp đồng → giá riêng phòng → giá mặc định khu trọ cho nhánh thử nghiệm. Đã tạo bộ chọn thuần `app/services/dated_utility_pricing.py`: mỗi giá phải có khoảng hiệu lực rõ ràng, ưu tiên từng ngày trong cả kỳ, từ chối thiếu lịch sử, các bản ghi cùng mức chồng lấn hoặc giá được chọn thay đổi giữa kỳ. Không dùng giá hiện tại để giả lập quá khứ. Kết quả kiểm thử bộ chọn không chứng minh toàn bộ tích hợp.

**Chưa nối bộ chọn này vào US-22 hoặc giao diện US-20.** Schema hiện tại chưa có lịch sử hiệu lực, mã nhận diện nguồn và dữ liệu/chứng từ cần thiết; Billing cũ vẫn có thể lấy giá hiện tại khi lập hóa đơn kỳ cũ. Không được coi luồng cũ đáp ứng quy tắc mới. Cần thiết kế, triển khai và test lưu lịch sử có kiểm soát, migration, quyền cấu hình và snapshot giá theo hóa đơn mới; đồng bộ bộ chọn vào US-20/US-22; xử lý dịch vụ chưa gán, fixed/variable, đồng thời và UI. Chưa có quy tắc chia tiêu thụ khi giá thay đổi giữa kỳ, trường hợp đó phải tiếp tục bị chặn. Không push bản này như tích hợp hoàn chỉnh.

## US-20 tích hợp thử nghiệm

Đã áp dụng thứ tự hợp đồng → phòng → khu trọ qua bảng `utility_price_history` có kỳ hiệu lực và chứng cứ. Giá chỉ thêm mới qua API, gán sai cơ sở/chồng lấn bị từ chối; không tự suy đoán giá cũ. Bộ chọn dùng cả kỳ, chặn thiếu giá hoặc khi giá được chọn thay đổi giữa kỳ. Giá nước theo đầu người và dịch vụ biến đổi ngoài quy tắc chỉ số đang bị chặn thay vì tự suy diễn.

API `POST/GET /api/utility-pricing/history` và `GET /api/utility-pricing/preview` kiểm tra RBAC/phạm vi. US-22 gọi cùng bộ tính preview, bỏ điện/nước trong gán dịch vụ để tránh tính hai lần và lưu snapshot điện/nước vào `invoice_utility_snapshots` trong transaction hóa đơn. Dịch vụ cố định khác tính theo gán hiện có và lưu snapshot giá, số lượng, đơn vị và thành tiền. Hóa đơn cũ không thay đổi; hóa đơn mới yêu cầu đủ lịch sử giá và cả hai chỉ số. Chưa tích hợp chỉnh sửa chỉ số US-19.

Migration `migrations/us20_dated_prices_mysql.sql` và rollback cần nhóm review trước production; không chạy trên products_db. Giá thay đổi giữa kỳ, chia kỳ hợp đồng và các phương thức nước ngoài m3 cần nhóm xác nhận. Xem TEST_RESULTS.md cho giới hạn kiểm thử.
