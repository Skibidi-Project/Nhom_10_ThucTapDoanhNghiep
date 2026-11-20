const API_BASE = "/api";
const accountInfo = document.getElementById("accountInfo");
const logoutBtn = document.getElementById("logoutBtn");
const contractSection = document.getElementById("contractSection");
const notice = document.getElementById("notice");
const contractForm = document.getElementById("contractForm");
const propertySelect = document.getElementById("propertySelect");
const roomSelect = document.getElementById("roomSelect");
const tenantSelect = document.getElementById("tenantSelect");
const contractRows = document.getElementById("contractRows");
const contractsLoading = document.getElementById("contractsLoading");
const contractsError = document.getElementById("contractsError");
const contractsEmpty = document.getElementById("contractsEmpty");
const contractsTableContainer = document.getElementById("contractsTableContainer");
const tenantDialog = document.getElementById("tenantDialog");
const tenantForm = document.getElementById("tenantForm");

let accessToken = sessionStorage.getItem("us05_access_token") || "";
let currentUser = null;
let properties = [];
let rooms = [];
let tenants = [];

function showNotice(message, type = "info") {
    notice.textContent = message;
    notice.className = `notice show ${type}`;
}

function hideNotice() {
    notice.textContent = "";
    notice.className = "notice";
}

async function apiRequest(path, options = {}) {
    const requestHeaders = new Headers(options.headers || {});
    requestHeaders.set("Authorization", `Bearer ${accessToken}`);
    if (options.body && !requestHeaders.has("Content-Type")) {
        requestHeaders.set("Content-Type", "application/json");
    }
    const response = await fetch(`${API_BASE}${path}`, {...options, headers: requestHeaders});
    if (response.status === 204) return null;
    const data = await response.json().catch(() => null);
    if (!response.ok) {
        const detail = typeof data?.detail === "string"
            ? data.detail
            : Array.isArray(data?.detail)
                ? data.detail.map(item => item.msg).join("; ")
                : `Yêu cầu thất bại (HTTP ${response.status}).`;
        throw new Error(detail);
    }
    return data;
}

function createElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
}

function formatMoney(value) {
    return new Intl.NumberFormat("vi-VN").format(Number(value) || 0) + " đ";
}

function formatDate(value) {
    const [year, month, day] = value.split("-");
    return `${day}/${month}/${year}`;
}

function setSelectOptions(select, placeholder, items, labelForItem) {
    select.replaceChildren(new Option(placeholder, ""));
    for (const item of items) {
        select.append(new Option(labelForItem(item), String(item.id)));
    }
    select.disabled = items.length === 0;
}

function selectedProperty() {
    return properties.find(property => String(property.id) === propertySelect.value) || null;
}

function updateRentHint() {
    const room = rooms.find(item => String(item.id) === roomSelect.value);
    const rentInput = document.getElementById("monthlyRent");
    const hint = document.getElementById("rentHint");
    if (!room || rentInput.value === "") {
        hint.textContent = "";
        hint.className = "field-hint";
        return;
    }
    if (Number(rentInput.value) !== room.base_rent) {
        hint.textContent = `Giá niêm yết: ${formatMoney(room.base_rent)}. Giá hợp đồng đang khác giá niêm yết.`;
        hint.className = "field-hint rent-warning";
    } else {
        hint.textContent = `Giá niêm yết: ${formatMoney(room.base_rent)}.`;
        hint.className = "field-hint";
    }
}

async function loadRoomsAndTenants() {
    const property = selectedProperty();
    rooms = [];
    tenants = [];
    setSelectOptions(roomSelect, property ? "Đang tải phòng trống..." : "Chọn khu trọ trước", []);
    setSelectOptions(tenantSelect, property ? "Đang tải khách thuê..." : "Chọn khu trọ trước", []);
    document.getElementById("monthlyRent").value = "";
    updateRentHint();
    if (!property) return;

    const params = new URLSearchParams({
        property_id: String(property.id),
        status: "available",
        page_size: "100",
    });
    const [roomResult, tenantResult] = await Promise.all([
        apiRequest(`/rooms?${params}`),
        apiRequest("/tenants"),
    ]);
    rooms = roomResult.items;
    tenants = tenantResult.filter(tenant => tenant.landlord_id === property.owner_id);
    setSelectOptions(
        roomSelect,
        rooms.length ? "Chọn phòng đang trống" : "Khu trọ chưa có phòng trống",
        rooms,
        room => `${room.room_number} · ${formatMoney(room.base_rent)}`,
    );
    setSelectOptions(
        tenantSelect,
        tenants.length ? "Chọn khách thuê đại diện" : "Chưa có khách thuê trong khu trọ này",
        tenants,
        tenant => `${tenant.full_name} · ${tenant.phone}`,
    );
}

