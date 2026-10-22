(function () {
    // Приветствие и дата — по времени на компьютере пользователя
    const hour = new Date().getHours();
    const greeting = hour >= 5 && hour < 12 ? 'Доброе утро'
                   : hour >= 12 && hour < 18 ? 'Добрый день'
                   : hour >= 18 && hour < 23 ? 'Добрый вечер'
                   : 'Доброй ночи';
    const greetingEl = document.querySelector('[data-greeting]');
    if (greetingEl) greetingEl.textContent = greeting;

    const todayEl = document.querySelector('[data-today]');
    if (todayEl) {
        const text = new Intl.DateTimeFormat('ru-RU', {
            weekday: 'long', day: 'numeric', month: 'long',
        }).format(new Date());
        todayEl.textContent = text.charAt(0).toUpperCase() + text.slice(1);
    }

    // Копирование ссылки на созвон
    function copyText(text) {
        if (navigator.clipboard && window.isSecureContext) {
            return navigator.clipboard.writeText(text);
        }
        const area = document.createElement('textarea');
        area.value = text;
        area.style.position = 'fixed';
        area.style.opacity = '0';
        document.body.appendChild(area);
        area.select();
        document.execCommand('copy');
        area.remove();
        return Promise.resolve();
    }

    document.querySelectorAll('[data-copy]').forEach(btn => {
        btn.addEventListener('click', () => {
            copyText(btn.dataset.copy).then(() => {
                const icon = btn.querySelector('i');
                btn.classList.add('copied');
                icon.className = 'ti ti-check';
                btn.title = 'Скопировано';
                setTimeout(() => {
                    btn.classList.remove('copied');
                    icon.className = 'ti ti-copy';
                    btn.title = 'Скопировать ссылку';
                }, 1500);
            });
        });
    });
})();
