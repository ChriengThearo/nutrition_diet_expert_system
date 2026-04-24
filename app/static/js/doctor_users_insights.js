(function () {
    const root = document.getElementById('users-insights-root');
    if (!root) {
        return;
    }

    const endpoints = {
        usersPage: String(root.dataset.usersPageUrl || '').trim(),
        usersData: String(root.dataset.usersDataUrl || '').trim(),
        analytics: String(root.dataset.analyticsUrl || '').trim()
    };

    const state = {
        page: 1,
        perPage: 10,
        q: '',
        role: 'all',
        status: 'all',
        sort: 'created_desc'
    };

    const dom = {
        refreshAllBtn: document.getElementById('refresh-insights-data'),
        refreshAnalyticsBtn: document.getElementById('refresh-analytics'),
        searchInput: document.getElementById('users-search-input'),
        roleFilter: document.getElementById('users-role-filter'),
        statusFilter: document.getElementById('users-status-filter'),
        sortFilter: document.getElementById('users-sort-filter'),
        perPageFilter: document.getElementById('users-per-page'),
        tableBody: document.getElementById('users-table-body'),
        pageInfo: document.getElementById('users-page-info'),
        pagination: document.getElementById('users-pagination'),
        analyticsBars: document.getElementById('rule-usage-bars'),
        kpiTotalAccounts: document.getElementById('kpi-total-accounts'),
        kpiActiveAccounts: document.getElementById('kpi-active-accounts'),
        kpiTotalSubmissions: document.getElementById('kpi-total-submissions'),
        kpiNoMatch: document.getElementById('kpi-no-match'),
        detailCanvasEl: document.getElementById('userDetailCanvas'),
        detailLoading: document.getElementById('user-detail-loading'),
        detailError: document.getElementById('user-detail-error'),
        detailContent: document.getElementById('user-detail-content'),
        detailUserTitle: document.getElementById('detail-user-title'),
        detailUserUsername: document.getElementById('detail-user-username'),
        detailUserEmail: document.getElementById('detail-user-email'),
        detailUserRoles: document.getElementById('detail-user-roles'),
        detailUserStatus: document.getElementById('detail-user-status'),
        detailUserCreated: document.getElementById('detail-user-created'),
        detailSummaryTotal: document.getElementById('detail-summary-total'),
        detailSummaryMatched: document.getElementById('detail-summary-matched'),
        detailSummaryNoMatch: document.getElementById('detail-summary-no-match'),
        detailSummaryLatestRule: document.getElementById('detail-summary-latest-rule'),
        detailLatestPlanEmpty: document.getElementById('detail-latest-plan-empty'),
        detailLatestPlanWrap: document.getElementById('detail-latest-plan-table-wrap'),
        detailLatestPlanBody: document.getElementById('detail-latest-plan-body'),
        detailHistoryBody: document.getElementById('detail-history-body')
    };

    const detailCanvas = dom.detailCanvasEl ? new bootstrap.Offcanvas(dom.detailCanvasEl) : null;
    let searchDebounceHandle = null;

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function formatNumber(value) {
        const number = Number(value);
        if (!Number.isFinite(number)) {
            return '0';
        }
        return new Intl.NumberFormat().format(number);
    }

    function formatDateTime(value) {
        if (!value) {
            return '-';
        }
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return '-';
        }
        return date.toLocaleString();
    }

    function formatMetric(value, suffix = '') {
        const number = Number(value);
        if (!Number.isFinite(number)) {
            return '-';
        }
        return `${number}${suffix}`;
    }

    function setKpi(el, value) {
        if (!el) {
            return;
        }
        el.textContent = formatNumber(value);
    }

    function getFiltersFromDom() {
        return {
            q: String(dom.searchInput?.value || '').trim(),
            role: String(dom.roleFilter?.value || 'all').trim() || 'all',
            status: String(dom.statusFilter?.value || 'all').trim() || 'all',
            sort: String(dom.sortFilter?.value || 'created_desc').trim() || 'created_desc',
            perPage: Number.parseInt(dom.perPageFilter?.value || '10', 10) || 10
        };
    }

    function updateStateFromDom(resetPage = false) {
        const filters = getFiltersFromDom();
        state.q = filters.q;
        state.role = filters.role;
        state.status = filters.status;
        state.sort = filters.sort;
        state.perPage = filters.perPage;
        if (resetPage) {
            state.page = 1;
        }
    }

    function setUsersTableLoading(message = 'Loading users...') {
        if (!dom.tableBody) {
            return;
        }
        dom.tableBody.innerHTML = `
            <tr>
                <td colspan="9" class="text-center text-muted py-4">${escapeHtml(message)}</td>
            </tr>
        `;
    }

    function buildStatusBadge(isActive) {
        return isActive
            ? '<span class="badge bg-success">Active</span>'
            : '<span class="badge bg-secondary">Inactive</span>';
    }

    function renderUsersTable(users, page, perPage) {
        if (!dom.tableBody) {
            return;
        }
        const rows = Array.isArray(users) ? users : [];
        if (rows.length === 0) {
            dom.tableBody.innerHTML = `
                <tr>
                    <td colspan="9" class="text-center text-muted py-4">No users found for current filters.</td>
                </tr>
            `;
            return;
        }

        dom.tableBody.innerHTML = rows.map((user, index) => {
            const roles = Array.isArray(user.roles) && user.roles.length > 0
                ? user.roles.map(role => `<span class="badge bg-info-subtle text-dark me-1">${escapeHtml(role)}</span>`).join('')
                : '<span class="text-muted">-</span>';
            const rowNumber = ((page - 1) * perPage) + index + 1;
            const lastRule = user.last_rule_name
                ? escapeHtml(user.last_rule_name)
                : (Number(user.plan_submissions) > 0 ? 'No Matched Rule' : '-');

            return `
                <tr data-user-detail-id="${escapeHtml(user.id)}">
                    <td>${rowNumber}</td>
                    <td>${escapeHtml(user.full_name || '-')}</td>
                    <td>${escapeHtml(user.username || '-')}</td>
                    <td>${escapeHtml(user.email || '-')}</td>
                    <td>${roles}</td>
                    <td>${buildStatusBadge(Boolean(user.is_active))}</td>
                    <td>${formatNumber(user.plan_submissions)}</td>
                    <td>${lastRule}</td>
                    <td class="text-end">
                        <button type="button"
                            class="btn btn-sm btn-outline-primary"
                            data-user-detail-id="${escapeHtml(user.id)}">
                            View
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    }

    function renderUsersPagination(pagination) {
        if (!dom.pagination || !dom.pageInfo) {
            return;
        }

        const page = Number(pagination?.page || 1);
        const totalPages = Number(pagination?.total_pages || 1);
        const totalRecords = Number(pagination?.total || 0);
        dom.pageInfo.textContent = `Page ${page} of ${Math.max(totalPages, 1)} (${formatNumber(totalRecords)} total)`;

        if (totalPages <= 1) {
            dom.pagination.innerHTML = '';
            return;
        }

        const pageItems = [];

        const pushPageItem = (label, targetPage, disabled = false, active = false) => {
            pageItems.push(`
                <li class="page-item ${disabled ? 'disabled' : ''} ${active ? 'active' : ''}">
                    <button class="page-link" type="button" data-page="${targetPage}" ${disabled ? 'disabled' : ''}>
                        ${label}
                    </button>
                </li>
            `);
        };

        pushPageItem('&laquo;', page - 1, page <= 1, false);

        const maxButtons = 5;
        const windowStart = Math.max(1, page - Math.floor(maxButtons / 2));
        const windowEnd = Math.min(totalPages, windowStart + maxButtons - 1);

        for (let current = windowStart; current <= windowEnd; current += 1) {
            pushPageItem(String(current), current, false, current === page);
        }

        pushPageItem('&raquo;', page + 1, page >= totalPages, false);

        dom.pagination.innerHTML = pageItems.join('');
    }

    async function loadUsers() {
        if (!endpoints.usersData) {
            setUsersTableLoading('Users data endpoint is unavailable.');
            return;
        }

        setUsersTableLoading();
        const params = new URLSearchParams({
            page: String(state.page),
            per_page: String(state.perPage),
            q: state.q,
            role: state.role,
            status: state.status,
            sort: state.sort
        });

        try {
            const response = await fetch(`${endpoints.usersData}?${params.toString()}`);
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.message || `Failed to load users (HTTP ${response.status})`);
            }
            renderUsersTable(data.users, Number(data.pagination?.page || state.page), Number(data.pagination?.per_page || state.perPage));
            renderUsersPagination(data.pagination);
        } catch (error) {
            console.error('Failed to load users table:', error);
            setUsersTableLoading('Failed to load users. Please try again.');
            if (dom.pagination) {
                dom.pagination.innerHTML = '';
            }
        }
    }

    function renderRuleUsageBars(usageItems, totalSubmissions) {
        if (!dom.analyticsBars) {
            return;
        }

        const items = Array.isArray(usageItems) ? usageItems : [];
        if (items.length === 0 || Number(totalSubmissions) <= 0) {
            dom.analyticsBars.innerHTML = '<p class="text-muted mb-0">No plan submission analytics available yet.</p>';
            return;
        }

        dom.analyticsBars.innerHTML = items.map(item => {
            const count = Number(item.count || 0);
            const percent = Number(item.percent || 0);
            const boundedPercent = Math.max(0, Math.min(percent, 100));
            const fillWidth = boundedPercent > 0 ? Math.max(boundedPercent, 2) : 0;
            const label = item.label || 'Unknown';
            const usersCount = Number(item.users_count || 0);

            return `
                <article class="rule-usage-item">
                    <div class="rule-usage-head">
                        <p class="rule-usage-label">${escapeHtml(label)}</p>
                        <p class="rule-usage-meta">${formatNumber(count)} submissions • ${formatNumber(usersCount)} users</p>
                    </div>
                    <div class="rule-usage-progress" role="progressbar" aria-valuemin="0" aria-valuemax="100"
                        aria-valuenow="${boundedPercent.toFixed(2)}">
                        <div class="rule-usage-fill" style="width: ${fillWidth.toFixed(2)}%;"></div>
                    </div>
                </article>
            `;
        }).join('');
    }

    async function loadAnalytics() {
        if (!endpoints.analytics) {
            if (dom.analyticsBars) {
                dom.analyticsBars.innerHTML = '<p class="text-danger mb-0">Analytics endpoint is unavailable.</p>';
            }
            return;
        }

        if (dom.analyticsBars) {
            dom.analyticsBars.innerHTML = '<p class="text-muted mb-0">Loading analytics...</p>';
        }

        try {
            const response = await fetch(endpoints.analytics);
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.message || `Failed to load analytics (HTTP ${response.status})`);
            }

            const summary = data.summary || {};
            setKpi(dom.kpiTotalAccounts, summary.total_accounts);
            setKpi(dom.kpiActiveAccounts, summary.active_accounts);
            setKpi(dom.kpiTotalSubmissions, summary.total_plan_submissions);
            setKpi(dom.kpiNoMatch, summary.no_match_submissions);

            renderRuleUsageBars(data.usage, summary.total_plan_submissions);
        } catch (error) {
            console.error('Failed to load analytics:', error);
            if (dom.analyticsBars) {
                dom.analyticsBars.innerHTML = '<p class="text-danger mb-0">Failed to load analytics. Please try again.</p>';
            }
        }
    }

    function setUserDetailLoading(loading) {
        if (dom.detailLoading) {
            dom.detailLoading.classList.toggle('d-none', !loading);
        }
        if (dom.detailContent) {
            dom.detailContent.classList.toggle('d-none', loading);
        }
    }

    function setUserDetailError(message) {
        if (!dom.detailError) {
            return;
        }
        if (!message) {
            dom.detailError.textContent = '';
            dom.detailError.classList.add('d-none');
            return;
        }
        dom.detailError.textContent = String(message);
        dom.detailError.classList.remove('d-none');
    }

    function renderLatestPlan(latestPlan) {
        if (!dom.detailLatestPlanBody || !dom.detailLatestPlanEmpty || !dom.detailLatestPlanWrap) {
            return;
        }

        if (!latestPlan) {
            dom.detailLatestPlanBody.innerHTML = '';
            dom.detailLatestPlanEmpty.classList.remove('d-none');
            dom.detailLatestPlanWrap.classList.add('d-none');
            return;
        }

        const rows = [
            ['Generated At', formatDateTime(latestPlan.generated_at)],
            ['Rule', latestPlan.rule_name || 'No Matched Rule'],
            ['Diet Type', latestPlan.diet_type || '-'],
            ['Meals / Day', latestPlan.meals_per_day ?? '-'],
            ['BMI', formatMetric(latestPlan.bmi)],
            ['Calories', formatMetric(latestPlan.calories, ' kcal')],
            ['Protein', formatMetric(latestPlan.protein, ' g')],
            ['Sugar', formatMetric(latestPlan.sugar, ' g')],
            ['Fat', formatMetric(latestPlan.fat, ' g')],
            ['Blood Sugar', formatMetric(latestPlan.blood_sugar, ' mg/dL')],
            ['Allergies', latestPlan.allergies_text || 'None']
        ];

        dom.detailLatestPlanBody.innerHTML = rows.map(([label, value]) => `
            <tr>
                <th class="text-nowrap">${escapeHtml(label)}</th>
                <td>${escapeHtml(value)}</td>
            </tr>
        `).join('');

        dom.detailLatestPlanEmpty.classList.add('d-none');
        dom.detailLatestPlanWrap.classList.remove('d-none');
    }

    function renderDetailHistory(history) {
        if (!dom.detailHistoryBody) {
            return;
        }
        const rows = Array.isArray(history) ? history : [];
        if (rows.length === 0) {
            dom.detailHistoryBody.innerHTML = '<tr><td colspan="3" class="text-muted">No recent submission history.</td></tr>';
            return;
        }
        dom.detailHistoryBody.innerHTML = rows.map(item => `
            <tr>
                <td>${escapeHtml(formatDateTime(item.generated_at))}</td>
                <td>${escapeHtml(item.rule_name || 'No Matched Rule')}</td>
                <td>${escapeHtml(formatMetric(item.bmi))}</td>
            </tr>
        `).join('');
    }

    function renderUserDetail(data) {
        const user = data.user || {};
        const summary = data.summary || {};

        if (dom.detailUserTitle) {
            dom.detailUserTitle.textContent = user.full_name || user.username || 'User';
        }
        if (dom.detailUserUsername) {
            dom.detailUserUsername.textContent = user.username || '-';
        }
        if (dom.detailUserEmail) {
            dom.detailUserEmail.textContent = user.email || '-';
        }
        if (dom.detailUserRoles) {
            const rolesText = Array.isArray(user.roles) && user.roles.length > 0
                ? user.roles.join(', ')
                : '-';
            dom.detailUserRoles.textContent = rolesText;
        }
        if (dom.detailUserStatus) {
            dom.detailUserStatus.textContent = user.is_active ? 'Active' : 'Inactive';
        }
        if (dom.detailUserCreated) {
            dom.detailUserCreated.textContent = formatDateTime(user.created_at);
        }

        if (dom.detailSummaryTotal) {
            dom.detailSummaryTotal.textContent = formatNumber(summary.total_plan_submissions || 0);
        }
        if (dom.detailSummaryMatched) {
            dom.detailSummaryMatched.textContent = formatNumber(summary.matched_submissions || 0);
        }
        if (dom.detailSummaryNoMatch) {
            dom.detailSummaryNoMatch.textContent = formatNumber(summary.no_match_submissions || 0);
        }
        if (dom.detailSummaryLatestRule) {
            dom.detailSummaryLatestRule.textContent = summary.latest_rule_name || '-';
        }

        renderLatestPlan(data.latest_plan);
        renderDetailHistory(data.history);
    }

    async function openUserDetail(userId) {
        if (!endpoints.usersPage || !userId) {
            return;
        }
        if (detailCanvas) {
            detailCanvas.show();
        }
        setUserDetailError('');
        setUserDetailLoading(true);

        try {
            const detailUrl = `${endpoints.usersPage}/${encodeURIComponent(String(userId))}/detail`;
            const response = await fetch(detailUrl);
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.message || `Failed to load user detail (HTTP ${response.status})`);
            }
            renderUserDetail(data);
            setUserDetailLoading(false);
        } catch (error) {
            console.error('Failed to load user detail:', error);
            setUserDetailLoading(false);
            setUserDetailError(error.message || 'Failed to load user detail.');
        }
    }

    function handleTableClick(event) {
        const button = event.target.closest('[data-user-detail-id]');
        if (!button) {
            return;
        }
        const userId = button.getAttribute('data-user-detail-id');
        if (!userId) {
            return;
        }
        openUserDetail(userId);
    }

    function handleFilterChange(resetPage = true) {
        updateStateFromDom(resetPage);
        loadUsers();
    }

    function bindEvents() {
        dom.refreshAllBtn?.addEventListener('click', function () {
            loadAnalytics();
            loadUsers();
        });

        dom.refreshAnalyticsBtn?.addEventListener('click', loadAnalytics);

        dom.searchInput?.addEventListener('input', function () {
            if (searchDebounceHandle) {
                clearTimeout(searchDebounceHandle);
            }
            searchDebounceHandle = setTimeout(function () {
                handleFilterChange(true);
            }, 250);
        });

        dom.roleFilter?.addEventListener('change', function () {
            handleFilterChange(true);
        });

        dom.statusFilter?.addEventListener('change', function () {
            handleFilterChange(true);
        });

        dom.sortFilter?.addEventListener('change', function () {
            handleFilterChange(true);
        });

        dom.perPageFilter?.addEventListener('change', function () {
            handleFilterChange(true);
        });

        dom.tableBody?.addEventListener('click', handleTableClick);

        dom.pagination?.addEventListener('click', function (event) {
            const button = event.target.closest('[data-page]');
            if (!button || button.disabled) {
                return;
            }
            const nextPage = Number.parseInt(button.getAttribute('data-page') || '', 10);
            if (!Number.isFinite(nextPage) || nextPage <= 0 || nextPage === state.page) {
                return;
            }
            state.page = nextPage;
            loadUsers();
        });
    }

    function initialize() {
        bindEvents();
        updateStateFromDom(false);
        loadAnalytics();
        loadUsers();
    }

    document.addEventListener('DOMContentLoaded', initialize);
})();
