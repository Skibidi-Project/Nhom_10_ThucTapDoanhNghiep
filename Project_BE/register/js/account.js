const token = sessionStorage.getItem("us05_access_token");
const profileDetails = document.getElementById("profileDetails");
const profileMessage = document.getElementById("profileMessage");
const passwordMessage = document.getElementById("passwordMessage");
const passwordForm = document.getElementById("passwordForm");
const changePasswordBtn = document.getElementById("changePasswordBtn");

const destinations = { admin: "/register/html/admin-users.html", landlord: "/register/html/properties.html", manager: "/register/html/properties.html" };
const roleNames = { admin: "Quản trị viên", landlord: "Chủ nhà", manager: "Quản lý", tenant: "Khách thuê" };

function logout() {
    sessionStorage.removeItem("us05_access_token");
    sessionStorage.removeItem("us05_user_role");
    window.location.assign("/register/html/login.html");
}

function showMessage(element, text, type) {
    element.textContent = text;
    element.className = "account-message " + type;
}

async function api(path, options = {}) {
    const response = await fetch(path, {
        ...options,
        headers: { Authorization: `Bearer ${token}`, ...(options.body ? { "Content-Type": "application/json" } : {}), ...options.headers }
    });
    if (response.status === 401) logout();
    if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(typeof body?.detail === "string" ? body.detail : "Không thể hoàn tất yêu cầu.");
    }
    return response.status === 204 ? null : response.json();
}

async function loadProfile() {
    if (!token) return logout();
    try {
        const user = await api("/api/users/me");
        const fields = [
            ["Họ và tên", user.full_name], ["Email", user.email], ["Điện thoại", user.phone || "Chưa cập nhật"],
            ["Vai trò", roleNames[user.role] || user.role],
            ["Ngày tạo", user.created_at ? new Date(user.created_at).toLocaleDateString("vi-VN") : "—"]
        ];
        for (const [label, value] of fields) {
            const dt = document.createElement("dt"); dt.textContent = label;
            const dd = document.createElement("dd"); dd.textContent = value;
            profileDetails.append(dt, dd);
        }
        const dashboardLink = document.getElementById("dashboardLink");
        if (destinations[user.role]) dashboardLink.href = destinations[user.role];
        else dashboardLink.hidden = true;
        sessionStorage.setItem("us05_user_role", user.role);
    } catch (error) {
        showMessage(profileMessage, error.message, "failure");
    }
}

passwordForm.addEventListener("submit", async event => {
    event.preventDefault();
    passwordMessage.className = "account-message";
    const current = document.getElementById("currentPassword").value;
    const next = document.getElementById("newPassword").value;
    const confirm = document.getElementById("confirmPassword").value;
    if (next.length < 8) return showMessage(passwordMessage, "Mật khẩu mới cần ít nhất 8 ký tự.", "failure");
    if (next !== confirm) return showMessage(passwordMessage, "Mật khẩu xác nhận không khớp.", "failure");
    changePasswordBtn.disabled = true;
    try {
        await api("/api/users/me/password", { method: "PUT", body: JSON.stringify({ current_password: current, new_password: next }) });
        passwordForm.reset();
        showMessage(passwordMessage, "Đổi mật khẩu thành công.", "success");
    } catch (error) {
        showMessage(passwordMessage, error.message, "failure");
    } finally {
        changePasswordBtn.disabled = false;
    }
});

document.getElementById("logoutBtn").addEventListener("click", logout);
loadProfile();
