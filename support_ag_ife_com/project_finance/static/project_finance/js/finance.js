/*
 * project_finance/js/finance.js
 *
 * Всплывающие окна раздела «Финансы проектов»: открытие/закрытие <dialog>,
 * заполнение форм задачи и прайса при редактировании, пересчёт суммы задачи,
 * подтверждение удаления. Сами данные сохраняются обычными POST-формами.
 */
(function () {
    'use strict';

    const dataEl = document.getElementById('pfData');
    const DATA   = dataEl ? JSON.parse(dataEl.textContent) : { price: {}, tasks: {} };

    const fmt = n => new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 })
        .format(Math.round((Number(n) || 0) * 100) / 100) + ' ₽';

    // ── Окна ──
    function openDialog(id) {
        const dlg = document.getElementById(id);
        if (!dlg) return null;
        if (!dlg.open) dlg.showModal();
        const first = dlg.querySelector('input:not([type=hidden]):not([disabled]), select, textarea');
        if (first) setTimeout(() => first.focus(), 30);
        return dlg;
    }

    document.addEventListener('click', e => {
        const opener = e.target.closest('[data-open]');
        if (opener) { openDialog(opener.dataset.open); return; }
        const closer = e.target.closest('[data-close]');
        if (closer) { closer.closest('dialog').close(); }
    });

    // Клик по затемнению вокруг окна закрывает его
    document.querySelectorAll('dialog.pf-dialog').forEach(dlg => {
        dlg.addEventListener('mousedown', e => { if (e.target === dlg) dlg.close(); });
    });

    // После сохранения позиции прайса страница открывается с ?open=price
    const toOpen = new URLSearchParams(location.search).get('open');
    if (toOpen === 'price') {
        openDialog('dlgPrice');
        history.replaceState(null, '', location.pathname);
    }

    // ── Подтверждение удаления ──
    const confirmDlg = document.getElementById('dlgConfirm');
    let pendingSubmit = null;
    document.addEventListener('click', e => {
        const btn = e.target.closest('button[type=submit][data-confirm]');
        if (!btn || !confirmDlg) return;
        e.preventDefault();
        pendingSubmit = btn;
        document.getElementById('confirmText').textContent = btn.dataset.confirm;
        confirmDlg.showModal();
    });
    if (confirmDlg) {
        document.getElementById('confirmOk').addEventListener('click', () => {
            confirmDlg.close();
            if (!pendingSubmit) return;
            const btn = pendingSubmit;
            pendingSubmit = null;
            btn.form.requestSubmit(btn);   // учитывает formaction кнопки
        });
    }

    // ── Прайс-лист ──
    const priceForm = document.getElementById('priceForm');
    if (priceForm) {
        const neg   = priceForm.elements.is_negotiable;
        const price = priceForm.elements.price;
        const syncNeg = () => { price.disabled = neg.checked; if (neg.checked) price.value = ''; };
        neg.addEventListener('change', syncNeg);

        const setEdit = (id, name) => {
            const item = id ? DATA.price[id] : null;
            priceForm.elements.item_id.value = id || '';
            priceForm.elements.name.value    = name || '';
            neg.checked  = !!(item && item.negotiable);
            price.value  = item && !item.negotiable ? item.price : '';
            syncNeg();
            document.getElementById('priceFormLabel').textContent = id ? 'Изменить позицию' : 'Новая позиция';
            document.getElementById('priceSubmit').textContent    = id ? 'Сохранить позицию' : 'Добавить позицию';
            document.getElementById('priceEditHint').hidden   = !id;
            document.getElementById('priceCancelEdit').hidden = !id;
            priceForm.elements.name.focus();
        };
        document.querySelectorAll('[data-price-edit]').forEach(b =>
            b.addEventListener('click', () => setEdit(b.dataset.priceEdit, b.dataset.name)));
        document.getElementById('priceCancelEdit').addEventListener('click', () => setEdit(null, ''));

        priceForm.addEventListener('submit', e => {
            if (!neg.checked && price.value === '') {
                e.preventDefault();
                price.setCustomValidity('Укажите цену или отметьте «По договорённости».');
                price.reportValidity();
            }
        });
        price.addEventListener('input', () => price.setCustomValidity(''));

        // Удаление используемой позиции — показать выбор замены
        document.querySelectorAll('[data-price-replace]').forEach(b => b.addEventListener('click', () => {
            const box = document.getElementById('replace-' + b.dataset.priceReplace);
            if (box) box.hidden = !box.hidden;
        }));
    }

    // ── Задача ──
    const taskForm = document.getElementById('taskForm');
    if (taskForm) {
        const f = taskForm.elements;
        const legacyOpt = f.price_item.querySelector('[data-legacy]');

        const recalc = () => {
            const sum = f.is_free.checked ? 0 : (Number(f.price.value) || 0) * (Number(f.quantity.value) || 1);
            document.getElementById('taskSum').textContent = fmt(sum);
            const item = DATA.price[f.price_item.value];
            document.getElementById('taskHint').textContent =
                item && item.negotiable ? 'Услуга по договорённости: впишите согласованную цену.' : '';
        };
        const applyService = () => {
            const item = DATA.price[f.price_item.value];
            if (item) f.price.value = item.negotiable ? '' : item.price;
            recalc();
        };
        f.price_item.addEventListener('change', applyService);
        ['price', 'quantity', 'is_free'].forEach(n => f[n].addEventListener('input', recalc));
        f.is_free.addEventListener('change', recalc);

        const fill = (id) => {
            const t = id ? DATA.tasks[id] : null;
            taskForm.reset();
            f.task_id.value = id || '';
            document.getElementById('taskErr').hidden = true;
            document.getElementById('taskFormTitle').textContent = t ? `Задача №${t.number}` : 'Новая задача';
            document.getElementById('taskSubmit').textContent    = t ? 'Сохранить' : 'Добавить задачу';
            // Услуга удалена из прайса — показываем сохранённое название
            legacyOpt.hidden = !(t && !t.price_item);
            legacyOpt.textContent = (t && t.service_name) || 'Без услуги';
            if (!t) { applyService(); return; }
            f.price_item.value  = t.price_item;
            f.title.value       = t.title;
            f.description.value = t.description;
            f.price.value       = t.price;
            f.quantity.value    = t.quantity;
            f.time_spent.value  = t.time_spent;
            f.date.value        = t.date;
            f.is_free.checked   = t.is_free;
            f.is_paid.checked   = t.is_paid;
            recalc();
        };

        document.querySelectorAll('[data-task-new]').forEach(b => b.addEventListener('click', () => {
            fill(null); openDialog('dlgTask');
        }));
        document.querySelectorAll('[data-task-edit]').forEach(b => b.addEventListener('click', () => {
            fill(b.dataset.taskEdit); openDialog('dlgTask');
        }));

        taskForm.addEventListener('submit', e => {
            if (f.price.value === '' && !f.is_free.checked) {
                e.preventDefault();
                const err = document.getElementById('taskErr');
                err.textContent = 'Укажите цену. Для бесплатной задачи отметьте «Не включать в стоимость».';
                err.hidden = false;
            }
        });
    }
})();
