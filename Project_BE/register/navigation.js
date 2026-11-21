(() => {
    const links = [
        ['dashboard.html', 'Tổng quan'], ['properties.html', 'Quản lý cơ sở'],
        ['rooms.html', 'Quản lý phòng'], ['contracts.html', 'Quản lý hợp đồng'],
        ['invoices.html', 'Chốt hóa đơn'], ['payments.html', 'Hóa đơn & Thanh toán'], ['services.html', 'Dịch vụ'],
        ['tenants.html', 'Khách thuê'], ['expenses.html', 'Chi phí'], ['account.html', 'Tài khoản'],
    ];
    const nav = document.createElement('nav');
    nav.className = 'unified-nav'; nav.setAttribute('aria-label', 'Điều hướng chính'); nav.hidden = true;
    const header = document.querySelector('header.topbar');
    if (!header) return;
    header.after(nav);
    async function refreshNavigation() {
        nav.hidden = true; nav.replaceChildren();
        const token = sessionStorage.getItem('us05_access_token');
        if (!token) return;
        try {
            const response = await fetch('/api/users/me', {headers: {Authorization: `Bearer ${token}`}, cache: 'no-store'});
            if (!response.ok) return;
            const user = await response.json();
            if (!['landlord','manager'].includes(user.role) || token !== sessionStorage.getItem('us05_access_token')) return;
            const page = location.pathname.split('/').pop();
            for (const [href, label] of links) {
                const a = document.createElement('a'); a.href = href; a.textContent = label;
                if (href === page) { a.className = 'active'; a.setAttribute('aria-current', 'page'); }
                nav.append(a);
            }
            nav.hidden = false;
        } catch (_) { nav.hidden = true; }
    }
    refreshNavigation();
    document.getElementById('logoutBtn')?.addEventListener('click', () => { nav.hidden = true; nav.replaceChildren(); });
    window.addEventListener('pageshow', event => {
        if (!event.persisted) return;
        if (!sessionStorage.getItem('us05_access_token')) { location.replace('login.html'); return; }
        refreshNavigation();
    });
})();
