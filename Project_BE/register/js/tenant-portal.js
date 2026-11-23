const token = sessionStorage.getItem("us05_access_token");
const rentalsPanel = document.getElementById("panel-contracts");
const readingsPanel = document.getElementById("panel-readings");
const invoicesPanel = document.getElementById("panel-invoices");
const contractFilter = document.getElementById("contractFilter");
const pageMessage = document.getElementById("pageMessage");

const utilityNames = { electricity: "Điện", water: "Nước" };
const contractStatuses = { active: "Đang hiệu lực", created: "Sắp bắt đầu", pending_liquidation: "Chờ thanh lý", expired: "Đã kết thúc" };
const invoiceStatuses = { paid: "Đã thanh toán", partially_paid: "Thanh toán một phần", unpaid: "Chưa thanh toán", overdue: "Quá hạn" };
const depositStatuses = { held: "Đang giữ", returned: "Đã hoàn", deducted: "Đã khấu trừ", unpaid: "Chưa thu", not_applicable: "Không áp dụng" };

function logout() {
    sessionStorage.removeItem("us05_access_token");
    sessionStorage.removeItem("us05_user_role");
    window.location.assign("/register/html/login.html");
}

async function api(path) {
    const response = await fetch(path, { headers: { Authorization: `Bearer ${token}` } });
    if (response.status === 401) logout();
    if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(typeof body?.detail === "string" ? body.detail : "Không thể tải thông tin thuê nhà.");
    }
    return response.json();
}

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}

function money(value) {
    return new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND", maximumFractionDigits: 0 }).format(Number(value || 0));
}

function dateLabel(value) {
    if (!value) return "—";
    const date = new Date(`${value}T00:00:00`);
    return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("vi-VN").format(date);
}

function emptyState(title, description) {
    return `<div class="empty-state"><strong>${escapeHTML(title)}</strong><span>${escapeHTML(description)}</span></div>`;
}

function renderContracts(rentals) {
    const selectedId = contractFilter.value;
    const visibleRentals = selectedId === "all" ? rentals : rentals.filter(item => String(item.contract_id) === selectedId);
    if (!visibleRentals.length) {
        rentalsPanel.innerHTML = emptyState("Chưa có hợp đồng được liên kết", "Khi chủ nhà liên kết tài khoản này với hồ sơ khách thuê và lập hợp đồng, thông tin sẽ xuất hiện tại đây.");
        return;
    }
    rentalsPanel.innerHTML = `<div class="contract-grid">${visibleRentals.map(rental => {
        const statusClass = rental.status === "active" ? "" : rental.status === "pending_liquidation" ? "warning" : "inactive";
        return `<article class="contract-card">
            <div class="contract-card-top"><div><h3 class="contract-room">Phòng ${escapeHTML(rental.room_number)}</h3><p class="contract-property">${escapeHTML(rental.property_name)} · ${escapeHTML(rental.property_address)}</p></div><span class="status-pill ${statusClass}">${escapeHTML(contractStatuses[rental.status] || rental.status)}</span></div>
            <dl class="contract-details">
                <div><dt>Thời hạn</dt><dd>${dateLabel(rental.start_date)} – ${dateLabel(rental.end_date)}</dd></div>
                <div><dt>Tiền thuê mỗi tháng</dt><dd>${money(rental.monthly_rent)}</dd></div>
                <div><dt>Chu kỳ thanh toán</dt><dd>${rental.payment_cycle_months} tháng</dd></div>
                <div><dt>Tiền cọc · ${escapeHTML(depositStatuses[rental.deposit_status] || rental.deposit_status)}</dt><dd>${money(rental.deposit)}</dd></div>
            </dl>
        </article>`;
    }).join("")}</div>`;
}

function renderReadings(rentals) {
    const selectedId = contractFilter.value;
    const selectedRentals = selectedId === "all" ? rentals : rentals.filter(item => String(item.contract_id) === selectedId);
    const readings = selectedRentals.flatMap(rental => rental.readings.map(reading => ({ ...reading, room_number: rental.room_number, property_name: rental.property_name })))
        .filter(reading => utilityNames[reading.utility_type])
        .sort((a, b) => b.period.localeCompare(a.period) || a.utility_type.localeCompare(b.utility_type));
    if (!readings.length) {
        readingsPanel.innerHTML = emptyState("Chưa có chỉ số điện/nước", "Chỉ số được ghi theo từng kỳ. Khi chủ nhà cập nhật số điện hoặc nước cho phòng, dữ liệu sẽ hiển thị tại đây.");
        return;
    }
    readingsPanel.innerHTML = `<div class="data-table-wrap"><table class="portal-table"><thead><tr><th>Kỳ</th><th>Phòng</th><th>Loại</th><th>Chỉ số đầu</th><th>Chỉ số cuối</th><th>Tiêu thụ</th></tr></thead><tbody>${readings.map(reading => {
        const unit = reading.utility_type === "electricity" ? "kWh" : "m³";
        const usage = Math.max(0, reading.current_reading - reading.previous_reading);
        const kind = reading.utility_type === "water" ? "water" : "";
        return `<tr><td>${escapeHTML(reading.period)}</td><td>${escapeHTML(reading.property_name)} · ${escapeHTML(reading.room_number)}</td><td><span class="reading-type"><i class="reading-dot ${kind}"></i>${utilityNames[reading.utility_type]}</span></td><td>${Number(reading.previous_reading).toLocaleString("vi-VN")} ${unit}</td><td>${Number(reading.current_reading).toLocaleString("vi-VN")} ${unit}</td><td><strong>${usage.toLocaleString("vi-VN")} ${unit}</strong></td></tr>`;
    }).join("")}</tbody></table></div>`;
}

