const API_BASE = "/api";
const accessToken = sessionStorage.getItem("us05_access_token") || "";

const categoryLabels = {
    repair: "Sửa chữa",
    supplies: "Vật tư",
    operations: "Vận hành",
    cleaning: "Vệ sinh",
    other: "Khác"
};

let currentUser = null;
let properties = [];
let expenses = [];
let page = 1;
let pageSize = 10;
let totalPages = 1;
let activeExpense = null;
let deleteExpenseId = null;
let searchTimer = null;

// Các hàm tiện ích định dạng, truy cập giao diện và thông báo.
const el = id => document.getElementById(id);

function createElement(tag, className, text) {
    const node = document.createElement(tag);

    if (className) {
        node.className = className;
    }

    if (text !== undefined) {
        node.textContent = text;
    }

    return node;
}

function formatMoney(value) {
    return new Intl.NumberFormat("vi-VN").format(Number(value) || 0) + " đ";
}

function formatDate(value) {
    if (!value) {
        return "";
    }

    const datePart = value.includes("T") ? value.split("T")[0] : value;
    const [year, month, day] = datePart.split("-");

    return year && month && day ? `${day}/${month}/${year}` : value;
}

function localDateString() {
    const date = new Date();

    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function showToast(message, type = "success") {
    const toast = el("toast");

    toast.textContent = message;
    toast.className = `toast show ${type}`;
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => toast.className = "toast", 3500);
}

function showNotice(message, type = "info") {
    const notice = el("notice");

    notice.textContent = message;
    notice.className = `notice show ${type}`;
}

// Gọi API và xử lý phiên đăng nhập hết hạn.
async function apiRequest(path, options = {}) {
    const headers = new Headers(options.headers || {});

    headers.set("Authorization", `Bearer ${accessToken}`);

    if (options.body && !headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
    }

    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });

    if (response.status === 401) {
        logout();
    }

    if (response.status === 204) {
        return null;
    }

    const data = await response.json().catch(() => null);

    if (!response.ok) {
        const detail = typeof data?.detail === "string"
            ? data.detail
            : Array.isArray(data?.detail)
                ? data.detail.map(item => item.msg).join("; ")
                : `Yêu cầu thất bại (HTTP ${response.status}).`;
        const error = new Error(detail);

        error.status = response.status;
        throw error;
    }

    return data;
}

function logout() {
    sessionStorage.removeItem("us05_access_token");
    window.location.href = "/register/html/login.html";
}

// Khởi tạo trang và nạp danh sách khu trọ được giao.
async function init() {
    if (!accessToken) {
        el("accountInfo").textContent = "Chưa đăng nhập";
        showNotice("Vui lòng đăng nhập bằng tài khoản chủ trọ hoặc quản lý.", "error");
        return;
    }

    try {
        currentUser = await apiRequest("/users/me");

        if (!["landlord", "manager"].includes(currentUser.role)) {
            el("accountInfo").textContent = currentUser.full_name || currentUser.role;
            showNotice("Trang này dành cho chủ nhà và quản lý", "error");

            const suitableLink = createElement("a", "", "Đăng nhập bằng tài khoản khác");

            suitableLink.href = "/register/html/login.html";
            el("notice").append(createElement("br"), suitableLink);
            el("expenseSection").hidden = true;
            return;
        }

        el("accountInfo").textContent = `${currentUser.full_name} · ${currentUser.role === "landlord" ? "Chủ nhà" : "Quản lý"}`;
        await loadProperties();
        el("expenseSection").hidden = false;
        bindEvents();
        await loadData();
    } catch (error) {
        if (error.status === 401) {
            logout();
            return;
        }

        el("accountInfo").textContent = "Không thể xác thực";
        showNotice(error.message, "error");
    }
}

async function loadProperties() {
    properties = await apiRequest("/properties");

    for (const property of properties) {
        const filterOption = createElement("option", "", property.name);

        filterOption.value = property.id;
        el("propertyFilter").append(filterOption);

        const formOption = createElement("option", "", property.name);

        formOption.value = property.id;
        el("expenseProperty").append(formOption);
    }

    const hasProperties = properties.length > 0;
    const addExpenseButton = el("addExpenseBtn");

    el("noPropertyNotice").hidden = hasProperties;
    addExpenseButton.disabled = !hasProperties;

    if (hasProperties) {
        addExpenseButton.removeAttribute("title");
    } else {
        addExpenseButton.title = "Bạn chưa được giao khu trọ nên chưa thể ghi nhận chi phí.";
    }
}

