const API_BASE = "/api";
const propertyId = Number(new URLSearchParams(window.location.search).get("property_id"));
const tokenForm = document.getElementById("tokenForm");
const authPanel = document.getElementById("authPanel");
const buildingSection = document.getElementById("buildingSection");
const buildingList = document.getElementById("buildingList");
const buildingDialog = document.getElementById("buildingDialog");
const buildingForm = document.getElementById("buildingForm");
const notice = document.getElementById("notice");
const floorInputs = document.getElementById("floorInputs");
const floorCountInput = document.getElementById("numberOfFloors");
const formError = document.getElementById("formError");
const addBuildingBtn = document.getElementById("addBuildingBtn");

let accessToken = sessionStorage.getItem("us05_access_token") || "";
let buildings = [];

function showNotice(message, type = "info") {
    notice.textContent = message;
    notice.className = `notice show ${type}`;
}

function createElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
}

async function apiRequest(path, options = {}) {
    const headers = new Headers(options.headers || {});
    headers.set("Authorization", `Bearer ${accessToken}`);
    if (options.body && !headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
    }
    const response = await fetch(`${API_BASE}${path}`, {...options, headers});
    if (response.status === 204) return null;
    const body = await response.json().catch(() => null);
    if (!response.ok) {
        const detail = typeof body?.detail === "string"
            ? body.detail
            : Array.isArray(body?.detail)
                ? body.detail.map(item => item.msg).join("; ")
                : `Yêu cầu thất bại (HTTP ${response.status}).`;
        throw new Error(detail);
    }
    return body;
}

function renderBuildings() {
    buildingList.replaceChildren();
    document.getElementById("buildingCount").textContent = String(buildings.length);
    document.getElementById("floorCount").textContent = String(
        buildings.reduce((sum, building) => sum + building.floor_count, 0)
    );
    document.getElementById("emptyState").hidden = buildings.length !== 0;

    for (const building of buildings) {
        const card = createElement("article", "building-card");
        const top = createElement("div", "building-card-top");
        const title = createElement("div");
        title.append(
            createElement("h3", "", building.name),
            createElement("span", "building-id", `Mã tòa nhà: #${building.id}`)
        );
        top.append(title, createElement("span", "building-badge", `${building.floor_count} tầng`));
        card.append(top);

        const floors = createElement("div", "floor-list");
        for (const floor of building.floors) {
            floors.append(createElement("span", "floor-chip", floor.name));
        }
        card.append(floors);

        const actions = createElement("div", "building-actions");
        const edit = createElement("button", "", "Chỉnh sửa");
        edit.type = "button";
        edit.addEventListener("click", () => openEditDialog(building));
        const remove = createElement("button", "danger", "Xóa tòa nhà");
        remove.type = "button";
        remove.addEventListener("click", () => deleteBuilding(building));
        actions.append(edit, remove);
        card.append(actions);
        buildingList.append(card);
    }
}

async function loadBuildings() {
    document.getElementById("loadingState").hidden = false;
    try {
        buildings = await apiRequest(`/properties/${propertyId}/buildings`);
        renderBuildings();
    } catch (error) {
        showNotice(error.message, "error");
    } finally {
        document.getElementById("loadingState").hidden = true;
    }
}

async function connect(token) {
    if (!Number.isSafeInteger(propertyId) || propertyId <= 0) {
        throw new Error("Thiếu mã cơ sở. Vui lòng mở trang này từ Quản lý cơ sở.");
    }
    accessToken = token.trim();
    if (!accessToken) throw new Error("Vui lòng nhập Access Token.");
    const user = await apiRequest("/users/me");
    if (!["landlord", "manager"].includes(user.role)) {
        throw new Error("Tài khoản không có quyền quản lý tòa nhà.");
    }
    const properties = await apiRequest("/properties");
    const property = properties.find(item => item.id === propertyId);
    if (!property) throw new Error("Bạn không có quyền truy cập cơ sở này.");

    sessionStorage.setItem("us05_access_token", accessToken);
    document.getElementById("accountInfo").textContent = `${user.full_name} · ${user.role}`;
    document.getElementById("propertyInfo").textContent = `${property.name} · ${property.address}`;
    authPanel.hidden = true;
    buildingSection.hidden = false;
    addBuildingBtn.hidden = false;
    await loadBuildings();
}

function disconnect() {
    sessionStorage.removeItem("us05_access_token");
    accessToken = "";
    buildings = [];
    buildingList.replaceChildren();
    document.getElementById("accessToken").value = "";
    document.getElementById("accountInfo").textContent = "Chưa xác thực";
    authPanel.hidden = false;
    buildingSection.hidden = true;
    addBuildingBtn.hidden = true;
}