function renderInvoices(invoices, rentals) {
    const selectedId = contractFilter.value;
    const selectedRentals = selectedId === "all" ? rentals : rentals.filter(item => String(item.contract_id) === selectedId);
    const allowedContracts = new Set(selectedRentals.map(item => item.contract_id));
    const visible = invoices.filter(invoice => allowedContracts.has(invoice.contract_id))
        .sort((a, b) => b.period.localeCompare(a.period) || b.id - a.id);
    if (!visible.length) {
        invoicesPanel.innerHTML = emptyState("Chưa có hóa đơn", "Hóa đơn sẽ xuất hiện sau khi chủ nhà chốt hóa đơn cho phòng của bạn.");
        return;
    }
    const rentalByContract = new Map(rentals.map(item => [item.contract_id, item]));
    invoicesPanel.innerHTML = `<div class="data-table-wrap"><table class="portal-table"><thead><tr><th>Kỳ hóa đơn</th><th>Phòng</th><th>Tiền thuê</th><th>Điện/nước & dịch vụ</th><th>Tổng tiền</th><th>Đã trả</th><th>Hạn thanh toán</th><th>Trạng thái</th></tr></thead><tbody>${visible.map(invoice => {
        const rental = rentalByContract.get(invoice.contract_id);
        const status = invoice.effective_status || invoice.status;
        const paid = Number(invoice.paid_amount || 0);
        const remaining = Number(invoice.remaining_amount ?? Math.max(0, invoice.total_amount - paid));
        const pillClass = status === "paid" ? "status-pill" : status === "overdue" ? "status-pill warning" : "status-pill inactive";
        return `<tr><td class="invoice-period">${escapeHTML(invoice.period)}</td><td>${rental ? `Phòng ${escapeHTML(rental.room_number)}` : escapeHTML(invoice.room_number || "—")}</td><td class="amount">${money(invoice.rent_amount)}</td><td class="amount">${money(invoice.utility_amount)}</td><td class="amount">${money(invoice.total_amount)}</td><td class="amount invoice-paid">${money(paid)}</td><td>${dateLabel(invoice.due_date)}</td><td><span class="${pillClass}">${escapeHTML(invoiceStatuses[status] || status)}</span>${remaining > 0 ? `<small class="invoice-remaining">Còn ${money(remaining)}</small>` : ""}</td></tr>`;
    }).join("")}</tbody></table></div>`;
}

function updateSummary(rentals, invoices) {
    document.getElementById("contractCount").textContent = rentals.length;
    const periods = rentals.flatMap(item => item.readings.filter(reading => utilityNames[reading.utility_type]).map(reading => reading.period));
    document.getElementById("latestReading").textContent = periods.length ? periods.sort().at(-1) : "Chưa có";
    const due = invoices.reduce((total, invoice) => total + Number(invoice.remaining_amount ?? Math.max(0, invoice.total_amount - Number(invoice.paid_amount || 0))), 0);
    document.getElementById("outstandingTotal").textContent = money(due);
}

function renderAll(rentals, invoices) {
    renderContracts(rentals);
    renderReadings(rentals);
    renderInvoices(invoices, rentals);
    updateSummary(rentals, invoices);
}

function showError(message) {
    pageMessage.hidden = false;
    pageMessage.classList.add("error");
    pageMessage.textContent = message;
}

async function loadPortal() {
    if (!token) return logout();
    try {
        const [rentals, invoices, user] = await Promise.all([
            api("/api/tenants/me/rentals"),
            api("/api/invoices"),
            api("/api/users/me")
        ]);
        document.getElementById("tenantGreeting").textContent = `Xin chào, ${user.full_name || user.email}`;
        contractFilter.innerHTML = '<option value="all">Tất cả hợp đồng</option>' + rentals.map(rental => `<option value="${rental.contract_id}">Phòng ${escapeHTML(rental.room_number)} · ${escapeHTML(rental.property_name)}</option>`).join("");
        renderAll(rentals, invoices);
        contractFilter.addEventListener("change", () => {
            renderContracts(rentals);
            renderReadings(rentals);
            renderInvoices(invoices, rentals);
        });
    } catch (error) {
        showError(error.message);
    }
}

document.querySelectorAll(".portal-tab").forEach(tab => {
    tab.addEventListener("click", () => {
        document.querySelectorAll(".portal-tab").forEach(item => {
            const active = item === tab;
            item.classList.toggle("active", active);
            item.setAttribute("aria-selected", String(active));
        });
        document.querySelectorAll(".tab-panel").forEach(panel => { panel.hidden = panel.id !== `panel-${tab.dataset.panel}`; });
    });
});

document.getElementById("logoutBtn").addEventListener("click", logout);
loadPortal();
