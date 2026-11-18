const token = sessionStorage.getItem("us05_access_token");
const section = document.getElementById("tenantSection");
const form = document.getElementById("tenantForm");
const notice = document.getElementById("notice");
const list = document.getElementById("tenantList");
const cancelEdit = document.getElementById("cancelEdit");
const title = document.getElementById("formTitle");
const propertyField = document.getElementById("propertyField");
const property = form.elements.property_id;
const identityFields = ["full_name", "phone", "id_number", "id_issue_date", "id_issue_place", "hometown"];
let manager = false;
let editing = null;

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

function action(parent, label, handler) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button button-outline";
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
    parent.append(button, " ");
}

async function loadTenants() {
    const tenants = await (await request("/tenants")).json();
    list.replaceChildren();
    if (!tenants.length) list.textContent = "Chưa có hồ sơ khách thuê.";
    for (const tenant of tenants) {
        const row = document.createElement("article");
        const heading = document.createElement("h3");
        heading.textContent = tenant.full_name;
        const details = document.createElement("p");
        details.textContent = [tenant.phone, tenant.id_number, tenant.id_issue_date, tenant.id_issue_place, tenant.hometown].filter(Boolean).join(" · ");
        row.append(heading, details);
        const url = `/tenants/${tenant.id}/id-photo`;
        const file = document.createElement("input");
        file.type = "file";
        file.accept = "image/png,image/jpeg";
        file.setAttribute("aria-label", `Ảnh CCCD của ${tenant.full_name}`);
        row.append(file);
        action(row, "Lưu ảnh CCCD", async () => {
            const selected = file.files[0];
            if (!selected) throw new Error("Hãy chọn ảnh CCCD.");
            await request(url, {method: "PUT", headers: {"Content-Type": selected.type}, body: selected});
            notice.textContent = "Đã lưu ảnh CCCD.";
            await loadTenants();
        });
        if (tenant.id_photo_type) {
            action(row, "Tải ảnh CCCD", async () => {
                const response = await request(url);
                const objectUrl = URL.createObjectURL(await response.blob());
                const link = document.createElement("a");
                link.href = objectUrl;
                link.download = `cccd-${tenant.id}.${tenant.id_photo_type === "image/png" ? "png" : "jpg"}`;
                link.click();
                setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
            });
            action(row, "Xóa ảnh", async () => {
                if (!confirm("Xóa ảnh CCCD của hồ sơ này?")) return;
                await request(url, {method: "DELETE"});
                notice.textContent = "Đã xóa ảnh CCCD.";
                await loadTenants();
            });
        }
        action(row, "Sửa hồ sơ", () => {
            resetEditor(tenant);
            form.elements.full_name.focus();
        });
        action(row, "Xóa hồ sơ", async () => {
            if (!confirm(`Xóa hồ sơ của ${tenant.full_name}?`)) return;
            await request(`/tenants/${tenant.id}`, {method: "DELETE"});
            if (editing === tenant.id) resetEditor();
            notice.textContent = "Đã xóa hồ sơ.";
            await loadTenants();
        });
        list.append(row);
    }
}

cancelEdit.addEventListener("click", () => resetEditor());
form.addEventListener("submit", async event => {
    event.preventDefault();
    const button = form.querySelector("[type=submit]");
    if (button.disabled) return;
    const payload = {};
    for (const field of identityFields) payload[field] = form.elements[field].value.trim() || null;
    if (editing === null && manager) payload.property_id = Number(property.value);
    button.disabled = true;
    try {
        await request(editing === null ? "/tenants" : `/tenants/${editing}`, {
            method: editing === null ? "POST" : "PUT",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload),
        });
        resetEditor();
        notice.textContent = "Đã lưu hồ sơ.";
        await loadTenants();
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
