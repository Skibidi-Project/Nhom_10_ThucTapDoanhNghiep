const API_BASE = "/api";
const tokenForm = document.getElementById("tokenForm");
const accessTokenInput = document.getElementById("accessToken");
const accountInfo = document.getElementById("accountInfo");
const authPanel = document.getElementById("authPanel");
const readingSection = document.getElementById("readingSection");
const propertySelect = document.getElementById("propertySelect");
const roomSelect = document.getElementById("roomSelect");
const periodInput = document.getElementById("periodInput");
const notice = document.getElementById("notice");
const historyRows = document.getElementById("historyRows");
const historyContainer = document.getElementById("historyContainer");
const historyEmpty = document.getElementById("historyEmpty");
let accessToken = sessionStorage.getItem("us05_access_token") || "";
let properties = [];
let rooms = [];
let readings = [];
let activeProperty = null;

const utilityMeta = {
    electricity: {prefix: "electricity", price: "electricity_unit_price", unit: "kWh", label: "Điện"},
    water: {prefix: "water", price: "water_unit_price", unit: "m³", label: "Nước"},
};

function money(value) { return new Intl.NumberFormat("vi-VN").format(Number(value) || 0) + " ₫"; }
function showNotice(message, type = "info") { notice.textContent = message; notice.className = `notice show ${type}`; }
function hideNotice() { notice.textContent = ""; notice.className = "notice"; }

async function apiRequest(path, options = {}) {
    const headers = new Headers(options.headers || {});
    headers.set("Authorization", `Bearer ${accessToken}`);
    if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    const response = await fetch(`${API_BASE}${path}`, {...options, headers});
    const data = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) {
        const detail = typeof data?.detail === "string" ? data.detail : Array.isArray(data?.detail) ? data.detail.map(item => item.msg).join("; ") : `Yêu cầu thất bại (HTTP ${response.status}).`;
        throw new Error(detail);
    }
    return data;
}

