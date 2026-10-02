Chart.register(ChartDataLabels);
const DASHBOARD_DATA = JSON.parse(document.getElementById('dashboard-data').textContent);
const stat = DASHBOARD_DATA.stat;
const monthLabels = DASHBOARD_DATA.monthLabels;
const monthlyData = DASHBOARD_DATA.monthlyData;
const urls = DASHBOARD_DATA.urls;
const csrfToken = DASHBOARD_DATA.csrfToken;
const currentPeriod = DASHBOARD_DATA.period;

const [periodYear, periodMonth] = currentPeriod.split('-');


const yearSelect = document.getElementById('select-year');
const currentYear = new Date().getFullYear();
const currentMonth = new Date().getMonth() + 1;
for (let y = currentYear; y >= currentYear - 4; y--) {
    const opt = document.createElement('option');
    opt.value = y;
    opt.textContent = y;
    yearSelect.appendChild(opt);
}

function filterMonths(selectedYear) {
    const monthSelect = document.getElementById('select-month');
    const maxMonth = parseInt(selectedYear) === currentYear ? currentMonth : 12;
    Array.from(monthSelect.options).forEach(opt => {
        opt.disabled = parseInt(opt.value) > maxMonth;
        opt.hidden   = parseInt(opt.value) > maxMonth;
    });
    if (parseInt(monthSelect.value) > maxMonth) {
        monthSelect.value = maxMonth;
    }
}


document.getElementById('select-year').value  = periodYear;
filterMonths(periodYear);
document.getElementById('select-month').value = parseInt(periodMonth);

yearSelect.addEventListener('change', () => filterMonths(yearSelect.value));

const periodBtn   = document.getElementById('period-button');
const periodPopup = document.getElementById('period-popup');

const monthNames = ['Январь','Февраль','Март','Апрель','Май','Июнь',
                    'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
periodBtn.textContent = `${monthNames[parseInt(periodMonth) - 1]} ${periodYear}`;

periodBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    periodPopup.classList.toggle('open');
});
document.addEventListener('click', (e) => {
    if (!periodPopup.contains(e.target) && e.target !== periodBtn) {
        periodPopup.classList.remove('open');
    }
});
document.getElementById('period-apply').addEventListener('click', () => {
    const monthSelect = document.getElementById('select-month');
    const monthNum    = parseInt(monthSelect.value);
    const month       = String(monthNum).padStart(2, '0');
    const year        = document.getElementById('select-year').value;
    const monthName   = monthSelect.options[monthNum - 1].text;
    periodBtn.textContent = `${monthName} ${year}`;
    periodPopup.classList.remove('open');
    window.location.href = `?period=${year}-${month}`;
});


document.getElementById('update-button').addEventListener('click', function () {
    this.disabled = true;
    this.textContent = 'Загрузка...';
    fetch(urls.update, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken,
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: `period=${encodeURIComponent(currentPeriod)}`
    })
    .then(r => r.json())
    .then(data => {
        if (data.ok) {
            location.reload();
        } else {
            showToast('error', 'Ошибка обновления', data.error || 'Не удалось получить данные от HelpDesk');
            this.disabled = false;
            this.textContent = 'Обновить статистику';
        }
    })
    .catch(() => {
        showToast('error', 'Ошибка соединения', 'Проверьте подключение к сети');
        this.disabled = false;
        this.textContent = 'Обновить статистику';
    });
});


document.getElementById('upload-statistic').addEventListener('click', function () {
    window.location.href = `${urls.export}?period=${encodeURIComponent(currentPeriod)}`;
});


const baseOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: { display: false },
        datalabels: { display: false },
        tooltip: { enabled: false }
    }
};

const categoryBarOptionsAfl = {
    ...baseOptions,
    layout: { padding: { top: 25 } },
    datasets: { bar: { maxBarThickness: 80 } },
    scales: {
        x: { ticks: { maxRotation: 45, minRotation: 45, font: { size: 11 }, autoSkip: false } },
        y: { ticks: { display: false }, grid: { display: false } }
    }
};

const categoryBarOptionsAkr = {
    ...baseOptions,
    layout: { padding: { top: 25 } },
    datasets: { bar: { maxBarThickness: 80 } },
    scales: {
        x: { ticks: { maxRotation: 45, minRotation: 45, font: { size: 11 }, autoSkip: false } },
        y: { ticks: { display: false }, grid: { display: false } }
    }
};