const contractStatusLabels = {
    created: "M\u1edbi t\u1ea1o",
    active: "\u0110ang hi\u1ec7u l\u1ef1c",
    pending_liquidation: "Ch\u1edd thanh l\u00fd",
    expired: "H\u1ebft h\u1ea1n",
    terminated: "\u0110\u00e3 ch\u1ea5m d\u1ee9t",
};
const depositStatusLabels = {
    unpaid: "Ch\u01b0a nh\u1eadn",
    held: "\u0110ang gi\u1eef",
    returned: "\u0110\u00e3 ho\u00e0n tr\u1ea3",
    deducted: "\u0110\u00e3 kh\u1ea5u tr\u1eeb",
    not_applicable: "Kh\u00f4ng c\u00f3 c\u1ecdc",
};

function actionButton(label, onClick, disabled = false) {
    const button = createElement("button", "button button-outline contract-action", label);
    button.type = "button";
    button.disabled = disabled;
    button.addEventListener("click", onClick);
    return button;
}

async function confirmDepositReceived(contract) {
    try {
        await apiRequest(`/contracts/${contract.id}/deposit`, {
            method: "PATCH",
            body: JSON.stringify({status: "held", returned_amount: 0}),
        });
        showNotice("\u0110\u00e3 ghi nh\u1eadn ti\u1ec1n c\u1ecdc \u0111ang \u0111\u01b0\u1ee3c gi\u1eef.", "success");
        await loadContracts();
    } catch (error) {
        showNotice(error.message, "error");
    }
}

