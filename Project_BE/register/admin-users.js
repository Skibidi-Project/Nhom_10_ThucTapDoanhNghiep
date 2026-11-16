const token = sessionStorage.getItem("us05_access_token");
const searchInput = document.getElementById("searchInput");
const roleFilter = document.getElementById("roleFilter");
const pageInfo = document.getElementById("pageInfo");
const usersTable = document.getElementById("usersTable");
const usersTableBody = document.getElementById("usersTableBody");
const loadingState = document.getElementById("loadingState");
const emptyState = document.getElementById("emptyState");
const notice = document.getElementById("notice");
const prevPageBtn = document.getElementById("prevPage");
const nextPageBtn = document.getElementById("nextPage");
const logoutBtn = document.getElementById("logoutBtn");

let currentUser = null;
let page = 1;
let pageSize = 10;
let totalPages = 1;
let searchTerm = "";
let roleValue = "";
let debounceTimer = null;

function setNotice(message, type = "info") {
    notice.textContent = message;
    notice.className = `notice show ${type}`;
}

function clearNotice() {
    notice.textContent = "";
    notice.className = "notice";
}

function logout() {
    sessionStorage.removeItem("us05_access_token");
    window.location.assign("login.html");
}

async function fetchJson(url, options = {}) {
    const headers = new Headers(options.headers || {});
    headers.set("Authorization", `Bearer ${token}`);
    const response = await fetch(url, {...options, headers});
    if (!response.ok) {
        const data = await response.json().catch(() => null);
        const detail = Array.isArray(data?.detail)
            ? data.detail.map(item => item.msg).join("; ")
            : typeof data?.detail === "string"
                ? data.detail
                : `HTTP ${response.status}`;
        throw new Error(detail || "Yêu cầu không thành công.");
    }
    return response.headers.get("content-type")?.includes("application/json") ? response.json() : null;
}

function formatDate(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleDateString("vi-VN");
}

function roleLabel(role) {
    const labels = {
        admin: "Quản trị viên",
        landlord: "Chủ nhà",
        manager: "Quản lý",
        tenant: "Khách thuê"
    };
    return labels[role] || role || "-";
}

function roleClass(role) {
    return `role-${role || "tenant"}`;
}

function renderUsers(items) {
    usersTableBody.innerHTML = "";
    if (!items.length) {
        usersTable.hidden = true;
        emptyState.hidden = false;
        return;
    }
    emptyState.hidden = true;
    usersTable.hidden = false;

    for (const user of items) {
        const row = document.createElement("tr");
        const actionCell = document.createElement("td");
        actionCell.className = "action-cell";

        const select = document.createElement("select");
        select.className = "action-select";
        ["landlord", "manager", "tenant"].forEach((role) => {
            const option = document.createElement("option");
            option.value = role;
            option.textContent = roleLabel(role);
            option.selected = role === user.role;
            select.append(option);
        });

        const saveBtn = document.createElement("button");
        saveBtn.type = "button";
        saveBtn.className = "button button-primary";
        saveBtn.textContent = user.role === "admin" ? "Quản trị viên" : "Lưu";
        saveBtn.disabled = user.role === "admin";

        if (user.role !== "admin") {
            saveBtn.addEventListener("click", async () => {
                const selectedRole = select.value;
                if (selectedRole === user.role) {
                    setNotice("Vai trò hiện tại đã khớp, không cần thay đổi.", "info");
                    return;
                }
                if (!window.confirm(`Chuyển tài khoản ${user.full_name} sang vai trò ${roleLabel(selectedRole)}?`)) {
                    return;
                }
                saveBtn.disabled = true;
                try {
                    const payload = await fetchJson(`/api/users/${user.id}/role`, {
                        method: "PUT",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify({role: selectedRole})
                    });
                    const message = payload?.revoked_property_count != null
                        ? `Đã cập nhật vai trò. Số khu bị thu hồi: ${payload.revoked_property_count}.`
                        : "Cập nhật vai trò thành công.";
                    setNotice(message, "success");
                    await loadUsers();
                } catch (error) {
                    setNotice(error.message, "error");
                } finally {
                    saveBtn.disabled = false;
                }
            });
        }

        actionCell.append(select, saveBtn);

        row.innerHTML = `
            <td>${user.id}</td>
            <td>${user.full_name}</td>
            <td>${user.email}</td>
            <td>${user.phone || "-"}</td>
            <td><span class="role-badge ${roleClass(user.role)}">${roleLabel(user.role)}</span></td>
            <td>${formatDate(user.created_at)}</td>
        `;
        row.append(actionCell);
        usersTableBody.append(row);
    }
}

async function loadUsers() {
    loadingState.hidden = false;
    usersTable.hidden = true;
    emptyState.hidden = true;
    clearNotice();

    try {
        const params = new URLSearchParams({page: String(page), page_size: String(pageSize)});
        if (searchTerm) params.set("q", searchTerm);
        if (roleValue) params.set("role", roleValue);

        const data = await fetchJson(`/api/users?${params.toString()}`);
        totalPages = Math.max(1, Math.ceil(data.total / pageSize));
        page = Math.min(page, totalPages);
        pageInfo.textContent = `Trang ${page} / ${totalPages}`;
        prevPageBtn.disabled = page <= 1;
        nextPageBtn.disabled = page >= totalPages;
        renderUsers(data.items || []);
    } catch (error) {
        usersTable.hidden = true;
        emptyState.hidden = false;
        setNotice(error.message, "error");
    } finally {
        loadingState.hidden = true;
    }
}

async function ensureAdminAccess() {
    if (!token) {
        setNotice("Chỉ quản trị viên được truy cập. Vui lòng đăng nhập.", "error");
        const link = document.createElement("a");
        link.href = "login.html";
        link.textContent = "Quay lại đăng nhập";
        notice.append(" ");
        notice.append(link);
        return false;
    }

    try {
        const me = await fetchJson("/api/users/me");
        currentUser = me;
        if (me.role !== "admin") {
            setNotice("Chỉ quản trị viên được truy cập.", "error");
            const link = document.createElement("a");
            link.href = "login.html";
            link.textContent = "Về trang đăng nhập";
            notice.append(" ");
            notice.append(link);
            return false;
        }
        return true;
    } catch (error) {
        setNotice("Chỉ quản trị viên được truy cập.", "error");
        const link = document.createElement("a");
        link.href = "login.html";
        link.textContent = "Về trang đăng nhập";
        notice.append(" ");
        notice.append(link);
        return false;
    }
}

searchInput.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        page = 1;
        searchTerm = searchInput.value.trim();
        loadUsers();
    }, 300);
});

roleFilter.addEventListener("change", () => {
    page = 1;
    roleValue = roleFilter.value;
    loadUsers();
});

prevPageBtn.addEventListener("click", () => {
    if (page > 1) {
        page -= 1;
        loadUsers();
    }
});

nextPageBtn.addEventListener("click", () => {
    if (page < totalPages) {
        page += 1;
        loadUsers();
    }
});

logoutBtn.addEventListener("click", logout);

(async function init() {
    const ok = await ensureAdminAccess();
    if (!ok) {
        loadingState.hidden = true;
        usersTable.hidden = true;
        emptyState.hidden = true;
        return;
    }
    await loadUsers();
})();
