# Hạn thanh toán US-25

Hóa đơn có `due_date` nullable; hóa đơn cũ không tự gán hạn. Landlord hoặc manager có quyền INVOICE_MANAGE và quyền khu trọ có thể đặt hạn kèm lý do/căn cứ. Lịch sử ghi hạn cũ, hạn mới, lý do, người thực hiện và thời điểm UTC trong cùng transaction. Tenant và người ngoài phạm vi không được sửa.

Trạng thái thanh toán `status` cũ được giữ cho tương thích; `effective_status` dựa vào tổng thanh toán, số tiền và ngày hạn. Đã thanh toán đủ ưu tiên cao nhất; còn nợ và ngày hiện tại tại Asia/Ho_Chi_Minh lớn hơn hạn là quá hạn; còn lại là một phần hoặc chưa thanh toán. Hạn null không bị coi là quá hạn. Một hóa đơn trả một phần quá hạn vẫn hiển thị số đã trả và số còn nợ.

Migration và rollback trong `migrations/`; đọc hướng dẫn sao lưu và giới hạn DDL ở DEMO_README.md. Chưa áp dụng migration trên products_db. Nhóm cần review schema, quyền, chứng từ và rollout trước production.