// Gắn sự kiện cho bộ lọc, phân trang, biểu mẫu và hộp thoại.
function bindEvents() {
    el("logoutBtn").addEventListener("click", logout);
    el("addExpenseBtn").addEventListener("click", () => openExpenseDialog());
    el("closeExpenseDialogBtn").addEventListener("click", () => el("expenseDialog").close());
    el("cancelExpenseBtn").addEventListener("click", () => el("expenseDialog").close());
    el("expenseForm").addEventListener("submit", saveExpense);
    el("expenseForm").addEventListener("input", clearFieldError);
    el("expenseForm").addEventListener("change", clearFieldError);
    el("expenseProperty").addEventListener("change", () => loadRooms(el("expenseProperty").value));
    el("propertyFilter").addEventListener("change", () => {
        page = 1;
        loadData();
    });
    el("categoryFilter").addEventListener("change", () => {
        page = 1;
        loadData();
    });
    el("dateFromFilter").addEventListener("change", () => {
        page = 1;
        loadData();
    });
    el("dateToFilter").addEventListener("change", () => {
        page = 1;
        loadData();
    });
    el("searchFilter").addEventListener("input", () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
            page = 1;
            loadData();
        }, 300);
    });
    el("clearFiltersBtn").addEventListener("click", clearFilters);
    el("prevPageBtn").addEventListener("click", () => {
        if (page > 1) {
            page--;
            loadData();
        }
    });
    el("nextPageBtn").addEventListener("click", () => {
        if (page < totalPages) {
            page++;
            loadData();
        }
    });
    el("closeDeleteDialogBtn").addEventListener("click", () => el("deleteExpenseDialog").close());
    el("cancelDeleteExpenseBtn").addEventListener("click", () => el("deleteExpenseDialog").close());
    el("confirmDeleteExpenseBtn").addEventListener("click", confirmDelete);
}

function clearFilters() {
    el("propertyFilter").value = "";
    el("categoryFilter").value = "";
    el("dateFromFilter").value = "";
    el("dateToFilter").value = "";
    el("searchFilter").value = "";
    page = 1;
    loadData();
}

function clearFieldError(event) {
    const field = event.target;

    if (!field.id || !field.id.startsWith("expense")) {
        return;
    }

    const error = el(`${field.id}Error`);

    if (!error) {
        return;
    }

    field.classList.remove("field-invalid");
    error.textContent = "";
}

// Tải và hiển thị chi phí theo bộ lọc hiện tại.
async function loadData() {
    el("expensesLoading").hidden = false;
    el("expensesError").hidden = true;
    el("expensesEmpty").hidden = true;
    el("expensesTableContainer").hidden = true;

    const dateFrom = el("dateFromFilter").value;
    const dateTo = el("dateToFilter").value;

    if (dateFrom && dateTo && dateFrom > dateTo) {
        showToast("Từ ngày không được sau đến ngày.", "error");
        el("expensesLoading").hidden = true;
        return;
    }

    const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize)
    });

    if (el("propertyFilter").value) {
        params.set("property_id", el("propertyFilter").value);
    }

    if (el("categoryFilter").value) {
        params.set("category", el("categoryFilter").value);
    }

    if (dateFrom) {
        params.set("date_from", dateFrom);
    }

    if (dateTo) {
        params.set("date_to", dateTo);
    }

    if (el("searchFilter").value.trim()) {
        params.set("search", el("searchFilter").value.trim());
    }

    try {
        const [list, summary] = await Promise.all([
            apiRequest(`/expenses?${params}`),
            apiRequest(`/expenses/summary?${summaryParams(params)}`)
        ]);

        if (!list.items.length && list.total > 0 && page > 1) {
            page = Math.max(1, Math.ceil(list.total / list.page_size));
            await loadData();
            return;
        }

        expenses = list.items;
        renderTable(list);
        renderSummary(summary);
    } catch (error) {
        el("expensesError").textContent = error.message;
        el("expensesError").hidden = false;
    } finally {
        el("expensesLoading").hidden = true;
    }
}

function summaryParams(params) {
    const summary = new URLSearchParams();

    if (params.has("property_id")) {
        summary.set("property_id", params.get("property_id"));
    }

    if (params.has("date_from")) {
        summary.set("date_from", params.get("date_from"));
    }

    if (params.has("date_to")) {
        summary.set("date_to", params.get("date_to"));
    }

    return summary.toString() ? `?${summary}` : "";
}