async function requestLiquidation(contract) {
    try {
        const data = await apiRequest(`/contracts/${contract.id}/liquidation-preview`);
        document.getElementById('liquidationSummary').textContent = `${data.property_name} · Phòng ${data.room_number} · ${data.tenant_name} · ${data.start_date} – ${data.end_date}`;
        document.getElementById('liquidationDeposit').textContent = formatMoney(data.deposit);
        document.getElementById('liquidationDebt').textContent = formatMoney(data.outstanding);
        document.getElementById('liquidationDate').value = data.settlement?.handover_date || new Date().toLocaleDateString('en-CA');
        document.getElementById('liquidationReason').value = data.settlement?.reason || '';
        const invoiceList = document.getElementById('liquidationInvoices'); invoiceList.replaceChildren();
        if (!data.invoices.length) invoiceList.textContent = 'Chưa có hóa đơn.';
        for (const invoice of data.invoices) {
            const reviewed=(data.invoice_reviews || []).some(r=>r.invoice_id===invoice.id);
            const row=document.createElement('div'); row.textContent=`${invoice.period}: ${formatMoney(invoice.balance)} còn nợ${reviewed ? ' · Đã đối soát' : ''} `;
            const show=document.createElement('button'); show.type='button'; show.className='button button-light'; show.textContent='Xem chứng từ';
            show.onclick=async () => {
                try {
                    const evidence=await apiRequest(`/invoices/${invoice.id}/snapshot`);
                    const details=document.createElement('pre'); details.style.whiteSpace='pre-wrap'; details.textContent=JSON.stringify(evidence.document || {status:evidence.status},null,2); row.append(details); show.disabled=true;
                    if (data.trial_enabled && evidence.status==='complete' && !(data.invoice_reviews || []).some(r=>r.invoice_id===invoice.id)) {
                        const approve=document.createElement('button'); approve.type='button'; approve.className='button button-light'; approve.textContent='Xác nhận đối soát';
                        approve.onclick=async () => { approve.disabled=true; try { await apiRequest(`/contracts/${contract.id}/liquidation-invoices/${invoice.id}/review`,{method:'POST'}); await refresh(); } catch(error) { document.getElementById('liquidationError').textContent=error.message; approve.disabled=false; } };
                        row.append(approve);
                    }
                } catch(error) { document.getElementById('liquidationError').textContent=error.message; }
            };
            row.append(show); invoiceList.append(row);
        }
        const damageList = document.getElementById('liquidationDamages'); damageList.replaceChildren();
        document.getElementById('liquidationFinalPeriod').textContent = data.trial_enabled ? (data.final_period_gaps.length ? data.final_period_gaps.join(' · ') : data.final_evidence_complete ? 'Đã có chứng từ đối soát thử nghiệm.' : 'Chưa đủ chứng từ đối soát hoặc chưa rõ quy tắc kết thúc giữa kỳ.') : 'Quyết toán thực tế chưa được mở.';
        document.getElementById('liquidationResult').textContent = data.trial_enabled ? `BẢN THỬ NGHIỆM — Hoàn cọc dự kiến: ${formatMoney(data.estimated_refund)}; nghĩa vụ hư hỏng riêng: ${formatMoney(data.damage_shortfall)}. ${data.settlement ? (data.settlement.refund_amount === null ? 'Đã bàn giao, chưa hoàn cọc.' : 'Đã ghi nhận quyết toán cọc.') : 'Chưa bàn giao.'}` : 'Quy tắc hư hỏng và hoàn cọc đang chờ duyệt.';
        document.getElementById('liquidationError').textContent = '';
        const dialog = document.getElementById('liquidationDialog');
        const refresh = async () => { dialog.close(); await loadContracts(); await requestLiquidation(contract); };
        const action = (id, disabled, url, payload) => {
            const button = document.getElementById(id); button.disabled = disabled;
            button.onclick = async () => {
                button.disabled = true;
                try { await apiRequest(url, {method:'POST', body:JSON.stringify(payload())}); await refresh(); }
                catch (error) { document.getElementById('liquidationError').textContent = error.message; button.disabled = false; }
            };
        };
        const base = `/contracts/${contract.id}`;
        const approvalSection = document.getElementById('trialApprovalSection'); approvalSection.hidden = !data.trial_enabled;
        if (data.trial_enabled) {
            const approvalList = document.getElementById('trialApprovalList'); approvalList.replaceChildren();
            const meterDate=document.getElementById('meterHandoverAt');
            const localNow=new Date(); localNow.setMinutes(localNow.getMinutes()-localNow.getTimezoneOffset()); meterDate.value=localNow.toISOString().slice(0,16);
            const initialReadings=await apiRequest(`/rooms/${contract.room_id}/readings`);
            const initialVersions=new Map();
            for (const r of initialReadings) initialVersions.set(r.id,(await apiRequest(`/rooms/${contract.room_id}/readings/${r.id}/version`)).version);
            const readings=await apiRequest(`/rooms/${contract.room_id}/readings`);
            const services=await apiRequest(`${base}/services`);
            const chargeSelect=document.getElementById('approvalCharge'); chargeSelect.replaceChildren(new Option('Tiền phòng','rent'),new Option('Điện','electricity'),new Option('Nước','water'));
            for (const service of services.filter(item=>!['electricity','water'].includes(item.service_code))) chargeSelect.add(new Option(service.service_name,`service:${service.service_code}`));
            for (const [kind,elementId] of [['electricity','finalElectricity'],['water','finalWater']]) {
                const select=document.getElementById(elementId); select.replaceChildren(); select.add(new Option('Chọn chỉ số',''));
                for (const r of readings.filter(item=>item.utility_type===kind)) {
                    const version=await apiRequest(`/rooms/${contract.room_id}/readings/${r.id}/version`);
                    if (!initialVersions.has(r.id) || initialVersions.get(r.id)!==version.version) throw new Error('Chỉ số vừa thay đổi; hãy mở lại thanh lý.');
                    const option=new Option(`${r.period}: ${r.previous_reading} → ${r.current_reading}`,r.id); option.dataset.version=version.version; select.add(option);
                }
            }
            const currentDate = document.getElementById('liquidationDate').value;
            document.getElementById('approvalStart').value = currentDate.slice(0, 8) + '01';
            document.getElementById('approvalEnd').value = currentDate;
            const requests = await apiRequest(`${base}/final-approvals`);
            for (const request of requests) {
                const section = document.createElement('section');
                const summary = document.createElement('p'); summary.textContent = `#${request.id} · ${request.charge_type} · ${formatMoney(request.proposed_amount)} · ${request.status} · ${request.proposed_method} · ${request.reason} · ${request.reference || 'Không có căn cứ tham chiếu'}`; section.append(summary);
                const details = document.createElement('details'); const label=document.createElement('summary'); label.textContent='Xem dữ liệu đầu vào (giá hiện tại chỉ để đối chiếu, không phải giá lịch sử)'; const content=document.createElement('pre'); content.style.whiteSpace='pre-wrap'; content.textContent=JSON.stringify(JSON.parse(request.inputs),null,2); details.append(label,content); section.append(details);
                if (request.status === 'pending' && currentUser?.role === 'landlord') {
                    const reason=document.createElement('input'); reason.placeholder='Lý do quyết định'; reason.maxLength=500; reason.setAttribute('aria-label','Lý do quyết định'); section.append(reason);
                    for (const approved of [true,false]) {
                        const button=document.createElement('button'); button.type='button'; button.className='button button-light'; button.textContent=approved ? 'Duyệt khoản này' : 'Từ chối khoản này';
                        button.onclick=async () => { button.disabled=true; try { await apiRequest(`${base}/final-approvals/${request.id}/decision`,{method:'POST',body:JSON.stringify({approved,reason:reason.value})}); await refresh(); } catch(error) { document.getElementById('liquidationError').textContent=error.message;button.disabled=false; } }; section.append(button);
                    }
                }
                approvalList.append(section);
            }
            action('approvalCreate',false,`${base}/final-approvals`,() => ({period_start:document.getElementById('approvalStart').value,period_end:document.getElementById('approvalEnd').value,charge_type:document.getElementById('approvalCharge').value,proposed_amount:document.getElementById('approvalAmount').value === '' ? null : Number(document.getElementById('approvalAmount').value),reason:document.getElementById('approvalReason').value,proposed_method:document.getElementById('approvalMethod').value,reference:document.getElementById('approvalReference').value || null}));
            action('finalMeterButton',!!data.meter_handover,`${base}/final-meter-handover`,() => ({handover_at:meterDate.value,electricity_reading_id:Number(document.getElementById('finalElectricity').value),water_reading_id:Number(document.getElementById('finalWater').value),electricity_expected_version:Number(document.getElementById('finalElectricity').selectedOptions[0]?.dataset.version ?? -1),water_expected_version:Number(document.getElementById('finalWater').selectedOptions[0]?.dataset.version ?? -1)}));
            document.getElementById('finalMeterButton').textContent = data.final_meter_complete ? 'Đã xác nhận chỉ số bàn giao' : 'Xác nhận chỉ số bàn giao';
            action('finalInvoiceButton',currentUser?.role !== 'landlord',`${base}/final-invoice`,() => ({}));
        }
        if (!data.damages.length) damageList.textContent = 'Chưa ghi hư hỏng.';
        for (const damage of data.damages) {
            const row = document.createElement('p');
            row.textContent = `${damage.description}: ${formatMoney(damage.amount)} (${damage.confirmed_by ? 'đã duyệt' : 'chưa duyệt'}) `;
            if (!damage.confirmed_by && data.trial_enabled && data.settlement?.refund_amount == null) {
                const confirm = document.createElement('button'); confirm.type = 'button'; confirm.className = 'button button-light'; confirm.textContent = 'Xác nhận hư hỏng';
                confirm.onclick = async () => { confirm.disabled = true; try { await apiRequest(`${base}/liquidation-damages/${damage.id}/confirm`, {method:'POST'}); await refresh(); } catch (error) { document.getElementById('liquidationError').textContent = error.message; confirm.disabled = false; } };
                row.append(confirm);
            }
            damageList.append(row);
        }
        action('damageButton', !data.trial_enabled || data.settlement?.refund_amount != null, `${base}/liquidation-damages`, () => ({description:document.getElementById('damageDescription').value, amount:Number(document.getElementById('damageCost').value), confirmed:false}));
        action('handoverButton', !data.trial_enabled || !!data.settlement, `${base}/liquidate`, () => ({actual_end_date:document.getElementById('liquidationDate').value,reason:document.getElementById('liquidationReason').value,confirmed:true}));
        if (data.trial_enabled && !data.final_meter_complete) document.getElementById('liquidationFinalPeriod').textContent += ' Chưa xác nhận chỉ số bàn giao.';
        action('refundButton', !data.trial_enabled || !data.settlement || data.settlement.refund_amount !== null || data.outstanding > 0 || data.final_period_gaps.length > 0 || !data.final_evidence_complete || !data.final_meter_complete || data.damages.some(d => !d.confirmed_by), `${base}/liquidation-refund`, () => ({confirmed:true,method:document.getElementById('refundMethod').value,reference:document.getElementById('refundReference').value || null}));
        document.getElementById('liquidationDialog').showModal();
    } catch (error) {
        showNotice(error.message, "error");
    }
}

