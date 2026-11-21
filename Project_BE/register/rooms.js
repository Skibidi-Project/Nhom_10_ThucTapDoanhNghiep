const API_BASE = "/api";
const PAGE_SIZE = 10;
const tokenForm = document.getElementById("tokenForm");
const accessTokenInput = document.getElementById("accessToken");
const connectBtn = document.getElementById("connectBtn");
const logoutBtn = document.getElementById("logoutBtn");
const accountInfo = document.getElementById("accountInfo");
const authPanel = document.getElementById("authPanel");
const roomSection = document.getElementById("roomSection");
const notice = document.getElementById("notice");
const roomRows = document.getElementById("roomRows");
const tableContainer = document.getElementById("tableContainer");
const loadingState = document.getElementById("loadingState");
const emptyState = document.getElementById("emptyState");
const errorState = document.getElementById("errorState");
const roomDialog = document.getElementById("roomDialog");
const detailDialog = document.getElementById("detailDialog");
const utilityHistoryDialog = document.getElementById("utilityHistoryDialog");
const roomForm = document.getElementById("roomForm");
const addRoomBtn = document.getElementById("addRoomBtn");
const searchInput = document.getElementById("searchInput");
const propertyFilter = document.getElementById("propertyFilter");
const statusFilter = document.getElementById("statusFilter");
const propertySelect = document.getElementById("roomProperty");
const formError = document.getElementById("formError");

let accessToken = sessionStorage.getItem("us05_access_token") || "";
let properties = [];
let currentPage = 1;
let total = 0;
let debounceTimer;
let utilityHistory = [];

function showNotice(message, type = "info") {
    notice.textContent = message;
    notice.className = `notice show ${type}`;
}

function hideNotice() {
    notice.textContent = "";
    notice.className = "notice";
}

async function apiRequest(path, options = {}) {
    const headers = new Headers(options.headers || {});
    headers.set("Authorization", `Bearer ${accessToken}`);
    if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

    const response = await fetch(`${API_BASE}${path}`, {...options, headers});
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

function createElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
}

function formatMoney(value) {
    return new Intl.NumberFormat("vi-VN").format(Number(value) || 0) + " đ";
}

function statusLabel(status) {
    return {available: "Đang trống", reserved: "Đã đặt cọc", occupied: "Đang thuê", maintenance: "Bảo trì"}[status] || status;
}

function setLoading(loading) {
    loadingState.hidden = !loading;
    tableContainer.hidden = true;
    emptyState.hidden = true;
    errorState.hidden = true;
}

function appendAction(actions, label, handler, className = "") {
    const button = createElement("button", `room-action ${className}`.trim(), label);
    button.type = "button";
    button.addEventListener("click", handler);
    actions.append(button);
}

function renderRows(items) {
    roomRows.replaceChildren();
    for (const room of items) {
        const row = document.createElement("tr");
        row.append(
            createElement("td", "", room.property_name),
        );
        const numberCell = document.createElement("td");
        const numberButton = createElement("button", "room-number-button", room.room_number);
        numberButton.type = "button";
        numberButton.addEventListener("click", () => showRoomDetail(room));
        numberCell.append(numberButton);
        row.append(numberCell);
        row.append(
            createElement("td", "", room.area_sqm == null ? "—" : `${room.area_sqm} m²`),
            createElement("td", "", formatMoney(room.base_rent)),
        );
        const statusCell = document.createElement("td");
        statusCell.append(createElement("span", `status-badge status-${room.status}`, statusLabel(room.status)));
        row.append(statusCell);

        const actionsCell = document.createElement("td");
        const actions = createElement("div", "room-actions");
        appendAction(actions, "Chi tiết", () => showRoomDetail(room));
        appendAction(actions, "Lịch sử điện/nước", () => showUtilityHistory(room), "utility-history-action");
        if (room.status === "available") {
            appendAction(actions, "Lập hợp đồng", () => {
                window.location.href = `contracts.html?room_id=${encodeURIComponent(room.id)}`;
            });
        }
        appendAction(actions, "Dịch vụ", () => {
            window.location.href = `services.html?room_id=${encodeURIComponent(room.id)}`;
        });
        if (room.status !== "occupied") {
            appendAction(actions, "Sửa", () => openEditDialog(room));
            appendAction(actions, "Xóa", () => deleteRoom(room), "danger");
        }
        actionsCell.append(actions);
        row.append(actionsCell);
        roomRows.append(row);
    }
}

function updatePagination() {
    const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
    document.getElementById("pageInfo").textContent = `Trang ${currentPage}/${pageCount} · ${total} phòng`;
    document.getElementById("resultSummary").textContent = `${total} phòng`;
    document.getElementById("previousPageBtn").disabled = currentPage <= 1;
    document.getElementById("nextPageBtn").disabled = currentPage >= pageCount;
}

