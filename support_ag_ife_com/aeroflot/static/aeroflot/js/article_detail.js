/* ── Модальное окно удаления ── */
function openDeleteModal()  { document.getElementById('deleteModal').style.display = 'block'; }
function closeDeleteModal() { document.getElementById('deleteModal').style.display = 'none'; }

/* ── Модальное окно изображения ── */
function openImageModal(src) {
    document.getElementById('imageModal').style.display = 'block';
    document.getElementById('modalImage').src = src;
}

function closeImageModal() {
    document.getElementById('imageModal').style.display = 'none';
}

window.addEventListener('click', function(e) {
    if (e.target === document.getElementById('deleteModal')) closeDeleteModal();
});

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') { closeDeleteModal(); closeImageModal(); }
});

document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.article-content img').forEach(img => {
        img.addEventListener('click', () => openImageModal(img.src));
    });

    if (typeof mermaid !== 'undefined') {
        document.querySelectorAll('.article-content pre code.language-mermaid').forEach(el => {
            const div       = document.createElement('div');
            div.className   = 'mermaid';
            div.textContent = el.textContent;
            el.closest('pre').replaceWith(div);
        });
        mermaid.run({ nodes: document.querySelectorAll('.article-content .mermaid') });
    }
});

/* ── Ознакомление — AJAX ── */
const ackForm = document.getElementById('ackForm');
if (ackForm) {
    ackForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const btn = document.getElementById('ackBtn');
        btn.disabled = true;

        try {
            const resp = await fetch(ackForm.action, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': ackForm.querySelector('[name=csrfmiddlewaretoken]').value
                },
            });
            const data = await resp.json();
            if (data.success) {
                // Скрываем кнопку
                ackForm.style.display = 'none';

                // Добавляем аватар текущего пользователя в список
                const avatars = document.getElementById('ackAvatars');
                if (avatars) {
                    const wrap = document.createElement('div');
                    wrap.className = 'ack-avatar-wrap';
                    wrap.title = data.full_name || data.username || 'Вы';

                    if (data.photo_url) {
                        const img = document.createElement('img');
                        img.className = 'ack-avatar';
                        img.src = data.photo_url;
                        img.alt = '';
                        wrap.appendChild(img);
                    } else {
                        const circle = document.createElement('div');
                        circle.className = 'ack-avatar ack-avatar-initials';
                        circle.textContent = (data.username || '?')[0].toUpperCase();
                        wrap.appendChild(circle);
                    }
                    avatars.appendChild(wrap);

                    // Показываем надпись "Ознакомились:" если её не было
                    const right = avatars.closest('.ack-right');
                    if (!right) {
                        const newRight = document.createElement('div');
                        newRight.className = 'ack-right';
                        const label = document.createElement('span');
                        label.className = 'ack-label';
                        label.textContent = 'Ознакомились:';
                        newRight.appendChild(label);
                        avatars.parentNode.insertBefore(newRight, avatars);
                        newRight.appendChild(avatars);
                    }
                }
            }
        } catch(err) {
            btn.disabled = false;
        }
    });
}