const token = sessionStorage.getItem("us05_access_token");
const form = document.getElementById("profile");
const avatarForm = document.getElementById("avatarForm");
const notice = document.getElementById("notice");
const avatar = document.getElementById("avatar");
let objectUrl = null;

async function request(path, options = {}) {
    const headers = new Headers(options.headers);
    headers.set("Authorization", "Bearer " + token);
    const response = await fetch("/api/users/me" + path, {...options, headers});
    if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(Array.isArray(data?.detail) ? data.detail.map(item => item.msg).join(". ") : data?.detail || "Yêu cầu thất bại.");
    }
    return response;
}

async function refresh() {
    const data = await (await request("")).json();
    for (const name of ["full_name", "email", "phone", "id_number"]) form.elements[name].value = data[name] ?? "";
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    avatar.hidden = true;
    if (data.avatar_type) {
        objectUrl = URL.createObjectURL(await (await request("/avatar")).blob());
        avatar.src = objectUrl;
        avatar.hidden = false;
    }
    form.hidden = false;
    avatarForm.hidden = false;
}

async function save(button, action) {
    if (button.disabled) return;
    button.disabled = true;
    try {
        await action();
        notice.textContent = "Đã lưu thay đổi.";
        await refresh();
    } catch (error) {
        notice.textContent = error.message;
    } finally {
        button.disabled = false;
    }
}

form.addEventListener("submit", event => {
    event.preventDefault();
    const data = {full_name: form.elements.full_name.value.trim(), email: form.elements.email.value.trim(), id_number: form.elements.id_number.value.trim() || null};
    if (form.elements.phone.value.trim()) data.phone = form.elements.phone.value.trim();
    save(form.querySelector("button"), () => request("", {method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)}));
});
avatarForm.addEventListener("submit", event => {
    event.preventDefault();
    const file = document.getElementById("photo").files[0];
    save(avatarForm.querySelector("button"), async () => {
        if (!file || file.size > 2 * 1024 * 1024) throw new Error("Hãy chọn ảnh tối đa 2 MB.");
        await request("/avatar", {method: "PUT", headers: {"Content-Type": file.type}, body: file});
    });
});
document.getElementById("removeAvatar").addEventListener("click", event => {
    save(event.target, () => request("/avatar", {method: "DELETE"}));
});
if (token) refresh().catch(error => { notice.textContent = error.message; });
else notice.textContent = "Hãy đăng nhập để xem hồ sơ.";
