document.addEventListener('DOMContentLoaded', function () {
    const app          = document.getElementById('knowledgeApp');
    const structureUrl = app.dataset.structureUrl;
    const searchUrl    = app.dataset.searchUrl;
    const articleBase  = app.dataset.articleBase;
    const categoryBase = app.dataset.categoryBase;

    /* ── Загрузка структуры ── */
    fetch(structureUrl)
        .then(r => r.json())
        .then(data => {
            const container = document.getElementById('categoriesGrid');
            if (!data.structure.length) {
                container.innerHTML = '<div style="text-align:center;color:#6c757d;font-size:13px;grid-column:1/-1">Нет категорий</div>';
                return;
            }
            container.innerHTML = data.structure.map(cat => `
                <a href="${categoryBase}${cat.slug}/" class="category-card">
                    ${cat.name}
                </a>
            `).join('');
        })
        .catch(err => console.error('Ошибка загрузки структуры:', err));

    /* ── Поиск ── */
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