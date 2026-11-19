const API_BASE = "/api";
const accountInfo = document.getElementById("accountInfo");
const logoutBtn = document.getElementById("logoutBtn");
const propertySelect = document.getElementById("propertySelect");
const targetSelect = document.getElementById("targetSelect");
const targetLabel = document.getElementById("targetLabel");
const targetButtons = [...document.querySelectorAll(".mode-btn")];
const serviceCatalogCards = document.getElementById("serviceCatalogCards");
const catalogLoading = document.getElementById("catalogLoading");
const catalogError = document.getElementById("catalogError");
const catalogEmpty = document.getElementById("catalogEmpty");
const totalServices = document.getElementById("totalServices");
const appliedServices = document.getElementById("appliedServices");
const serviceTableBody = document.getElementById("serviceTableBody");
const summaryText = document.getElementById("summaryText");
const assignmentsLoading = document.getElementById("assignmentsLoading");
const assignmentsError = document.getElementById("assignmentsError");
const emptyState = document.getElementById("emptyState");
const notice = document.getElementById("notice");
const assignButtons = [
    document.getElementById("assignBtn"),
    document.getElementById("listAssignBtn"),
];

const assignDialog = document.getElementById("assignDialog");
const assignForm = document.getElementById("assignForm");
const assignDialogTitle = document.getElementById("assignDialogTitle");
const editSourceHint = document.getElementById("editSourceHint");
const serviceCodeSelect = document.getElementById("serviceCode");
const selectedServiceInfo = document.getElementById("selectedServiceInfo");
const noAvailableServices = document.getElementById("noAvailableServices");
const formError = document.getElementById("formError");
const saveAssignBtn = document.getElementById("saveAssignBtn");

const removeDialog = document.getElementById("removeDialog");
const removeServiceName = document.getElementById("removeServiceName");
const removeServiceCode = document.getElementById("removeServiceCode");
const removeServiceSource = document.getElementById("removeServiceSource");
const removeError = document.getElementById("removeError");
const closeRemoveDialogBtn = document.getElementById("closeRemoveDialogBtn");
const cancelRemoveBtn = document.getElementById("cancelRemoveBtn");
const confirmRemoveBtn = document.getElementById("confirmRemoveBtn");
const removeButtonLabel = document.getElementById("removeButtonLabel");
const removeSpinner = document.getElementById("removeSpinner");

let accessToken = sessionStorage.getItem("us05_access_token") || "";
let properties = [];
let rooms = [];
let contracts = [];
let serviceCatalog = [];
let assignments = [];
let directAssignments = [];
let currentMode = "room";
let selectedAssignmentId = null;
let propertyLoadVersion = 0;
let assignmentLoadVersion = 0;
let pendingRemoval = null;
let isRemovingAssignment = false;

function showNotice(message, type = "info") {
    notice.textContent = message;
    notice.className = `notice show ${type}`;
}

function hideNotice() {
    notice.textContent = "";
    notice.className = "notice";
}

function createElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
}

function parseQueryString() {
    const params = new URLSearchParams(window.location.search);
    return {
        roomId: params.get("room_id"),
        contractId: params.get("contract_id"),
    };
}

async function apiRequest(path, options = {}) {
    const headers = new Headers(options.headers || {});
    headers.set("Authorization", `Bearer ${accessToken}`);
    if (options.body && !headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
    }

    const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers
    });
    if (response.status === 204) return null;
    const data = await response.json().catch(() => null);
    if (!response.ok) {
        const detail = typeof data?.detail === "string" ?
            data.detail :
            Array.isArray(data?.detail) ?
            data.detail.map(item => item.msg || item).join("; ") :
            `Yêu cầu thất bại (HTTP ${response.status}).`;
        throw new Error(detail);
    }
    return data;
}

function selectedProperty() {
    return properties.find(property => String(property.id) === propertySelect.value) || null;
}

function serviceName(serviceCode) {
    return serviceCatalog.find(service => service.code === serviceCode)?.name || serviceCode;
}

