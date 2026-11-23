const token = sessionStorage.getItem("us05_access_token");
const section = document.getElementById("tenantSection");
const form = document.getElementById("tenantForm");
const notice = document.getElementById("notice");
const list = document.getElementById("tenantList");
const searchInput = document.getElementById("tenantSearch");
const clearSearchButton = document.getElementById("clearTenantSearch");
const resultCount = document.getElementById("tenantResultCount");
const pagination = document.getElementById("tenantPagination");
const previousButton = document.getElementById("tenantPreviousBtn");
const nextButton = document.getElementById("tenantNextBtn");
const TENANT_PAGE_SIZE = 10;
const cancelEdit = document.getElementById("cancelEdit");
const title = document.getElementById("formTitle");
const propertyField = document.getElementById("propertyField");
const property = form.elements.property_id;
const identityFields = ["full_name", "phone", "id_number", "id_issue_date", "id_issue_place", "hometown"];
let manager = false;
let editing = null;
let tenantPage = 1;
let tenantRequestId = 0;
let searchTimer = null;
let accountLinkTenant = null;

async function request(path, options = {}) {
    const headers = new Headers(options.headers);
    headers.set("Authorization", `Bearer ${token}`);
    const response = await fetch(`/api${path}`, {...options, headers});
    if (!response.ok) {
        const data = await response.json().catch(() => null);
        const detail = data?.detail;
        throw new Error(Array.isArray(detail) ? detail.map(item => item.msg).join(". ") : detail || `HTTP ${response.status}`);
    }
    return response;
}

function resetEditor(tenant = null) {
    editing = tenant?.id ?? null;
    form.reset();
    for (const field of identityFields) form.elements[field].value = tenant?.[field] ?? "";
    title.textContent = tenant ? "Chỉnh sửa khách thuê" : "Thêm khách thuê";
    cancelEdit.hidden = !tenant;
    propertyField.hidden = Boolean(tenant) || !manager;
    property.required = !tenant && manager;
}

function action(parent, label, handler, className = "button button-outline") {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = label;
    button.addEventListener("click", async () => {
        button.disabled = true;
        try {
            await handler();
        } catch (error) {
            notice.textContent = error.message;
        } finally {
            button.disabled = false;
        }
    });
    parent.append(button);
}

const accountLinkDialog = document.getElementById("accountLinkDialog");
const accountLinkForm = document.getElementById("accountLinkForm");
const accountLinkIdentifier = document.getElementById("accountLinkIdentifier");
const accountLinkError = document.getElementById("accountLinkError");
const accountLinkSubmitBtn = document.getElementById("accountLinkSubmitBtn");
const accountLinkCancelBtn = document.getElementById("accountLinkCancelBtn");
const accountLinkCloseBtn = document.getElementById("accountLinkCloseBtn");

function openAccountLinkModal(tenant) {
    accountLinkTenant = tenant;
    accountLinkForm.reset();
    accountLinkError.textContent = "";
    accountLinkSubmitBtn.disabled = false;
    accountLinkDialog.showModal();
    requestAnimationFrame(() => accountLinkIdentifier.focus());
}

function closeAccountLinkModal() {
    if (accountLinkSubmitBtn.disabled) return;
    accountLinkDialog.close();
    accountLinkTenant = null;
    accountLinkError.textContent = "";
}

accountLinkCancelBtn.addEventListener("click", closeAccountLinkModal);
accountLinkCloseBtn.addEventListener("click", closeAccountLinkModal);
accountLinkDialog.addEventListener("cancel", event => {
    if (accountLinkSubmitBtn.disabled) {
        event.preventDefault();
        return;
    }
    accountLinkTenant = null;
    accountLinkError.textContent = "";
});
accountLinkDialog.addEventListener("click", event => {
    if (event.target === accountLinkDialog) closeAccountLinkModal();
});

accountLinkForm.addEventListener("submit", async event => {
    event.preventDefault();
    if (!accountLinkTenant) return;
    const identifier = accountLinkIdentifier.value.trim();
    if (!identifier) {
        accountLinkError.textContent = "Vui lòng nhập email hoặc số điện thoại.";
        accountLinkIdentifier.focus();
        return;
    }
    accountLinkError.textContent = "";
    accountLinkSubmitBtn.disabled = true;
    accountLinkCancelBtn.disabled = true;
    accountLinkCloseBtn.disabled = true;
    try {
        const payload = await request(`/tenants/${accountLinkTenant.id}/account`, {
            method: "PUT",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({identifier})
        }).then(response => response.json());
        const tenantName = accountLinkTenant.full_name;
        accountLinkDialog.close();
        accountLinkTenant = null;
        notice.textContent = `Đã liên kết tài khoản ${payload.full_name} (${payload.email}) với hồ sơ ${tenantName}.`;
        await loadTenants();
    } catch (error) {
        accountLinkError.textContent = error.message;
    } finally {
        accountLinkSubmitBtn.disabled = false;
        accountLinkCancelBtn.disabled = false;
        accountLinkCloseBtn.disabled = false;
    }
});

