/*
 * monitoring/js/monitoring.js — отрисовка страницы «Мониторинг узлов».
 *
 * Данные об узлах берутся из глобального массива window.MONITORING_MACHINES,
 * который объявляется в шаблоне monitoring/monitoring.html.
 */
(function () {
  'use strict';

  const machines = window.MONITORING_MACHINES || [];

  const grid      = document.getElementById('monGrid');
  const statsEl   = document.getElementById('monStats');
  const tsEl      = document.getElementById('monTs');
  const overlay   = document.getElementById('monOverlay');
  const modal     = document.getElementById('monModal');
  const refreshEl = document.getElementById('monRefresh');

  if (!grid) return;

  const STREAM_LABELS = [
    ['passengers', 'Пассажиры'],
    ['catering',   'Кейтеринг'],
    ['skyshop',    'Скайшоп'],
    ['schedule',   'Расписание'],
    ['crew',       'Экипаж'],
    ['mail',       'Почта АК'],
  ];

  const CONT_STATUS = {
    running:    'ok',
    exited:     'bad',
    restarting: 'warn',
  };

  // Экранирование строк перед вставкой в HTML
  function esc(value) {
    return String(value).replace(/[&<>"']/g, ch => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[ch]));
  }

  function diskPercent(m) {
    return m.disk.total ? Math.round(m.disk.used / m.disk.total * 100) : 0;
  }

  function diskLevel(pct) {
    return pct >= 90 ? 'bad' : pct >= 70 ? 'warn' : 'ok';
  }

  // Сводное состояние узла: off — нет связи, warn — есть проблемы, ok — всё в порядке
  function machineState(m) {
    if (!m.online) return 'off';
    const streamsDown = Object.values(m.streams).some(v => !v);
    const contsDown   = m.containers.some(c => c.status !== 'running');
    return (streamsDown || contsDown || diskPercent(m) >= 90) ? 'warn' : 'ok';
  }

  const STATE_BADGE = {
    ok:   '<span class="mon-badge mon-badge--ok">Онлайн</span>',
    warn: '<span class="mon-badge mon-badge--warn">Есть проблемы</span>',
    off:  '<span class="mon-badge mon-badge--bad">Офлайн</span>',
  };

  /* ── Сводка над карточками ─────────────────────────────────────────── */
  function renderStats() {
    const states = machines.map(machineState);
    const count  = s => states.filter(x => x === s).length;
    statsEl.innerHTML = `
      <span class="mon-stat">Всего: <b>${machines.length}</b></span>
      <span class="mon-stat"><span class="mon-dot mon-dot--ok"></span>Онлайн: <b>${count('ok')}</b></span>
      <span class="mon-stat"><span class="mon-dot mon-dot--warn"></span>С проблемами: <b>${count('warn')}</b></span>
      <span class="mon-stat"><span class="mon-dot mon-dot--bad"></span>Офлайн: <b>${count('off')}</b></span>
    `;
  }

  /* ── Карточки узлов ────────────────────────────────────────────────── */
  function renderCards() {
    grid.innerHTML = machines.map((m, i) => {
      const state   = machineState(m);
      const pct     = diskPercent(m);
      const running = m.containers.filter(c => c.status === 'running').length;
      return `
        <button type="button" class="mon-card mon-card--${state}" data-i="${i}">
          <div class="mon-card__head">
            <div>
              <div class="mon-card__ip">${esc(m.ip)}</div>
              <div class="mon-card__name">${esc(m.name)}</div>
            </div>
            ${STATE_BADGE[state]}
          </div>
          <div class="mon-card__meta">
            <div class="mon-card__row">
              <span>Диск</span><b>${pct}%</b>
            </div>
            <div class="mon-bar mon-bar--${diskLevel(pct)}"><i style="width:${pct}%"></i></div>
            <div class="mon-card__row">
              <span>Контейнеры</span><b>${running} / ${m.containers.length}</b>
            </div>
          </div>
        </button>
      `;
    }).join('');
  }

  function renderTimestamp() {
    tsEl.textContent = new Date().toLocaleTimeString('ru-RU');
  }

  /* ── Окно с подробностями узла ─────────────────────────────────────── */
  function openModal(m) {
    const maxRep = Math.max(1, ...m.reports.map(r => r.count));
    const pct    = diskPercent(m);

    const streamsHtml = STREAM_LABELS.map(([key, label]) => `
      <div class="mon-chip">
        <span class="mon-dot mon-dot--${m.streams[key] ? 'ok' : 'bad'}"></span>${label}
      </div>
    `).join('');

    const reportsHtml = m.reports.map(r => `
      <div class="mon-rep">
        <span class="mon-rep__lbl">${esc(r.name)}</span>
        <span class="mon-bar"><i style="width:${Math.round(r.count / maxRep * 100)}%"></i></span>
        <span class="mon-rep__cnt${r.count ? '' : ' mon-rep__cnt--zero'}">${r.count}</span>
      </div>
    `).join('');

    const contHtml = m.containers.map(c => `
      <div class="mon-cont">
        <span class="mon-cont__name">${esc(c.name)}</span>
        <span class="mon-badge mon-badge--${CONT_STATUS[c.status] || 'warn'}">${esc(c.status)}</span>
      </div>
    `).join('');

    modal.innerHTML = `
      <div class="mon-modal__head">
        <div>
          <div class="mon-modal__ip" id="monModalTitle">${esc(m.ip)}</div>
          <div class="mon-modal__name">${esc(m.name)}</div>
        </div>
        <div class="mon-modal__right">
          <span class="mon-badge mon-badge--${m.online ? 'ok' : 'bad'}">
            ${m.online ? 'Связанность: OK' : 'Связанность: нет'}
          </span>
          <button type="button" class="mon-close" id="monClose" aria-label="Закрыть">
            <i class="ti ti-x"></i>
          </button>
        </div>
      </div>

      <div class="mon-modal__body">
        <div class="mon-section">
          <h4>Сетевая связанность потоков</h4>
          <div class="mon-chips">${streamsHtml}</div>
        </div>

        <div class="mon-section">
          <h4>Отчёты в ИШП</h4>
          ${reportsHtml}
        </div>

        <div class="mon-section mon-disk">
          <h4>Место на машине</h4>
          <div class="mon-disk__top">
            <span>${m.disk.used} ГБ / ${m.disk.total} ГБ</span>
            <span>${pct}% занято</span>
          </div>
          <div class="mon-bar mon-bar--${diskLevel(pct)}"><i style="width:${pct}%"></i></div>
        </div>

        <div class="mon-section">
          <h4>Статус контейнеров</h4>
          ${contHtml}
        </div>
      </div>
    `;

    overlay.classList.add('open');
    overlay.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    document.getElementById('monClose').addEventListener('click', closeModal);
    document.getElementById('monClose').focus();
  }

  function closeModal() {
    overlay.classList.remove('open');
    overlay.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }

  /* ── События ───────────────────────────────────────────────────────── */
  grid.addEventListener('click', e => {
    const card = e.target.closest('.mon-card');
    if (card) openModal(machines[+card.dataset.i]);
  });

  overlay.addEventListener('click', e => {
    if (e.target === overlay) closeModal();
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && overlay.classList.contains('open')) closeModal();
  });

  function renderAll() {
    renderStats();
    renderCards();
    renderTimestamp();
  }

  refreshEl.addEventListener('click', renderAll);

  renderAll();
})();