function openDepositDialog(contract) {
    const form = document.getElementById("depositForm");
    form.reset();
    document.getElementById("depositFormError").textContent = "";
    document.getElementById("depositContractId").value = contract.id;
    document.getElementById("depositContractSummary").textContent =
        `${contract.property_name} \u00b7 Ph\u00f2ng ${contract.room_number} \u00b7 Ti\u1ec1n c\u1ecdc ${formatMoney(contract.deposit)}`;
    const returnedAmount = document.getElementById("returnedAmount");
    returnedAmount.max = String(contract.deposit);
    returnedAmount.value = contract.deposit ? String(contract.deposit) : "";
    updateSettlementFields();
    document.getElementById("depositDialog").showModal();
}

function renderContracts(items) {
    contractRows.replaceChildren();
    for (const contract of items) {
        const row = document.createElement("tr");
        const statusLabel = contractStatusLabels[contract.status] || contract.status;
        const status = createElement(
            "span",
            `contract-status contract-status-${contract.status}`,
            statusLabel,
        );
        const statusCell = document.createElement("td");
        statusCell.append(status);

        const depositCell = document.createElement("td");
        depositCell.append(
            createElement("strong", "", formatMoney(contract.deposit)),
            createElement(
                "span",
                "deposit-state",
                contract.deposit === 0 && contract.deposit_status === "unpaid"
                    ? depositStatusLabels.not_applicable
                    : depositStatusLabels[contract.deposit_status] || contract.deposit_status,
            ),
        );
        if (contract.deposit_returned_amount > 0) {
            depositCell.append(createElement("small", "deposit-returned", `\u0110\u00e3 ho\u00e0n ${formatMoney(contract.deposit_returned_amount)}`));
        }

        const actionsCell = document.createElement("td");
        const actions = createElement("div", "contract-actions");
        actions.append(actionButton("Dịch vụ", () => {
            window.location.href = `services.html?contract_id=${encodeURIComponent(contract.id)}`;
        }));
        if (["created", "active"].includes(contract.status)) {
            if (contract.deposit > 0 && contract.deposit_status === "unpaid") {
                actions.append(actionButton("X\u00e1c nh\u1eadn nh\u1eadn c\u1ecdc", () => confirmDepositReceived(contract)));
            }
            actions.append(actionButton("Ch\u1edd thanh l\u00fd", async () => {
                if (!window.confirm(`Chuy\u1ec3n h\u1ee3p \u0111\u1ed3ng ph\u00f2ng ${contract.room_number} sang ch\u1edd thanh l\u00fd?`)) return;
                try {
                    await apiRequest(`/contracts/${contract.id}/terminate`, {method: "POST"});
                    showNotice("H\u1ee3p \u0111\u1ed3ng \u0111ang ch\u1edd thanh l\u00fd.", "success");
                    await loadContracts();
                } catch (error) {
                    showNotice(error.message, "error");
                }
            }));
        } else if (contract.status === "pending_liquidation") {
            if (contract.deposit > 0 && !["returned", "deducted"].includes(contract.deposit_status)) {
                actions.append(actionButton("Quy\u1ebft to\u00e1n c\u1ecdc", () => openDepositDialog(contract)));
            }
            actions.append(actionButton("Thanh lý hợp đồng", () => requestLiquidation(contract)));
        } else if (contract.status === 'expired') {
            actions.append(actionButton('Xem quyết toán', () => requestLiquidation(contract)));
        } else {
            actions.append(createElement("span", "muted-action", "\u0110\u00e3 ho\u00e0n t\u1ea5t"));
        }
        actionsCell.append(actions);
        row.append(
            createElement("td", "", contract.property_name),
            createElement("td", "", contract.room_number),
            createElement("td", "", contract.tenant_name),
            createElement("td", "", `${formatDate(contract.start_date)} \u2013 ${formatDate(contract.end_date)}`),
            depositCell,
            createElement("td", "", formatMoney(contract.monthly_rent)),
            createElement("td", "", `${contract.payment_cycle_months} th\u00e1ng/l\u1ea7n`),
            statusCell,
            actionsCell,
        );
        contractRows.append(row);
    }
}