function currentTarget() {
    const targetId = Number(targetSelect.value);
    return (currentMode === "room" ? rooms : contracts).find(target => target.id === targetId) || null;
}

function setAssignButtonsDisabled(disabled) {
    assignButtons.forEach(button => {
        button.disabled = disabled || !selectedProperty() || !targetSelect.value;
    });
}

function renderTargetSelect(preferredId = null) {
    const isRoomMode = currentMode === "room";
    const targets = isRoomMode ? rooms : contracts;
    targetLabel.textContent = isRoomMode ? "Phòng" : "Hợp đồng";
    const placeholder = !selectedProperty() ?
        "Chọn khu trọ trước" :
        targets.length ?
        isRoomMode ? "Chọn phòng" : "Chọn hợp đồng chưa kết thúc" :
        isRoomMode ? "Khu trọ chưa có phòng" : "Không có hợp đồng hợp lệ";
    targetSelect.replaceChildren(new Option(placeholder, ""));

    for (const target of targets) {
        const label = isRoomMode ?
            `Phòng ${target.room_number}` :
            `Phòng ${target.room_number} · ${target.tenant_name}`;
        targetSelect.append(new Option(label, String(target.id)));
    }
    targetSelect.disabled = targets.length === 0;

    if (preferredId && targets.some(target => String(target.id) === String(preferredId))) {
        targetSelect.value = String(preferredId);
    } else if (targets.length) {
        targetSelect.value = String(targets[0].id);
    }
}

function renderCatalog() {
    serviceCatalogCards.replaceChildren();
    catalogEmpty.hidden = Boolean(selectedProperty() && serviceCatalog.length);
    if (selectedProperty() && !serviceCatalog.length) {
        catalogEmpty.textContent = "Danh mục chưa có dịch vụ.";
    } else {
        catalogEmpty.textContent = "Chọn khu trọ để xem danh mục dịch vụ.";
    }
    totalServices.textContent = selectedProperty() ? String(serviceCatalog.length) : "—";

    if (!selectedProperty() || !serviceCatalog.length) return;

    for (const service of serviceCatalog) {
        const directlyAssigned = directAssignments.some(item => item.service_code === service.code);
        const effectiveAssignment = assignments.find(item => item.service_code === service.code);
        const inherited = currentMode === "contract" &&
            effectiveAssignment?.source === "room" &&
            !directlyAssigned;

        const card = createElement("article", "service-card");
        card.append(
            createElement("h3", "", service.name),
            createElement("span", "service-code", service.code),
        );

        const footer = createElement("div", "service-card-footer");
        const status = directlyAssigned ?
            "Đã gán" :
            inherited ?
            "Đang áp dụng từ phòng" :
            currentTarget() ?
            "Có thể gán" :
            "Chọn mục tiêu";
        const statusClass = directlyAssigned || inherited ? "assigned" : "available";
        const action = createElement(
            "button",
            "button",
            directlyAssigned ? "Đã gán" : inherited ? "Gán trực tiếp" : "Gán",
        );
        action.type = "button";
        action.disabled = !currentTarget() || directlyAssigned;
        action.addEventListener("click", () => openAssignDialog(service.code));
        footer.append(createElement("span", `service-status ${statusClass}`, status), action);
        card.append(footer);
        serviceCatalogCards.append(card);
    }
}

