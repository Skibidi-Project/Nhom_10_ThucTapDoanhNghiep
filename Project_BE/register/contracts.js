const API_BASE = "/api";
const accountInfo = document.getElementById("accountInfo");
const logoutBtn = document.getElementById("logoutBtn");
const contractSection = document.getElementById("contractSection");
const notice = document.getElementById("notice");
const contractForm = document.getElementById("contractForm");
const propertySelect = document.getElementById("propertySelect");
const roomSelect = document.getElementById("roomSelect");
const tenantSelect = document.getElementById("tenantSelect");
const contractRows = document.getElementById("contractRows");
const contractsLoading = document.getElementById("contractsLoading");
const contractsError = document.getElementById("contractsError");
const contractsEmpty = document.getElementById("contractsEmpty");
const contractsTableContainer = document.getElementById("contractsTableContainer");
const tenantDialog = document.getElementById("tenantDialog");
const tenantForm = document.getElementById("tenantForm");

let accessToken = sessionStorage.getItem("us05_access_token") || "";
let currentUser = null;
let properties = [];
let rooms = [];
let tenants = [];

function showNotice(message, type = "info") {
    notice.textContent = message;
    notice.className = `notice show ${type}`;
}

function hideNotice() {
    notice.textContent = "";
    notice.className = "notice";
}

