# Kết quả kiểm thử tích hợp

- `DATABASE_URL=sqlite://` với JWT secret thử nghiệm, `python -m pytest -q -p no:cacheprovider`: 14 PASS, 0 FAIL, 1 cảnh báo deprecation. Bao gồm API US-21 theo phòng/kỳ, phân quyền và chống trùng; US-25/27 và các test có sẵn.
- MySQL InnoDB database riêng: PASS migration, giữ dữ liệu cũ, hai thanh toán đồng thời, chống vượt, công nợ và dashboard. Không ghi products_db.
- Chrome headless với backend thực và SQLite riêng: PASS desktop 1366, tablet 768, mobile 390 cho login không reload, menu, lịch sử điện/nước US-21, thanh toán từng phần, đối chiếu US-25, dashboard, back, logout và đăng nhập lại cho landlord; không lỗi console hay response HTTP >=400 trong luồng đó.
- Các test chưa chạy: toàn bộ AC US-20/21/24/26, logout/login lại cho manager, tenant và admin, full regression register, phòng, hợp đồng và US-16/19; không coi là PASS.
- Lỗi tìm được: login main đưa mọi role sang trang account; sửa điều hướng theo role. Không thể khẳng định cache hay server cũ có phải nguyên nhân báo cáo ban đầu.
