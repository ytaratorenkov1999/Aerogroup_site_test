const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
process.env.TZ = 'America/New_York';
const ids = new Map();
let document;

class Element {
    constructor(tag = 'div', id = '') {
        this.tagName = tag.toUpperCase();
        this.id = id;
        this.children = [];
        this.parentNode = null;
        this.dataset = {};
        this.style = {};
        this.hidden = false;
        this.open = false;
        this.attributes = {};
        this.handlers = {};
        this._text = '';
        this.className = '';
        this.classList = { toggle: (name, enabled) => {
            const classes = new Set(this.className.split(' ').filter(Boolean));
            enabled ? classes.add(name) : classes.delete(name);
            this.className = [...classes].join(' ');
        }};
        if (id) ids.set(id, this);
    }
    set textContent(value) { this.replaceChildren(); this._text = String(value); }
    get textContent() { return this._text + this.children.map(c => c.textContent).join(' '); }
    set innerHTML(value) { throw new Error('Unsafe innerHTML used'); }
    appendChild(child) { child.parentNode = this; this.children.push(child); return child; }
    replaceChildren(...children) {
        this.children.forEach(child => child.parentNode = null);
        this.children = [];
        this._text = '';
        children.forEach(child => this.appendChild(child));
    }
    setAttribute(name, value) { this.attributes[name] = String(value); }
    addEventListener(name, handler) { (this.handlers[name] ||= []).push(handler); }
    fire(name, extra = {}) {
        const event = { target: this, key: '', preventDefault() {}, ...extra };
        (this.handlers[name] || []).forEach(handler => handler(event));
    }
    click() { this.fire('click'); }
    focus() { document.activeElement = this; }
    matches(selector) {
        if (selector === 'details[open]') return this.tagName === 'DETAILS' && this.open;
        if (selector[0] === '.') return this.className.split(' ').includes(selector.slice(1));
        return this.tagName.toLowerCase() === selector;
    }
    querySelectorAll(selector) {
        const matches = [];
        const selectors = selector.split(',').map(s => s.trim());
        const walk = node => node.children.forEach(child => {
            if (selectors.some(s => child.matches(s))) matches.push(child);
            walk(child);
        });
        walk(this);
        return matches;
    }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
    closest(selector) {
        let node = this;
        while (node) { if (node.matches(selector)) return node; node = node.parentNode; }
        return null;
    }
    get isConnected() {
        let node = this;
        while (node) { if (node === document.body) return true; node = node.parentNode; }
        return false;
    }
    get offsetParent() { return this.isConnected ? document.body : null; }
}
document = {
    body: new Element('body'), hidden: false, activeElement: null,
    createElement: tag => new Element(tag),
    getElementById: id => ids.get(id),
    querySelectorAll: selector => document.body.querySelectorAll(selector),
    addEventListener() {}
};
function make(tag, id, parent, cls = '') {
    const node = new Element(tag, id);
    node.className = cls;
    parent.appendChild(node);
    return node;
}
const rootNode = make('div', 'monRoot', document.body);
rootNode.dataset.url = '/monitoring/data/';
make('tbody', 'monServers', rootNode);
make('button', 'monRefresh', rootNode);

const banner = make('div', 'monBanner', rootNode);
banner.hidden = true;
const overlay = make('div', 'monOverlay', rootNode);
overlay.hidden = true;
const modal = make('section', 'modal', overlay, 'mon-modal');
make('h3', 'monModalTitle', modal);
make('div', 'monModalIp', modal);

make('button', 'monClose', modal);
for (const tab of ['network','disks','reports','content']) {
    const node = make('button', 'monTab-' + tab, modal, 'mon-tab');
    node.dataset.tab = tab;
}
make('div', 'monTabContent', modal);
const now = '2026-11-18T15:00:00Z';
const base = { enabled: true, error: null, finished_at: now, duration_ms: 1 };
const data = {
    generated_at: now,
    servers: [{
        id: 1, name: 'Synthetic <img src=x onerror=alert(1)>', ip_address: '192.0.2.1',
        agent: { site_id: 'test', agent_id: 'synthetic', enabled: true },
        report: {
            checked_at: now, received_at: now, error: null,
            checks: [
                { ...base, check_id: 'NETWORK', type: 'network', results: [
                    { target: '192.0.2.1:443', enabled: true, reachable: false, error: 'refused',
                      details: { check_id: 'NETWORK_PLATFORM', name: 'Имя потока из JSON <script>test</script>', group: 'platform', method: 'telnet', port: 443 } },
                    { target: '192.0.2.2:443', enabled: true, reachable: true, error: null,
                      details: { check_id: 'NETWORK_NEW_STREAM', group: 'customer', method: 'telnet' } }
                ]},
                { ...base, check_id: 'DISK', type: 'memory', results: [
                    { target: '/', value: 42, error: null, details: { used_gb: 4.2, avail_gb: 5.8, size_gb: 10 } }
                ]},
                { ...base, check_id: 'REPORT', type: 'report', results: [
                    { target: '/reports', value: 17, error: null, details: {} }
                ]},
                { ...base, check_id: 'DATA_FILES', type: 'content', results: [
                    { target: 'DIR', value: 2, error: null, details: {
                        directory: '/content', last_file: '<script>synthetic</script>',
                        last_time: now, err_count: 1, err_files: ['sample.err']
                    }}
                ]}
            ]
        }
    }]
};
let fail = false;
let calls = 0;
vm.runInNewContext(fs.readFileSync(path.join(
    __dirname, 'support_ag_ife_com/monitoring/static/monitoring/js/monitoring.js'
), 'utf8'), {
    document, Intl, Date, Map, Set, Array, Number, String, AbortController,
    setInterval() { return 1; },
    setTimeout() { return 1; },
    clearTimeout() {},
    fetch: async (url, options) => {
        assert.equal(url, '/monitoring/data/');
        assert.equal(options.credentials, 'same-origin');
        calls++;
        return { ok: !fail, status: fail ? 500 : 200, json: async () => data };
    }
});
async function settle() { await new Promise(resolve => setImmediate(resolve)); }