async function loadTenants(resetPage = false) {
    if (resetPage) tenantPage = 1;
    const requestId = ++tenantRequestId;
    const search = searchInput.value.trim();
    const pageSize = TENANT_PAGE_SIZE;
    const query = `${search ? `q=${encodeURIComponent(search)}&` : ""}page=${tenantPage}&page_size=${pageSize}`;
    clearSearchButton.hidden = !searchInput.value;
    let result;
    try {
        result = await (await request(`/tenants?${query}`)).json();
    } catch (error) {
        if (requestId !== tenantRequestId) return;
        throw error;
    }
    if (requestId !== tenantRequestId) return;
    const tenants = result.items || [];
    if (tenants.length === 0 && result.total > 0 && tenantPage > 1) {
        tenantPage = Math.max(1, Math.ceil(result.total / result.page_size));
        await loadTenants();
        return;
    }

    resultCount.textContent = search
        ? `${result.total} kết quả cho "${search}"`
        : `${result.total} khách thuê`;
    const totalPages = Math.max(1, Math.ceil(result.total / result.page_size));
    pagination.hidden = result.total === 0;
    document.getElementById("tenantPageInfo").textContent = `Trang ${result.page}/${totalPages}`;
    previousButton.disabled = result.page <= 1;
    nextButton.disabled = result.page >= totalPages;

    list.replaceChildren();
    if (!tenants.length) {
        const emptyState = document.createElement("div");
        emptyState.className = "tenant-empty-state";
        emptyState.textContent = search
            ? `Không tìm thấy khách thuê nào khớp với "${search}". Thử nhập tên, số CCCD hoặc số điện thoại khác.`
            : "Chưa có hồ sơ khách thuê.";
        list.append(emptyState);
    }
    for (const tenant of tenants) {
        const row = document.createElement("article");
        row.className = "tenant-card";

        const header = document.createElement("div");
        header.className = "tenant-card-header";
        const avatar = document.createElement("div");
        avatar.className = "tenant-avatar";
        avatar.textContent = tenant.full_name ? tenant.full_name.trim().charAt(0).toUpperCase() : "?";
        avatar.setAttribute("aria-hidden", "true");
        const headingWrap = document.createElement("div");
        headingWrap.className = "tenant-card-heading";
        const heading = document.createElement("h3");
        heading.textContent = tenant.full_name;
        const tenantCode = document.createElement("p");
        tenantCode.textContent = `Mã hồ sơ: ${tenant.id}`;
        headingWrap.append(heading, tenantCode);
        header.append(avatar, headingWrap);

        const info = document.createElement("dl");
        info.className = "tenant-info-grid";
        const infoItems = [
            ["Số điện thoại", tenant.phone],
            ["Số CCCD", tenant.id_number],
            ["Ngày cấp", tenant.id_issue_date],
            ["Nơi cấp", tenant.id_issue_place],
            ["Quê quán", tenant.hometown],
        ];
        for (const [label, value] of infoItems) {
            const item = document.createElement("div");
            item.className = "tenant-info-item";
            const term = document.createElement("dt");
            term.textContent = label;
            const description = document.createElement("dd");
            description.textContent = value || "-";
            item.append(term, description);
            info.append(item);
        }

        const accountRow = document.createElement("div");
        accountRow.className = "tenant-account-row";
        const accountStatus = document.createElement("span");
        accountStatus.className = `tenant-account-status${tenant.user_id ? " linked" : ""}`;
        accountStatus.textContent = tenant.user_id ? "Đã liên kết" : "Chưa liên kết";
        const accountActions = document.createElement("div");
        accountActions.className = "tenant-account-actions";
        accountRow.append(accountStatus, accountActions);
        row.append(header, info, accountRow);

        if (tenant.user_id) {
            action(accountActions, "Gỡ liên kết", async () => {
                if (!confirm(`Gỡ liên kết tài khoản khỏi hồ sơ của ${tenant.full_name}?`)) return;
                await request(`/tenants/${tenant.id}/account`, {method: "DELETE"});
                notice.textContent = `Đã gỡ liên kết tài khoản khỏi hồ sơ ${tenant.full_name}.`;
                await loadTenants();
            });
        } else {
            action(accountActions, "Liên kết tài khoản", () => openAccountLinkModal(tenant));
        }

        const url = `/tenants/${tenant.id}/id-photo`;
        const file = document.createElement("input");
        file.type = "file";
        file.accept = "image/png,image/jpeg";
        file.setAttribute("aria-label", `Ảnh CCCD của ${tenant.full_name}`);
        const photoSection = document.createElement("section");
        photoSection.className = "tenant-photo-section";
        const photoHeading = document.createElement("h4");
        photoHeading.textContent = "Ảnh CCCD";
        const photoActions = document.createElement("div");
        photoActions.className = "tenant-photo-actions";
        photoSection.append(photoHeading, file, photoActions);
        row.append(photoSection);

        const cardActions = document.createElement("div");
        cardActions.className = "tenant-card-actions";
        action(cardActions, "Lưu ảnh CCCD", async () => {
            const selected = file.files[0];
            if (!selected) throw new Error("Hãy chọn ảnh CCCD.");
            await request(url, {method: "PUT", headers: {"Content-Type": selected.type}, body: selected});
            notice.textContent = "Đã lưu ảnh CCCD.";
            await loadTenants();
        }, "button tenant-save-photo");
        if (tenant.id_photo_type) {
            action(photoActions, "Tải ảnh CCCD", async () => {
                const response = await request(url);
                const objectUrl = URL.createObjectURL(await response.blob());
                const link = document.createElement("a");
                link.href = objectUrl;
                link.download = `cccd-${tenant.id}.${tenant.id_photo_type === "image/png" ? "png" : "jpg"}`;
                link.click();
                setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
            });
            action(photoActions, "Xóa ảnh", async () => {
                if (!confirm("Xóa ảnh CCCD của hồ sơ này?")) return;
                await request(url, {method: "DELETE"});
                notice.textContent = "Đã xóa ảnh CCCD.";
                await loadTenants();
            });
        }
        action(cardActions, "Sửa hồ sơ", () => {
            resetEditor(tenant);
            form.elements.full_name.focus();
        }, "button button-outline tenant-edit");
        action(cardActions, "Xóa hồ sơ", async () => {
            if (!confirm(`Xóa hồ sơ của ${tenant.full_name}?`)) return;
            await request(`/tenants/${tenant.id}`, {method: "DELETE"});
            if (editing === tenant.id) resetEditor();
            notice.textContent = "Đã xóa hồ sơ.";
            await loadTenants();
        }, "button tenant-delete");
        row.append(cardActions);
        list.append(row);
    }
}

