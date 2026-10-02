document.addEventListener('DOMContentLoaded', function () {
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
                        searchGrid.innerHTML = `<div class="no-results">Ничего не найдено по запросу «${query}»</div>`;
                    } else {
                        searchGrid.innerHTML = data.results.map(r => `
                            <a href="${articleBase}${r.slug}/" class="search-result-card">
                                <div class="result-title">${r.title}</div>
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