async function loadRooms() {
    setLoading(true);
    try {
        const params = new URLSearchParams({page: String(currentPage), page_size: String(PAGE_SIZE)});
        const search = searchInput.value.trim();
        if (search) params.set("search", search);
        if (propertyFilter.value) params.set("property_id", propertyFilter.value);
        if (statusFilter.value) params.set("status", statusFilter.value);
        const result = await apiRequest(`/rooms?${params}`);
        total = result.total;
        renderRows(result.items);
        loadingState.hidden = true;
        tableContainer.hidden = result.items.length === 0;
        emptyState.hidden = result.items.length !== 0;
        updatePagination();
    } catch (error) {
        total = 0;
        roomRows.replaceChildren();
        loadingState.hidden = true;
        errorState.textContent = error.message;
        errorState.hidden = false;
        updatePagination();
    }
}

function fillPropertySelect(select, includeAll) {
    select.replaceChildren();
    if (includeAll) select.append(new Option("Tất cả khu trọ", ""));
    for (const property of properties) {
        select.append(new Option(property.name, String(property.id)));
    }
}

async function loadProperties() {
    properties = await apiRequest("/properties");
    const filterValue = propertyFilter.value;
    fillPropertySelect(propertyFilter, true);
    fillPropertySelect(propertySelect, false);
    if (filterValue && properties.some(property => String(property.id) === filterValue)) {
        propertyFilter.value = filterValue;
    }
    const requestedProperty = new URLSearchParams(window.location.search).get("property_id");
    if (requestedProperty && properties.some(property => String(property.id) === requestedProperty)) {
        propertyFilter.value = requestedProperty;
    }
}

async function connect(token) {
    accessToken = token.trim();
    if (!accessToken) throw new Error("Vui lòng nhập Access Token.");
    const user = await apiRequest("/users/me");
    if (!user || !["landlord", "manager"].includes(user.role)) {
        throw new Error("Tài khoản hiện tại không có quyền truy cập chức năng quản lý phòng.");
    }
    sessionStorage.setItem("us05_access_token", accessToken);
    accountInfo.textContent = `${user.full_name} · ${user.role}`;
    authPanel.hidden = true;
    roomSection.hidden = false;
    addRoomBtn.hidden = false;
    await loadProperties();
    await loadRooms();
}

function disconnect() {
    sessionStorage.removeItem("us05_access_token");
    accessToken = "";
    properties = [];
    roomRows.replaceChildren();
    roomSection.hidden = true;
    authPanel.hidden = false;
    addRoomBtn.hidden = true;
    accountInfo.textContent = "Chưa xác thực";
    accessTokenInput.value = "";
    hideNotice();
}

function resetForm() {
    roomForm.reset();
    document.getElementById("roomId").value = "";
    propertySelect.disabled = false;
    document.getElementById("statusFormGroup").hidden = true;
    formError.textContent = "";
}

function openCreateDialog() {
    resetForm();
    document.getElementById("roomDialogTitle").textContent = "Thêm phòng";
    document.getElementById("saveRoomBtn").textContent = "Lưu phòng";
    if (propertyFilter.value) propertySelect.value = propertyFilter.value;
    roomDialog.showModal();
}

function openEditDialog(room) {
    resetForm();
    document.getElementById("roomDialogTitle").textContent = "Cập nhật phòng";
    document.getElementById("saveRoomBtn").textContent = "Lưu thay đổi";
    document.getElementById("roomId").value = room.id;
    propertySelect.value = String(room.property_id);
    propertySelect.disabled = true;
    document.getElementById("roomNumber").value = room.room_number;
    document.getElementById("roomArea").value = room.area_sqm ?? "";
    document.getElementById("roomRent").value = room.base_rent;
    document.getElementById("roomStatus").value = room.status;
    document.getElementById("statusFormGroup").hidden = false;
    roomDialog.showModal();
}

function readFormData(isEditing) {
    const roomNumber = document.getElementById("roomNumber").value.trim();
    const rent = Number(document.getElementById("roomRent").value);
    const areaInput = document.getElementById("roomArea").value.trim();
    const area = areaInput === "" ? null : Number(areaInput);
    if (!roomNumber || roomNumber.length > 20) throw new Error("Số phòng bắt buộc và tối đa 20 ký tự.");
    if (!Number.isSafeInteger(rent) || rent < 0) throw new Error("Giá thuê phải là số nguyên không âm.");
    if (area !== null && (!Number.isFinite(area) || area <= 0 || !/^\d+(\.\d{1,2})?$/.test(areaInput))) {
        throw new Error("Diện tích phải lớn hơn 0 và tối đa 2 chữ số thập phân.");
    }

    const data = {room_number: roomNumber, base_rent: rent, area_sqm: area};
    if (isEditing) {
        data.status = document.getElementById("roomStatus").value;
    } else {
        data.property_id = Number(propertySelect.value);
    }
    return data;
}

