document.addEventListener('DOMContentLoaded', function () {

    // Экранирование данных с сервера перед вставкой в innerHTML (защита от XSS)
    function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, ch => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        })[ch]);
    }
    const app        = document.getElementById('categoryApp');
    const searchUrl  = app.dataset.searchUrl;
    const articleBase = app.dataset.articleBase;

    let searchTimeout;
    const searchInput    = document.getElementById('searchInput');
    const searchResults  = document.getElementById('searchResults');
    const searchGrid     = document.getElementById('searchResultsGrid');
    const contentSection = document.getElementById('contentSection');

    searchInput.addEventListener('input', function () {
        clearTimeout(searchTimeout);
        const query = this.value.trim();
        if (query.length < 2) {
            searchResults.classList.remove('active');
            contentSection.classList.remove('hidden');
            return;
        }
        searchTimeout = setTimeout(() => {
            contentSection.classList.add('hidden');
            searchResults.classList.add('active');
            fetch(`${searchUrl}?q=${encodeURIComponent(query)}`)
                .then(r => r.json())
                .then(data => {
                    if (!data.results.length) {
                        searchGrid.innerHTML = `<div class="no-results">Ничего не найдено по запросу «${escapeHtml(query)}»</div>`;
                    } else {
                        searchGrid.innerHTML = data.results.map(r => `
                            <a href="${articleBase}${encodeURIComponent(r.slug)}/" class="search-result-card">
                                <div class="result-title">${escapeHtml(r.title)}</div>
                            </a>
                        `).join('');
                    }
                })
                .catch(() => {
                    searchGrid.innerHTML = '<div class="no-results">Ошибка при выполнении поиска</div>';
                });
        }, 300);
    });
});