async function apiRequest(path, options = {}) {
    const requestHeaders = new Headers(options.headers || {});
    requestHeaders.set("Authorization", `Bearer ${accessToken}`);
    if (options.body && !requestHeaders.has("Content-Type")) {
        requestHeaders.set("Content-Type", "application/json");
    }
    const response = await fetch(`${API_BASE}${path}`, {...options, headers: requestHeaders});
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

function formatDate(value) {
    const [year, month, day] = value.split("-");
    return `${day}/${month}/${year}`;
}

function setSelectOptions(select, placeholder, items, labelForItem) {
    select.replaceChildren(new Option(placeholder, ""));
    for (const item of items) {
        select.append(new Option(labelForItem(item), String(item.id)));
    }
    select.disabled = items.length === 0;
}

function selectedProperty() {
    return properties.find(property => String(property.id) === propertySelect.value) || null;
}

function updateRentHint() {
    const room = rooms.find(item => String(item.id) === roomSelect.value);
    const rentInput = document.getElementById("monthlyRent");
    const hint = document.getElementById("rentHint");
    if (!room || rentInput.value === "") {
        hint.textContent = "";
        hint.className = "field-hint";
        return;
    }
    if (Number(rentInput.value) !== room.base_rent) {
        hint.textContent = `Giá niêm yết: ${formatMoney(room.base_rent)}. Giá hợp đồng đang khác giá niêm yết.`;
        hint.className = "field-hint rent-warning";
    } else {
        hint.textContent = `Giá niêm yết: ${formatMoney(room.base_rent)}.`;
        hint.className = "field-hint";
    }
}

async function loadRoomsAndTenants() {
    const property = selectedProperty();
    rooms = [];
    tenants = [];
    setSelectOptions(roomSelect, property ? "Đang tải phòng trống..." : "Chọn khu trọ trước", []);
    setSelectOptions(tenantSelect, property ? "Đang tải khách thuê..." : "Chọn khu trọ trước", []);
    document.getElementById("monthlyRent").value = "";
    updateRentHint();
    if (!property) return;

    const params = new URLSearchParams({
        property_id: String(property.id),
        status: "available",
        page_size: "100",
    });
    const [roomResult, tenantResult] = await Promise.all([
        apiRequest(`/rooms?${params}`),
        apiRequest("/tenants"),
    ]);
    rooms = roomResult.items;
    tenants = tenantResult.filter(tenant => tenant.landlord_id === property.owner_id);
    setSelectOptions(
        roomSelect,
        rooms.length ? "Chọn phòng đang trống" : "Khu trọ chưa có phòng trống",
        rooms,
        room => `${room.room_number} · ${formatMoney(room.base_rent)}`,
    );
    setSelectOptions(
        tenantSelect,
        tenants.length ? "Chọn khách thuê đại diện" : "Chưa có khách thuê trong khu trọ này",
        tenants,
        tenant => `${tenant.full_name} · ${tenant.phone}`,
    );
}

function renderContracts(items) {
    contractRows.replaceChildren();
    for (const contract of items) {
        const row = document.createElement("tr");
        const statusLabel = contract.status === "active" ? "Hoạt động" : "Đã chấm dứt";
        const status = createElement(
            "span",
            `contract-status contract-status-${contract.status}`,
            statusLabel,
        );
        const statusCell = document.createElement("td");
        statusCell.append(status);
        row.append(
            createElement("td", "", contract.property_name),
            createElement("td", "", contract.room_number),
            createElement("td", "", contract.tenant_name),
            createElement("td", "", `${formatDate(contract.start_date)} – ${formatDate(contract.end_date)}`),
            createElement("td", "", formatMoney(contract.deposit)),
            createElement("td", "", formatMoney(contract.monthly_rent)),
            createElement("td", "", `${contract.payment_cycle_months} tháng/lần`),
            statusCell,
        );
        contractRows.append(row);
    }
}

async function loadContracts() {
    contractsLoading.hidden = false;
    contractsError.hidden = true;
    contractsEmpty.hidden = true;
    contractsTableContainer.hidden = true;
    try {
        const items = await apiRequest("/contracts");
        renderContracts(items);
        contractsLoading.hidden = true;
        contractsTableContainer.hidden = items.length === 0;
        contractsEmpty.hidden = items.length !== 0;
    } catch (error) {
        contractsLoading.hidden = true;
        contractsError.textContent = error.message;
        contractsError.hidden = false;
    }
}

async function loadProperties() {
    properties = await apiRequest("/properties");
    setSelectOptions(
        propertySelect,
        properties.length ? "Chọn khu trọ" : "Chưa có khu trọ được quản lý",
        properties,
        property => property.name,
    );
}

async function connect() {
    if (!accessToken) throw new Error("Vui lòng đăng nhập để sử dụng chức năng lập hợp đồng.");
    currentUser = await apiRequest("/users/me");
    if (!["landlord", "manager"].includes(currentUser.role)) {
        throw new Error("Tài khoản hiện tại không có quyền lập hợp đồng.");
    }
    sessionStorage.setItem("us05_access_token", accessToken);
    accountInfo.textContent = `${currentUser.full_name} · ${currentUser.role}`;
    contractSection.hidden = false;
    await loadProperties();

    const requestedRoomId = new URLSearchParams(window.location.search).get("room_id");
    if (requestedRoomId) {
        const requestedRoom = await apiRequest(`/rooms/${encodeURIComponent(requestedRoomId)}`);
        if (requestedRoom.status !== "available") {
            showNotice("Phòng được chọn hiện không còn trống để lập hợp đồng.", "error");
        } else {
            propertySelect.value = String(requestedRoom.property_id);
            await loadRoomsAndTenants();
            roomSelect.value = String(requestedRoom.id);
            document.getElementById("monthlyRent").value = requestedRoom.base_rent;
            updateRentHint();
        }
    } else if (properties.length) {
        propertySelect.value = String(properties[0].id);
        await loadRoomsAndTenants();
    }
    await loadContracts();
}

function clearSession() {
    sessionStorage.removeItem("us05_access_token");
    accessToken = "";
    currentUser = null;
    properties = [];
    rooms = [];
    tenants = [];
    contractRows.replaceChildren();
    contractSection.hidden = true;
    accountInfo.textContent = "Chưa xác thực";
}

function disconnect() {
    clearSession();
    window.location.replace("index.html");
}

function readContractForm() {
    const roomId = Number(roomSelect.value);
    const tenantId = Number(tenantSelect.value);
    const monthlyRent = Number(document.getElementById("monthlyRent").value);
    const deposit = Number(document.getElementById("deposit").value);
    const startDate = document.getElementById("startDate").value;
    const endDate = document.getElementById("endDate").value;
    const paymentCycleMonths = Number(document.getElementById("paymentCycle").value);
    if (!roomId || !tenantId) throw new Error("Vui lòng chọn phòng và khách thuê đại diện.");
    if (!startDate || !endDate || endDate <= startDate) {
        throw new Error("Ngày kết thúc phải sau ngày bắt đầu.");
    }
    if (!Number.isSafeInteger(monthlyRent) || monthlyRent <= 0) {
        throw new Error("Tiền thuê hàng tháng phải là số nguyên lớn hơn 0.");
    }
    if (!Number.isSafeInteger(deposit) || deposit < 0) {
        throw new Error("Tiền cọc phải là số nguyên không âm.");
    }
    if (deposit > 3 * monthlyRent) {
        throw new Error("Tiền cọc không được vượt quá 3 tháng tiền thuê.");
    }
    return {
        room_id: roomId,
        tenant_id: tenantId,
        start_date: startDate,
        end_date: endDate,
        deposit,
        monthly_rent: monthlyRent,
        payment_cycle_months: paymentCycleMonths,
    };
}

contractForm.addEventListener("submit", async event => {
    event.preventDefault();
    const button = document.getElementById("createContractBtn");
    const error = document.getElementById("formError");
    button.disabled = true;
    error.textContent = "";
    try {
        const body = readContractForm();
        await apiRequest("/contracts", {method: "POST", body: JSON.stringify(body)});
        showNotice("Lập hợp đồng thành công.", "success");
        const selectedPropertyId = propertySelect.value;
        contractForm.reset();
        propertySelect.value = selectedPropertyId;
        document.getElementById("deposit").value = "0";
        await Promise.all([loadContracts(), loadRoomsAndTenants()]);
    } catch (requestError) {
        error.textContent = requestError.message;
    } finally {
        button.disabled = false;
    }
});

document.getElementById("addTenantBtn").addEventListener("click", () => {
    document.getElementById("tenantFormError").textContent = "";
    tenantForm.reset();
    tenantDialog.showModal();
});

tenantForm.addEventListener("submit", async event => {
    event.preventDefault();
    const button = document.getElementById("saveTenantBtn");
    const error = document.getElementById("tenantFormError");
    button.disabled = true;
    error.textContent = "";
    try {
        const property = selectedProperty();
        if (!property) throw new Error("Vui lòng chọn khu trọ trước khi thêm khách thuê.");
        const body = {
            full_name: document.getElementById("tenantName").value.trim(),
            phone: document.getElementById("tenantPhone").value.trim(),
            id_number: document.getElementById("tenantIdNumber").value.trim(),
            property_id: property.id,
        };
        const email = document.getElementById("tenantEmail").value.trim();
        if (email) body.email = email;
        const created = await apiRequest("/tenants", {method: "POST", body: JSON.stringify(body)});
        tenants.push(created);
        setSelectOptions(
            tenantSelect,
            "Chọn khách thuê đại diện",
            tenants,
            tenant => `${tenant.full_name} · ${tenant.phone}`,
        );
        tenantSelect.value = String(created.id);
        tenantDialog.close();
        showNotice("Đã thêm và chọn khách thuê đại diện.", "success");
    } catch (requestError) {
        error.textContent = requestError.message;
    } finally {
        button.disabled = false;
    }
});

propertySelect.addEventListener("change", () => {
    loadRoomsAndTenants().catch(error => showNotice(error.message, "error"));
});
roomSelect.addEventListener("change", () => {
    const room = rooms.find(item => String(item.id) === roomSelect.value);
    document.getElementById("monthlyRent").value = room ? room.base_rent : "";
    updateRentHint();
});
document.getElementById("monthlyRent").addEventListener("input", updateRentHint);
document.getElementById("refreshContractsBtn").addEventListener("click", loadContracts);
document.getElementById("closeTenantDialogBtn").addEventListener("click", () => tenantDialog.close());
document.getElementById("cancelTenantBtn").addEventListener("click", () => tenantDialog.close());
logoutBtn.addEventListener("click", disconnect);

if (!accessToken) {
    window.location.replace("index.html");
} else {
    connect().catch(error => {
        clearSession();
        showNotice(error.message, "error");
    });
}