roomForm.addEventListener("submit", async event => {
    event.preventDefault();
    const saveButton = document.getElementById("saveRoomBtn");
    saveButton.disabled = true;
    formError.textContent = "";
    try {
        const roomId = document.getElementById("roomId").value;
        const data = readFormData(Boolean(roomId));
        if (roomId) {
            delete data.property_id;
            await apiRequest(`/rooms/${roomId}`, {method: "PUT", body: JSON.stringify(data)});
            showNotice("Cập nhật phòng thành công.", "success");
        } else {
            const propertyId = data.property_id;
            delete data.property_id;
            await apiRequest(`/properties/${propertyId}/rooms`, {method: "POST", body: JSON.stringify(data)});
            showNotice("Tạo phòng mới thành công.", "success");
        }
        roomDialog.close();
        await loadRooms();
    } catch (error) {
        formError.textContent = error.message;
    } finally {
        saveButton.disabled = false;
    }
});

async function deleteRoom(room) {
    if (!window.confirm(`Bạn có chắc muốn xóa phòng ${room.room_number} tại ${room.property_name}?`)) return;
    try {
        await apiRequest(`/rooms/${room.id}`, {method: "DELETE"});
        showNotice("Đã xóa phòng.", "success");
        await loadRooms();
    } catch (error) {
        showNotice(error.message, "error");
    }
}

function detailRow(label, value) {
    const row = createElement("div", "detail-row");
    row.append(createElement("strong", "", `${label}: `), document.createTextNode(value));
    return row;
}

async function showRoomDetail(room) {
    try {
        const detail = await apiRequest(`/rooms/${room.id}`);
        document.getElementById("detailTitle").textContent = `Phòng ${detail.room_number}`;
        const body = document.getElementById("detailBody");
        body.replaceChildren(
            detailRow("Khu trọ", detail.property_name),
            detailRow("Diện tích", detail.area_sqm == null ? "Chưa cập nhật" : `${detail.area_sqm} m²`),
            detailRow("Giá thuê", formatMoney(detail.base_rent)),
            detailRow("Trạng thái", statusLabel(detail.status)),
        );
        if (detail.active_contract) {
            const contract = createElement("section", "detail-contract");
            contract.append(
                createElement("h3", "", "Hợp đồng đang hoạt động"),
                detailRow("Mã hợp đồng", `#${detail.active_contract.id}`),
                detailRow("Khách thuê", detail.active_contract.tenant),
                detailRow("Thời hạn", `${detail.active_contract.start_date} — ${detail.active_contract.end_date}`),
                detailRow("Tiền thuê/tháng", formatMoney(detail.active_contract.monthly_rent)),
            );
            body.append(contract);
        } else {
            body.append(detailRow("Hợp đồng", "Không có hợp đồng đang hoạt động."));
        }
        detailDialog.showModal();
    } catch (error) {
        showNotice(error.message, "error");
    }
}

function utilityTypeLabel(type) {
    return type === "electricity" ? "Điện" : "Nước";
}

function utilityUnit(type) {
    return type === "electricity" ? "kWh" : "m³";
}

function formatUsage(value) {
    return new Intl.NumberFormat("vi-VN", {maximumFractionDigits: 2}).format(value);
}

