(function () {
    const page        = document.getElementById('profilePage');
    const defaultAvatar = page.dataset.defaultAvatar;
    const toastMessage  = page.dataset.toastMessage;

    // Предпросмотр фото при выборе файла
    document.getElementById('photoInput').addEventListener('change', function () {
        const file = this.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = e => {
            document.getElementById('photoPreview').src = e.target.result;
        };
        reader.readAsDataURL(file);
    });

    // Удаление фото
    const deleteBtn = document.getElementById('deletePhotoBtn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', function () {
            document.getElementById('deletePhotoInput').value = '1';
            document.getElementById('photoPreview').src = defaultAvatar;
            this.remove();
        });
    }

    // Toast-уведомление
    let toastTimer;

    function showToast(title, message) {
        const toast = document.getElementById('toast');
        toast.className = 'toast';
        document.getElementById('toast-title').textContent = title;
        document.getElementById('toast-message').textContent = message;
        toast.classList.add('show');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(hideToast, 5000);
    }

    window.hideToast = function () {
        document.getElementById('toast').classList.remove('show');
    };

    // Показываем toast если есть сообщение от Django
    if (toastMessage) {
        showToast('Профиль обновлён', toastMessage);
    }
})();