function renderAssignments(rows) {
    serviceTableBody.replaceChildren();
    assignments = rows;
    appliedServices.textContent = String(rows.length);
    emptyState.hidden = rows.length > 0;

    rows.forEach((item, index) => {
        const row = document.createElement("tr");
        const assignmentId = item.assignment_id ?? item.id;
        const source = currentMode === "room" ?
            "Phòng" :
            item.source === "room" ? "Phòng (kế thừa)" : "Hợp đồng";

        const editButton = createElement("button", "button button-outline", "Sửa");
        editButton.type = "button";
        editButton.disabled = !assignmentId;
        editButton.addEventListener("click", () => openAssignDialog(null, item));

        const removeButton = createElement("button", "button button-light danger", "Gỡ");
        removeButton.type = "button";
        removeButton.disabled = !assignmentId;
        removeButton.addEventListener("click", () => openRemoveDialog(assignmentId, item));

        const actions = createElement("div", "inline-actions");
        actions.append(editButton, removeButton);

        const sourceCell = document.createElement("td");
        sourceCell.append(createElement("span", "source-badge", source));
        const actionCell = document.createElement("td");
        actionCell.append(actions);
        row.append(
            createElement("td", "", index + 1),
            createElement("td", "", item.service_name || serviceName(item.service_code)),
            createElement("td", "service-code-cell", item.service_code),
            sourceCell,
            actionCell,
        );
        serviceTableBody.append(row);
    });
}

function clearAssignments(message, showEmpty = true) {
    assignments = [];
    directAssignments = [];
    serviceTableBody.replaceChildren();
    appliedServices.textContent = "0";
    summaryText.textContent = message;
    emptyState.textContent = message;
    emptyState.hidden = !showEmpty;
    renderCatalog();
}

async function loadAssignments() {
    const version = ++assignmentLoadVersion;
    const property = selectedProperty();
    const target = currentTarget();
    assignmentsError.hidden = true;
    assignmentsLoading.hidden = true;

    if (!property || !target) {
        clearAssignments(!property ?
            "Chọn khu trọ và mục tiêu để xem dịch vụ." :
            currentMode === "room" ?
            "Khu trọ chưa có phòng để chọn." :
            "Khu trọ chưa có hợp đồng hợp lệ để chọn.");
        setAssignButtonsDisabled(true);
        renderCatalog();
        return;
    }

    assignments = [];
    directAssignments = [];
    serviceTableBody.replaceChildren();
    emptyState.hidden = true;
    assignmentsLoading.hidden = false;
    appliedServices.textContent = "—";
    setAssignButtonsDisabled(true);
    renderCatalog();

    try {
        if (currentMode === "room") {
            const rows = await apiRequest(`/service-assignments?room_id=${target.id}`);
            if (version !== assignmentLoadVersion) return;
            directAssignments = rows;
            summaryText.textContent = `Phòng ${target.room_number} · ${property.name}`;
            assignmentsLoading.hidden = true;
            renderAssignments(rows);
        } else {
            const [effectiveRows, directRows] = await Promise.all([
                apiRequest(`/contracts/${target.id}/services`),
                apiRequest(`/service-assignments?contract_id=${target.id}`),
            ]);
            if (version !== assignmentLoadVersion) return;
            directAssignments = directRows;
            summaryText.textContent = `Hợp đồng · Phòng ${target.room_number} · ${target.tenant_name}`;
            assignmentsLoading.hidden = true;
            renderAssignments(effectiveRows);
        }
        renderCatalog();
        setAssignButtonsDisabled(false);
    } catch (error) {
        if (version !== assignmentLoadVersion) return;
        assignmentsLoading.hidden = true;
        assignmentsError.textContent = `Không tải được danh sách dịch vụ: ${error.message}`;
        assignmentsError.hidden = false;
        clearAssignments("Không tải được dịch vụ. Hãy thử lại hoặc kiểm tra kết nối.", false);
        setAssignButtonsDisabled(true);
        showNotice(error.message, "error");
    }
}