function renderUtilityHistory() {
    const state = document.getElementById("utilityHistoryState");
    const chartSection = document.getElementById("utilityChartSection");
    const tableSection = document.getElementById("utilityTableSection");
    const chart = document.getElementById("utilityChart");
    const rows = document.getElementById("utilityHistoryRows");
    const selectedMonth = document.getElementById("utilityMonthFilter").value;
    const filtered = utilityHistory
        .filter(reading => !selectedMonth || reading.period === selectedMonth)
        .sort((a, b) => b.period.localeCompare(a.period) || a.utility_type.localeCompare(b.utility_type));

    chart.replaceChildren();
    rows.replaceChildren();
    if (!filtered.length) {
        state.textContent = selectedMonth ? "Tháng này chưa có chỉ số điện/nước." : "Phòng chưa có lịch sử chỉ số điện/nước.";
        state.hidden = false;
        chartSection.hidden = true;
        tableSection.hidden = true;
        return;
    }

    state.hidden = true;
    chartSection.hidden = false;
    tableSection.hidden = false;
    const monthly = new Map();
    for (const reading of filtered) {
        if (!monthly.has(reading.period)) monthly.set(reading.period, {electricity: 0, water: 0});
        monthly.get(reading.period)[reading.utility_type] = reading.current_reading - reading.previous_reading;
    }
    const maxUsage = Math.max(1, ...Array.from(monthly.values()).flatMap(value => [value.electricity, value.water]));
    for (const [period, values] of Array.from(monthly.entries()).sort(([a], [b]) => a.localeCompare(b))) {
        const group = createElement("div", "utility-month-group");
        const bars = createElement("div", "utility-bars");
        for (const type of ["electricity", "water"]) {
            const bar = createElement("div", `utility-bar ${type}`);
            bar.style.height = `${Math.max(2, values[type] / maxUsage * 100)}%`;
            bar.setAttribute("aria-label", `${utilityTypeLabel(type)} ${formatUsage(values[type])} ${utilityUnit(type)}`);
            bar.append(createElement("span", "utility-bar-value", formatUsage(values[type])));
            bars.append(bar);
        }
        group.append(bars, createElement("div", "utility-month-label", period));
        chart.append(group);
    }

    for (const reading of filtered) {
        const usage = reading.current_reading - reading.previous_reading;
        const row = document.createElement("tr");
        row.append(
            createElement("td", "", reading.period),
            createElement("td", "", utilityTypeLabel(reading.utility_type)),
            createElement("td", "", formatUsage(reading.previous_reading)),
            createElement("td", "", formatUsage(reading.current_reading)),
            createElement("td", "", `${formatUsage(usage)} ${utilityUnit(reading.utility_type)}`),
        );
        rows.append(row);
    }
}

async function showUtilityHistory(room) {
    const title = document.getElementById("utilityHistoryTitle");
    const monthFilter = document.getElementById("utilityMonthFilter");
    const state = document.getElementById("utilityHistoryState");
    const chartSection = document.getElementById("utilityChartSection");
    const tableSection = document.getElementById("utilityTableSection");
    title.textContent = `Lịch sử điện/nước · Phòng ${room.room_number}`;
    monthFilter.replaceChildren(new Option("Tất cả các tháng", ""));
    state.textContent = "Đang tải lịch sử...";
    state.hidden = false;
    chartSection.hidden = true;
    tableSection.hidden = true;
    utilityHistory = [];
    utilityHistoryDialog.showModal();
    try {
        const readings = await apiRequest(`/rooms/${room.id}/readings`);
        utilityHistory = readings.filter(reading => ["electricity", "water"].includes(reading.utility_type));
        const months = [...new Set(utilityHistory.map(reading => reading.period))].sort((a, b) => b.localeCompare(a));
        for (const month of months) monthFilter.append(new Option(month, month));
        renderUtilityHistory();
    } catch (error) {
        state.textContent = error.message;
        state.hidden = false;
    }
}

tokenForm.addEventListener("submit", async event => {
    event.preventDefault();
    connectBtn.disabled = true;
    connectBtn.textContent = "Đang kết nối...";
    try {
        await connect(accessTokenInput.value);
        showNotice("Kết nối tài khoản thành công.", "success");
    } catch (error) {
        showNotice(error.message, "error");
    } finally {
        connectBtn.disabled = false;
        connectBtn.textContent = "Kết nối";
    }
});

addRoomBtn.addEventListener("click", openCreateDialog);
document.getElementById("refreshBtn").addEventListener("click", loadRooms);
document.getElementById("previousPageBtn").addEventListener("click", () => {
    if (currentPage > 1) {
        currentPage -= 1;
        loadRooms();
    }
});
document.getElementById("nextPageBtn").addEventListener("click", () => {
    if (currentPage < Math.ceil(total / PAGE_SIZE)) {
        currentPage += 1;
        loadRooms();
    }
});
searchInput.addEventListener("input", () => {
    window.clearTimeout(debounceTimer);
    debounceTimer = window.setTimeout(() => {
        currentPage = 1;
        loadRooms();
    }, 300);
});
propertyFilter.addEventListener("change", () => {
    currentPage = 1;
    loadRooms();
});
statusFilter.addEventListener("change", () => {
    currentPage = 1;
    loadRooms();
});
document.getElementById("closeDialogBtn").addEventListener("click", () => roomDialog.close());
document.getElementById("cancelBtn").addEventListener("click", () => roomDialog.close());
document.getElementById("closeDetailBtn").addEventListener("click", () => detailDialog.close());
document.getElementById("closeDetailActionBtn").addEventListener("click", () => detailDialog.close());
document.getElementById("closeUtilityHistoryBtn").addEventListener("click", () => utilityHistoryDialog.close());
document.getElementById("utilityMonthFilter").addEventListener("change", renderUtilityHistory);
logoutBtn.addEventListener("click", disconnect);

if (!accessToken) {
    window.location.replace("index.html");
} else {
    connect(accessToken).catch(error => {
        disconnect();
        showNotice(error.message, "error");
    });
}
