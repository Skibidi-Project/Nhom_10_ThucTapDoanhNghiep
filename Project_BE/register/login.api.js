const form = document.getElementById("loginForm");
const button = document.getElementById("loginBtn");
const message = document.getElementById("message");
const userInfo = document.getElementById("userInfo");
const identifier = document.getElementById("identifier");
const password = document.getElementById("password");

function showMessage(text, type) {
    message.textContent = text;
    message.className = "message " + type;
}

document.querySelectorAll(".toggle-password").forEach(toggle => {
    toggle.addEventListener("click", () => {
        const visible = password.type === "password";
        password.type = visible ? "text" : "password";
        toggle.textContent = visible ? "◎" : "◉";
        toggle.setAttribute("aria-label", visible ? "Ẩn mật khẩu" : "Hiện mật khẩu");
    });
});

document.querySelectorAll(".input-wrapper input").forEach(input => {
    input.addEventListener("input", () => {
        input.classList.remove("invalid");
        document.getElementById(input.id + "Error").textContent = "";
    });
});

form.addEventListener("submit", async event => {
    event.preventDefault();
    if (button.disabled) return;
    message.textContent = "";
    message.className = "message";
    userInfo.replaceChildren();
    userInfo.className = "message";
    document.querySelectorAll(".error").forEach(item => item.textContent = "");
    document.querySelectorAll(".invalid").forEach(item => item.classList.remove("invalid"));
    const value = identifier.value.trim();
    let valid = true;
    if (!(/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) || /^0[0-9]{9}$/.test(value))) {
        identifier.classList.add("invalid");
        document.getElementById("identifierError").textContent = "Nhập email hợp lệ hoặc SĐT 10 chữ số bắt đầu bằng 0.";
        valid = false;
    }
    if (!password.value) {
        password.classList.add("invalid");
        document.getElementById("passwordError").textContent = "Vui lòng nhập mật khẩu.";
        valid = false;
    }
    if (!valid) return;
    const buttonHTML = button.innerHTML;
    button.disabled = true;
    button.textContent = "Đang đăng nhập...";
    try {
        const response = await fetch("/api/auth/login", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({identifier: value, password: password.value})
        });
        const data = await response.json().catch(() => null);
        if (response.status !== 200) {
            const detail = typeof data?.detail === "string" ? data.detail : null;
            const validation = Array.isArray(data?.detail) ? data.detail.map(item => item.msg).join("; ") : null;
            throw new Error(detail || validation || (response.status === 401 ? "Email/SĐT hoặc mật khẩu không đúng." : response.status >= 500 ? "Máy chủ gặp lỗi. Vui lòng thử lại sau." : "Không thể đăng nhập."));
        }
        if (!data?.user || typeof data.message !== "string") throw new Error("Phản hồi máy chủ không hợp lệ.");
        // Lưu JWT trong sessionStorage để trang US-05 tự xác thực khi được chuyển tới.
        // Chỉ landlord/manager được vào màn hình quản lý cơ sở.
        if (!["landlord", "manager"].includes(data.user.role)) {
            showMessage("Đăng nhập thành công, nhưng tài khoản chưa có quyền quản lý cơ sở. Vui lòng liên hệ quản trị viên để được cấp vai trò phù hợp.", "failure");
            password.value = "";
            return;
        }

        sessionStorage.setItem("us05_access_token", data.access_token);
        showMessage(data.message + ". Đang chuyển đến trang quản lý cơ sở...", "success");
        password.value = "";
        window.location.assign("/register/properties.html");
    } catch (error) {
        showMessage(error instanceof TypeError ? "Không thể kết nối máy chủ. Vui lòng thử lại." : error.message, "failure");
    } finally {
        button.disabled = false;
        button.innerHTML = buttonHTML;
    }
});
