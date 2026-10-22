let currentDate = new Date();

// Экранирование данных с сервера перед вставкой в innerHTML (защита от XSS)
function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, ch => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[ch]);
}
let employees = [];
let scheduleData = {};

const STATUS_CYCLE = {
    '':                'working',
    'working':         'working_holiday',
    'working_holiday': 'vacation',
    'vacation':        ''
};

const STATUS_DISPLAY = {
    working:         'ЯП',
    working_holiday: 'РВ',
    vacation:        'В',
    '':              ''
};

const STATUS_CLASSES = {
    working:         'working',
    working_holiday: 'working-holiday',
    vacation:        'vacation',
    '':              ''
};

const dayNames = ['Вс','Пн','Вт','Ср','Чт','Пт','Сб'];

document.addEventListener('DOMContentLoaded', function() {
    loadScheduleData();
    setupEventListeners();
});

function loadScheduleData() {
    const year  = currentDate.getFullYear();
    const month = currentDate.getMonth() + 1;

    fetch(`/daily/get-data/?year=${year}&month=${month}`)
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                employees     = data.employees;
                scheduleData  = data.schedule;
            } else {
                console.error('Ошибка загрузки:', data.error);
            }
            renderTable();
        })
        .catch(err => {
            console.error('Ошибка:', err);
            renderTable();
        });
}

function renderTable() {
    const year        = currentDate.getFullYear();
    const month       = currentDate.getMonth();
    const daysInMonth = new Date(year, month + 1, 0).getDate();

    const monthName = currentDate.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' });
    document.getElementById('current-period').textContent =
        monthName.charAt(0).toUpperCase() + monthName.slice(1);

    // Шапка
    const head = document.getElementById('scheduleHead');
    let row1 = '<tr><th class="number-column" rowspan="2">№</th><th class="fio-column" rowspan="2">ФИО сотрудника</th>';
    let row2 = '<tr>';

    for (let d = 1; d <= daysInMonth; d++) {
        const dow  = new Date(year, month, d).getDay();
        const isWE = dow === 0 || dow === 6;
        row1 += `<th${isWE ? ' style="color:#ef9a9a"' : ''}>${d}</th>`;
        row2 += `<th class="day-header"${isWE ? ' style="color:#ef9a9a"' : ''}>${dayNames[dow]}</th>`;
    }
    head.innerHTML = row1 + '</tr>' + row2 + '</tr>';

    // Тело
    const body = document.getElementById('scheduleBody');
    let html = '';

    employees.forEach((emp, index) => {
        html += `<tr class="employee-row">
            <td class="number-column">${index + 1}</td>
            <td class="fio-column">${escapeHtml(emp.name)}</td>`;

        for (let d = 1; d <= daysInMonth; d++) {
            const date    = new Date(year, month, d);
            const dateKey = formatDate(date);
            const dow     = date.getDay();
            const isWE    = dow === 0 || dow === 6;
            const empSch  = scheduleData[emp.id] || {};
            const status  = empSch[dateKey] || '';
            const statusClass = status ? STATUS_CLASSES[status] : (isWE ? 'weekend' : '');

            html += `<td class="day-cell ${statusClass}"
                         data-employee-id="${escapeHtml(emp.id)}"
                         data-date="${dateKey}"
                         data-status="${status}"
                         data-is-weekend="${isWE}">
                ${STATUS_DISPLAY[status] || ''}
            </td>`;
        }
        html += '</tr>';
    });

    body.innerHTML = html;

    document.querySelectorAll('.day-cell').forEach(cell => {
        cell.addEventListener('click', toggleDayStatus);
    });
}

function toggleDayStatus() {
    const employeeId = parseInt(this.dataset.employeeId);
    const date       = this.dataset.date;
    const curStatus  = this.dataset.status || '';
    const isWeekend  = this.dataset.isWeekend === 'true';
    const newStatus  = STATUS_CYCLE[curStatus];

    fetch('/daily/save-entry/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            employee_id: employeeId,
            date:        date,
            status:      newStatus || ''
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            if (!scheduleData[employeeId]) scheduleData[employeeId] = {};
            if (newStatus) {
                scheduleData[employeeId][date] = newStatus;
            } else {
                delete scheduleData[employeeId][date];
            }
            updateCellDisplay(this, newStatus, isWeekend);
            this.dataset.status = newStatus || '';
        } else {
            console.error('Ошибка сохранения:', data.error);
        }
    })
    .catch(err => console.error('Ошибка:', err));
}

function updateCellDisplay(cell, newStatus, isWeekend) {
    cell.classList.remove('working', 'working-holiday', 'vacation', 'weekend');
    cell.textContent = STATUS_DISPLAY[newStatus] || '';
    if (newStatus) {
        cell.classList.add(STATUS_CLASSES[newStatus]);
    } else if (isWeekend) {
        cell.classList.add('weekend');
    }
}

function formatDate(date) {
    return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
}

function setupEventListeners() {
    document.getElementById('prev-period').addEventListener('click', () => {
        currentDate.setMonth(currentDate.getMonth() - 1);
        loadScheduleData();
    });
    document.getElementById('next-period').addEventListener('click', () => {
        currentDate.setMonth(currentDate.getMonth() + 1);
        loadScheduleData();
    });

    // Кнопка открывает диалог выбора файла
    document.getElementById('upload-schedule').addEventListener('click', () => {
        document.getElementById('xlsx-input').value = '';
        document.getElementById('xlsx-input').click();
    });

    // После выбора файла — сразу отправляем
    document.getElementById('xlsx-input').addEventListener('change', function() {
        const file = this.files[0];
        if (!file) return;

        const btn = document.getElementById('upload-schedule');
        btn.textContent = 'Загружаем...';
        btn.disabled = true;

        const formData = new FormData();
        formData.append('file', file);

        fetch('/daily/import/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCookie('csrftoken') },
            body: formData,
        })
        .then(r => r.json())
        .then(data => {
            btn.textContent = 'Загрузить график';
            btn.disabled = false;

            if (data.success) {
                let msg = `✓ Импортировано: ${data.imported} записей (${data.period})`;
                if (data.skipped_names && data.skipped_names.length) {
                    msg += `\nНе найдены: ${data.skipped_names.join(', ')}`;
                }
                if (data.skipped_codes && data.skipped_codes.length) {
                    msg += `\nНеизвестные коды: ${data.skipped_codes.join(', ')}`;
                }
                const type = (data.skipped_names?.length || data.skipped_codes?.length) ? 'warning' : 'success';
                showToast(msg, type);
                loadScheduleData();
            } else {
                showToast('✗ Ошибка: ' + data.error, 'error');
            }
        })
        .catch(err => {
            btn.textContent = 'Загрузить график';
            btn.disabled = false;
            showToast('✗ Ошибка соединения', 'error');
            console.error(err);
        });
    });
}

function showToast(message, type = 'success') {
    const existing = document.querySelector('.import-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = `import-toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    requestAnimationFrame(() => toast.classList.add('show'));
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

function getCookie(name) {
    let value = null;
    if (document.cookie) {
        document.cookie.split(';').forEach(c => {
            c = c.trim();
            if (c.startsWith(name + '=')) value = decodeURIComponent(c.slice(name.length + 1));
        });
    }
    return value;
}