async function loadPropertyData(preferredTargetId = null) {
    const version = ++propertyLoadVersion;
    const property = selectedProperty();
    rooms = [];
    contracts = [];
    serviceCatalog = [];
    assignments = [];
    directAssignments = [];
    serviceCatalogCards.replaceChildren();
    serviceTableBody.replaceChildren();
    catalogError.hidden = true;
    assignmentsError.hidden = true;
    catalogLoading.hidden = !property;
    assignmentsLoading.hidden = true;
    renderCatalog();
    renderTargetSelect();

    if (!property) {
        clearAssignments("Chọn khu trọ và mục tiêu để xem dịch vụ.");
        setAssignButtonsDisabled(true);
        return;
    }

    catalogEmpty.hidden = true;
    emptyState.hidden = true;
    setAssignButtonsDisabled(true);
    targetSelect.disabled = true;
    targetSelect.replaceChildren(new Option("Đang tải dữ liệu...", ""));

    try {
        const [roomResult, contractResult, catalogResult] = await Promise.all([
            apiRequest(`/properties/${property.id}/rooms`),
            apiRequest("/contracts"),
            apiRequest(`/properties/${property.id}/service-prices`),
        ]);
        if (version !== propertyLoadVersion) return;

        rooms = roomResult;
        contracts = contractResult.filter(contract =>
            Number(contract.property_id) === property.id &&
            ["created", "active"].includes(contract.status),
        );
        serviceCatalog = catalogResult.map(item => ({
            code: item.code,
            name: item.name,
        }));
        catalogLoading.hidden = true;
        renderTargetSelect(preferredTargetId);
        await loadAssignments();
    } catch (error) {
        if (version !== propertyLoadVersion) return;
        catalogLoading.hidden = true;
        catalogError.textContent = `Không tải được dữ liệu khu trọ: ${error.message}`;
        catalogError.hidden = false;
        renderTargetSelect();
        clearAssignments("Không tải được dữ liệu khu trọ.", false);
        setAssignButtonsDisabled(true);
        showNotice(error.message, "error");
    }
}

function setMode(mode) {
    if (!["room", "contract"].includes(mode)) return;
    currentMode = mode;
    targetButtons.forEach(button => button.classList.toggle("active", button.dataset.mode === mode));
    renderTargetSelect();
    loadAssignments();
}

function updateSelectedServiceInfo() {
    const service = serviceCatalog.find(item => item.code === serviceCodeSelect.value);
    selectedServiceInfo.textContent = service ? `Đã chọn: ${service.name}` : "";
    selectedServiceInfo.hidden = !service;
}

async function openAssignDialog(serviceCode = null, item = null) {
    const target = currentTarget();
    if (!selectedProperty() || !target) {
        showNotice("Chọn khu trọ và mục tiêu trước khi gán dịch vụ.", "error");
        return;
    }

    let existingRows = directAssignments;
    if (item?.source === "room" && currentMode === "contract" && item.room_id) {
        try {
            existingRows = await apiRequest(`/service-assignments?room_id=${item.room_id}`);
        } catch (error) {
            showNotice(`Không tải được dịch vụ của phòng: ${error.message}`, "error");
            return;
        }
    }

    const currentCode = item?.service_code;
    const alreadyAssigned = new Set(existingRows.map(assignment => assignment.service_code));
    if (currentCode) alreadyAssigned.delete(currentCode);
    const availableServices = serviceCatalog.filter(service => !alreadyAssigned.has(service.code));

    serviceCodeSelect.replaceChildren(new Option(
        availableServices.length ? "Chọn dịch vụ" : "Không còn dịch vụ để gán",
        "",
    ));
    for (const service of availableServices) {
        serviceCodeSelect.append(new Option(service.name, service.code));
    }

    selectedAssignmentId = item?.assignment_id ?? item?.id ?? null;
    assignDialogTitle.textContent = item ? "Chỉnh sửa dịch vụ đã gán" : "Gán dịch vụ";
    editSourceHint.hidden = !item;
    editSourceHint.textContent = item?.source === "room" && currentMode === "contract" ?
        "Dịch vụ này được kế thừa từ phòng; thay đổi sẽ cập nhật gán dịch vụ tại phòng." :
        "Chọn dịch vụ muốn áp dụng cho mục tiêu hiện tại.";

    noAvailableServices.textContent = availableServices.length ?
        "" :
        "Tất cả dịch vụ trong danh mục đã được gán cho mục tiêu này.";
    noAvailableServices.hidden = availableServices.length > 0;
    serviceCodeSelect.disabled = availableServices.length === 0;
    saveAssignBtn.disabled = availableServices.length === 0;
    formError.textContent = "";

    const initialCode = currentCode || serviceCode || "";
    serviceCodeSelect.value = availableServices.some(service => service.code === initialCode) ?
        initialCode :
        "";
    updateSelectedServiceInfo();
    assignDialog.showModal();
}

