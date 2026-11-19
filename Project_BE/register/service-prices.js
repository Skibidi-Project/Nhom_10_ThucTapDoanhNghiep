const API_BASE = "/api";
const accountInfo = document.getElementById("accountInfo");
const logoutBtn = document.getElementById("logoutBtn");
const propertySelect = document.getElementById("propertySelect");
const notice = document.getElementById("notice");
const priceSummary = document.getElementById("priceSummary");
const priceLoading = document.getElementById("priceLoading");
const priceError = document.getElementById("priceError");
const priceEmpty = document.getElementById("priceEmpty");
const servicePriceList = document.getElementById("servicePriceList");

const priceDialog = document.getElementById("priceDialog");
const priceForm = document.getElementById("priceForm");
const priceDialogTitle = document.getElementById("priceDialogTitle");
const priceServiceName = document.getElementById("priceServiceName");
const billingUnitSelect = document.getElementById("billingUnitSelect");
const unitPriceInput = document.getElementById("unitPriceInput");
const priceFormError = document.getElementById("priceFormError");
const closePriceDialogBtn = document.getElementById("closePriceDialogBtn");
const cancelPriceBtn = document.getElementById("cancelPriceBtn");
const savePriceBtn = document.getElementById("savePriceBtn");
const savePriceLabel = document.getElementById("savePriceLabel");
const savePriceSpinner = document.getElementById("savePriceSpinner");

const BILLING_UNIT_LABELS = {
    kwh: "kWh",
    m3: "m³",
    person_month: "người/tháng",
    room_month: "phòng/tháng",
    vehicle_month: "xe/tháng",
};

let accessToken = sessionStorage.getItem("us05_access_token") || "";
let properties = [];
let servicePrices = [];
let activeService = null;
let isSaving = false;
let priceLoadVersion = 0;

function showNotice(message, type = "info") {
    notice.textContent = message;
    notice.className = `notice show ${type}`;
}

function hideNotice() {
    notice.textContent = "";
    notice.className = "notice";
}

function formatMoney(value) {
    return new Intl.NumberFormat("vi-VN").format(value) + " đ";
}

function unitLabel(unit) {
    return BILLING_UNIT_LABELS[unit] || unit;
}

function selectedProperty() {
    return properties.find(property => String(property.id) === propertySelect.value) || null;
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

    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    if (response.status === 204) return null;

    const data = await response.json().catch(() => null);
    if (!response.ok) {
        const detail = typeof data?.detail === "string"
            ? data.detail
            : Array.isArray(data?.detail)
                ? data.detail.map(item => item.msg || item).join("; ")
                : `Yêu cầu thất bại (HTTP ${response.status}).`;
        throw new Error(detail);
    }
    return data;
}

function renderServicePrices() {
    servicePriceList.replaceChildren();
    priceEmpty.hidden = Boolean(selectedProperty() && servicePrices.length);
    if (selectedProperty() && !servicePrices.length) {
        priceEmpty.textContent = "Danh mục dịch vụ chưa có dữ liệu.";
    } else {
        priceEmpty.textContent = "Chọn khu trọ để xem cấu hình đơn giá.";
    }

    for (const service of servicePrices) {
        const configured = service.unit_price !== null && service.unit_price !== undefined;
        const card = createElement("article", "price-card");
        const heading = createElement("div", "price-card-heading");
        const identity = createElement("div");
        identity.append(
            createElement("h3", "", service.name),
            createElement("span", "price-code", service.code),
        );
        heading.append(identity, createElement(
            "span",
            `price-status${configured ? " configured" : ""}`,
            configured ? "Đã cấu hình" : "Chưa cấu hình",
        ));

        const value = createElement(
            "p",
            `price-value${configured ? "" : " unconfigured"}`,
            configured ? `${formatMoney(service.unit_price)} / ${unitLabel(service.billing_unit)}` : "Chưa cấu hình",
        );
        const units = service.allowed_units.map(unitLabel).join(" hoặc ");
        const unit = createElement(
            "p",
            "price-unit",
            configured ? `Đơn vị tính: ${unitLabel(service.billing_unit)}` : `Đơn vị phù hợp: ${units}`,
        );
        const button = createElement(
            "button",
            "button button-outline",
            configured ? "Chỉnh sửa" : "Nhập đơn giá",
        );
        button.type = "button";
        button.addEventListener("click", () => openPriceDialog(service));
        card.append(heading, value, unit, button);
        servicePriceList.append(card);
    }
}

async function loadServicePrices() {
    const version = ++priceLoadVersion;
    const property = selectedProperty();
    priceError.hidden = true;
    servicePriceList.replaceChildren();
    servicePrices = [];

    if (!property) {
        priceLoading.hidden = true;
        priceSummary.textContent = "Chọn khu trọ để xem cấu hình đơn giá.";
        renderServicePrices();
        return;
    }

    priceSummary.textContent = `Đơn giá áp dụng tại ${property.name}.`;
    priceLoading.hidden = false;
    priceEmpty.hidden = true;

    try {
        const result = await apiRequest(`/properties/${property.id}/service-prices`);
        if (version !== priceLoadVersion) return;
        servicePrices = result;
        priceLoading.hidden = true;
        renderServicePrices();
    } catch (error) {
        if (version !== priceLoadVersion) return;
        priceLoading.hidden = true;
        priceError.textContent = `Không tải được danh mục đơn giá: ${error.message}`;
        priceError.hidden = false;
        priceSummary.textContent = `Không tải được đơn giá tại ${property.name}.`;
        showNotice(error.message, "error");
    }
}

