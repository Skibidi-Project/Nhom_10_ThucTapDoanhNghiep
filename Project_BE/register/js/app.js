
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

function getUsers() {
    const data = localStorage.getItem("miniStayUsers");

    if (data === null) {
        return [];
    }

    try {
        const users = JSON.parse(data);

        if (Array.isArray(users)) {
            return users;
        }
    } catch (error) {
        console.error("Lỗi đọc dữ liệu:", error);
    }

    throw new Error("Dữ liệu tài khoản không hợp lệ");
}

function checkEmailExists(emailValue) {
    const users = getUsers();

    for (let i = 0; i < users.length; i++) {
        if (
            typeof users[i].email === "string" &&
            users[i].email.toLowerCase() === emailValue.toLowerCase()
        ) {
            return true;
        }
    }

    return false;
}

function checkPhoneExists(phoneValue) {
    const users = getUsers();

    for (let i = 0; i < users.length; i++) {
        if (users[i].phone === phoneValue) {
            return true;
        }
    }

    return false;
}

function registerUser(nameValue, emailValue, phoneValue) {
    const users = getUsers();

    if (checkEmailExists(emailValue) || checkPhoneExists(phoneValue)) {
        throw new Error("Email hoặc số điện thoại đã tồn tại");
    }

    const newUser = {
        id: Date.now(),
        fullName: nameValue,
        email: emailValue,
        phone: phoneValue,
        createdAt: new Date().toISOString()
    };

    users.push(newUser);

    localStorage.setItem("miniStayUsers", JSON.stringify(users));
}

registerForm.addEventListener("submit", function (event) {
    event.preventDefault();

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

    try {
        registerBtn.disabled = true;
        registerBtn.textContent = "Đang tạo tài khoản...";

        if (checkEmailExists(emailValue)) {
            showError(email, "emailError", "Email đã được đăng ký");
            showMessage("Email đã tồn tại trong hệ thống.", "failure");
            return;
        }

        if (checkPhoneExists(phoneValue)) {
            showError(phone, "phoneError", "Số điện thoại đã được đăng ký");
            showMessage("Số điện thoại đã tồn tại.", "failure");
            return;
        }

        registerUser(nameValue, emailValue, phoneValue);

        showMessage(
            "Đăng ký MiniStay thành công! Thông tin demo đã được lưu.",
            "success"
        );

        registerForm.reset();

        window.scrollTo({
            top: 0,
            behavior: "smooth"
        });

    } catch (error) {
        console.error(error);

        showMessage(
            "Không thể lưu thông tin. Vui lòng thử lại.",
            "failure"
        );
    } finally {
        registerBtn.disabled = false;
        registerBtn.textContent = "Đăng ký tài khoản →";
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

document.getElementById("loginLink").addEventListener("click", function (event) {
    event.preventDefault();
    alert("Chức năng đăng nhập đang được phát triển.");
});
