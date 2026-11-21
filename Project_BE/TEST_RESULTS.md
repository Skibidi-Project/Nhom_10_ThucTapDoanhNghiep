# Kết quả kiểm thử US-25

- Pytest và API: 12 PASS, 0 FAIL, 1 warning; bao gồm quá hạn, thiếu hạn, hạn hôm nay, ranh giới giờ Việt Nam, thanh toán và quyền.
- MySQL InnoDB riêng: PASS migration trên schema cũ, giữ hạn NULL của hóa đơn cũ, ghi audit, thanh toán HTTP đồng thời và chống vượt số dư. Không ghi products_db.
- Chrome desktop/mobile với backend SQLite demo thực: PASS đăng nhập, thanh toán từng phần, đặt hạn có căn cứ, quá hạn còn nợ, thanh toán hết, đối chiếu, dashboard, lọc, console và API.
- Regression US-22/US-24/US-27: PARTIAL, chưa bao phủ đầy đủ các luồng nghiệp vụ. Login PASS. Kiểm thử đầy đủ giao diện phòng và hợp đồng: SKIP.
- Các thay đổi hạn được khóa theo hóa đơn và ghi lịch sử cùng transaction. Ngày giờ audit lưu UTC; ngày quá hạn dùng Asia/Ho_Chi_Minh. Trạng thái thanh toán cũ được giữ để tương thích; `effective_status` là trạng thái được hiển thị và lọc.
