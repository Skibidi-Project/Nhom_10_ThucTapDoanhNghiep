"use strict";
const $ = id => document.getElementById(id);
let busy = false, group = null, contract = null, tenants = [], pendingRemove = null;
const token = () => sessionStorage.getItem("us05_access_token") || "";
function notice(message, error = false) {
    $("notice").textContent = message;
    $("notice").className = error ? "error" : "";
    $("notice").hidden = false;
}
async function api(path, options = {}) {
    const response = await fetch(`/api${path}`, {...options, headers: {
        Authorization: `Bearer ${token()}`, ...(options.body ? {"Content-Type":"application/json"} : {})
    }});
    const data = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) {
        if (response.status === 401) {
            sessionStorage.removeItem("us05_access_token");
            $("workspace").hidden = true;
            throw new Error("Phiên không hợp lệ hoặc đã hết hạn. Vui lòng đăng nhập lại bằng liên kết phía trên.");
        }
        if (response.status === 403) throw new Error("Bạn không có quyền thao tác trên hợp đồng hoặc khách thuê này. Phiên đăng nhập vẫn được giữ.");
        throw new Error(typeof data?.detail === "string" ? data.detail : `Không thể thực hiện yêu cầu (HTTP ${response.status}).`);
    }
    return data;
}
function writable() {
    const today = new Date();
    const localDay = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,"0")}-${String(today.getDate()).padStart(2,"0")}`;
    return contract && ["created","active"].includes(contract.status) && contract.end_date >= localDay;
}
function lock(value) {
    busy = value;
    for (const button of document.querySelectorAll("button")) button.disabled = value;
    $("addBtn").disabled = value || !writable() || !$("tenantId").options.length || !$("tenantId").value;
    $("tenantId").disabled = value || !writable();
    $("loading").hidden = !value;
    $("workspace").setAttribute("aria-busy", String(value));
}
function person(item, representative = false) {
    const row = document.createElement("div"); row.className = "person";
    const avatar = document.createElement("div"); avatar.className = "avatar";
    avatar.textContent = item.full_name.split(/\s+/).map(s => s[0]).slice(-2).join("").toUpperCase();
    const detail = document.createElement("div"), name = document.createElement("strong"), id = document.createElement("small");
    name.textContent = item.full_name; id.textContent = `Mã khách thuê #${item.tenant_id}`;
    detail.append(name,id); row.append(avatar,detail);
    if (representative) {
        const badge = document.createElement("span"); badge.className = "badge"; badge.textContent = "Người đại diện"; row.append(badge);
    } else if (writable()) {
        const button = document.createElement("button"); button.className = "remove"; button.textContent = "Xóa";
        button.setAttribute("aria-label", `Xóa ${item.full_name}`);
        button.onclick = () => { if (busy) return; pendingRemove = item; $("removeText").textContent = `Xóa ${item.full_name} khỏi hợp đồng #${group.contract_id}?`; $("removeDialog").showModal(); };
        row.append(button);
    }
    return row;
}
function render() {
    $("contractTitle").textContent = `Hợp đồng #${group.contract_id}`;
    const statuses = {active:"Đang hiệu lực",created:"Mới tạo",expired:"Đã kết thúc",pending_liquidation:"Chờ thanh lý"};
    $("status").textContent = statuses[contract.status] || contract.status;
    $("room").textContent = `#${group.room_id}`;
    const date = value => value.split("-").reverse().join("/");
    $("dates").textContent = `${date(contract.start_date)} – ${date(contract.end_date)}`;
    $("rent").textContent = new Intl.NumberFormat("vi-VN",{style:"currency",currency:"VND"}).format(contract.monthly_rent);
    $("total").textContent = `${group.members.length + 1} người`;
    $("count").textContent = `${group.members.length} thành viên`;
    $("representative").replaceChildren(person(group.representative,true));
    $("members").replaceChildren(...group.members.map(item => person(item)));
    $("empty").hidden = group.members.length !== 0;
    const excluded = new Set([group.representative.tenant_id,...group.members.map(item => item.tenant_id)]);
    $("tenantId").replaceChildren(new Option("Chọn khách thuê", ""));
    for (const tenant of tenants.filter(item => !excluded.has(item.id))) $("tenantId").add(new Option(`${tenant.full_name} · #${tenant.id}`,String(tenant.id)));
    $("readonly").hidden = writable();
    $("workspace").hidden = false;
}
async function load(contractId) {
    if (!Number.isSafeInteger(contractId) || contractId < 1) throw new Error("Mã hợp đồng phải là số nguyên dương.");
    // Fetch all data before exposing the selected contract to avoid stale controls.
    const [nextGroup,nextContract,nextTenants] = await Promise.all([
        api(`/contracts/${contractId}/tenant-group`),api(`/contracts/${contractId}`),api("/tenants")
    ]);
    group = nextGroup; contract = nextContract; tenants = nextTenants; render();
}
async function action(fn) {
    if (busy) return;
    lock(true);
    try { await fn(); }
    catch (error) { notice(error instanceof TypeError ? "Không kết nối được máy chủ. Vui lòng thử lại." : error.message,true); }
    finally { lock(false); }
}
$("contractForm").addEventListener("submit", event => {
    event.preventDefault();
    action(async () => { $("workspace").hidden = true; await load(Number($("contractId").value)); $("notice").hidden = true; });
});
$("tenantId").addEventListener("change", () => lock(busy));
$("memberForm").addEventListener("submit", event => {
    event.preventDefault();
    action(async () => {
        const id = Number($("tenantId").value);
        if (!writable() || !Number.isSafeInteger(id) || id < 1) throw new Error("Vui lòng chọn khách thuê hợp lệ.");
        await api(`/contracts/${group.contract_id}/members`,{method:"POST",body:JSON.stringify({tenant_id:id})});
        await load(group.contract_id); notice("Đã thêm thành viên vào hợp đồng.");
    });
});
$("cancelRemove").onclick = () => { pendingRemove = null; $("removeDialog").close(); };
$("confirmRemove").onclick = () => action(async () => {
    if (!pendingRemove) return;
    const member = pendingRemove; pendingRemove = null; $("removeDialog").close();
    await api(`/contracts/${group.contract_id}/members/${member.tenant_id}`,{method:"DELETE"});
    await load(group.contract_id); notice("Đã xóa liên kết thành viên. Hồ sơ khách thuê vẫn được giữ nguyên.");
});
$("contractId").value = new URLSearchParams(location.search).get("contract_id") || "1";
action(async () => {
    if (!token()) { notice("Vui lòng đăng nhập bằng tài khoản Chủ trọ hoặc Quản lý, sau đó mở lại trang này.",true); return; }
    const user = await api("/users/me"); $("account").textContent = `${user.full_name} · ${user.role}`;
    await load(Number($("contractId").value));
});