function monthValue() {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function updateCalculation(type) {
    const meta = utilityMeta[type];
    const previous = document.getElementById(`${meta.prefix}Previous`);
    const current = document.getElementById(`${meta.prefix}Current`);
    const usageOutput = document.getElementById(`${meta.prefix}Usage`);
    const amountOutput = document.getElementById(`${meta.prefix}Amount`);
    const button = document.querySelector(`.save-reading[data-type="${type}"]`);
    const oldValue = previous.value === "" ? null : Number(previous.value);
    const newValue = current.value === "" ? null : Number(current.value);
    const valid = oldValue !== null && newValue !== null && Number.isInteger(oldValue) && Number.isInteger(newValue) && oldValue >= 0 && newValue >= oldValue;
    const price = Number(activeProperty?.[meta.price] || 0);
    usageOutput.innerHTML = valid ? `${newValue - oldValue} <small>${meta.unit}</small>` : `— <small>${meta.unit}</small>`;
    amountOutput.textContent = valid ? money((newValue - oldValue) * price) : "—";
    current.setCustomValidity(newValue !== null && oldValue !== null && newValue < oldValue ? "Chỉ số mới phải lớn hơn hoặc bằng chỉ số cũ." : "");
    const alreadySaved = readings.some(item => item.utility_type === type);
    button.disabled = !roomSelect.value || !periodInput.value || !valid || alreadySaved;
}

function updateCalculations() { Object.keys(utilityMeta).forEach(updateCalculation); }

function renderHistory() {
    const items = readings.filter(item => ["electricity", "water"].includes(item.utility_type));
    historyRows.replaceChildren();
    for (const item of items) {
        const meta = utilityMeta[item.utility_type];
        const row = document.createElement("tr");
        [meta.label, new Intl.NumberFormat("vi-VN").format(item.previous_reading), new Intl.NumberFormat("vi-VN").format(item.current_reading), `${new Intl.NumberFormat("vi-VN").format(item.current_reading - item.previous_reading)} ${meta.unit}`].forEach(value => {
            const cell = document.createElement("td"); cell.textContent = value; row.append(cell);
        });
        historyRows.append(row);
        document.getElementById(`${meta.prefix}Previous`).value = item.previous_reading;
        document.getElementById(`${meta.prefix}Current`).value = item.current_reading;
        const saved = document.getElementById(`${meta.prefix}Saved`);
        saved.textContent = `Đã lưu chỉ số kỳ ${item.period}.`;
        saved.hidden = false;
    }
    historyContainer.hidden = items.length === 0;
    historyEmpty.hidden = items.length > 0;
    if (items.length === 0) historyEmpty.textContent = roomSelect.value ? "Chưa có chỉ số nào được ghi trong kỳ này." : "Chọn phòng để xem chỉ số.";
    updateCalculations();
}

function periodChanged() { loadReadings().catch(error => showNotice(error.message, "error")); }

async function loadReadings() {
    readings = [];
    Object.keys(utilityMeta).forEach(type => {
        const meta = utilityMeta[type];
        document.getElementById(`${meta.prefix}Previous`).value = "";
        document.getElementById(`${meta.prefix}Current`).value = "";
        const saved = document.getElementById(`${meta.prefix}Saved`); saved.hidden = true; saved.textContent = "";
    });
    if (!roomSelect.value || !periodInput.value) { renderHistory(); return; }
    const roomReadings = await apiRequest(`/rooms/${roomSelect.value}/readings`);
    readings = roomReadings.filter(item => item.period === periodInput.value);
    for (const [type, meta] of Object.entries(utilityMeta)) {
        if (readings.some(item => item.utility_type === type)) continue;
        const prior = roomReadings
            .filter(item => item.utility_type === type && item.period < periodInput.value)
            .sort((a, b) => b.period.localeCompare(a.period))[0];
        if (prior) document.getElementById(`${meta.prefix}Previous`).value = prior.current_reading;
    }
    renderHistory();
}

async function loadRooms() {
    roomSelect.replaceChildren(new Option("Chọn phòng", ""));
    roomSelect.disabled = true;
    rooms = [];
    activeProperty = properties.find(item => String(item.id) === propertySelect.value) || null;
    document.getElementById("electricityPrice").textContent = activeProperty ? `Đơn giá: ${money(activeProperty.electricity_unit_price)}/kWh` : "Đơn giá: —";
    document.getElementById("waterPrice").textContent = activeProperty ? `Đơn giá: ${money(activeProperty.water_unit_price)}/m³` : "Đơn giá: —";
    if (!activeProperty) { await loadReadings(); return; }
    rooms = await apiRequest(`/properties/${activeProperty.id}/rooms`);
    for (const room of rooms) roomSelect.add(new Option(`Phòng ${room.room_number}`, room.id));
    roomSelect.disabled = rooms.length === 0;
    updateCalculations();
    await loadReadings();
}

async function loadData() {
    hideNotice();
    properties = await apiRequest("/properties");
    propertySelect.replaceChildren(new Option("Chọn khu trọ", ""));
    for (const property of properties) propertySelect.add(new Option(property.name, property.id));
    if (properties.length === 0) showNotice("Tài khoản chưa có khu trọ trong phạm vi quản lý.", "info");
    await loadRooms();
}

async function saveReading(type) {
    const meta = utilityMeta[type];
    const previous = Number(document.getElementById(`${meta.prefix}Previous`).value);
    const current = Number(document.getElementById(`${meta.prefix}Current`).value);
    if (!roomSelect.value || !periodInput.value || !Number.isInteger(previous) || !Number.isInteger(current) || current < previous) {
        document.getElementById(`${meta.prefix}Current`).reportValidity();
        return;
    }
    const button = document.querySelector(`.save-reading[data-type="${type}"]`);
    button.disabled = true;
    try {
        await apiRequest(`/rooms/${roomSelect.value}/readings`, {method: "POST", body: JSON.stringify({utility_type: type, period: periodInput.value, previous_reading: previous, current_reading: current})});
        showNotice(`Đã lưu chỉ số ${meta.label.toLowerCase()} kỳ ${periodInput.value}. Thành tiền ước tính: ${money((current - previous) * Number(activeProperty[meta.price] || 0))}.`, "success");
        await loadReadings();
    } catch (error) {
        showNotice(error.message, "error");
        updateCalculation(type);
    }
}

async function connect(token) {
    accessToken = token.trim();
    if (!accessToken) return;
    sessionStorage.setItem("us05_access_token", accessToken);
    try {
        const user = await apiRequest("/users/me");
        accountInfo.textContent = user.full_name || user.email || "Đã xác thực";
        authPanel.hidden = true;
        readingSection.hidden = false;
        await loadData();
    } catch (error) {
        sessionStorage.removeItem("us05_access_token");
        accessToken = "";
        accountInfo.textContent = "Chưa xác thực";
        authPanel.hidden = false;
        readingSection.hidden = true;
        showNotice(error.message, "error");
    }
}

tokenForm.addEventListener("submit", event => { event.preventDefault(); connect(accessTokenInput.value); });
document.getElementById("logoutBtn").addEventListener("click", () => {
    sessionStorage.removeItem("us05_access_token"); accessToken = ""; properties = []; rooms = [];
    authPanel.hidden = false; readingSection.hidden = true; accountInfo.textContent = "Chưa xác thực"; accessTokenInput.value = ""; hideNotice();
});
document.getElementById("refreshBtn").addEventListener("click", () => loadData().catch(error => showNotice(error.message, "error")));
propertySelect.addEventListener("change", () => loadRooms().catch(error => showNotice(error.message, "error")));
roomSelect.addEventListener("change", () => loadReadings().catch(error => showNotice(error.message, "error")));
periodInput.addEventListener("change", periodChanged);
for (const type of Object.keys(utilityMeta)) {
    const meta = utilityMeta[type];
    document.getElementById(`${meta.prefix}Previous`).addEventListener("input", () => updateCalculation(type));
    document.getElementById(`${meta.prefix}Current`).addEventListener("input", () => updateCalculation(type));
    document.querySelector(`.save-reading[data-type="${type}"]`).addEventListener("click", () => saveReading(type));
}
periodInput.value = monthValue();
if (accessToken) connect(accessToken);
