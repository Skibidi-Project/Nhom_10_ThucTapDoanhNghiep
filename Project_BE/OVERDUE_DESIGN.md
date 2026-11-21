# Phương án hạn thanh toán cần duyệt

Schema hiện tại không có ngày đến hạn hóa đơn; ngày kết thúc hợp đồng không phải chứng cứ về hạn thanh toán. Không suy ra hạn từ kỳ hoặc thời hạn hợp đồng.

Trước khi triển khai production, nhóm cần duyệt nguồn chứng từ, ai được ghi/sửa hạn và quy tắc khi thay đổi hạn sau phát hành. Phương án chuẩn bị: một cột ngày đến hạn nullable trên hóa đơn và bảng lịch sử thay đổi chứa hạn cũ/mới, người thực hiện, thời điểm, lý do và tham chiếu chứng từ; migration riêng có kiểm tra schema và rollback. API ghi hạn phải kiểm tra quyền hóa đơn và quyền với khu trọ, kiểm tra ngày, khóa hóa đơn trong transaction và ghi lịch sử cùng transaction. Không nhận hạn tự sinh khi thiếu căn cứ.

Quá hạn nên là thuộc tính hiển thị độc lập với trạng thái thanh toán: còn nợ và ngày hiện tại theo Asia/Ho_Chi_Minh lớn hơn ngày đến hạn. Ngày đến hạn được tính hết ngày; thanh toán một phần vẫn giữ nhãn một phần đồng thời hiển thị quá hạn. Hóa đơn cũ chưa có hạn hiển thị thiếu dữ liệu, không bị coi là quá hạn. Cách tính này là đề xuất an toàn để duyệt, chưa phải quy tắc production được phê duyệt.

Cần test ranh giới 23:59/00:00 giờ Việt Nam, thiếu hạn, thanh toán đủ/một phần, cập nhật đồng thời và RBAC trước khi áp dụng. Chưa chạy DDL/migration, chưa có API ghi hạn hay chức năng quá hạn.