(async () => {
    await settle();
    assert.equal(calls, 1);
    const body = ids.get('monServers');
    assert.equal(body.children.length, 1);
    assert.doesNotMatch(body.textContent, /Есть недоступные|Данные получены|192\.0\.2/);
    assert.match(body.textContent, /18\.11\.2026, 15:00:00 UTC/);
    assert.equal(body.querySelectorAll('.mon-row-status').length, 0);
    assert.equal(body.querySelectorAll('.mon-dot--bad').length, 1);
    const row = body.children[0];
    body.fire('click', { target: row });
    assert.equal(overlay.hidden, false);
    const content = ids.get('monTabContent');
    assert.match(content.textContent, /Площадка/);
    assert.match(content.textContent, /Заказчик/);
    assert.equal(content.querySelectorAll('.mon-pill').length, 0);
    assert.match(content.textContent, /Имя потока из JSON <script>test<\/script>/);
    assert.match(content.textContent, /NETWORK_NEW_STREAM/);
    assert.equal(content.querySelectorAll('.mon-network-list').length, 2);
    content.querySelectorAll('summary').forEach(summary => {
        assert.doesNotMatch(summary.textContent, /192\.0\.2|443|Доступен|Нет соединения/);
    });
    assert.match(content.textContent, /192\.0\.2/);
    ids.get('monTab-disks').click();
    assert.match(content.textContent, /42%/);
    assert.doesNotMatch(content.textContent, /Проверено|Использовано|Свободно|Всего/);
    assert.equal(content.querySelectorAll('.mon-progress-fill--warning').length, 0);
    data.disk_limit = 90;
    data.servers[0].report.checks[1].results[0].value = 85;
    ids.get('monRefresh').click();
    await settle();
    assert.equal(content.querySelectorAll('.mon-progress-fill--warning').length, 1);
    data.servers[0].report.checks[1].results[0].value = 90;
    ids.get('monRefresh').click();
    await settle();
    assert.equal(content.querySelectorAll('.mon-progress-fill--bad').length, 1);
    data.disk_limit = 75;
    data.servers[0].report.checks[1].results[0].value = 75;
    ids.get('monRefresh').click();
    await settle();
    assert.equal(content.querySelectorAll('.mon-progress-fill--bad').length, 1);
    ids.get('monTab-reports').click();
    assert.match(content.textContent, /17/);
    ids.get('monTab-content').click();
    assert.match(content.textContent, /sample.err/);
    assert.doesNotMatch(content.textContent, /Проверено:/);
    assert.match(content.textContent, /<script>synthetic<\/script>/);
    ids.get('monClose').click();
    assert.equal(overlay.hidden, true);
    assert.equal(document.activeElement, body.children[0]);

    fail = true;
    ids.get('monRefresh').click();
    await settle();
    assert.equal(banner.hidden, false);
    assert.match(banner.textContent, /ранее полученные данные/);
    assert.equal(body.children.length, 1);
    fail = false;
    data.servers[0].report.error = 'file_missing';
    ids.get('monRefresh').click();
    await settle();
    assert.equal(banner.hidden, true);
    body.fire('click', { target: body.children[0] });
    assert.match(content.textContent, /отсутствует в хранилище/);
    const result = data.servers[0].report.checks[3].results[0];
    result.value = null;
    result.details = { directory: '/empty' };
    data.servers[0].report.error = null;
    ids.get('monRefresh').click();
    await settle();
    ids.get('monTab-content').click();
    assert.doesNotMatch(content.textContent, /Нет данных|Файлов нет|Проверено/);
    assert.match(content.textContent, /-/);
    console.log('UI DOM checks passed: four tabs, modal, network groups, text escaping, fetch errors, missing file.');
})().catch(error => { console.error(error); process.exitCode = 1; });
