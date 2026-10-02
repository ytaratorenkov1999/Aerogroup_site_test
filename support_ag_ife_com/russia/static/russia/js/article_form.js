(function () {
    'use strict';

    const CSRF = document.querySelector('[name=csrfmiddlewaretoken]').value;
    const ATTACHMENT_DELETE_URL = window.RUSSIA_URLS.attachmentDeleteBase;

    /* ── Markdown тулбар ── */
    function insertMarkdown(before, after) {
        const ta = document.getElementById('content');
        const s = ta.selectionStart, e = ta.selectionEnd;
        const sel = ta.value.substring(s, e);
        ta.value = ta.value.substring(0, s) + before + sel + after + ta.value.substring(e);
        const pos = s + before.length + sel.length;
        ta.setSelectionRange(pos, pos);
        ta.focus();
    }

    function insertCodeBlock() {
        const ta = document.getElementById('content');
        const s = ta.selectionStart, e = ta.selectionEnd;
        const sel = ta.value.substring(s, e);
        const rep = '\n```\n' + sel + '\n```\n';
        ta.value = ta.value.substring(0, s) + rep + ta.value.substring(e);
        ta.setSelectionRange(s + 5 + sel.length, s + 5 + sel.length);
        ta.focus();
    }

    document.querySelectorAll('.toolbar-btn[data-md-wrap]').forEach(btn => {
        btn.addEventListener('click', () => {
            const [before, after] = btn.dataset.mdWrap.split('|');
            insertMarkdown(before, after);
        });
    });

    document.querySelectorAll('.toolbar-btn[data-md-prefix]').forEach(btn => {
        btn.addEventListener('click', () => insertMarkdown(btn.dataset.mdPrefix, ''));
    });

    document.querySelector('.toolbar-btn[data-md-code-block]')
        ?.addEventListener('click', insertCodeBlock);

    /* ── Переключение режимов + Mermaid в предпросмотре ── */
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const mode    = btn.dataset.mode;
            const content = document.getElementById('content');
            const preview = document.getElementById('preview');
            if (mode === 'edit') {
                content.classList.remove('hidden');
                preview.classList.remove('active');
                document.getElementById('editBtn').classList.add('active');
                document.getElementById('previewBtn').classList.remove('active');
            } else {
                content.classList.add('hidden');
                preview.classList.add('active');
                document.getElementById('editBtn').classList.remove('active');
                document.getElementById('previewBtn').classList.add('active');
                if (typeof marked !== 'undefined') {
                    preview.innerHTML = marked.parse(content.value);
                }
                if (typeof mermaid !== 'undefined') {
                    preview.querySelectorAll('pre code.language-mermaid').forEach(el => {
                        const div       = document.createElement('div');
                        div.className   = 'mermaid';
                        div.textContent = el.textContent;
                        el.closest('pre').replaceWith(div);
                    });
                    mermaid.run({ nodes: preview.querySelectorAll('.mermaid') });
                }
            }
        });
    });

    /* ── Диаграмма: вставка шаблона ── */
    document.querySelector('.toolbar-btn[data-md-mermaid]')
        ?.addEventListener('click', () => {
            const ta  = document.getElementById('content');
            const s   = ta.selectionStart;
            const tpl = '\n```mermaid\ngraph TD\n    A[Начало] --> B[Конец]\n```\n';
            ta.value  = ta.value.substring(0, s) + tpl + ta.value.substring(ta.selectionEnd);
            ta.setSelectionRange(s + tpl.length, s + tpl.length);
            ta.focus();
        });

    /* ── Изображение: выбор файла → загрузка → вставка в редактор ── */
    const IMAGE_UPLOAD_URL = window.RUSSIA_URLS.imageUploadUrl;
    const ARTICLE_ID       = window.RUSSIA_URLS.articleId;
    const imgFileInput     = document.getElementById('imgFileInput');

    document.getElementById('btnInsertImage').addEventListener('click', () => {
        imgFileInput.value = '';
        imgFileInput.click();
    });

    imgFileInput.addEventListener('change', function () {
        const file = this.files[0];
        if (!file) return;

        const fd = new FormData();
        fd.append('image', file);
        if (ARTICLE_ID) fd.append('article_id', ARTICLE_ID);

        fetch(IMAGE_UPLOAD_URL, {
            method: 'POST',
            headers: { 'X-CSRFToken': CSRF },
            body: fd,
        })
        .then(r => r.json())
        .then(data => {
            if (!data.success) {
                alert(data.error || 'Ошибка загрузки изображения');
                return;
            }
            /* Вставляем markdown в редактор */
            const ta  = document.getElementById('content');
            const pos = ta.selectionStart;
            const md  = `![${data.file_name}](${data.url})`;
            ta.value  = ta.value.substring(0, pos) + md + ta.value.substring(pos);
            ta.setSelectionRange(pos + md.length, pos + md.length);
            ta.focus();

            /* Добавляем карточку в блок существующих вложений */
            let grid = document.querySelector('.existing-attachments-grid');
            if (!grid) {
                const wrap = document.createElement('div');
                wrap.className = 'existing-attachments';
                wrap.innerHTML = '<label>Текущие вложения:</label><div class="existing-attachments-grid"></div>';
                const uploadsGroup = document.getElementById('fileUploadArea').closest('.form-group');
                uploadsGroup.parentNode.insertBefore(wrap, uploadsGroup);
                grid = wrap.querySelector('.existing-attachments-grid');
            }
            const card = document.createElement('a');
            card.className = 'existing-attachment';
            card.href      = data.url;
            card.target    = '_blank';
            card.id        = `attachment-${data.attachment_id}`;
            card.innerHTML = `
                <div class="file-info">
                    <div class="file-type-badge-sm file-type-img">IMG</div>
                    <span class="file-name">${data.file_name}</span>
                </div>
                <button type="button" class="attachment-delete-btn"
                        data-attachment-id="${data.attachment_id}" title="Удалить">×</button>`;
            card.querySelector('.attachment-delete-btn').addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                const id   = this.dataset.attachmentId;
                const name = card.querySelector('.file-name')?.textContent || 'файл';
                openAttachmentDeleteModal(id, name, card);
            });
            bindDeleteBtn(card.querySelector('.attachment-delete-btn'));
            grid.appendChild(card);
        })
        .catch(() => alert('Ошибка соединения с сервером'));
    });

    /* ── Загрузка файлов ── */
    const fileUploadArea = document.getElementById('fileUploadArea');
    const fileInput      = document.getElementById('fileInput');
    const filesList      = document.getElementById('filesList');
    const MAX_SIZE       = 50 * 1024 * 1024;
    let selectedFiles    = [];

    fileUploadArea.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', e => handleFiles(Array.from(e.target.files)));
    fileUploadArea.addEventListener('dragover', e => { e.preventDefault(); fileUploadArea.classList.add('dragover'); });
    fileUploadArea.addEventListener('dragleave', () => fileUploadArea.classList.remove('dragover'));
    fileUploadArea.addEventListener('drop', e => {
        e.preventDefault();
        fileUploadArea.classList.remove('dragover');
        handleFiles(Array.from(e.dataTransfer.files));
    });

    function handleFiles(newFiles) {
        const oversized = newFiles.filter(f => f.size > MAX_SIZE).map(f => f.name);
        const valid     = newFiles.filter(f => f.size <= MAX_SIZE);
        if (oversized.length) showFileError(`Файлы превышают 50 МБ и не добавлены: ${oversized.join(', ')}`);
        else clearFileError();
        selectedFiles = [...selectedFiles, ...valid];
        updateFileInput();
        renderFiles();
    }

    function updateFileInput() {
        const dt = new DataTransfer();
        selectedFiles.forEach(f => dt.items.add(f));
        fileInput.files = dt.files;
    }

    function renderFiles() {
        filesList.innerHTML = '';
        selectedFiles.forEach((file, i) => {
            const item = document.createElement('div');
            item.className = 'file-item';
            item.innerHTML = `
                <div class="file-info">
                    ${getIcon(file.name)}
                    <div>
                        <div class="file-name-text">${file.name}</div>
                        <div class="file-size">${fmtSize(file.size)}</div>
                    </div>
                </div>
                <button type="button" class="remove-file">Удалить</button>
            `;
            item.querySelector('.remove-file').addEventListener('click', () => {
                selectedFiles.splice(i, 1);
                updateFileInput();
                renderFiles();
            });
            filesList.appendChild(item);
        });
    }

    function getIcon(name) {
        const ext = name.split('.').pop().toLowerCase();
        if (['jpg','jpeg','png','gif'].includes(ext)) return '<div class="file-type-badge-sm file-type-img">IMG</div>';
        if (ext === 'pdf')                            return '<div class="file-type-badge-sm file-type-pdf">PDF</div>';
        if (['doc','docx'].includes(ext))             return '<div class="file-type-badge-sm file-type-doc">DOC</div>';
        if (['xls','xlsx'].includes(ext))             return '<div class="file-type-badge-sm file-type-xls">XLS</div>';
        return '<div class="file-type-badge-sm file-type-other">FILE</div>';
    }

    function fmtSize(b) {
        if (!b) return '0 B';
        const k = 1024, s = ['B','KB','MB','GB'];
        const i = Math.floor(Math.log(b) / Math.log(k));
        return Math.round(b / Math.pow(k, i) * 100) / 100 + ' ' + s[i];
    }

    function showFileError(msg) {
        let el = document.getElementById('file-upload-error');
        if (!el) {
            el = document.createElement('div');
            el.id = 'file-upload-error';
            el.className = 'field-error';
            filesList.before(el);
        }
        el.textContent = msg;
        el.classList.add('visible');
    }

    function clearFileError() {
        document.getElementById('file-upload-error')?.classList.remove('visible');
    }


    const attDelModal   = document.getElementById('attachmentDeleteModal');
    const attDelName    = document.getElementById('attachmentDeleteName');
    const attDelConfirm = document.getElementById('attachmentDeleteConfirm');
    const attDelCancel  = document.getElementById('attachmentDeleteCancel');
    let   attDelPending = null; // { id, cardEl }

    function openAttachmentDeleteModal(id, name, cardEl) {
        attDelPending = { id, cardEl };
        attDelName.textContent = name;
        attDelModal.style.display = 'block';
    }

    function closeAttachmentDeleteModal() {
        attDelModal.style.display = 'none';
        attDelPending = null;
    }

    attDelCancel.addEventListener('click', closeAttachmentDeleteModal);
    attDelModal.addEventListener('click', e => { if (e.target === attDelModal) closeAttachmentDeleteModal(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeAttachmentDeleteModal(); });

    attDelConfirm.addEventListener('click', () => {
        if (!attDelPending) return;
        const { id, cardEl } = attDelPending;
        closeAttachmentDeleteModal();
        fetch(`${ATTACHMENT_DELETE_URL}${id}/delete/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': CSRF },
        })
        .then(r => r.json())
        .then(data => { if (data.success) cardEl.remove(); });
    });

    function bindDeleteBtn(btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            const id   = this.dataset.attachmentId;
            const card = document.getElementById(`attachment-${id}`);
            const name = card?.querySelector('.file-name')?.textContent || 'файл';
            openAttachmentDeleteModal(id, name, card);
        });
    }


    document.querySelectorAll('.attachment-delete-btn').forEach(btn => bindDeleteBtn(btn));


    function showErr(id, msg) {
        const err = document.getElementById(`${id}-error`);
        const el  = document.getElementById(id);
        if (err) { err.textContent = msg; err.classList.add('visible'); }
        if (el)  el.classList.add('invalid');
    }

    function clearErr(id) {
        document.getElementById(`${id}-error`)?.classList.remove('visible');
        document.getElementById(id)?.classList.remove('invalid');
    }

    document.getElementById('title')?.addEventListener('input', () => clearErr('title'));
    document.getElementById('category_id')?.addEventListener('change', () => clearErr('category_id'));
    document.getElementById('content')?.addEventListener('input', () => {
        clearErr('content');
        document.getElementById('editorContainer')?.classList.remove('invalid');
        document.getElementById('content-error')?.classList.remove('visible');
    });

    document.getElementById('articleForm').addEventListener('submit', function (e) {
        let valid = true;
        if (!document.getElementById('title').value.trim())       { showErr('title', 'Введите название статьи'); valid = false; }
        if (!document.getElementById('category_id').value)        { showErr('category_id', 'Выберите категорию'); valid = false; }
        if (!document.getElementById('content').value.trim()) {
            document.getElementById('editorContainer').classList.add('invalid');
            document.getElementById('content-error').classList.add('visible');
            valid = false;
        }
        if (!valid) {
            e.preventDefault();
            document.querySelector('.field-error.visible')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    });

})();