const barLabelsPluginAfl = {
    afterDatasetsDraw(chart) {
        const ctx = chart.ctx;
        chart.data.datasets.forEach((dataset, i) => {
            const meta = chart.getDatasetMeta(i);
            if (meta.hidden) return;
            meta.data.forEach((element, index) => {
                const value = dataset.data[index];
                ctx.fillStyle = '#03a0dc';
                ctx.beginPath();
                ctx.arc(element.x, element.y - 8, 3, 0, Math.PI * 2);
                ctx.fill();
                ctx.fillStyle = '#333';
                ctx.font = 'bold 11px Arial';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'bottom';
                ctx.fillText(value.toString(), element.x, element.y - 12);
            });
        });
    }
};

const barLabelsPluginAkr = {
    afterDatasetsDraw(chart) {
        const ctx = chart.ctx;
        chart.data.datasets.forEach((dataset, i) => {
            const meta = chart.getDatasetMeta(i);
            if (meta.hidden) return;
            meta.data.forEach((element, index) => {
                const value = dataset.data[index];
                ctx.fillStyle = '#ef9a9a';
                ctx.beginPath();
                ctx.arc(element.x, element.y - 8, 3, 0, Math.PI * 2);
                ctx.fill();
                ctx.fillStyle = '#333';
                ctx.font = 'bold 11px Arial';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'bottom';
                ctx.fillText(value.toString(), element.x, element.y - 12);
            });
        });
    }
};

const lineLabelsPlugin = {
    afterDatasetsDraw(chart) {
        const ctx = chart.ctx;
        chart.data.datasets.forEach((dataset, i) => {
            const meta = chart.getDatasetMeta(i);
            if (meta.hidden) return;
            meta.data.forEach((element, index) => {
                ctx.fillStyle = '#03a0dc';
                ctx.font = 'bold 11px Arial';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'bottom';
                ctx.fillText(dataset.data[index].toString(), element.x, element.y - 5);
            });
        });
    }
};