async function loadContracts() {
    contractsLoading.hidden = false;
    contractsError.hidden = true;
    contractsEmpty.hidden = true;
    contractsTableContainer.hidden = true;
    try {
        const items = await apiRequest("/contracts");
        renderContracts(items);
        contractsLoading.hidden = true;
        contractsTableContainer.hidden = items.length === 0;
        contractsEmpty.hidden = items.length !== 0;
    } catch (error) {
        contractsLoading.hidden = true;
        contractsError.textContent = error.message;
        contractsError.hidden = false;
    }
}

async function loadProperties() {
    properties = await apiRequest("/properties");
    setSelectOptions(
        propertySelect,
        properties.length ? "Chọn khu trọ" : "Chưa có khu trọ được quản lý",
        properties,
        property => property.name,
    );
}

async function connect() {
    if (!accessToken) throw new Error("Vui lòng đăng nhập để sử dụng chức năng lập hợp đồng.");
    currentUser = await apiRequest("/users/me");
    if (!["landlord", "manager"].includes(currentUser.role)) {
        throw new Error("Tài khoản hiện tại không có quyền lập hợp đồng.");
    }
    sessionStorage.setItem("us05_access_token", accessToken);
    accountInfo.textContent = `${currentUser.full_name} · ${currentUser.role}`;
    contractSection.hidden = false;
    await loadProperties();

    const requestedRoomId = new URLSearchParams(window.location.search).get("room_id");
    if (requestedRoomId) {
        const requestedRoom = await apiRequest(`/rooms/${encodeURIComponent(requestedRoomId)}`);
        if (requestedRoom.status !== "available") {
            showNotice("Phòng được chọn hiện không còn trống để lập hợp đồng.", "error");
        } else {
            propertySelect.value = String(requestedRoom.property_id);
            await loadRoomsAndTenants();
            roomSelect.value = String(requestedRoom.id);
            document.getElementById("monthlyRent").value = requestedRoom.base_rent;
            updateRentHint();
        }
    } else if (properties.length) {
        propertySelect.value = String(properties[0].id);
        await loadRoomsAndTenants();
    }
    await loadContracts();
}

