const token = sessionStorage.getItem("us05_access_token");
const form = document.getElementById("invoiceForm");
const notice = document.getElementById("notice");
const contractSelect = document.getElementById("contract");
const month = document.getElementById("period");
const invoiceDocument = document.getElementById("invoiceDocument");
const now = new Date();
month.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;

async function request(path, options = {}) {
    const response = await fetch("/api" + path, {
        ...options,
        headers: {
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            ...options.headers
        }
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(Array.isArray(data.detail) ? data.detail.map(item => item.msg).join(". ") : data
            .detail || "Yêu cầu thất bại.");
    }
    return data;
}

const money = value => Number(value || 0).toLocaleString("vi-VN") + " ₫";

async function loadInvoices() {
    const me = await request("/users/me");
    const isTenant = me.role === "tenant";
    form.hidden = isTenant;
    if (isTenant) {
        document.getElementById("pageTitle").textContent = "Hóa đơn của tôi";
        document.getElementById("pageDescription").textContent =
            "Xem chi tiết các khoản thu, lịch sử thanh toán và in hoặc lưu hóa đơn thành PDF.";
    }
    const invoices = isTenant ?
        await request("/users/me/invoices") :
        await request("/invoices");
    const container = document.getElementById("invoices");
    container.replaceChildren();
    for (const invoice of invoices) {
        const row = document.createElement("article");
        row.className = "invoice-row";
        const summary = document.createElement("p");
        summary.textContent =
            `#${invoice.id} · Kỳ ${invoice.period} · Tiền phòng ${money(invoice.rent_amount)} · Phí dịch vụ ${money(invoice.utility_amount)} · Tổng ${money(invoice.total_amount)} · ${invoice.status}`;
        const details = document.createElement("button");
        details.type = "button";
        details.className = "button secondary";
        details.textContent = "Xem chi tiết & in";
        details.addEventListener("click", () => showInvoice(invoice.id));
        row.append(summary, details);
        container.append(row);
    }
    if (!invoices.length) container.textContent = "Chưa có hóa đơn.";
    if (!isTenant) {
        const contracts = await request("/contracts");
        contractSelect.replaceChildren();
        for (const item of contracts.filter(item => item.status === "active")) {
            contractSelect.add(new Option(
                `${item.property_name} / ${item.room_number} / ${item.tenant_name}`, item.id));
        }
        form.hidden = contractSelect.options.length === 0;
        if (form.hidden) notice.textContent = "Chưa có hợp đồng đang hoạt động.";
    }
}

function addText(parent, tag, text, className) {
    const element = document.createElement(tag);
    element.textContent = text;
    if (className) element.className = className;
    parent.append(element);
    return element;
}

async function showInvoice(invoiceId) {
    notice.textContent = "";
    try {
        const invoice = await request(`/invoices/${invoiceId}`);
        invoiceDocument.replaceChildren();
        invoiceDocument.hidden = false;
        const heading = addText(invoiceDocument, "h2", `HÓA ĐƠN TỔNG HỢP · ${invoice.period}`);
        heading.className = "invoice-title";
        addText(invoiceDocument, "p", `Mã hóa đơn: #${invoice.id} · Hợp đồng: #${invoice.contract_id}`);
        addText(invoiceDocument, "p", `Khu trọ: ${invoice.property_name} · ${invoice.property_address}`);
        addText(invoiceDocument, "p",
            `Phòng: ${invoice.room_number} · Khách thuê: ${invoice.tenant_name}`);
        addText(invoiceDocument, "p",
            `Điện thoại: ${invoice.tenant_phone} · Email: ${invoice.tenant_email || "—"}`);

        const table = document.createElement("table");
        table.className = "invoice-items";
        const thead = document.createElement("thead");
        const headRow = document.createElement("tr");
        for (const label of ["Khoản thu", "Số lượng", "Đơn giá", "Thành tiền"]) addText(headRow, "th",
            label);
        thead.append(headRow);
        const tbody = document.createElement("tbody");
        for (const item of invoice.line_items) {
            const row = document.createElement("tr");
            addText(row, "td", item.description);
            addText(row, "td", `${item.quantity} ${item.unit}`);
            addText(row, "td", money(item.unit_price));
            addText(row, "td", money(item.amount));
            tbody.append(row);
        }
        table.append(thead, tbody);
        invoiceDocument.append(table);
        addText(invoiceDocument, "p", `Tiền thuê: ${money(invoice.rent_amount)}`);
        addText(invoiceDocument, "p", `Điện, nước và dịch vụ: ${money(invoice.utility_amount)}`);
        addText(invoiceDocument, "p", `Tổng hóa đơn: ${money(invoice.total_amount)}`, "invoice-total");
        addText(invoiceDocument, "p",
            `Đã thanh toán: ${money(invoice.paid_amount)} · Còn lại: ${money(invoice.remaining_amount)}`
            );
        addText(invoiceDocument, "p", `Trạng thái: ${invoice.status}`);
        if (invoice.payments.length) {
            addText(invoiceDocument, "h3", "Lịch sử thanh toán");
            for (const payment of invoice.payments) {
                addText(invoiceDocument, "p",
                    `${new Date(payment.paid_at).toLocaleString("vi-VN")} · ${payment.method} · ${money(payment.amount)}`
                    );
            }
        }
        const controls = document.createElement("div");
        controls.className = "invoice-actions no-print";
        const printButton = addText(controls, "button", "In / lưu PDF");
        printButton.type = "button";
        printButton.className = "button";
        printButton.addEventListener("click", () => window.print());
        const closeButton = addText(controls, "button", "Đóng");
        closeButton.type = "button";
        closeButton.className = "button secondary";
        closeButton.addEventListener("click", () => {
            invoiceDocument.hidden = true;
        });
        invoiceDocument.append(controls);
        invoiceDocument.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
    } catch (error) {
        notice.textContent = error.message;
    }
}

form.addEventListener("submit", async event => {
    event.preventDefault();
    const button = form.querySelector("button");
    if (button.disabled) return;
    button.disabled = true;
    try {
        const result = await request(`/contracts/${contractSelect.value}/invoices`, {
            method: "POST",
            body: JSON.stringify({
                period: month.value
            })
        });
        notice.textContent = `Đã chốt hóa đơn #${result.id}.`;
        await loadInvoices();
    } catch (error) {
        notice.textContent = error.message;
    } finally {
        button.disabled = false;
    }
});

if (!token) {
    form.hidden = true;
    notice.textContent = "Hãy đăng nhập để xem hoặc quản lý hóa đơn.";
} else {
    loadInvoices().catch(error => {
        notice.textContent = error.message;
    });
}