function setSaving(isLoading) {
    isSaving = isLoading;
    savePriceBtn.disabled = isLoading;
    cancelPriceBtn.disabled = isLoading;
    closePriceDialogBtn.disabled = isLoading;
    billingUnitSelect.disabled = isLoading;
    unitPriceInput.disabled = isLoading;
    savePriceLabel.textContent = isLoading ? "Đang lưu..." : "Lưu cấu hình";
    savePriceSpinner.hidden = !isLoading;
    priceDialog.setAttribute("aria-busy", String(isLoading));
}

function openPriceDialog(service) {
    if (!selectedProperty() || isSaving) return;

    activeService = service;
    const configured = service.unit_price !== null && service.unit_price !== undefined;
    priceDialogTitle.textContent = configured ? "Chỉnh sửa đơn giá" : "Nhập đơn giá";
    priceServiceName.value = service.name;
    billingUnitSelect.replaceChildren();
    for (const unit of service.allowed_units) {
        billingUnitSelect.append(new Option(unitLabel(unit), unit));
    }
    billingUnitSelect.value = configured ? service.billing_unit : service.allowed_units[0] || "";
    unitPriceInput.value = configured ? String(service.unit_price) : "";
    priceFormError.textContent = "";
    priceFormError.hidden = true;
    setSaving(false);
    priceDialog.showModal();
}

async function saveServicePrice(event) {
    event.preventDefault();
    if (!activeService || isSaving) return;

    const rawPrice = unitPriceInput.value.trim();
    const unitPrice = Number(rawPrice);
    if (!rawPrice || !Number.isSafeInteger(unitPrice) || unitPrice < 0 || unitPrice > 2_147_483_647) {
        priceFormError.textContent = "Đơn giá phải là số nguyên từ 0 đến 2.147.483.647 VNĐ.";
        priceFormError.hidden = false;
        unitPriceInput.focus();
        return;
    }

    const billingUnit = billingUnitSelect.value;
    if (!activeService.allowed_units.includes(billingUnit)) {
        priceFormError.textContent = "Hãy chọn đơn vị tính phù hợp với dịch vụ.";
        priceFormError.hidden = false;
        billingUnitSelect.focus();
        return;
    }

    const property = selectedProperty();
    if (!property) {
        priceFormError.textContent = "Hãy chọn khu trọ trước khi lưu đơn giá.";
        priceFormError.hidden = false;
        return;
    }

    setSaving(true);
    priceFormError.textContent = "";
    priceFormError.hidden = true;
    try {
        const saved = await apiRequest(
            `/properties/${property.id}/service-prices/${encodeURIComponent(activeService.code)}`,
            {
                method: "PUT",
                body: JSON.stringify({ billing_unit: billingUnit, unit_price: unitPrice }),
            },
        );
        if (!saved || saved.code !== activeService.code) {
            throw new Error("Backend trả về cấu hình đơn giá không hợp lệ.");
        }

        servicePrices = servicePrices.map(service => service.code === saved.code ? saved : service);
        renderServicePrices();
        priceDialog.close();
        activeService = null;
        showNotice(`Đã lưu đơn giá dịch vụ ${saved.name}.`, "success");
    } catch (error) {
        priceFormError.textContent = `Không thể lưu đơn giá: ${error.message}`;
        priceFormError.hidden = false;
        showNotice(error.message, "error");
    } finally {
        setSaving(false);
    }
}

propertySelect.addEventListener("change", () => {
    hideNotice();
    loadServicePrices();
});

priceForm.addEventListener("submit", saveServicePrice);
closePriceDialogBtn.addEventListener("click", () => {
    if (!isSaving) priceDialog.close();
});
cancelPriceBtn.addEventListener("click", () => {
    if (!isSaving) priceDialog.close();
});
priceDialog.addEventListener("click", event => {
    if (event.target === priceDialog && !isSaving) priceDialog.close();
});
priceDialog.addEventListener("cancel", event => {
    if (isSaving) event.preventDefault();
});
priceDialog.addEventListener("close", () => {
    activeService = null;
    if (!isSaving) priceDialog.removeAttribute("aria-busy");
});

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
        properties.forEach(property => propertySelect.append(new Option(property.name, String(property.id))));
        propertySelect.disabled = properties.length === 0;

        if (!properties.length) {
            priceSummary.textContent = "Tài khoản này chưa được cấp quyền quản lý khu trọ nào.";
            priceEmpty.textContent = "Không có khu trọ trong phạm vi tài khoản hiện tại.";
            priceEmpty.hidden = false;
            return;
        }

        propertySelect.value = String(properties[0].id);
        await loadServicePrices();
    } catch (error) {
        propertySelect.disabled = true;
        priceSummary.textContent = "Không tải được dữ liệu cấu hình đơn giá.";
        priceError.textContent = `Không tải được dữ liệu trang: ${error.message}`;
        priceError.hidden = false;
        showNotice(error.message, "error");
    }
}

bootstrap();