function clearSession() {
    sessionStorage.removeItem("us05_access_token");
    accessToken = "";
    currentUser = null;
    properties = [];
    rooms = [];
    tenants = [];
    contractRows.replaceChildren();
    contractSection.hidden = true;
    accountInfo.textContent = "Chưa xác thực";
}

function disconnect() {
    clearSession();
    window.location.replace("index.html");
}

function readContractForm() {
    const roomId = Number(roomSelect.value);
    const tenantId = Number(tenantSelect.value);
    const monthlyRent = Number(document.getElementById("monthlyRent").value);
    const deposit = Number(document.getElementById("deposit").value);
    const startDate = document.getElementById("startDate").value;
    const endDate = document.getElementById("endDate").value;
    const paymentCycleMonths = Number(document.getElementById("paymentCycle").value);
    if (!roomId || !tenantId) throw new Error("Vui lòng chọn phòng và khách thuê đại diện.");
    if (!startDate || !endDate || endDate <= startDate) {
        throw new Error("Ngày kết thúc phải sau ngày bắt đầu.");
    }
    if (!Number.isSafeInteger(monthlyRent) || monthlyRent <= 0) {
        throw new Error("Tiền thuê hàng tháng phải là số nguyên lớn hơn 0.");
    }
    if (!Number.isSafeInteger(deposit) || deposit < 0) {
        throw new Error("Tiền cọc phải là số nguyên không âm.");
    }
    if (deposit > 3 * monthlyRent) {
        throw new Error("Tiền cọc không được vượt quá 3 tháng tiền thuê.");
    }
    return {
        room_id: roomId,
        tenant_id: tenantId,
        start_date: startDate,
        end_date: endDate,
        deposit,
        monthly_rent: monthlyRent,
        payment_cycle_months: paymentCycleMonths,
    };
}

contractForm.addEventListener("submit", async event => {
    event.preventDefault();
    const button = document.getElementById("createContractBtn");
    const error = document.getElementById("formError");
    button.disabled = true;
    error.textContent = "";
    try {
        const body = readContractForm();
        await apiRequest("/contracts", {method: "POST", body: JSON.stringify(body)});
        showNotice("Lập hợp đồng thành công.", "success");
        const selectedPropertyId = propertySelect.value;
        contractForm.reset();
        propertySelect.value = selectedPropertyId;
        document.getElementById("deposit").value = "0";
        await Promise.all([loadContracts(), loadRoomsAndTenants()]);
    } catch (requestError) {
        error.textContent = requestError.message;
    } finally {
        button.disabled = false;
    }
});