// Kết xuất thẻ tổng hợp, bảng chi phí và các ô dữ liệu.
function renderSummary(summary) {
    el("totalSummary").textContent = formatMoney(summary.total_amount);
    el("countSummary").textContent = String(summary.count);
    el("topCategory").textContent = summary.by_category.length ? summary.by_category[0].category_label : "-";
    el("categoryWeights").replaceChildren();

    for (const item of summary.by_category) {
        const row = createElement("div", "weight-row");
        const percent = summary.total_amount ? Math.round(item.total / summary.total_amount * 100) : 0;

        row.append(createElement("span", "", item.category_label));

        const track = createElement("div", "weight-track");
        const bar = createElement("div", "weight-bar");

        bar.style.width = `${percent}%`;
        track.append(bar);
        row.append(track, createElement("span", "", `${formatMoney(item.total)} · ${percent}%`));
        el("categoryWeights").append(row);
    }
}

function renderTable(data) {
    el("expenseRows").replaceChildren();
    el("totalFiltered").textContent = `Tổng theo bộ lọc: ${formatMoney(data.total_amount)}`;

    totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
    el("pageInfo").textContent = `Trang ${data.page}/${totalPages}`;
    el("pageTotal").textContent = `${data.total} khoản`;
    el("prevPageBtn").disabled = data.page <= 1;
    el("nextPageBtn").disabled = data.page >= totalPages;

    if (!data.items.length) {
        el("expensesEmpty").hidden = false;
        el("expensesTableContainer").hidden = true;
        return;
    }

    el("expensesEmpty").hidden = true;
    el("expensesTableContainer").hidden = false;

    for (const expense of data.items) {
        const row = document.createElement("tr");
        const location = expense.room_number
            ? `${expense.property_name} · Phòng ${expense.room_number}`
            : `${expense.property_name} · Chi phí chung`;

        row.append(
            td(formatDate(expense.expense_date), "Ngày chi"),
            td(location, "Khu trọ/Phòng"),
            categoryCell(expense.category),
            td(expense.vendor ? `${expense.description} · ${expense.vendor}` : expense.description, "Nội dung"),
            td(formatMoney(expense.amount), "Số tiền")
        );

        const actions = createElement("td", "expense-actions");

        actions.dataset.label = "Thao tác";

        const edit = createElement("button", "button button-outline expense-action", "Sửa");

        edit.type = "button";
        edit.addEventListener("click", () => openExpenseDialog(expense));

        const remove = createElement("button", "button button-danger expense-action", "Xóa");

        remove.type = "button";
        remove.addEventListener("click", () => openDeleteDialog(expense));
        actions.append(edit, remove);
        row.append(actions);
        el("expenseRows").append(row);
    }
}

function td(text, label) {
    const cell = createElement("td", "", text);

    if (label) {
        cell.dataset.label = label;
    }

    return cell;
}

function categoryCell(category) {
    const cell = createElement("td");

    cell.dataset.label = "Danh mục";

    const badge = createElement("span", `category-badge category-${category}`, categoryLabels[category] || category);

    cell.append(badge);
    return cell;
}

// Chuẩn bị biểu mẫu, tải phòng và quản lý lỗi nhập liệu.
async function openExpenseDialog(expense = null) {
    activeExpense = expense;
    clearFieldErrors();
    el("expenseFormSummary").hidden = true;
    el("expenseDialogTitle").textContent = expense ? "Sửa chi phí" : "Thêm chi phí";
    el("expenseProperty").disabled = !!expense;

    if (expense) {
        el("expenseProperty").value = expense.property_id;
        el("expenseCategory").value = expense.category;
        el("expenseDescription").value = expense.description || "";
        el("expenseVendor").value = expense.vendor || "";
        el("expenseAmount").value = expense.amount;
        el("expenseDate").value = expense.expense_date;
        await loadRooms(expense.property_id, expense.room_id);
    } else {
        el("expenseProperty").value = el("propertyFilter").value || properties[0]?.id || "";
        el("expenseCategory").value = "";
        el("expenseDescription").value = "";
        el("expenseVendor").value = "";
        el("expenseAmount").value = "";
        el("expenseDate").value = localDateString();
        await loadRooms(el("expenseProperty").value);
    }

    el("expenseDate").max = localDateString();
    el("expenseDialog").showModal();
}

async function loadRooms(propertyId, selected = null) {
    el("expenseRoom").replaceChildren(createElement("option", "", "Chi phí chung"));

    if (!propertyId) {
        return;
    }

    try {
        const rooms = await apiRequest(`/properties/${propertyId}/rooms`);

        for (const room of rooms) {
            const option = createElement("option", "", room.room_number);

            option.value = room.id;
            el("expenseRoom").append(option);
        }

        el("expenseRoom").value = selected ? String(selected) : "";
    } catch (error) {
        showToast(error.message, "error");
    }
}