function createMetricChart(canvasId, value, total) {
    new Chart(document.getElementById(canvasId), {
        type: 'doughnut',
        data: {
            datasets: [{
                data: [value, Math.max(total - value, 0)],
                backgroundColor: ['#03a0dc', '#f0f0f0'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '75%',
            plugins: {
                legend: { display: false },
                datalabels: { display: false },
                tooltip: { enabled: false }
            }
        }
    });
}

new Chart(document.getElementById('helpdesk-request'), {
    type: 'line',
    data: {
        labels: monthLabels,
        datasets: [{
            label: 'Количество обращений',
            data: monthlyData,
            borderColor: '#03a0dc',
            backgroundColor: 'rgba(3, 160, 220, 0.1)',
            borderWidth: 2,
            tension: 0.3,
            fill: true,
            pointBackgroundColor: '#03a0dc',
            pointBorderColor: '#fff',
            pointBorderWidth: 2,
            pointRadius: 4,
            pointHoverRadius: 6
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 20 } },
        plugins: {
            legend: { display: true, position: 'top', align: 'end' },
            datalabels: { display: false },
            tooltip: {
                enabled: true,
                callbacks: {
                    title: (items) => items[0].label,
                    label: (item) => ` Обращений: ${item.raw}`
                }
            }
        },
        scales: { x: { grid: { display: false } } }
    },
    plugins: [lineLabelsPlugin]
});

new Chart(document.getElementById('total-company-request'), {
    type: 'doughnut',
    data: {
        labels: ['ПАО "Аэрофлот"', 'Россия'],
        datasets: [{
            data: [stat.request_count_afl, stat.request_count_akr],
            backgroundColor: ['#4bb9e5', '#ef9a9a'],
            borderWidth: 1
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false },
            datalabels: { display: false },
            tooltip: { enabled: false }
        }
    }
});


const chartAdmins = new Chart(document.getElementById('total-user-request'), {
    type: 'bar',
    data: {
        labels: stat.admins.map(a => a.name),
        datasets: [{
            data: stat.admins.map(a => a.count),
            backgroundColor: '#4bb9e5',
            maxBarThickness: 80,
            borderWidth: 1
        }]
    },
    options: {
        ...baseOptions,
        onClick(e) {
            const points = chartAdmins.getElementsAtEventForMode(e, 'nearest', { intersect: true }, false);
            if (!points.length) return;
            const admin = stat.admins[points[0].index];
            openTicketsModal(`${admin.name} — ${admin.count}`, admin.tickets);
        },
        onHover(e, elements) {
            e.native.target.style.cursor = elements.length ? 'pointer' : 'default';
        }
    },
    plugins: [{
        afterDatasetsDraw(chart) {
            const ctx = chart.ctx;
            chart.data.datasets.forEach((dataset, i) => {
                const meta = chart.getDatasetMeta(i);
                if (meta.hidden) return;
                meta.data.forEach((element, index) => {
                    const value = dataset.data[index];
                    const barHeight = element.base - element.y;
                    ctx.fillStyle = 'white';
                    ctx.font = 'bold 11px Arial';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillText(value.toString(), element.x, element.y + barHeight / 2);
                });
            });
        }
    }]
});


new Chart(document.getElementById('total-service-request'), {
    type: 'doughnut',
    data: {
        labels: ['IFE.AFL', 'r.portal'],
        datasets: [{
            data: [stat.count_service_ife, stat.count_service_rportal],
            backgroundColor: ['#a7ddf4', '#f5c4c4'],
            borderWidth: 1
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false },
            datalabels: {
                display: true,
                color: 'white',
                font: { weight: 'bold', size: 14 },
                formatter: (value) => value
            },
            tooltip: { enabled: false }
        }
    }
});


document.getElementById('redirect-value').textContent = stat.redirect_second_line + '%';
const redirectCount = stat.redirect_second_line_count ?? '—';
document.getElementById('redirect-subtitle').textContent =
    `Переведено: ${redirectCount} из ${stat.total_ticket}`;
createMetricChart('redirect-second-line', stat.redirect_second_line, 100);

const avgText = stat.avg_time_first_answer ? stat.avg_time_first_answer + ' мин' : '0';
document.getElementById('avg-value').textContent = avgText;
document.getElementById('avg-subtitle').textContent = 'Всего обращений: ' + stat.total_ticket;
createMetricChart('avg-time-request', Math.min(stat.avg_time_first_answer || 0, 100), 100);

const chartAfl = new Chart(document.getElementById('total-name-request-afl'), {
    type: 'bar',
    data: {
        labels: stat.categories_afl.map(c => c.category),
        datasets: [{
            data: stat.categories_afl.map(c => c.count),
            backgroundColor: '#4bb9e5',
            maxBarThickness: 70,
            borderWidth: 1
        }]
    },
    options: {
        ...categoryBarOptionsAfl,
        onClick(e) {
            const points = chartAfl.getElementsAtEventForMode(e, 'nearest', { intersect: true }, false);
            if (!points.length) return;
            const idx = points[0].index;
            const cat = stat.categories_afl[idx];
            openTicketsModal(cat.category, idsToLinks(cat.ticket_ids, BASE_URL_AFL, 'afl'));
        },
        onHover(e, elements) {
            e.native.target.style.cursor = elements.length ? 'pointer' : 'default';
        }
    },
    plugins: [barLabelsPluginAfl]
});


const chartAkr = new Chart(document.getElementById('total-name-request-akr'), {
    type: 'bar',
    data: {
        labels: stat.categories_akr.map(c => c.category),
        datasets: [{
            data: stat.categories_akr.map(c => c.count),
            backgroundColor: '#ef9a9a',
            maxBarThickness: 120,
            borderWidth: 1
        }]
    },
    options: {
        ...categoryBarOptionsAkr,
        onClick(e) {
            const points = chartAkr.getElementsAtEventForMode(e, 'nearest', { intersect: true }, false);
            if (!points.length) return;
            const idx = points[0].index;
            const cat = stat.categories_akr[idx];
            openTicketsModal(cat.category, idsToLinks(cat.ticket_ids, BASE_URL_AKR, 'akr'));
        },
        onHover(e, elements) {
            e.native.target.style.cursor = elements.length ? 'pointer' : 'default';
        }
    },
    plugins: [barLabelsPluginAkr]
});