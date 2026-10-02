(function() {
  'use strict';

  // ============================================
  // 1. Flap-анимация
  // ============================================
  const FLAP_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";

  function flap(el, target) {
    const from = el.textContent;
    const len = Math.max(from.length, target.length);
    const to = target.padEnd(len, " ");
    const current = from.padEnd(len, " ").split("");

    for (let i = 0; i < len; i++) {
      const cycles = 5 + Math.floor(Math.random() * 5);
      let n = 0;
      setTimeout(function step() {
        if (n < cycles) {
          current[i] = FLAP_CHARS[Math.floor(Math.random() * FLAP_CHARS.length)];
          n++;
          el.textContent = current.join("");
          setTimeout(step, 45);
        } else {
          current[i] = to[i];
          el.textContent = current.join("");
        }
      }, i * 35);
    }
  }

  function initFlapDemo() {
    const nameEl = document.getElementById('flapName');
    const emailEl = document.getElementById('flapEmail');
    if (!nameEl || !emailEl) return;

    const real = {
      name: 'TARATORENKOV YURII',
      email: 'Y.TARATORENKOV@ROSSIYA-AIRLINES.COM'
    };
    const fake = {
      name: 'CONOR MACGREGOR',
      email: 'C.MACGREGOR@ROSSIYA-AIRLINES.COM'
    };
    let showingFake = false;

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    setInterval(() => {
      showingFake = !showingFake;
      const target = showingFake ? fake : real;
      flap(nameEl, target.name);
      flap(emailEl, target.email);
    }, 4200);
  }

  initFlapDemo();

  // ============================================
  // 2. Иконки для чипов файлов
  // ============================================
  const ICONS = {
    json: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 2h9l5 5v15H6z"/><path d="M15 2v5h5"/></svg>',
    csv: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 2h9l5 5v15H6z"/><path d="M15 2v5h5"/><path d="M9 13h6M9 16h6"/></svg>'
  };

  // ============================================
  // 3. DOM-элементы
  // ============================================
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const browseBtn = document.getElementById('browseBtn');
  const chipsEl = document.getElementById('fileChips');
  const chipsEmpty = document.getElementById('chipsEmpty');
  const summaryEl = document.getElementById('summary');
  const processBtn = document.getElementById('processBtn');
  const logBody = document.getElementById('logBody');
  const logPlaceholder = document.getElementById('logPlaceholder');

  let files = [];

  // ============================================
  // 4. Обработчики загрузки
  // ============================================
  browseBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    fileInput.click();
  });

  dropzone.addEventListener('click', () => fileInput.click());

  dropzone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      fileInput.click();
    }
  });

  fileInput.addEventListener('change', (e) => {
    addFiles(e.target.files);
    fileInput.value = '';
  });

  ['dragenter', 'dragover'].forEach(evt => {
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.add('is-dragover');
    });
  });

  ['dragleave', 'drop'].forEach(evt => {
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.remove('is-dragover');
    });
  });

  dropzone.addEventListener('drop', (e) => addFiles(e.dataTransfer.files));

  // ============================================
  // 5. Работа с файлами
  // ============================================
  function detectExtension(filename) {
    const clean = filename.replace(/\.\d+$/, '');
    return clean.split('.').pop().toLowerCase();
  }

  function addFiles(fileListObj) {
    Array.from(fileListObj).forEach(f => {
      const ext = detectExtension(f.name);
      if (ext !== 'json' && ext !== 'csv') return;
      files.push({ name: f.name, size: f.size, ext, raw: f });
    });
    render();
  }

  function removeFile(index) {
    files.splice(index, 1);
    render();
  }

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' Б';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' КБ';
    return (bytes / (1024 * 1024)).toFixed(1) + ' МБ';
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // ============================================
  // 6. Рендеринг
  // ============================================
  function renderChips() {
    chipsEl.innerHTML = '';
    chipsEmpty.style.display = files.length === 0 ? 'block' : 'none';

    files.forEach((f, i) => {
      const chip = document.createElement('div');
      chip.className = 'chip';
      chip.innerHTML = `
        <span class="chip__icon chip__icon--${f.ext}">${ICONS[f.ext]}</span>
        <span class="chip__body">
          <span class="chip__name" title="${escapeHtml(f.name)}">${escapeHtml(f.name)}</span>
          <span class="chip__meta">${f.ext.toUpperCase()} · ${formatSize(f.size)}</span>
        </span>
        <button class="chip__remove" type="button" aria-label="Удалить файл ${escapeHtml(f.name)}" data-index="${i}">✕</button>
      `;
      chipsEl.appendChild(chip);
    });

    summaryEl.textContent = files.length === 0 ? '' : `Файлов выбрано: ${files.length}`;
    processBtn.disabled = files.length === 0;
  }

  function render() {
    renderChips();
    logBody.innerHTML = '';
    logBody.appendChild(logPlaceholder);
  }

  // Удаление файла по клику на крестик
  chipsEl.addEventListener('click', (e) => {
    const btn = e.target.closest('.chip__remove');
    if (btn) removeFile(Number(btn.dataset.index));
  });

  // ============================================
  // 7. Логи
  // ============================================
  function clearLog() {
    logBody.innerHTML = '';
  }

  function appendLogLine(text, variant) {
    const div = document.createElement('div');
    div.className = 'log-line' + (variant === 'done' ? ' log-line--done' : variant === 'error' ? ' log-line--error' : '');
    div.textContent = text;
    logBody.appendChild(div);
    logBody.scrollTop = logBody.scrollHeight;
  }

  // ============================================
  // 8. Работа с куками (CSRF)
  // ============================================
  function getCookie(name) {
    const match = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return match ? decodeURIComponent(match.pop()) : '';
  }

  // ============================================
  // 9. Загрузка/скачивание
  // ============================================
  function base64ToBlob(base64, contentType) {
    const byteChars = atob(base64);
    const byteNumbers = new Array(byteChars.length);
    for (let i = 0; i < byteChars.length; i++) {
      byteNumbers[i] = byteChars.charCodeAt(i);
    }
    return new Blob([new Uint8Array(byteNumbers)], { type: contentType });
  }

  function downloadBlob(blob, filename) {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  }

  // ============================================
  // 10. Основной обработчик
  // ============================================
  processBtn.addEventListener('click', async () => {
    if (files.length === 0) return;

    processBtn.disabled = true;
    const originalText = processBtn.textContent;
    processBtn.textContent = 'Обработка…';

    clearLog();

    const formData = new FormData();
    files.forEach(f => formData.append('files', f.raw, f.name));

    try {
      const csrfInput = document.querySelector('.frame input[name="csrfmiddlewaretoken"]');
      const response = await fetch(processBtn.dataset.processUrl, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrfInput ? csrfInput.value : getCookie('csrftoken')
        },
        body: formData
      });

      if (!response.ok) {
        let message = `Ошибка сервера (HTTP ${response.status})`;
        try {
          const errJson = await response.json();
          if (errJson.error) message = errJson.error;
        } catch (e) {}
        appendLogLine(message, 'error');
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let gotResult = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.trim()) continue;
          const event = JSON.parse(line);

          if (event.type === 'log') {
            appendLogLine(event.message);
          } else if (event.type === 'error') {
            gotResult = true;
            appendLogLine(`Ошибка обработки: ${event.message}`, 'error');
          } else if (event.type === 'result') {
            gotResult = true;
            appendLogLine('Формирование архива с обезличенными данными...');
            const blob = base64ToBlob(event.zip_base64, 'application/zip');
            downloadBlob(blob, 'fake_crew.zip');
            files = [];
            renderChips();
          }
        }
      }

      if (!gotResult) {
        appendLogLine('Соединение прервано до получения результата.', 'error');
      }
    } catch (err) {
      appendLogLine(`Не удалось связаться с сервером: ${err.message}`, 'error');
    } finally {
      processBtn.disabled = files.length === 0;
      processBtn.textContent = originalText;
    }
  });

  // ============================================
  // 11. Инициализация
  // ============================================
  render();

})();