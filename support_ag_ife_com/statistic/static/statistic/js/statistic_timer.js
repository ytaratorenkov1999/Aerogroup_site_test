let toastTimer;

function showToast(type, title, message) {
    const toast = document.getElementById('toast');
    toast.className = `toast ${type}`;
    document.getElementById('toast-icon').textContent = type === 'error' ? '✕' : '✓';
    document.getElementById('toast-title').textContent = title;
    document.getElementById('toast-message').textContent = message;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(hideToast, 5000);
}

function hideToast() {
    document.getElementById('toast').classList.remove('show');
}

document.getElementById('toast-close').addEventListener('click', hideToast);