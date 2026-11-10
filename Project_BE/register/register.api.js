
const registerForm = document.getElementById("registerForm");
const registerBtn = document.getElementById("registerBtn");
const message = document.getElementById("message");

const fullName = document.getElementById("fullName");
const email = document.getElementById("email");
const phone = document.getElementById("phone");
const password = document.getElementById("password");
const confirmPassword = document.getElementById("confirmPassword");
const agreeTerms = document.getElementById("agreeTerms");

function showError(input, errorId, text) {
    document.getElementById(errorId).textContent = text;

    if (input !== null) {
        input.classList.add("invalid");
    }
}

function clearErrors() {
    document.querySelectorAll(".error").forEach(function (item) {
        item.textContent = "";
    });

    document.querySelectorAll(".invalid").forEach(function (item) {
        item.classList.remove("invalid");
    });

    message.textContent = "";
    message.className = "message";
}

function showMessage(text, type) {
    message.textContent = text;
    message.className = "message " + type;
}

function validateName(value) {
    if (value.length === 0) {
        return "Vui lòng nhập họ và tên";
    }

    if (value.length < 2) {
        return "Họ và tên phải có ít nhất 2 ký tự";
    }

    return "";
}

function validateEmail(value) {
    if (value.length === 0) {
        return "Vui lòng nhập địa chỉ email";
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (!emailRegex.test(value)) {
        return "Email không đúng định dạng";
    }

    return "";
}

function validatePhone(value) {
    if (value.length === 0) {
        return "Vui lòng nhập số điện thoại";
    }

    const phoneRegex = /^0[0-9]{9}$/;

    if (!phoneRegex.test(value)) {
        return "Số điện thoại phải có 10 chữ số và bắt đầu bằng 0";
    }

    return "";
}

function validatePassword(value) {
    if (value.length === 0) {
        return "Vui lòng nhập mật khẩu";
    }

    if (value.length < 8) {
        return "Mật khẩu phải có ít nhất 8 ký tự";
    }

    if (!/[A-Z]/.test(value)) {
        return "Mật khẩu phải có ít nhất 1 chữ hoa";
    }

    if (!/[a-z]/.test(value)) {
        return "Mật khẩu phải có ít nhất 1 chữ thường";
    }

    if (!/[0-9]/.test(value)) {
        return "Mật khẩu phải có ít nhất 1 chữ số";
    }

    return "";
}

function validateConfirmPassword(value, originalPassword) {
    if (value.length === 0) {
        return "Vui lòng xác nhận mật khẩu";
    }

    if (value !== originalPassword) {
        return "Mật khẩu xác nhận không khớp";
    }

    return "";
}

registerForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    if (registerBtn.disabled) return;
    clearErrors();

    const nameValue = fullName.value.trim();
    const emailValue = email.value.trim().toLowerCase();
    const phoneValue = phone.value.trim();
    const passwordValue = password.value;
    const confirmValue = confirmPassword.value;

    let isValid = true;

    const nameError = validateName(nameValue);

    if (nameError !== "") {
        showError(fullName, "nameError", nameError);
        isValid = false;
    }

    const emailError = validateEmail(emailValue);

    if (emailError !== "") {
        showError(email, "emailError", emailError);
        isValid = false;
    }

    const phoneError = validatePhone(phoneValue);

    if (phoneError !== "") {
        showError(phone, "phoneError", phoneError);
        isValid = false;
    }

    const passwordError = validatePassword(passwordValue);

    if (passwordError !== "") {
        showError(password, "passwordError", passwordError);
        isValid = false;
    }

    const confirmError = validateConfirmPassword(
        confirmValue,
        passwordValue
    );

    if (confirmError !== "") {
        showError(confirmPassword, "confirmError", confirmError);
        isValid = false;
    }

    if (!agreeTerms.checked) {
        showError(null, "termsError", "Vui lòng đồng ý với điều khoản");
        isValid = false;
    }

    if (!isValid) {
        showMessage("Vui lòng kiểm tra lại thông tin đăng ký.", "failure");
        return;
    }

    const buttonHTML = registerBtn.innerHTML;
    let registered = false;
    try {
        registerBtn.disabled = true;
        registerBtn.textContent = "Đang tạo tài khoản...";
        const response = await fetch("/api/auth/register", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({full_name: nameValue, email: emailValue, phone: phoneValue, password: passwordValue})
        });
        const data = await response.json().catch(() => null);
        if (response.status !== 201) {
            if (response.status === 422 && Array.isArray(data?.detail)) {
                const fields = {full_name: [fullName, "nameError"], email: [email, "emailError"], phone: [phone, "phoneError"], password: [password, "passwordError"]};
                data.detail.forEach(item => {
                    const field = fields[item.loc?.[1]];
                    if (field) showError(field[0], field[1], item.msg);
                });
            }
            const detail = typeof data?.detail === "string" ? data.detail : null;
            throw new Error(detail || (response.status === 409 ? "Email hoặc số điện thoại đã được sử dụng." : response.status === 422 ? "Dữ liệu không hợp lệ. Vui lòng kiểm tra lại." : response.status >= 500 ? "Máy chủ gặp lỗi. Vui lòng thử lại sau." : "Không thể đăng ký tài khoản."));
        }
        registered = true;
        showMessage("Đăng ký MiniStay thành công! Đang chuyển tới trang đăng nhập...", "success");
        registerForm.reset();
        window.scrollTo({top: 0, behavior: "smooth"});
        window.setTimeout(() => window.location.assign("login.html"), 1500);
    } catch (error) {
        showMessage(error instanceof TypeError ? "Không thể kết nối máy chủ. Vui lòng kiểm tra kết nối và thử lại." : error.message, "failure");
    } finally {
        if (!registered) {
            registerBtn.disabled = false;
            registerBtn.innerHTML = buttonHTML;
        }
    }
});

document.querySelectorAll(".toggle-password").forEach(function (button) {
    button.addEventListener("click", function () {
        const targetId = button.getAttribute("data-target");
        const input = document.getElementById(targetId);

        if (input.type === "password") {
            input.type = "text";
            button.textContent = "◎";
            button.setAttribute("aria-label", "Ẩn mật khẩu");
        } else {
            input.type = "password";
            button.textContent = "◉";
            button.setAttribute("aria-label", "Hiện mật khẩu");
        }
    });
});

document.querySelectorAll(".input-wrapper input").forEach(function (input) {
    input.addEventListener("input", function () {
        input.classList.remove("invalid");

        const errorElement = input
            .closest(".form-group")
            .querySelector(".error");

        errorElement.textContent = "";
    });
});

document.getElementById("termsLink").addEventListener("click", function (event) {
    event.preventDefault();
    alert("Trang điều khoản sử dụng đang được phát triển.");
});

document.getElementById("privacyLink").addEventListener("click", function (event) {
    event.preventDefault();
    alert("Trang chính sách bảo mật đang được phát triển.");
});

document.getElementById("loginLink").href = "login.html";
