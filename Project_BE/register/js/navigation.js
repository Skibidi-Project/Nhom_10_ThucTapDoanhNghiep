(() => {
    
const groups = [
    {
        label: 'TỔNG QUAN',
        links: [
            ['/register/html/dashboard.html', 'Tổng quan', 'overview']
        ]
    },
    {
        label: 'QUẢN LÝ',
        links: [
            ['/register/html/properties.html', 'Quản lý cơ sở', 'properties'],
            ['/register/html/rooms.html', 'Quản lý phòng', 'rooms'],
            ['/register/html/contracts.html', 'Quản lý hợp đồng', 'contracts']
        ]
    },
    {
        label: 'TÀI CHÍNH',
        links: [
            ['/register/html/utility-pricing.html', 'Điện/nước', 'utility'],
            ['/register/html/service-prices.html', 'Cấu hình đơn giá dịch vụ', 'service-prices'],
            ['/register/html/invoices.html', 'Chốt hóa đơn', 'invoices'],
            ['/register/html/payments.html', 'Hóa đơn & Thanh toán', 'payments'],
            ['/register/html/expenses.html', 'Chi phí', 'expenses']
        ]
    },
    {
        label: 'VẬN HÀNH',
        links: [
            ['/register/html/services.html', 'Dịch vụ', 'services'],
            ['/register/html/tenants.html', 'Khách thuê', 'tenants']
        ]
    },
    {
        label: 'CÁ NHÂN',
        links: [
            ['/register/html/account.html', 'Tài khoản', 'account']
        ]
    }
];


    const icons = {
        overview: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 11.5 12 4l8.5 7.5"/><path d="M5.5 10v9h13v-9"/><path d="M9.5 19v-5h5v5"/></svg>',
        properties: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 21V7l8-4 8 4v14"/><path d="M8 21v-7h8v7M8 10h8"/></svg>',
        rooms: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 20V7h18v13M3 12h18"/><path d="M7 12V8h4v4M13 12V8h4v4"/></svg>',
        contracts: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h9l3 3v15H6z"/><path d="M15 3v4h4M9 11h6M9 15h6M9 18h4"/></svg>',
        utility: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M13.5 2.5 6 13h5l-.5 8.5L18 10h-5z"/></svg>',
        'service-prices': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3h14v18l-3-2-4 2-4-2-3 2z"/><path d="M8 7h8M8 11h2M14 11h2M8 15h2M14 15h2"/></svg>',
        invoices: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3h14v18l-3-2-4 2-4-2-3 2z"/><path d="M8 8h8M8 12h8M8 16h5"/></svg>',
        payments: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 10h18M7 15h4"/></svg>',
        expenses: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16v12H4zM7 7V5h10v2"/><circle cx="12" cy="13" r="2.5"/><path d="M12 11v4"/></svg>',
        services: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"/></svg>',
        tenants: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="8" r="3"/><path d="M3 20c.5-4 2.5-6 6-6s5.5 2 6 6M16 5c2 0 3 1 3 3s-1 3-3 3M17 14c3 0 4 2 4 5"/></svg>',
        account: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21c1-5 3.5-7 8-7s7 2 8 7"/></svg>',
        admin: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 5 6v5c0 5 2.8 8.2 7 10 4.2-1.8 7-5 7-10V6z"/><path d="M9 12l2 2 4-4"/></svg>'
    };

    const roleNames = { landlord: 'Chủ nhà', manager: 'Quản lý', admin: 'Quản trị viên', tenant: 'Khách thuê' };
    const token = sessionStorage.getItem('us05_access_token');
    if (!token) return;

    const page = location.pathname;
    const header = document.querySelector('header.topbar') || document.querySelector('header.account-header');
    if (!header) return;

    header.classList.add('navigation-header');
    document.body.classList.add('unified-navigation-active');
    if (document.querySelector('.account-shell')) document.body.classList.add('account-page-active');

    const aside = document.createElement('aside');
    aside.className = 'ministay-sidebar unified-nav';
    aside.setAttribute('aria-label', 'Thanh điều hướng MiniStay');

    const brand = document.createElement('a');
    brand.className = 'sidebar-brand';
    brand.href = sessionStorage.getItem('us05_user_role') === 'tenant' ? '/register/html/tenant-portal.html' : '/register/html/properties.html';
    brand.innerHTML = '<span class="sidebar-brand-mark">M</span><span class="sidebar-brand-name">MiniStay</span>';
    aside.append(brand);

    const collapseBtn = document.createElement('button');
    collapseBtn.type = 'button';
    collapseBtn.className = 'sidebar-collapse';
    collapseBtn.setAttribute('aria-label', 'Thu gọn thanh điều hướng');
    collapseBtn.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14 7-5 5 5 5"/></svg>';
    aside.append(collapseBtn);

    const nav = document.createElement('nav');
    nav.className = 'sidebar-nav';
    aside.append(nav);

    const footer = document.createElement('div');
    footer.className = 'sidebar-footer';
    footer.innerHTML = '<div class="sidebar-user"><span class="sidebar-avatar">M</span><div class="sidebar-user-copy"><strong id="sidebarUserName">Tài khoản</strong><span id="sidebarUserRole"></span></div></div><button type="button" class="sidebar-logout" data-action="logout">Đăng xuất</button>';
    aside.append(footer);

    const backdrop = document.createElement('button');
    backdrop.type = 'button';
    backdrop.className = 'navigation-backdrop';
    backdrop.setAttribute('aria-label', 'Đóng menu');

    const bottom = document.createElement('nav');
    bottom.className = 'mobile-bottom-nav';
    bottom.setAttribute('aria-label', 'Điều hướng nhanh');

    const moreSheet = document.createElement('div');
    moreSheet.className = 'mobile-more-sheet';
    moreSheet.setAttribute('aria-hidden', 'true');
    moreSheet.innerHTML = '<div class="mobile-more-heading"><strong>Thêm chức năng</strong><button type="button" class="mobile-more-close" aria-label="Đóng">×</button></div><div class="mobile-more-list"></div>';

    document.body.append(aside, backdrop, bottom, moreSheet);

    function closeDrawer() {
        aside.classList.remove('drawer-open');
        backdrop.classList.remove('visible');
        document.body.classList.remove('drawer-open');
    }

    function openDrawer() {
        aside.classList.add('drawer-open');
        backdrop.classList.add('visible');
        document.body.classList.add('drawer-open');
    }

    function closeMore() {
        moreSheet.classList.remove('open');
        moreSheet.setAttribute('aria-hidden', 'true');
    }

    backdrop.addEventListener('click', closeDrawer);
    moreSheet.querySelector('.mobile-more-close').addEventListener('click', closeMore);

    let menuButton = header.querySelector('#navMenuBtn');
    if (!menuButton) {
        menuButton = document.createElement('button');
        menuButton.type = 'button';
        menuButton.id = 'navMenuBtn';
        menuButton.className = 'nav-menu-button';
        menuButton.setAttribute('aria-label', 'Mở menu');
        menuButton.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg>';
        const left = header.querySelector('.topbar-left');
        if (left) left.prepend(menuButton);
        else header.prepend(menuButton);
    }
    menuButton.addEventListener('click', openDrawer);

    let headerAccount = header.querySelector('.header-account');
    if (!headerAccount) {
        headerAccount = document.createElement('div');
        headerAccount.className = 'header-account';
        headerAccount.innerHTML = '<span id="headerUserName">Tài khoản</span>';
        header.append(headerAccount);
    }

    function logout() {
        sessionStorage.removeItem('us05_access_token');
        sessionStorage.removeItem('us05_user_role');
        location.replace('/register/html/login.html');
    }

    footer.querySelector('[data-action="logout"]').addEventListener('click', logout);

    let currentRole = sessionStorage.getItem('us05_user_role');

    function isManagerLink(link) {
        return ['landlord', 'manager'].includes(currentRole);
    }

    function buildNavigation(user) {
        currentRole = user.role;
        sessionStorage.setItem('us05_user_role', user.role);

        let visibleGroups;
        if (['landlord', 'manager'].includes(user.role)) {
            visibleGroups = groups;
        } else if (user.role === 'admin') {
            visibleGroups = [
                { label: 'QUẢN TRỊ', links: [['/register/html/admin-users.html', 'Quản lý người dùng', 'admin']] },
                { label: 'CÁ NHÂN', links: [['/register/html/account.html', 'Tài khoản', 'account']] }
            ];
        } else if (user.role === 'tenant') {
            visibleGroups = [
                { label: 'THUÊ NHÀ', links: [['/register/html/tenant-portal.html', 'Thông tin thuê nhà', 'overview']] },
                { label: 'CÁ NHÂN', links: [['/register/html/account.html', 'Tài khoản', 'account']] }
            ];
        } else {
            visibleGroups = [{ label: 'CÁ NHÂN', links: [['/register/html/account.html', 'Tài khoản', 'account']] }];
        }

        nav.replaceChildren();
        for (const group of visibleGroups) {
            const section = document.createElement('section');
            section.className = 'sidebar-group';
            const label = document.createElement('div');
            label.className = 'sidebar-group-label';
            label.textContent = group.label;
            section.append(label);
            for (const [href, text, icon] of group.links) {
                const link = document.createElement('a');
                link.href = href;
                link.className = 'sidebar-link';
                link.dataset.tooltip = text;
                link.innerHTML = icons[icon] + '<span class="sidebar-link-text">' + text + '</span>';
                if (href === page) {
                    link.classList.add('active');
                    link.setAttribute('aria-current', 'page');
                }
                section.append(link);
            }
            nav.append(section);
        }

        const name = user.full_name || user.email || 'Tài khoản';
        const role = roleNames[user.role] || user.role || '';
        const sidebarName = footer.querySelector('#sidebarUserName');
        const sidebarRole = footer.querySelector('#sidebarUserRole');
        const sidebarAvatar = footer.querySelector('.sidebar-avatar');
        const headerName = headerAccount.querySelector('#headerUserName');
        sidebarName.textContent = name;
        sidebarRole.textContent = role;
        sidebarAvatar.textContent = name.trim().charAt(0).toUpperCase();
        headerName.textContent = name + (role ? ' · ' + role : '');

        buildMobileNavigation(visibleGroups, user.role);
    }

    function buildMobileNavigation(visibleGroups, role) {
        bottom.replaceChildren();
        const allLinks = visibleGroups.flatMap(group => group.links);
        const primary = role === 'admin'
            ? [allLinks.find(link => link[2] === 'admin') || allLinks[0], allLinks.find(link => link[2] === 'account') || allLinks[0]]
            : [
                allLinks.find(link => link[2] === 'overview'),
                allLinks.find(link => link[2] === 'rooms'),
                allLinks.find(link => link[2] === 'payments')
            ].filter(Boolean);

        const mobileItems = [];
        if (role === 'tenant') {
            mobileItems.push(
                [allLinks.find(link => link[2] === 'overview')[0], 'Thuê nhà', 'overview'],
                [allLinks.find(link => link[2] === 'account')[0], 'Tài khoản', 'account']
            );
        } else if (primary.length === 3) {
            mobileItems.push(
                [primary[0][0], 'Tổng quan', 'overview'],
                [primary[1][0], 'Phòng', 'rooms'],
                [primary[2][0], 'Hóa đơn', 'payments']
            );
        } else {
            mobileItems.push(['/register/html/account.html', 'Tài khoản', 'account']);
        }

        for (const [href, label, icon] of mobileItems) {
            const link = document.createElement('a');
            link.href = href;
            link.className = 'mobile-nav-item';
            link.innerHTML = icons[icon] + '<span>' + label + '</span>';
            if (href === page) link.classList.add('active');
            bottom.append(link);
        }

        const more = document.createElement('button');
        more.type = 'button';
        more.className = 'mobile-nav-item mobile-more-button';
        more.innerHTML = icons.services + '<span>Thêm</span>';
        more.addEventListener('click', () => {
            moreSheet.classList.toggle('open');
            moreSheet.setAttribute('aria-hidden', moreSheet.classList.contains('open') ? 'false' : 'true');
        });
        bottom.append(more);

        const moreList = moreSheet.querySelector('.mobile-more-list');
        moreList.replaceChildren();
        for (const group of visibleGroups) {
            const label = document.createElement('div');
            label.className = 'mobile-more-label';
            label.textContent = group.label;
            moreList.append(label);
            for (const [href, text, icon] of group.links) {
                if (mobileItems.some(item => item[0] === href)) continue;
                const link = document.createElement('a');
                link.href = href;
                link.innerHTML = icons[icon] + '<span>' + text + '</span>';
                if (href === page) link.classList.add('active');
                moreList.append(link);
            }
        }
        if (!visibleGroups.some(group => group.links.some(link => link[0] === '/register/html/account.html'))) {
            const accountLink = document.createElement('a');
            accountLink.href = '/register/html/account.html';
            accountLink.innerHTML = icons.account + '<span>Tài khoản</span>';
            if (page === '/register/html/account.html') accountLink.classList.add('active');
            moreList.append(accountLink);
        }

        const logoutButton = document.createElement('button');
        logoutButton.type = 'button';
        logoutButton.className = 'mobile-more-logout';
        logoutButton.textContent = 'Đăng xuất';
        logoutButton.addEventListener('click', logout);
        moreList.append(logoutButton);
    }

    const collapsed = localStorage.getItem('ministay_sidebar_collapsed') === 'true';
    if (collapsed) document.body.classList.add('sidebar-collapsed');
    collapseBtn.addEventListener('click', () => {
        document.body.classList.toggle('sidebar-collapsed');
        const isCollapsed = document.body.classList.contains('sidebar-collapsed');
        localStorage.setItem('ministay_sidebar_collapsed', String(isCollapsed));
        collapseBtn.setAttribute('aria-label', isCollapsed ? 'Mở rộng thanh điều hướng' : 'Thu gọn thanh điều hướng');
    });

    async function refreshNavigation() {
        try {
            const response = await fetch('/api/users/me', {
                headers: { Authorization: 'Bearer ' + token },
                cache: 'no-store'
            });
            if (!response.ok) return;
            const user = await response.json();
            if (token !== sessionStorage.getItem('us05_access_token')) return;
            buildNavigation(user);
        } catch (_) {
            closeDrawer();
        }
    }

    refreshNavigation();
    window.addEventListener('pageshow', event => {
        if (!event.persisted) return;
        if (!sessionStorage.getItem('us05_access_token')) {
            location.replace('/register/html/login.html');
            return;
        }
        refreshNavigation();
    });
})();