document.getElementById("addTenantBtn").addEventListener("click", () => {
    document.getElementById("tenantFormError").textContent = "";
    tenantForm.reset();
    tenantDialog.showModal();
});

tenantForm.addEventListener("submit", async event => {
    event.preventDefault();
    const button = document.getElementById("saveTenantBtn");
    const error = document.getElementById("tenantFormError");
    button.disabled = true;
    error.textContent = "";
    try {
        const property = selectedProperty();
        if (!property) throw new Error("Vui lòng chọn khu trọ trước khi thêm khách thuê.");
        const body = {
            full_name: document.getElementById("tenantName").value.trim(),
            phone: document.getElementById("tenantPhone").value.trim(),
            id_number: document.getElementById("tenantIdNumber").value.trim(),
            property_id: property.id,
        };
        const email = document.getElementById("tenantEmail").value.trim();
        if (email) body.email = email;
        const created = await apiRequest("/tenants", {method: "POST", body: JSON.stringify(body)});
        tenants.push(created);
        setSelectOptions(
            tenantSelect,
            "Chọn khách thuê đại diện",
            tenants,
            tenant => `${tenant.full_name} · ${tenant.phone}`,
        );
        tenantSelect.value = String(created.id);
        tenantDialog.close();
        showNotice("Đã thêm và chọn khách thuê đại diện.", "success");
    } catch (requestError) {
        error.textContent = requestError.message;
    } finally {
        button.disabled = false;
    }
});

propertySelect.addEventListener("change", () => {
    loadRoomsAndTenants().catch(error => showNotice(error.message, "error"));
});
roomSelect.addEventListener("change", () => {
    const room = rooms.find(item => String(item.id) === roomSelect.value);
    document.getElementById("monthlyRent").value = room ? room.base_rent : "";
    updateRentHint();
});
document.getElementById("monthlyRent").addEventListener("input", updateRentHint);
document.getElementById("refreshContractsBtn").addEventListener("click", loadContracts);
document.getElementById("closeTenantDialogBtn").addEventListener("click", () => tenantDialog.close());
document.getElementById("cancelTenantBtn").addEventListener("click", () => tenantDialog.close());
const depositDialog = document.getElementById("depositDialog");
const depositForm = document.getElementById("depositForm");
const settlementStatus = document.getElementById("depositSettlementStatus");
const returnedAmountGroup = document.getElementById("returnedAmountGroup");

function updateSettlementFields() {
    const returning = settlementStatus.value === "returned";
    returnedAmountGroup.hidden = !returning;
    document.getElementById("returnedAmount").required = returning;
}

settlementStatus.addEventListener("change", updateSettlementFields);
depositForm.addEventListener("submit", async event => {
    event.preventDefault();
    const submitButton = document.getElementById("saveDepositBtn");
    const error = document.getElementById("depositFormError");
    const status = settlementStatus.value;
    const returnedAmount = status === "returned" ? Number(document.getElementById("returnedAmount").value) : 0;
    error.textContent = "";
    if (status === "returned" && (!Number.isSafeInteger(returnedAmount) || returnedAmount <= 0)) {
        error.textContent = "Nhập số tiền hoàn trả hợp lệ.";
        return;
    }
    submitButton.disabled = true;
    try {
        await apiRequest(`/contracts/${document.getElementById("depositContractId").value}/deposit`, {
            method: "PATCH",
            body: JSON.stringify({
                status,
                returned_amount: returnedAmount,
                note: document.getElementById("depositNote").value.trim() || null,
            }),
        });
        depositDialog.close();
        showNotice("Đã lưu quyết toán tiền cọc. Bạn có thể hoàn tất thanh lý hợp đồng.", "success");
        await loadContracts();
    } catch (requestError) {
        error.textContent = requestError.message;
    } finally {
        submitButton.disabled = false;
    }
});
document.getElementById("closeDepositDialogBtn").addEventListener("click", () => depositDialog.close());
document.getElementById("cancelDepositBtn").addEventListener("click", () => depositDialog.close());
logoutBtn.addEventListener("click", disconnect);

if (!accessToken) {
    window.location.replace("index.html");
} else {
    connect().catch(error => {
        clearSession();
        showNotice(error.message, "error");
    });
}