cancelEdit.addEventListener("click", () => resetEditor());
searchInput.addEventListener("input", () => {
    tenantRequestId++;
    clearTimeout(searchTimer);
    clearSearchButton.hidden = !searchInput.value;
    searchTimer = setTimeout(() => loadTenants(true).catch(error => {
        notice.textContent = error.message;
    }), 300);
});
clearSearchButton.addEventListener("click", () => {
    searchInput.value = "";
    loadTenants(true).catch(error => {
        notice.textContent = error.message;
    });
});
previousButton.addEventListener("click", () => {
    if (tenantPage > 1) {
        tenantPage--;
        loadTenants().catch(error => {
            notice.textContent = error.message;
        });
    }
});
nextButton.addEventListener("click", () => {
    tenantPage++;
    loadTenants().catch(error => {
        notice.textContent = error.message;
    });
});
form.addEventListener("submit", async event => {
    event.preventDefault();
    const button = form.querySelector("[type=submit]");
    if (button.disabled) return;
    const payload = {};
    for (const field of identityFields) payload[field] = form.elements[field].value.trim() || null;
    if (editing === null && manager) payload.property_id = Number(property.value);
    button.disabled = true;
    try {
        const isCreating = editing === null;
        await request(isCreating ? "/tenants" : `/tenants/${editing}`, {
            method: editing === null ? "POST" : "PUT",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload),
        });
        resetEditor();
        notice.textContent = "Đã lưu hồ sơ.";
        await loadTenants(isCreating);
    } catch (error) {
        notice.textContent = error.message;
    } finally {
        button.disabled = false;
    }
});

async function start() {
    if (!token) throw new Error("Hãy đăng nhập bằng tài khoản chủ trọ hoặc người quản lý.");
    const user = await (await request("/users/me")).json();
    if (!["landlord", "manager"].includes(user.role)) throw new Error("Tài khoản này không có quyền quản lý khách thuê.");
    manager = user.role === "manager";
    if (manager) {
        const properties = await (await request("/properties")).json();
        property.add(new Option("Chọn khu trọ", ""));
        for (const item of properties) property.add(new Option(item.name, item.id));
    }
    resetEditor();
    await loadTenants();
    section.hidden = false;
}

start().catch(error => { notice.textContent = error.message; });
