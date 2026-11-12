const API_BASE = "/api";
const logoutBtn = document.getElementById("logoutBtn");
const accountInfo = document.getElementById("accountInfo");
const guestActions = document.getElementById("guestActions");
const propertySection = document.getElementById("propertySection");
const propertyList = document.getElementById("propertyList");
const propertyCount = document.getElementById("propertyCount");
const emptyState = document.getElementById("emptyState");
const notice = document.getElementById("notice");
const dialog = document.getElementById("propertyDialog");
const propertyForm = document.getElementById("propertyForm");
const addPropertyBtn = document.getElementById("addPropertyBtn");

let accessToken = sessionStorage.getItem("us05_access_token") || "";
let currentUser = null;
let properties = [];

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
    if (options.body && !headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
    }

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

function formatMoney(value) {
    return new Intl.NumberFormat("vi-VN").format(Number(value) || 0) + " đ";
}

function createElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
}

function renderProperties() {
    propertyList.replaceChildren();
    propertyCount.textContent = `${properties.length} cơ sở`;
    emptyState.hidden = properties.length !== 0;

    for (const property of properties) {
        const card = createElement("article", "property-card");
        const top = createElement("div", "card-top");
        const heading = createElement("div");
        heading.append(
            createElement("h3", "", property.name),
            createElement("span", "property-id", `Mã cơ sở: #${property.id}`)
        );
        top.append(heading);

        if (currentUser?.role !== "landlord") {
            top.append(createElement("span", "readonly-tag", "Chỉ xem"));
        }

        card.append(top, createElement("p", "address", property.address));
        const prices = createElement("div", "price-list");
        const priceItems = [
            ["Điện", property.electricity_unit_price],
            ["Nước", property.water_unit_price],
            ["Dịch vụ", property.service_unit_price]
        ];
        for (const [label, value] of priceItems) {
            const item = createElement("div", "price-item");
            item.append(createElement("span", "", label), createElement("strong", "", formatMoney(value)));
            prices.append(item);
        }
        card.append(prices);

        const roomsLink = createElement("a", "button button-outline rooms-link", "Quản lý phòng");
        roomsLink.href = `rooms.html?property_id=${encodeURIComponent(property.id)}`;
        card.append(roomsLink);

        if (currentUser?.role === "landlord") {
            const actions = createElement("div", "card-actions");
            const editButton = createElement("button", "edit-btn", "Chỉnh sửa");
            editButton.type = "button";
            editButton.addEventListener("click", () => openEditDialog(property));
            const deleteButton = createElement("button", "delete-btn", "Xóa cơ sở");
            deleteButton.type = "button";
            deleteButton.addEventListener("click", () => deleteProperty(property));
            actions.append(editButton, deleteButton);
            card.append(actions);
        }
        propertyList.append(card);
    }
}

async function loadProperties() {
    hideNotice();
    try {
        properties = await apiRequest("/properties");
        renderProperties();
    } catch (error) {
        showNotice(error.message, "error");
    }
}

function renderGuestView() {
    currentUser = null;
    properties = [];
    propertyList.replaceChildren();
    propertyCount.textContent = "Đăng nhập để xem cơ sở";
    emptyState.hidden = false;
    document.getElementById("emptyTitle").textContent = "Đăng nhập để xem danh sách cơ sở";
    document.getElementById("emptyDescription").textContent = "Đăng nhập hoặc đăng ký để sử dụng các chức năng quản lý.";
    guestActions.hidden = false;
    accountInfo.hidden = true;
    logoutBtn.hidden = true;
    addPropertyBtn.hidden = true;
    document.getElementById("refreshBtn").hidden = true;
    document.getElementById("roomsLink").hidden = true;
    document.getElementById("contractsLink").hidden = true;
}

async function connect(token) {
    accessToken = token.trim();
    if (!accessToken) throw new Error("Vui lòng nhập Access Token.");

    const user = await apiRequest("/users/me");
    if (!user || !["landlord", "manager"].includes(user.role)) {
        throw new Error("Tài khoản hiện tại không có quyền truy cập chức năng quản lý cơ sở.");
    }

    currentUser = user;
    sessionStorage.setItem("us05_access_token", accessToken);
    accountInfo.textContent = `${user.full_name} · ${user.role}`;
    accountInfo.hidden = false;
    logoutBtn.hidden = false;
    guestActions.hidden = true;
    document.getElementById("refreshBtn").hidden = false;
    document.getElementById("roomsLink").hidden = false;
    document.getElementById("contractsLink").hidden = false;
    addPropertyBtn.hidden = user.role !== "landlord";
    document.getElementById("emptyTitle").textContent = "Chưa có cơ sở nào";
    document.getElementById("emptyDescription").textContent = "Tạo cơ sở đầu tiên để bắt đầu quản lý khu trọ.";
    await loadProperties();
}

