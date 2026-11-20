const API_BASE = "/api";
const accountInfo = document.getElementById("accountInfo");
const logoutBtn = document.getElementById("logoutBtn");
const paymentSection = document.getElementById("paymentSection");
const notice = document.getElementById("notice");
const paymentRows = document.getElementById("paymentRows");
const paymentsLoading = document.getElementById("paymentsLoading");
const paymentsError = document.getElementById("paymentsError");
const paymentsEmpty = document.getElementById("paymentsEmpty");
const paymentsTableContainer = document.getElementById("paymentsTableContainer");
const statusFilter = document.getElementById("statusFilter");
const periodFilter = document.getElementById("periodFilter");
const searchFilter = document.getElementById("searchFilter");
const paymentDialog = document.getElementById("paymentDialog");
const paymentForm = document.getElementById("paymentForm");
const paymentSummary = document.getElementById("paymentSummary");
const paymentAmount = document.getElementById("paymentAmount");
const paymentMethod = document.getElementById("paymentMethod");
const paymentPaidAt = document.getElementById("paymentPaidAt");
const paymentNote = document.getElementById("paymentNote");
const paymentPreview = document.getElementById("paymentPreview");
const savePaymentBtn = document.getElementById("savePaymentBtn");
const paymentFormError = document.getElementById("paymentFormError");
const historyDialog = document.getElementById("historyDialog");

let accessToken = sessionStorage.getItem("us05_access_token") || "";
let currentUser = null;
let invoices = [];
let activeInvoice = null;

function createElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
}

function formatMoney(value) {
    return new Intl.NumberFormat("vi-VN").format(Number(value) || 0) + " đ";
}

function formatDate(value) {
    if (!value) return "";
    const datePart = value.includes("T") ? value.split("T")[0] : value;
    const [year, month, day] = datePart.split("-");
    return year && month && day ? `${day}/${month}/${year}` : value;
}

function localDateString() {
    const date = new Date();
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

function showNotice(message, type = "info") {
    notice.textContent = message;
    notice.className = `notice show ${type}`;
}

async function apiRequest(path, options = {}) {
    const requestHeaders = new Headers(options.headers || {});
    requestHeaders.set("Authorization", `Bearer ${accessToken}`);
    if (options.body && !requestHeaders.has("Content-Type")) {
        requestHeaders.set("Content-Type", "application/json");
    }
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers: requestHeaders });
    if (response.status === 204) return null;
    const data = await response.json().catch(() => null);
    if (!response.ok) {
        const detail = typeof data?.detail === "string"
            ? data.detail
            : Array.isArray(data?.detail)
                ? data.detail.map(item => item.msg).join("; ")
                : `Yêu cầu thất bại (HTTP ${response.status}).`;
        throw new Error(detail);
    }
    return data;
}

const invoiceStatusLabels = {
    unpaid: "Chưa thanh toán",
    partially_paid: "Thanh toán một phần",
    paid: "Đã thanh toán",
};

function logout() {
    sessionStorage.removeItem("us05_access_token");
    window.location.href = "login.html";
}

async function loadUserAndInvoices() {
    if (!accessToken) {
        accountInfo.textContent = "Chưa đăng nhập";
        showNotice("Vui lòng đăng nhập bằng tài khoản chủ trọ hoặc quản lý.", "error");
        return;
    }
    try {
        currentUser = await apiRequest("/users/me");
        if (!["landlord", "manager"].includes(currentUser.role)) {
            accountInfo.textContent = currentUser.full_name || currentUser.role;
            showNotice("Trang thanh toán chỉ dành cho chủ trọ hoặc quản lý.", "error");
            paymentSection.hidden = true;
            return;
        }
        accountInfo.textContent = `${currentUser.full_name} · ${currentUser.role === "landlord" ? "Chủ trọ" : "Quản lý"}`;
        paymentSection.hidden = false;
        await loadInvoices();
    } catch (error) {
        accountInfo.textContent = "Không thể xác thực";
        showNotice(error.message, "error");
    }
}

