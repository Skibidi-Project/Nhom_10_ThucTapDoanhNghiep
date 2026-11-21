const token = sessionStorage.getItem("us05_access_token");
const form = document.getElementById("invoiceForm");
const notice = document.getElementById("notice");
const contractSelect = document.getElementById("contract");
const month = document.getElementById("period");
const now = new Date();
month.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;

async function request(path, options = {}) {
    const response = await fetch("/api" + path, {
        ...options,
        headers: {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(Array.isArray(data.detail) ? data.detail.map(item => item.msg).join(". ") : data.detail || "Yêu cầu thất bại.");
    }
    return data;
}

async function loadInvoices() {
    const invoices = await request("/invoices");
    const container = document.getElementById("invoices");
    container.replaceChildren();
    const money = value => value.toLocaleString("vi-VN") + " đ";
    const labels = {unpaid: "Chưa thanh toán", partially_paid: "Thanh toán một phần", paid: "Đã thanh toán", overdue: "Quá hạn"};
    for (const invoice of invoices) {
        const row = document.createElement("p");
        const status = invoice.effective_status || invoice.status;
        row.textContent = `#${invoice.id} · Hợp đồng ${invoice.contract_id} · ${invoice.period} · Phòng ${money(invoice.rent_amount)} · Điện, nước và dịch vụ ${money(invoice.utility_amount)} · Tổng ${money(invoice.total_amount)} · ${labels[status] || status}`;
        container.append(row);
    }
    if (!invoices.length) container.textContent = "Chưa có hóa đơn.";
}

form.addEventListener("submit", async event => {
    event.preventDefault();
    const button = form.querySelector("button");
    if (button.disabled) return;
    button.disabled = true;
    try {
        const result = await request(`/contracts/${contractSelect.value}/invoices`, {
            method: "POST",
            body: JSON.stringify({period: month.value})
        });
        notice.textContent = `Đã chốt hóa đơn #${result.id}.`;
        await loadInvoices();
    } catch (error) {
        notice.textContent = error.message;
    } finally {
        button.disabled = false;
    }
});

async function start() {
    form.hidden = true;
    if (!token) throw new Error("Hãy đăng nhập bằng tài khoản chủ trọ hoặc người quản lý.");
    const contracts = await request("/contracts");
    for (const item of contracts.filter(item => item.status === "active")) {
        contractSelect.add(new Option(`${item.property_name} / ${item.room_number} / ${item.tenant_name}`, item.id));
    }
    form.hidden = contractSelect.options.length === 0;
    if (form.hidden) notice.textContent = "Chưa có hợp đồng đang hoạt động.";
    await loadInvoices();
}
start().catch(error => { notice.textContent = error.message; });
