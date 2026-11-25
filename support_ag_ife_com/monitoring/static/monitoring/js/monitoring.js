(() => {
    'use strict';
    const root = document.getElementById('monRoot');
    if (!root) return;

    const body = document.getElementById('monServers');
    const refreshButton = document.getElementById('monRefresh');
    const banner = document.getElementById('monBanner');
    const overlay = document.getElementById('monOverlay');
    const modal = overlay.querySelector('.mon-modal');
    const title = document.getElementById('monModalTitle');
    const ip = document.getElementById('monModalIp');
    const content = document.getElementById('monTabContent');
    const tabs = [...document.querySelectorAll('.mon-tab')];
    const numberFormat = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 });
    let servers = new Map();
    let diskLimit = 90;
    let selectedId = null;
    let selectedTab = 'network';
    let previousFocus = null;
    let previousOverflow = '';
    let busy = false;
    let expanded = new Set();

    const names = {
        REPORT: 'Отчёты',
        DISK: 'Диски',
        DATA_CREWID: 'Профили экипажа',
        DATA_CREWLIST: 'Экипаж',
        DATA_ECLB: 'ECLB',
        DATA_PAX: 'Пассажиры',
        DATA_PAXPNL: 'Забронированные пассажиры',
        DATA_PAXPRL: 'Зарегистрированные / допущенные пассажиры',
        DATA_SKYSHOP: 'SkyShop',
        DATA_XML4OPS: 'Рейсы'
    };
    const errorLabels = {
        file_missing: 'Файл отчёта отсутствует в хранилище',
        file_unreadable: 'Нет доступа к файлу отчёта',
        file_invalid: 'Файл отчёта повреждён или имеет неверный формат',
        directory_not_found: 'Каталог не найден',
        permission_denied: 'Нет доступа к каталогу',
        not_a_directory: 'Указанный путь не является каталогом',
        incomplete_scan: 'Каталог прочитан не полностью',
        partial_collection: 'Часть данных получить не удалось',
        check_timeout: 'Проверка не завершилась за отведённое время',
        cycle_deadline_exceeded: 'Проверка не выполнена в этом цикле',
        no_local_disk_metrics: 'Не удалось получить данные дисков'
    };
    const el = (tag, className, text) => {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = String(text);
        return node;
    };
    const append = (parent, ...children) => {
        children.forEach(child => parent.appendChild(child));
        return parent;
    };
    const date = value => {
        if (!value) return '-';
        const parsed = new Date(value);
        return Number.isNaN(parsed.getTime()) ? '-' :
            parsed.toLocaleString('ru-RU', { timeZone: 'UTC' }) + ' UTC';
    };
    const number = value => typeof value === 'number' && Number.isFinite(value)
        ? numberFormat.format(value) : '-';
    const label = id => names[id] || id || 'Проверка';
    const errorText = value => errorLabels[value] || String(value || 'Не удалось получить данные');
    const notice = (text, error = false) => el('div', error ? 'mon-notice mon-notice--error' : 'mon-notice', text);
    const badge = (text, kind = 'neutral') => el('span', 'mon-pill mon-pill--' + kind, text);

    function state(server) {
        const indicator = server.indicator;
        if (indicator && ['ok', 'bad', 'unknown'].includes(indicator.kind)) {
            return [indicator.kind, indicator.text];
        }
        return ['unknown', 'Нет результатов проверки'];
    }

    function renderServers() {
        body.replaceChildren();
        if (!servers.size) {
            const cell = el('td', 'mon-empty', 'Серверов пока нет. Добавьте сервер и агента в админке.');
            cell.colSpan = 3;
            append(body, append(el('tr'), cell));
            return;
        }
        servers.forEach(server => {
            const [kind, text] = state(server);
            const row = el('tr', 'mon-server');
            row.dataset.id = String(server.id);
            row.tabIndex = 0;
            row.setAttribute('role', 'button');
            row.setAttribute('aria-label', 'Открыть сведения: ' + server.name);
            const details = el('td');
            const identity = el('div', 'mon-server-details');
            const identityText = el('div');
            const subtitle = server.agent
                ? server.agent.agent_id : '-';
            append(identityText, el('strong', '', server.name), el('small', '', subtitle));
            const indicator = el('span', 'mon-dot mon-dot--' + kind);
            indicator.setAttribute('title', text);
            indicator.setAttribute('aria-label', text);
            append(identity, indicator, identityText);
            append(details, identity);
            const checked = el('td', 'mon-date');
            append(checked, el('div', '', date(server.report?.checked_at)));
            append(row, el('td', 'mon-id', '#' + server.id), details, checked);
            body.appendChild(row);
        });
    }

    function field(parent, key, value, pre = false) {
        const row = el('div', 'mon-check-field');
        append(row, el('span', 'mon-check-field-label', key),
            el(pre ? 'pre' : 'span', 'mon-check-field-value', value ?? '-'));
        parent.appendChild(row);
    }

    function detail(key, name, pill, kind = 'unknown') {
        const item = el('details', 'mon-check');
        item.dataset.key = key;
        item.open = expanded.has(key);
        const summary = el('summary', 'mon-check-summary');
        append(summary, el('span', 'mon-dot mon-dot--' + kind),
            el('span', 'mon-check-name', name));
        if (pill) summary.appendChild(pill);
        summary.appendChild(el('span', 'mon-chevron', '⌄'));
        const detailBody = el('div', 'mon-check-detail');
        append(item, summary, detailBody);
        return [item, detailBody];
    }

    function network(checks) {
        const groups = new Map([
            ['platform', ['Площадка', []]],
            ['customer', ['Заказчик', []]],
            ['other', ['Другие подключения', []]]
        ]);
        checks.forEach(check => {
            if (check.error) content.appendChild(notice(label(check.check_id) + ': ' + errorText(check.error), true));
            if (!check.results.length) {
                content.appendChild(notice(check.enabled ? 'Результатов сетевой проверки нет' : 'Сетевая проверка отключена'));
            }
            check.results.forEach(result => {
                const group = groups.has(result.details.group) ? result.details.group : 'other';
                groups.get(group)[1].push([check, result]);
            });
        });
        groups.forEach(([name, rows]) => {
            if (!rows.length) return;
            content.appendChild(el('h4', 'mon-section-title', name));
            const list = el('div', 'mon-network-list');
            rows.forEach(([check, result]) => {
                const enabled = check.enabled && result.enabled !== false;
                const reachable = result.reachable;
                const kind = !enabled ? 'unknown' : result.error || reachable === false ? 'bad' : reachable === true ? 'ok' : 'unknown';
                const text = !enabled ? 'Отключено' : result.error ? 'Ошибка проверки' : reachable === true ? 'Доступен' : reachable === false ? 'Нет соединения' : 'Нет результата';
                const name = result.details.name ||
                    (result.details.check_id ? result.details.check_id : check.name || check.check_id);
                const [item, fields] = detail(
                    check.check_id + ':' + (result.details.check_id || '') + ':' + result.target,
                    name, null, kind
                );
                item.querySelector('.mon-dot').setAttribute('title', text);
                item.querySelector('.mon-dot').setAttribute('aria-label', text);
                field(fields, 'Адрес', result.details.ip || result.details.host || result.target);
                if (result.details.port !== undefined) field(fields, 'Порт', result.details.port);
                field(fields, 'Метод', result.details.method || check.type);
                field(fields, 'Проверено', date(result.details.finished_at || check.finished_at));
                if (result.error) field(fields, 'Ошибка', errorText(result.error));
                if (result.details.output) field(fields, 'Ответ ping', result.details.output, true);
                list.appendChild(item);
            });
            content.appendChild(list);
        });
    }

    function checkSection(check, showTime = true) {
        const section = el('section', 'mon-section');
        section.appendChild(el('h4', 'mon-section-title', label(check.check_id)));
        if (showTime) section.appendChild(el('p', 'mon-muted', 'Проверено: ' + date(check.finished_at)));
        content.appendChild(section);
        if (!check.enabled) {
            section.appendChild(notice('Проверка отключена'));
            return null;
        }
        if (check.error) section.appendChild(notice(errorText(check.error), true));
        if (!check.results.length) section.appendChild(notice(check.type === 'content' ? '-' : 'Измерений в отчёте нет'));
        return section;
    }

    function disks(checks) {
        checks.forEach(check => {
            const section = checkSection(check, false);
            if (!section) return;
            check.results.forEach(result => {
                const row = el('div', 'mon-meter-row');
                append(row, append(el('div', 'mon-meter-head'),
                    el('strong', 'mon-meter-name', result.target),
                    el('strong', '', result.error ? 'Нет данных' : number(result.value) + '%')));
                if (result.error) {
                    row.appendChild(notice(errorText(result.error), true));
                } else {
                    const progress = el('div', 'mon-progress');
                    const fill = el('div', 'mon-progress-fill');
                    const value = typeof result.value === 'number' ? result.value : 0;
                    fill.style.width = Math.min(100, Math.max(0, value)) + '%';
                    if (value >= diskLimit) fill.classList.toggle('mon-progress-fill--bad', true);
                    else if (value >= Math.max(0, diskLimit - 5)) fill.classList.toggle('mon-progress-fill--warning', true);
                    progress.setAttribute('role', 'meter');
                    progress.setAttribute('aria-label', 'Заполненность ' + result.target);
                    progress.setAttribute('aria-valuemin', '0');
                    progress.setAttribute('aria-valuemax', '100');
                    progress.setAttribute('aria-valuenow', String(Math.min(100, Math.max(0, value))));
                    progress.appendChild(fill);
                    row.appendChild(progress);
                }
                section.appendChild(row);
            });
        });
    }

    function reports(checks) {
        checks.forEach(check => {
            const section = checkSection(check);
            if (!section) return;
            const list = el('div', 'mon-count-list');
            check.results.forEach(result => {
                const row = el('div', 'mon-count-row');
                append(row, el('span', 'mon-meter-name', result.target),
                    el('strong', '', result.error ? 'Нет данных' : number(result.value)));
                const card = el('div', 'mon-count-card');
                card.appendChild(row);
                if (result.error) card.appendChild(notice(errorText(result.error), true));
                list.appendChild(card);
            });
            section.appendChild(list);
        });
    }

    function contentChecks(checks) {
        const errorSources = [];
        checks.forEach(check => {
            const section = checkSection(check, false);
            if (!section) return;
            const list = el('div', 'mon-check-list');
            check.results.forEach(result => {
                if (result.enabled === false) return;
                const data = result.details;
                errorSources.push({ check, result, data });
                const [item, fields] = detail(
                    check.check_id + ':' + result.target,
                    data.directory || result.target,
                    badge(result.error ? 'Ошибка чтения' : result.value == null ? '-' : 'Новых: ' + number(result.value),
                        result.error ? 'bad' : 'neutral'),
                    result.error || (data.err_total_count ?? data.err_count) > 0 ? 'bad' : 'ok'
                );
                if (result.error) field(fields, 'Ошибка', errorText(result.error));
                field(fields, 'Новых файлов', result.error ? 'Нет полных данных' : number(result.value));
                field(fields, 'Последний файл',
                    ('last_normal_file' in data ? data.last_normal_file : data.last_file) || '-');
                field(fields, 'Время изменения последнего файла',
                    date('last_normal_time' in data ? data.last_normal_time : data.last_time));
                list.appendChild(item);
            });
            section.appendChild(list);
        });
        if (!checks.some(check => check.enabled)) return;
        const errors = el('section', 'mon-section mon-content-errors');
        errors.appendChild(el('h4', 'mon-section-title', 'Наличие .err файлов'));
        let total = 0;
        let incomplete = errorSources.length === 0;
        let legacy = false;
        errorSources.forEach(({ check, result, data }) => {
            const fullCount = data.err_total_count;
            const hasFullCount = typeof fullCount === 'number' && Number.isFinite(fullCount) && fullCount >= 0;
            const count = hasFullCount ? fullCount : data.err_count;
            if (!hasFullCount) legacy = true;
            if (typeof count === 'number' && Number.isFinite(count) && count >= 0) total += count;
            else incomplete = true;
            if (check.error || result.error) incomplete = true;
        });
        field(errors, 'Общее количество ошибок',
            incomplete || legacy ? total > 0 ? 'Не менее ' + number(total) : '-' : number(total));
        if (legacy) errors.appendChild(notice('Часть данных содержит только ошибки за период проверки.'));
        if (incomplete) errors.appendChild(notice('Не все каталоги удалось проверить полностью.', true));
        errorSources.forEach(({ check, result, data }) => {
            const files = Array.isArray(data.err_latest_files)
                ? data.err_latest_files : Array.isArray(data.err_files) ? data.err_files : [];
            if (!files.length) return;
            const group = el('div', 'mon-error-stream');
            const name = check.name && check.name !== check.check_id ? check.name : label(check.check_id);
            group.appendChild(el('h5', 'mon-error-stream-title',
                name + (result.target !== 'DIR' ? ' · ' + result.target : '')));
            if (data.directory) group.appendChild(el('div', 'mon-muted', data.directory));
            files.slice(0, 5).forEach(file => {
                const path = typeof file === 'string' ? file : file?.path;
                if (!path) return;
                const line = el('div', 'mon-error-file', path);
                if (typeof file === 'object' && file.modified_at) {
                    line.appendChild(el('small', 'mon-muted', date(file.modified_at)));
                }
                group.appendChild(line);
            });
            errors.appendChild(group);
        });
        content.appendChild(errors);
    }

    function renderModal() {
        const server = servers.get(selectedId);
        if (!server) {
            content.replaceChildren(notice('Сервер больше не найден'));
            return;
        }
        expanded = new Set([...content.querySelectorAll('details[open]')].map(item => item.dataset.key));
        title.textContent = server.name;
        ip.textContent = server.ip_address + (server.agent ? ' · ' + server.agent.site_id : '');
        content.replaceChildren();
        tabs.forEach(tab => {
            const active = tab.dataset.tab === selectedTab;
            tab.classList.toggle('active', active);
            tab.setAttribute('aria-selected', String(active));
            tab.tabIndex = active ? 0 : -1;
        });
        content.setAttribute('aria-labelledby', 'monTab-' + selectedTab);
        if (!server.report) {
            content.appendChild(notice(server.agent ? 'Агент ещё не передал отчёты' : 'Агент для этого сервера не настроен'));
            return;
        }
        if (server.report.error) {
            content.appendChild(notice(errorText(server.report.error), true));
            return;
        }
        const types = {
            network: ['network', 'ping', 'telnet'],
            disks: ['memory'],
            reports: ['report'],
            content: ['content']
        };
        const checks = server.report.checks.filter(check => types[selectedTab].includes(check.type));
        if (!checks.length) {
            content.appendChild(notice(selectedTab === 'content' ? '-' : 'Эта проверка не настроена в последнем отчёте'));
            return;
        }
        ({ network, disks, reports, content: contentChecks })[selectedTab](checks);
    }

    function open(id, source) {
        if (!servers.has(id)) return;
        previousFocus = source;
        selectedId = id;
        selectedTab = 'network';
        expanded = new Set();
        content.replaceChildren();
        renderModal();
        previousOverflow = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
        overlay.hidden = false;
        document.getElementById('monClose').focus();
    }

    function close() {
        overlay.hidden = true;
        document.body.style.overflow = previousOverflow;
        if (previousFocus?.isConnected) previousFocus.focus();
        else [...body.querySelectorAll('.mon-server')].find(row => row.dataset.id === selectedId)?.focus();
        selectedId = null;
    }

    function applyDashboard(data) {
        if (!Array.isArray(data.servers)) throw new Error('Сайт вернул неверный формат данных.');
        diskLimit = typeof data.disk_limit === 'number' &&
            Number.isFinite(data.disk_limit) && data.disk_limit > 0 && data.disk_limit <= 100
            ? data.disk_limit : 90;
        servers = new Map(data.servers.map(server => [String(server.id), server]));
        renderServers();
        if (selectedId !== null) renderModal();
    }

    async function refresh() {
        if (busy) return;
        busy = true;
        refreshButton.disabled = true;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 15000);
        try {
            const response = await fetch(root.dataset.url, {
                credentials: 'same-origin', cache: 'no-store',
                headers: { Accept: 'application/json' }, signal: controller.signal
            });
            if (response.status === 401) throw new Error('Сессия завершена. Войдите на сайт повторно.');
            if (!response.ok) throw new Error('Не удалось получить данные мониторинга.');
            const data = await response.json();
            applyDashboard(data);
            banner.hidden = true;
        } catch (error) {
            banner.textContent = error.name === 'AbortError'
                ? 'Сайт не ответил вовремя. Ранее полученные данные могут быть неактуальны.'
                : error.message + (servers.size ? ' Показаны ранее полученные данные.' : '');
            banner.hidden = false;
        } finally {
            clearTimeout(timeout);
            busy = false;
            refreshButton.disabled = false;
        }
    }

    body.addEventListener('click', event => {
        const row = event.target.closest('.mon-server');
        if (row) open(row.dataset.id, row);
    });
    body.addEventListener('keydown', event => {
        const row = event.target.closest('.mon-server');
        if (row && (event.key === 'Enter' || event.key === ' ')) {
            event.preventDefault();
            open(row.dataset.id, row);
        }
    });
    document.getElementById('monClose').addEventListener('click', close);
    overlay.addEventListener('click', event => { if (event.target === overlay) close(); });
    document.addEventListener('keydown', event => {
        if (overlay.hidden) return;
        if (event.key === 'Escape') close();
        if (event.key === 'Tab') {
            const focusable = [...modal.querySelectorAll('button, summary')].filter(node => node.offsetParent !== null);
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last?.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first?.focus();
            }
        }
    });
    tabs.forEach((tab, index) => {
        tab.addEventListener('click', () => {
            selectedTab = tab.dataset.tab;
            renderModal();
        });
        tab.addEventListener('keydown', event => {
            let next;
            if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
            if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
            if (event.key === 'Home') next = 0;
            if (event.key === 'End') next = tabs.length - 1;
            if (next !== undefined) {
                event.preventDefault();
                tabs[next].click();
                tabs[next].focus();
            }
        });
    });
    refreshButton.addEventListener('click', refresh);
    setInterval(() => { if (!document.hidden) refresh(); }, 60000);
    const initial = document.getElementById('monInitialData');
    if (initial) {
        try {
            applyDashboard(JSON.parse(initial.textContent));
        } catch {
            refresh();
        }
    } else {
        refresh();
    }
})();