async function loadInvoices() {
    paymentsLoading.hidden = false;
    paymentsError.hidden = true;
    paymentsEmpty.hidden = true;
    paymentsTableContainer.hidden = true;
    try {
        const params = new URLSearchParams();
        if (statusFilter.value) params.set("status", statusFilter.value);
        if (periodFilter.value) params.set("period", periodFilter.value);
        const query = params.toString();
        invoices = await apiRequest(`/invoices${query ? `?${query}` : ""}`);
        renderInvoices();
    } catch (error) {
        paymentsError.textContent = error.message;
        paymentsError.hidden = false;
    } finally {
        paymentsLoading.hidden = true;
    }
}

function renderInvoices() {
    const search = searchFilter.value.trim().toLowerCase();
    const filtered = invoices.filter(invoice => {
        if (!search) return true;
        return `${invoice.room_number || ""} ${invoice.property_name || ""} ${invoice.tenant_name || ""}`
            .toLowerCase()
            .includes(search);
    });
    paymentRows.replaceChildren();
    if (!filtered.length) {
        paymentsEmpty.hidden = false;
        paymentsTableContainer.hidden = true;
        return;
    }
    paymentsEmpty.hidden = true;
    paymentsTableContainer.hidden = false;
    for (const invoice of filtered) {
        const row = document.createElement("tr");
        row.append(
            createElement("td", "", invoice.period),
            createElement("td", "", invoice.property_name || "-"),
            createElement("td", "", invoice.room_number || "-"),
            createElement("td", "", invoice.tenant_name || "-"),
            createElement("td", "", formatMoney(invoice.total_amount)),
            createElement("td", "", formatMoney(invoice.paid_amount ?? 0)),
            createElement("td", "", formatMoney(invoice.remaining_amount ?? invoice.total_amount)),
        );
        const statusCell = createElement("td");
        const badge = createElement(
            "span",
            `payment-status payment-status-${invoice.status}`,
            invoiceStatusLabels[invoice.status] || invoice.status,
        );
        statusCell.append(badge);
        row.append(statusCell);

        const actions = createElement("td", "payment-actions");
        const recordButton = createElement("button", "button button-primary payment-action", "Ghi nhận thanh toán");
        recordButton.type = "button";
        recordButton.disabled = invoice.status === "paid" || (invoice.remaining_amount ?? 0) <= 0;
        recordButton.addEventListener("click", () => openPaymentDialog(invoice));
        const historyButton = createElement("button", "button button-outline payment-action", "Lịch sử");
        historyButton.type = "button";
        historyButton.addEventListener("click", () => openHistory(invoice));
        actions.append(recordButton, historyButton);
        row.append(actions);
        paymentRows.append(row);
    }
}

function updatePaymentPreview() {
    if (!activeInvoice) return;
    const remaining = activeInvoice.remaining_amount ?? activeInvoice.total_amount;
    const amount = Number(paymentAmount.value);
    savePaymentBtn.disabled = false;
    paymentPreview.className = "payment-preview";
    if (!paymentAmount.value || amount <= 0) {
        paymentPreview.textContent = "";
        savePaymentBtn.disabled = false;
        return;
    }
    if (amount < remaining) {
        const after = remaining - amount;
        paymentPreview.textContent = `Sau khi ghi nhận, còn thiếu ${formatMoney(after)}`;
    } else if (amount === remaining) {
        paymentPreview.textContent = "Hóa đơn sẽ được thanh toán đủ";
        paymentPreview.className = "payment-preview success";
    } else {
        paymentPreview.textContent = `Vượt quá số còn nợ ${formatMoney(remaining)}, không thể ghi nhận`;
        paymentPreview.className = "payment-preview error";
        savePaymentBtn.disabled = true;
    }
}

