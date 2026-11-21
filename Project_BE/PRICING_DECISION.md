# US-20 — Quyết định nguồn đơn giá cần nhóm phê duyệt

## Bằng chứng

- Backlog `Danh_Sach_Task_15_Ngay-v2.xlsx`, US-20: tiêu thụ = chỉ số mới − cũ; thành tiền = tiêu thụ × đơn giá.
- [SRS](../Tài%20Liệu%20Đặc%20Tả%20Yêu%20Cầu%20Phần%20Mềm%20(SRS)%20.docx): giá điện/nước cấu hình theo bất động sản, áp dụng cho phòng trừ khi được ghi đè; công thức theo từng tiện ích. SRS không xác định đầy đủ thứ tự nhiều mức ghi đè hoặc giá có hiệu lực theo thời gian.
- [SDD](../Tài%20Liệu%20Thiết%20Kế%20Hệ%20Thống%20(SDD)%20.docx): đơn giá tiện ích nằm trong bảng riêng. Không thấy quy tắc giải quyết xung đột nhiều nguồn hoặc cách chọn giá lịch sử.
- Nhánh `origin/feature/us-20-tinh-luong-tieu-thu-dien-nuoc`, commit `cbe4cd2`, `Project_BE/register/readings.js`: giao diện nhân tiêu thụ với `properties.electricity_unit_price` hoặc `water_unit_price`, không đọc gán/giá riêng.

## Ma trận thực trạng — không phải quyết định đã được duyệt

| Trường hợp | Dữ liệu hiện có | Billing US-22 hiện tại | Căn cứ / hạn chế |
|---|---|---|---|
| Không có bất kỳ dịch vụ được gán | Giá điện/nước trên `properties` | Chỉ số từng loại × giá cột khu trọ | `app/services/billing_service.py::_utility_amount`; giá hiện tại, không có ngày hiệu lực. |
| Gán điện/nước theo phòng, không giá riêng | `service_assignments.room_id` và `property_service_prices` | Giá catalog của khu trọ | `get_effective_services`, `_serialize_effective_service`; thiếu catalog hoặc đơn vị báo 409. |
| Gán theo phòng, có giá riêng | `price_override` của gán phòng | Giá riêng phòng | Tên và hành vi trong service; SRS chỉ nói có thể ghi đè, không mô tả xung đột. |
| Có gán cùng mã theo hợp đồng và phòng | Hai gán cùng mã | Gán hợp đồng được chọn trước gán phòng; dùng giá riêng hợp đồng nếu có, nếu không dùng catalog | `get_effective_services` dùng gán hợp đồng trước `setdefault` phòng. Đây là hành vi code, chưa xác nhận từ tài liệu. |
| Có gán hợp đồng không giá riêng, phòng có giá riêng | Hai gán cùng mã | Giá catalog; giá riêng phòng không được dùng | Hệ quả thứ tự gán hiện tại, cần nhóm phê duyệt. |
| Có gán dịch vụ khác nhưng không gán điện/nước | Có ít nhất một assignment, chỉ số vẫn tồn tại | Billing đi nhánh assignment và không tự cộng loại chưa được gán | Quy tắc tính đủ điện/nước khi chỉ gán một phần chưa rõ. |
| Giá thay đổi trước khi lập hóa đơn kỳ cũ | Cột giá / assignment hiện tại, không có `effective_from`/`effective_to` | Lấy cấu hình hiện tại lúc lập | Không thể chứng minh giá có hiệu lực trong kỳ lịch sử. `created_at` của assignment không phải khoảng hiệu lực hoặc lịch sử thay đổi. |
| Hóa đơn đã lập | `invoices` lưu tiền thuê, tiện ích và tổng | Không tự tính lại sau khi sửa giá | Không lưu snapshot chi tiết giá/đơn vị theo từng loại để kiểm toán đầy đủ. |

`Room` và `Contract` hiện không có cột giá điện/nước trực tiếp; mức phòng/hợp đồng được biểu diễn bằng `service_assignments.price_override`. Không tự cộng cả hai assignment cùng một mã: code chọn một assignment, nhưng các trường hợp còn lại ở bảng vẫn cần review. Test `test_us20_existing_billing_price_source_difference` minh họa giá khu trọ 2 và giá riêng 4 với cùng 10 đơn vị cho 20 và 40; test `test_billing_existing_price_paths_and_assignment_precedence` mô tả hành vi code hiện tại, không chứng minh phê duyệt nghiệp vụ.

## Các phương án để nhóm quyết định

1. **Thống nhất theo assignment hiện tại:** gán hợp đồng > gán phòng, giá riêng > catalog, fallback giá cột khu trọ. Cần quyết định xử lý điện/nước chưa được gán khi đã có gán khác; ưu điểm ít thay đổi, nhưng phải xử lý giá theo kỳ và chứng từ.
2. **Một catalog theo khu trọ và override có phạm vi:** chuyển cả US-20 và US-22 dùng chung dịch vụ tính giá phía server, quy định thứ tự contract/room rõ ràng, bổ sung lịch sử hiệu lực và snapshot chi tiết vào hóa đơn mới. Cần migration và kế hoạch tương thích dữ liệu cũ.
3. **Chỉ dùng giá khu trọ:** đơn giản nhưng bỏ qua giá riêng đã tồn tại, có nguy cơ trái điều khoản; không khuyến nghị áp dụng nếu chưa được xác nhận.

Nhóm cần duyệt: thứ tự contract/room; một loại không được gán có thu không; giá tại ngày nào hoặc theo kỳ nào; cách xử lý thiếu/đổi giá, hợp đồng chồng kỳ và đơn vị; cách snapshot; phân quyền chỉnh giá; và cách đối soát hóa đơn cũ. Sau phê duyệt, US-20 và US-22 phải gọi chung một logic, test không tính trùng, khóa dữ liệu khi lập hóa đơn và giữ nguyên hóa đơn lịch sử. Trạng thái lúc kiểm toán trước; xem mục triển khai thử nghiệm bên dưới.

## Cập nhật quy tắc thử nghiệm

Người dùng đã chấp thuận thứ tự **hợp đồng → phòng → khu trọ** nếu giá hợp lệ tại kỳ tính tiền. Điều còn thiếu không phải là phê duyệt thứ tự: schema hiện chưa có khoảng hiệu lực hoặc lịch sử đáng tin cậy, chưa thể dùng dữ liệu hiện tại để khẳng định giá kỳ cũ. Chưa được phê duyệt phương pháp chia tiêu thụ khi giá đổi giữa kỳ. Các mô tả Billing cũ ở trên là trạng thái trước khi triển khai; xem mục triển khai thử nghiệm bên dưới.

## Triển khai thử nghiệm

Thứ tự giá hợp đồng → phòng → khu trọ đã được áp dụng cho điện và nước bằng lịch sử có khoảng hiệu lực đầy đủ. US-20 preview và US-22 gọi chung tính toán; thiếu lịch sử, thiếu chỉ số, giá đổi giữa kỳ và đơn vị nước không theo m3 bị chặn. Không migrate hoặc suy đoán giá quá khứ. Lịch sử điện/nước đã dùng được snapshot cho hóa đơn mới. Các dịch vụ cố định tiếp tục dùng assignment hiện có và được lưu snapshot chi tiết; nhóm cần review thêm trước production.