function clearFieldErrors() {
    for (const name of ["Property", "Room", "Category", "Description", "Vendor", "Amount", "Date"]) {
        const input = el(`expense${name}`);
        const error = el(`expense${name}Error`);

        if (input) {
            input.classList.remove("field-invalid");
        }

        if (error) {
            error.textContent = "";
        }
    }
}

function setFieldError(name, message) {
    const input = el(`expense${name}`);
    const error = el(`expense${name}Error`);

    if (input) {
        input.classList.add("field-invalid");
    }

    if (error) {
        error.textContent = message;
    }
}

function validateForm() {
    clearFieldErrors();

    const missing = [];

    if (!el("expenseProperty").value) {
        setFieldError("Property", "Hãy chọn khu trọ.");
        missing.push("Khu trọ");
    }

    if (!el("expenseCategory").value) {
        setFieldError("Category", "Hãy chọn danh mục chi.");
        missing.push("Danh mục");
    }

    if (!el("expenseDescription").value.trim()) {
        setFieldError("Description", "Nội dung không được để trống.");
        missing.push("Nội dung");
    }

    const amount = Number(el("expenseAmount").value);

    if (!el("expenseAmount").value || !Number.isInteger(amount) || amount <= 0 || amount > 2000000000) {
        setFieldError("Amount", "Số tiền phải là số nguyên lớn hơn 0 và tối đa 2.000.000.000.");
        missing.push("Số tiền");
    }

    if (!el("expenseDate").value) {
        setFieldError("Date", "Hãy chọn ngày chi.");
        missing.push("Ngày chi");
    } else if (el("expenseDate").value > localDateString()) {
        setFieldError("Date", "Ngày chi không được ở tương lai.");
        missing.push("Ngày chi");
    }

    if (el("expenseVendor").value.length > 120) {
        setFieldError("Vendor", "Đơn vị thực hiện tối đa 120 ký tự.");
        missing.push("Đơn vị thực hiện");
    }

    if (missing.length) {
        el("expenseFormSummary").textContent = `Vui lòng sửa các mục: ${missing.join(", ")}.`;
        el("expenseFormSummary").hidden = false;
        return false;
    }

    return true;
}

async function saveExpense(event) {
    event.preventDefault();

    if (!validateForm()) {
        return;
    }

    const body = {
        category: el("expenseCategory").value,
        description: el("expenseDescription").value.trim(),
        vendor: el("expenseVendor").value.trim() || null,
        amount: Number(el("expenseAmount").value),
        expense_date: el("expenseDate").value,
        room_id: el("expenseRoom").value ? Number(el("expenseRoom").value) : null
    };

    if (!activeExpense) {
        body.property_id = Number(el("expenseProperty").value);
    }

    try {
        el("saveExpenseBtn").disabled = true;

        if (activeExpense) {
            await apiRequest(`/expenses/${activeExpense.id}`, {
                method: "PUT",
                body: JSON.stringify(body)
            });
        } else {
            await apiRequest("/expenses", {
                method: "POST",
                body: JSON.stringify(body)
            });
        }

        el("expenseDialog").close();
        showToast(activeExpense ? "Đã cập nhật khoản chi." : "Đã thêm khoản chi.", "success");
        activeExpense = null;
        await loadData();
    } catch (error) {
        el("expenseFormSummary").textContent = error.message;
        el("expenseFormSummary").hidden = false;
    } finally {
        el("saveExpenseBtn").disabled = false;
    }
}

// Xác nhận xóa khoản chi đã chọn.
function openDeleteDialog(expense) {
    deleteExpenseId = expense.id;
    el("deleteExpenseSummary").textContent = `Xóa khoản chi "${expense.description}" số tiền ${formatMoney(expense.amount)} ngày ${formatDate(expense.expense_date)}?`;
    el("deleteExpenseDialog").showModal();
}

async function confirmDelete() {
    if (!deleteExpenseId) {
        return;
    }

    try {
        el("confirmDeleteExpenseBtn").disabled = true;
        await apiRequest(`/expenses/${deleteExpenseId}`, { method: "DELETE" });
        el("deleteExpenseDialog").close();
        deleteExpenseId = null;
        showToast("Đã xóa khoản chi.", "success");
        await loadData();
    } catch (error) {
        showToast(error.message, "error");
    } finally {
        el("confirmDeleteExpenseBtn").disabled = false;
    }
}

init();