assignForm.addEventListener("submit", async event => {
    event.preventDefault();
    const target = currentTarget();
    const service = serviceCatalog.find(item => item.code === serviceCodeSelect.value);
    if (!target || !service) {
        formError.textContent = "Hãy chọn một dịch vụ trong danh mục.";
        return;
    }

    saveAssignBtn.disabled = true;
    formError.textContent = "";
    const payload = {
        service_code: service.code,
        [currentMode === "room" ? "room_id" : "contract_id"]: target.id,
    };

    try {
        if (selectedAssignmentId) {
            await apiRequest(`/service-assignments/${selectedAssignmentId}`, {
                method: "PUT",
                body: JSON.stringify({
                    service_code: service.code
                }),
            });
            showNotice("Đã cập nhật dịch vụ.", "success");
        } else {
            await apiRequest("/service-assignments", {
                method: "POST",
                body: JSON.stringify(payload),
            });
            showNotice("Đã gán dịch vụ.", "success");
        }
        assignDialog.close();
        await loadAssignments();
    } catch (error) {
        formError.textContent = error.message;
        showNotice(error.message, "error");
    } finally {
        saveAssignBtn.disabled = false;
    }
});

function removalSource(item) {
    const target = currentTarget();
    const propertyName = selectedProperty()?.name;

    if (currentMode === "contract" && item.source === "room") {
        const room = rooms.find(candidate => candidate.id === item.room_id);
        const roomLabel = room ?
            `Phòng ${room.room_number} · ${propertyName}` :
            `Phòng ${item.room_id}`;
        return `${roomLabel} (nguồn áp dụng; hợp đồng hiện tại đang kế thừa)`;
    }

    if (currentMode === "room") {
        return `Phòng ${target?.room_number} · ${propertyName}`;
    }

    return `Hợp đồng · Phòng ${target?.room_number} · ${target?.tenant_name}`;
}

function openRemoveDialog(assignmentId, item) {
    if (!assignmentId || !item || isRemovingAssignment) return;

    pendingRemoval = {
        assignmentId,
        item
    };
    removeServiceName.textContent = item.service_name || serviceName(item.service_code);
    removeServiceCode.textContent = item.service_code || "—";
    removeServiceSource.textContent = removalSource(item);
    removeError.textContent = "";
    removeError.hidden = true;
    setRemovalLoading(false);
    removeDialog.showModal();
}

function setRemovalLoading(isLoading) {
    isRemovingAssignment = isLoading;
    confirmRemoveBtn.disabled = isLoading;
    cancelRemoveBtn.disabled = isLoading;
    closeRemoveDialogBtn.disabled = isLoading;
    removeButtonLabel.textContent = isLoading ? "Đang gỡ..." : "Xác nhận gỡ";
    removeSpinner.hidden = !isLoading;
    removeDialog.setAttribute("aria-busy", String(isLoading));
}

async function confirmRemoveAssignment() {
    if (!pendingRemoval || isRemovingAssignment) return;

    const {
        assignmentId
    } = pendingRemoval;
    setRemovalLoading(true);
    removeError.textContent = "";
    removeError.hidden = true;

    try {
        await apiRequest(`/service-assignments/${assignmentId}`, {
            method: "DELETE"
        });
        removeDialog.close();
        pendingRemoval = null;
        showNotice("Đã gỡ dịch vụ.", "success");
        await loadAssignments();
    } catch (error) {
        removeError.textContent = `Không thể gỡ dịch vụ: ${error.message}`;
        removeError.hidden = false;
        showNotice(error.message, "error");
    } finally {
        setRemovalLoading(false);
    }
}

