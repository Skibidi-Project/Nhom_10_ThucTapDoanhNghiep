const token = sessionStorage.getItem('us05_access_token');
const contract = document.getElementById('contract');
const period = document.getElementById('period');
const message = document.getElementById('message');
const result = document.getElementById('result');
const issueLink = document.getElementById('issueLink');
const readingRoom = document.getElementById('readingRoom');
const configuredUtilityPrices = document.getElementById('configuredUtilityPrices');
const readingForms = [...document.querySelectorAll('.utility-reading-card')];
let activeContracts = [];
let readings = [];

async function api(path, options = {}) {
    const response = await fetch('/api' + path, {
        ...options,
        headers: {
            Authorization: 'Bearer ' + token,
            ...(options.body ? { 'Content-Type': 'application/json' } : {})
        }
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
        throw new Error(typeof data?.detail === 'string' ? data.detail : 'Dữ liệu không hợp lệ');
    }
    return data;
}

function localMonth() {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

function selectedContract() {
    return activeContracts.find(item => String(item.id) === contract.value);
}

function refreshConsumption(form) {
    const previous = form.elements.previous.value;
    const current = form.elements.current.value;
    const output = form.querySelector('.utility-consumption');
    output.textContent = previous !== '' && current !== '' && Number(current) >= Number(previous)
        ? `Tiêu thụ: ${Number(current) - Number(previous)}`
        : 'Tiêu thụ: —';
}

function prepareReadingForms() {
    const selected = selectedContract();
    for (const form of readingForms) {
        const previousInput = form.elements.previous;
        const currentInput = form.elements.current;
        const submit = form.querySelector('button[type="submit"]');
        const status = form.querySelector('.utility-reading-message');
        const kind = form.dataset.utility;
        const existing = readings.find(item => item.utility_type === kind && item.period === period.value);
        const prior = readings
            .filter(item => item.utility_type === kind && item.period < period.value)
            .sort((a, b) => b.period.localeCompare(a.period))[0];

        previousInput.value = existing ? existing.previous_reading : (prior ? prior.current_reading : '');
        currentInput.value = existing ? existing.current_reading : '';
        previousInput.disabled = Boolean(existing);
        currentInput.disabled = Boolean(existing);
        submit.disabled = Boolean(existing) || !selected || !period.value;
        status.textContent = existing
            ? `Kỳ ${period.value} đã có chỉ số. Chức năng hiện tại không hỗ trợ sửa bản ghi đã lưu.`
            : prior
                ? `Đã gợi ý chỉ số đầu kỳ từ tháng ${prior.period}. Hãy kiểm tra lại trước khi lưu.`
                : 'Chưa có kỳ trước để gợi ý chỉ số đầu kỳ.';
        refreshConsumption(form);
    }
    if (selected) {
        readingRoom.textContent = `Phòng ${selected.room_number} · ${selected.property_name} · Hợp đồng #${selected.id}`;
    } else {
        readingRoom.textContent = 'Chọn hợp đồng và kỳ ở phía trên để nhập chỉ số.';
    }
}

async function loadReadings() {
    const selected = selectedContract();
    readings = [];
    if (selected) readings = await api(`/rooms/${selected.room_id}/readings`);
    prepareReadingForms();
}

async function loadConfiguredPrices(selected) {
    configuredUtilityPrices.textContent = 'Đang tải đơn giá…';
    if (!selected) {
        configuredUtilityPrices.textContent = 'Chọn hợp đồng để xem đơn giá của cơ sở.';
        return;
    }
    try {
        const [prices, assignments] = await Promise.all([
            api(`/properties/${selected.property_id}/service-prices`),
            api(`/contracts/${selected.id}/services`)
        ]);
        const priceByCode = new Map(prices.map(item => [item.code, item]));
        const assignmentByCode = new Map(assignments.map(item => [item.service_code, item]));
        const labels = { electricity: 'Điện', water: 'Nước' };
        const units = { electricity: 'kwh', water: 'm3' };
        configuredUtilityPrices.replaceChildren();
        for (const code of ['electricity', 'water']) {
            const configured = priceByCode.get(code);
            const assignment = assignmentByCode.get(code);
            const price = assignment?.effective_price ?? configured?.unit_price;
            const unit = assignment?.billing_unit ?? configured?.billing_unit;
            const row = document.createElement('p');
            if (price === null || price === undefined) {
                row.textContent = `${labels[code]}: chưa cấu hình đơn giá.`;
            } else if (unit !== units[code]) {
                row.textContent = `${labels[code]}: đơn vị hiện tại là ${unit || 'chưa chọn'}, cần ${units[code]}.`;
            } else {
                const source = assignment?.price_override !== null && assignment?.price_override !== undefined
                    ? 'giá riêng đã gán'
                    : assignment ? 'dịch vụ đã gán' : 'cấu hình cơ sở';
                row.textContent = `${labels[code]}: ${Number(price).toLocaleString('vi-VN')} đ/${unit} (${source})`;
            }
            configuredUtilityPrices.append(row);
        }
    } catch (error) {
        configuredUtilityPrices.textContent = `Không tải được cấu hình đơn giá: ${error.message}`;
    }
}

async function start() {
    if (!token) throw new Error('Vui lòng đăng nhập.');
    const [contracts, properties] = await Promise.all([api('/contracts'), api('/properties')]);
    activeContracts = contracts.filter(item => item.status === 'active');
    for (const item of activeContracts) {
        contract.add(new Option(`${item.property_name} / ${item.room_number} / ${item.tenant_name}`, item.id));
    }
    for (const item of properties) property.add(new Option(item.name, item.id));
    period.value = localMonth();
    if (activeContracts.length) contract.value = String(activeContracts[0].id);
    await loadReadings();
    await loadConfiguredPrices(selectedContract());
}

for (const element of [contract, period]) {
    element.addEventListener('change', async () => {
        result.hidden = true;
        issueLink.hidden = true;
        message.textContent = '';
        try {
            await loadReadings();
            if (element === contract) await loadConfiguredPrices(selectedContract());
        } catch (error) {
            message.textContent = error.message;
        }
    });
}

for (const form of readingForms) {
    for (const input of [form.elements.previous, form.elements.current]) {
        input.addEventListener('input', () => refreshConsumption(form));
    }
    form.addEventListener('submit', async event => {
        event.preventDefault();
        const selected = selectedContract();
        const previous = Number(form.elements.previous.value);
        const current = Number(form.elements.current.value);
        const status = form.querySelector('.utility-reading-message');
        const submit = form.querySelector('button[type="submit"]');
        if (!selected || !period.value) {
            status.textContent = 'Hãy chọn hợp đồng và kỳ ghi.';
            return;
        }
        if (!Number.isSafeInteger(previous) || !Number.isSafeInteger(current) || previous < 0 || current < previous) {
            status.textContent = 'Chỉ số phải là số nguyên không âm; chỉ số cuối kỳ phải lớn hơn hoặc bằng đầu kỳ.';
            return;
        }
        submit.disabled = true;
        status.textContent = 'Đang lưu chỉ số…';
        try {
            await api(`/rooms/${selected.room_id}/readings`, {
                method: 'POST',
                body: JSON.stringify({
                    utility_type: form.dataset.utility,
                    period: period.value,
                    previous_reading: previous,
                    current_reading: current
                })
            });
            readings = await api(`/rooms/${selected.room_id}/readings`);
            prepareReadingForms();
            status.textContent = 'Đã lưu chỉ số. Bạn có thể bấm “Xem tính tiền” để xem hóa đơn tạm tính.';
        } catch (error) {
            status.textContent = error.message;
            submit.disabled = false;
        }
    });
}

document.getElementById('previewForm').addEventListener('submit', async event => {
    event.preventDefault();
    result.hidden = true;
    issueLink.hidden = true;
    result.replaceChildren();
    try {
        const data = await api('/utility-pricing/preview?' + new URLSearchParams({ contract_id: contract.value, period: period.value }));
        for (const item of data.items) {
            const row = document.createElement('p');
            const source = item.source === 'service_config' ? 'cấu hình đơn giá dịch vụ' : item.source;
            const validity = item.valid_from ? `; hiệu lực ${item.valid_from} — ${item.valid_to}` : '';
            row.textContent = `${item.utility === 'electricity' ? 'Điện' : 'Nước'}: ${item.previous_reading} → ${item.current_reading}; tiêu thụ ${item.consumption}; đơn giá ${Number(item.unit_price).toLocaleString('vi-VN')} đ; nguồn ${source}${validity}; thành tiền ${Number(item.amount).toLocaleString('vi-VN')} đ`;
            result.append(row);
        }
        const total = document.createElement('strong');
        total.textContent = 'Tổng tiện ích: ' + data.total + ' đ';
        result.append(total);
        result.hidden = false;
        issueLink.hidden = false;
        message.textContent = '';
    } catch (error) {
        message.textContent = error.message;
    }
});

start().catch(error => { message.textContent = error.message; });
