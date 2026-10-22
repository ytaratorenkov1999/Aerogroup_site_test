const BASE_URL_AFL = DASHBOARD_DATA.ticketUrls.afl;
const BASE_URL_AKR = DASHBOARD_DATA.ticketUrls.akr;
const ticketsModal = document.getElementById('tickets-modal');


function openTicketsModal(title, links) {
    document.getElementById('modal-category').textContent = title;

    const linksEl = document.getElementById('modal-links');
    linksEl.innerHTML = '';

    const valid = (links || []).filter(l => l && l.id && l.url);
    if (!valid.length) {
        const empty = document.createElement('div');
        empty.className = 'tickets-modal-empty';
        empty.textContent = 'Нет ссылок на заявки — обновите статистику за этот период';
        linksEl.appendChild(empty);
    }

    valid.forEach(({ id, url, airline }) => {
        const a = document.createElement('a');
        a.href = url;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
        a.textContent = `Заявка #${id}`;
        a.className = 'tickets-modal-link' + (airline ? ` ${airline}` : '');
        linksEl.appendChild(a);
    });

    ticketsModal.classList.add('open');
    document.body.style.overflow = 'hidden';
}

function idsToLinks(ticketIds, baseUrl, airline) {
    return (ticketIds || []).filter(Boolean).map(id => ({ id, url: baseUrl + id, airline }));
}

function closeTicketsModal() {
    ticketsModal.classList.remove('open');
    document.body.style.overflow = '';
}


document.getElementById('modal-close').addEventListener('click', closeTicketsModal);


ticketsModal.addEventListener('click', (e) => {
    if (e.target === ticketsModal) closeTicketsModal();
});


document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeTicketsModal();
});