function redrawFloorInputs(names = []) {
    const count = Number(floorCountInput.value);
    const oldNames = names.length ? names : [...floorInputs.querySelectorAll("input")].map(input => input.value);
    floorInputs.replaceChildren();
    if (!Number.isSafeInteger(count) || count < 1 || count > 30) return;

    for (let number = 1; number <= count; number++) {
        const wrapper = createElement("div", "floor-input");
        const id = `floorName${number}`;
        const label = createElement("label", "", `Tầng số ${number}`);
        label.htmlFor = id;
        const input = document.createElement("input");
        input.id = id;
        input.type = "text";
        input.maxLength = 80;
        input.required = true;
        input.value = oldNames[number - 1] ?? `Tầng ${number}`;
        wrapper.append(label, input);
        floorInputs.append(wrapper);
    }
}

function openCreateDialog() {
    buildingForm.reset();
    document.getElementById("buildingId").value = "";
    floorCountInput.value = "1";
    document.getElementById("dialogTitle").textContent = "Thêm tòa nhà";
    formError.textContent = "";
    redrawFloorInputs(["Tầng 1"]);
    buildingDialog.showModal();
}

function openEditDialog(building) {
    buildingForm.reset();
    document.getElementById("buildingId").value = String(building.id);
    document.getElementById("buildingName").value = building.name;
    document.getElementById("dialogTitle").textContent = "Chỉnh sửa tòa nhà";
    floorCountInput.value = String(building.floor_count);
    formError.textContent = "";
    redrawFloorInputs(building.floors.map(floor => floor.name));
    buildingDialog.showModal();
}

function formData() {
    const name = document.getElementById("buildingName").value.trim();
    const floorCount = Number(floorCountInput.value);
    const floorNames = [...floorInputs.querySelectorAll("input")].map(input => input.value.trim());
    if (!name || name.length > 120) throw new Error("Tên tòa nhà bắt buộc và tối đa 120 ký tự.");
    if (!Number.isSafeInteger(floorCount) || floorCount < 1 || floorCount > 30) {
        throw new Error("Số tầng phải từ 1 đến 30.");
    }
    if (floorNames.length !== floorCount || floorNames.some(value => !value || value.length > 80)) {
        throw new Error("Mỗi tầng cần có tên từ 1 đến 80 ký tự.");
    }
    if (new Set(floorNames.map(value => value.toLocaleLowerCase("vi-VN"))).size !== floorNames.length) {
        throw new Error("Tên các tầng không được trùng nhau.");
    }
    return {name, floor_count: floorCount, floor_names: floorNames};
}

async function deleteBuilding(building) {
    if (!window.confirm(`Xóa tòa nhà “${building.name}” cùng ${building.floor_count} tầng?`)) return;
    try {
        await apiRequest(`/buildings/${building.id}`, {method: "DELETE"});
        await loadBuildings();
        showNotice("Đã xóa tòa nhà.", "success");
    } catch (error) {
        showNotice(error.message, "error");
    }
}

buildingForm.addEventListener("submit", async event => {
    event.preventDefault();
    const saveButton = document.getElementById("saveBuildingBtn");
    saveButton.disabled = true;
    formError.textContent = "";
    try {
        const body = JSON.stringify(formData());
        const id = document.getElementById("buildingId").value;
        if (id) {
            await apiRequest(`/buildings/${id}`, {method: "PUT", body});
        } else {
            await apiRequest(`/properties/${propertyId}/buildings`, {method: "POST", body});
        }
        buildingDialog.close();
        await loadBuildings();
        showNotice(id ? "Đã cập nhật tòa nhà." : "Đã tạo tòa nhà.", "success");
    } catch (error) {
        formError.textContent = error.message;
    } finally {
        saveButton.disabled = false;
    }
});

tokenForm.addEventListener("submit", async event => {
    event.preventDefault();
    const button = document.getElementById("connectBtn");
    button.disabled = true;
    try {
        await connect(document.getElementById("accessToken").value);
    } catch (error) {
        showNotice(error.message, "error");
    } finally {
        button.disabled = false;
    }
});

floorCountInput.addEventListener("input", () => redrawFloorInputs());
addBuildingBtn.addEventListener("click", openCreateDialog);
document.getElementById("refreshBtn").addEventListener("click", loadBuildings);
document.getElementById("logoutBtn").addEventListener("click", disconnect);
document.getElementById("closeDialogBtn").addEventListener("click", () => buildingDialog.close());
document.getElementById("cancelBtn").addEventListener("click", () => buildingDialog.close());

if (!Number.isSafeInteger(propertyId) || propertyId <= 0) {
    showNotice("Hãy mở trang này bằng nút Quản lý tòa nhà tại trang Cơ sở / Khu trọ.", "error");
} else if (accessToken) {
    connect(accessToken).catch(error => {
        disconnect();
        showNotice(error.message, "error");
    });
}