function disconnect() {
    sessionStorage.removeItem("us05_access_token");
    accessToken = "";
    currentUser = null;
    properties = [];
    propertyList.replaceChildren();
    renderGuestView();
    hideNotice();
}

function resetForm() {
    propertyForm.reset();
    document.getElementById("propertyId").value = "";
    document.getElementById("electricityPrice").value = "0";
    document.getElementById("waterPrice").value = "0";
    document.getElementById("servicePrice").value = "0";
}

function openCreateDialog() {
    resetForm();
    document.getElementById("dialogTitle").textContent = "Thêm cơ sở mới";
    document.getElementById("saveBtn").textContent = "Lưu cơ sở";
    dialog.showModal();
}

function openEditDialog(property) {
    resetForm();
    document.getElementById("dialogTitle").textContent = "Cập nhật cơ sở";
    document.getElementById("saveBtn").textContent = "Lưu thay đổi";
    document.getElementById("propertyId").value = property.id;
    document.getElementById("propertyName").value = property.name;
    document.getElementById("propertyAddress").value = property.address;
    document.getElementById("electricityPrice").value = property.electricity_unit_price;
    document.getElementById("waterPrice").value = property.water_unit_price;
    document.getElementById("servicePrice").value = property.service_unit_price;
    dialog.showModal();
}

function readFormData() {
    const name = document.getElementById("propertyName").value.trim();
    const address = document.getElementById("propertyAddress").value.trim();
    if (!name || !address) throw new Error("Tên cơ sở và địa chỉ không được để trống.");

    const readPrice = id => {
        const value = Number(document.getElementById(id).value);
        if (!Number.isSafeInteger(value) || value < 0) {
            throw new Error("Đơn giá phải là số nguyên không âm.");
        }
        return value;
    };

    return {
        name,
        address,
        electricity_unit_price: readPrice("electricityPrice"),
        water_unit_price: readPrice("waterPrice"),
        service_unit_price: readPrice("servicePrice")
    };
}

propertyForm.addEventListener("submit", async event => {
    event.preventDefault();
    const saveButton = document.getElementById("saveBtn");
    saveButton.disabled = true;
    try {
        const data = readFormData();
        const propertyId = document.getElementById("propertyId").value;
        if (propertyId) {
            await apiRequest(`/properties/${propertyId}`, {method: "PUT", body: JSON.stringify(data)});
            showNotice("Cập nhật cơ sở thành công.", "success");
        } else {
            await apiRequest("/properties", {method: "POST", body: JSON.stringify(data)});
            showNotice("Tạo cơ sở mới thành công.", "success");
        }
        dialog.close();
        await loadProperties();
    } catch (error) {
        showNotice(error.message, "error");
    } finally {
        saveButton.disabled = false;
    }
});

async function deleteProperty(property) {
    const confirmed = window.confirm(`Bạn có chắc muốn xóa cơ sở “${property.name}”?\n\nChỉ có thể xóa cơ sở chưa có phòng.`);
    if (!confirmed) return;

    try {
        await apiRequest(`/properties/${property.id}`, {method: "DELETE"});
        showNotice("Đã xóa cơ sở.", "success");
        await loadProperties();
    } catch (error) {
        showNotice(error.message, "error");
    }
}

addPropertyBtn.addEventListener("click", openCreateDialog);
document.getElementById("refreshBtn").addEventListener("click", loadProperties);
document.getElementById("closeDialogBtn").addEventListener("click", () => dialog.close());
document.getElementById("cancelBtn").addEventListener("click", () => dialog.close());
logoutBtn.addEventListener("click", disconnect);

if (accessToken) {
    connect(accessToken).catch(error => {
        disconnect();
        showNotice(error.message, "error");
    });
} else {
    renderGuestView();
}