function openPaymentDialog(invoice) {
    activeInvoice = invoice;
    const remaining = invoice.remaining_amount ?? invoice.total_amount;
    paymentSummary.textContent =
        `Kỳ ${invoice.period} · ${invoice.property_name || "-"} · Phòng ${invoice.room_number || "-"} · ${invoice.tenant_name || "-"} · ` +
        `Tổng ${formatMoney(invoice.total_amount)} · Đã thu ${formatMoney(invoice.paid_amount ?? 0)} · Còn thiếu ${formatMoney(remaining)}`;
    paymentAmount.value = "";
    paymentMethod.value = "cash";
    paymentPaidAt.value = localDateString();
    paymentPaidAt.max = localDateString();
    paymentNote.value = "";
    paymentFormError.textContent = "";
    paymentPreview.textContent = "";
    savePaymentBtn.disabled = false;
    paymentDialog.showModal();
}

async function savePayment(event) {
    event.preventDefault();
    if (!activeInvoice) return;
    paymentFormError.textContent = "";
    savePaymentBtn.disabled = true;
    try {
        const body = {
            amount: Number(paymentAmount.value),
            method: paymentMethod.value,
            paid_at: `${paymentPaidAt.value}T00:00:00`,
            note: paymentNote.value,
        };
        const result = await apiRequest(`/invoices/${activeInvoice.id}/payments`, {
            method: "POST",
            body: JSON.stringify(body),
        });
        activeInvoice.paid_amount = result.total_paid;
        activeInvoice.remaining_amount = result.remaining_amount;
        activeInvoice.status = result.invoice_status;
        paymentDialog.close();
        renderInvoices();
        showNotice("Đã ghi nhận thanh toán thành công.", "success");
    } catch (error) {
        paymentFormError.textContent = error.message;
        savePaymentBtn.disabled = false;
    }
}

async function openHistory(invoice) {
    document.getElementById("historyTitle").textContent =
        `Lịch sử thanh toán · Kỳ ${invoice.period} · Phòng ${invoice.room_number || "-"}`;
    const historyLoading = document.getElementById("historyLoading");
    const historyError = document.getElementById("historyError");
    const historyEmpty = document.getElementById("historyEmpty");
    const historyTableContainer = document.getElementById("historyTableContainer");
    const historyRows = document.getElementById("historyRows");
    historyLoading.hidden = false;
    historyError.hidden = true;
    historyEmpty.hidden = true;
    historyTableContainer.hidden = true;
    historyRows.replaceChildren();
    historyDialog.showModal();
    try {
        const payments = await apiRequest(`/invoices/${invoice.id}/payments`);
        if (!payments.length) {
            historyEmpty.hidden = false;
            return;
        }
        historyTableContainer.hidden = false;
        for (const payment of payments) {
            const row = document.createElement("tr");
            row.append(
                createElement("td", "", formatDate(payment.paid_at)),
                createElement("td", "", formatMoney(payment.amount)),
                createElement("td", "", payment.method === "bank_transfer" ? "Chuyển khoản" : "Tiền mặt"),
                createElement("td", "", payment.note || "-"),
                createElement("td", "", payment.recorded_by_name || "-"),
            );
            historyRows.append(row);
        }
    } catch (error) {
        historyError.textContent = error.message;
        historyError.hidden = false;
    } finally {
        historyLoading.hidden = true;
    }
}

logoutBtn.addEventListener("click", logout);
statusFilter.addEventListener("change", loadInvoices);
periodFilter.addEventListener("change", loadInvoices);
searchFilter.addEventListener("input", renderInvoices);
paymentAmount.addEventListener("input", updatePaymentPreview);
paymentForm.addEventListener("submit", savePayment);
document.getElementById("fillRemainingBtn").addEventListener("click", () => {
    if (!activeInvoice) return;
    paymentAmount.value = String(activeInvoice.remaining_amount ?? activeInvoice.total_amount);
    updatePaymentPreview();
});
document.getElementById("closePaymentDialogBtn").addEventListener("click", () => paymentDialog.close());
document.getElementById("cancelPaymentBtn").addEventListener("click", () => paymentDialog.close());
document.getElementById("closeHistoryDialogBtn").addEventListener("click", () => historyDialog.close());

loadUserAndInvoices();
