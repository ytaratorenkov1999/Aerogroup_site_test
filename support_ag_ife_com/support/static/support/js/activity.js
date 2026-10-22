// Календарь активности шире экрана на узких экранах — показываем последние недели
(function () {
    window.scrollHeatmapToEnd = function () {
        document.querySelectorAll('[data-heatmap-scroll]').forEach(el => {
            el.scrollLeft = el.scrollWidth;
        });
    };
    window.scrollHeatmapToEnd();
})();