confirmRemoveBtn.addEventListener("click", confirmRemoveAssignment);
closeRemoveDialogBtn.addEventListener("click", () => {
    if (!isRemovingAssignment) removeDialog.close();
});
cancelRemoveBtn.addEventListener("click", () => {
    if (!isRemovingAssignment) removeDialog.close();
});
removeDialog.addEventListener("click", event => {
    if (event.target === removeDialog && !isRemovingAssignment) removeDialog.close();
});
removeDialog.addEventListener("cancel", event => {
    if (isRemovingAssignment) event.preventDefault();
});
removeDialog.addEventListener("close", () => {
    pendingRemoval = null;
    if (!isRemovingAssignment) removeDialog.removeAttribute("aria-busy");
});

propertySelect.addEventListener("change", () => {
    hideNotice();
    loadPropertyData();
});

targetSelect.addEventListener("change", () => {
    hideNotice();
    loadAssignments();
});

targetButtons.forEach(button => button.addEventListener("click", () => setMode(button.dataset.mode)));
serviceCodeSelect.addEventListener("change", updateSelectedServiceInfo);
assignButtons.forEach(button => button.addEventListener("click", () => openAssignDialog()));
document.getElementById("closeAssignDialogBtn").addEventListener("click", () => assignDialog.close());
document.getElementById("cancelAssignBtn").addEventListener("click", () => assignDialog.close());

logoutBtn.addEventListener("click", () => {
    sessionStorage.removeItem("us05_access_token");
    window.location.href = "login.html";
});

async function bootstrap() {
    if (!accessToken) {
        window.location.href = "login.html";
        return;
    }

    try {
        const [user, propertyResult] = await Promise.all([
            apiRequest("/users/me"),
            apiRequest("/properties"),
        ]);
        accountInfo.textContent = `${user.full_name} · ${user.role}`;
        properties = propertyResult;
        propertySelect.replaceChildren(new Option(
            properties.length ? "Chọn khu trọ" : "Chưa có khu trọ được phép quản lý",
            "",
        ));
        properties.forEach(property => propertySelect.append(new Option(property.name, String(property
            .id))));
        propertySelect.disabled = properties.length === 0;

        if (!properties.length) {
            clearAssignments("Tài khoản này chưa được cấp quyền quản lý khu trọ nào.");
            showNotice("Không có khu trọ nào trong phạm vi tài khoản hiện tại.", "info");
            return;
        }

        let initialPropertyId = properties[0].id;
        const query = parseQueryString();
        if (query.contractId) {
            try {
                const contract = await apiRequest(`/contracts/${query.contractId}`);
                if (properties.some(property => property.id === contract.property_id)) {
                    initialPropertyId = contract.property_id;
                }
            } catch (error) {
                showNotice(`Không thể mở hợp đồng được yêu cầu: ${error.message}`, "info");
            }
        } else if (query.roomId) {
            try {
                const room = await apiRequest(`/rooms/${query.roomId}`);
                if (properties.some(property => property.id === room.property_id)) {
                    initialPropertyId = room.property_id;
                }
            } catch (error) {
                showNotice(`Không thể mở phòng được yêu cầu: ${error.message}`, "info");
            }
        }

        currentMode = query.contractId ? "contract" : "room";
        targetButtons.forEach(button => button.classList.toggle("active", button.dataset.mode ===
            currentMode));
        propertySelect.value = String(initialPropertyId);
        await loadPropertyData(query.contractId || query.roomId);
    } catch (error) {
        catalogLoading.hidden = true;
        catalogError.textContent = `Không tải được dữ liệu trang: ${error.message}`;
        catalogError.hidden = false;
        clearAssignments("Không tải được dữ liệu trang.", false);
        setAssignButtonsDisabled(true);
        showNotice(error.message, "error");
    }
}

bootstrap();
