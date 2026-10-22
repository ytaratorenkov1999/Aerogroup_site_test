(function () {
'use strict';


// URL читаем из data-атрибутов элемента #kcTestView
// (они рендерятся шаблонизатором Django в knowledge.html)
const _el = document.getElementById('kcTestView');
const URLS = {
    start:    _el.dataset.urlStart,
    resume:   _el.dataset.urlResume,
    question: _el.dataset.urlQuestion,
    submit:   _el.dataset.urlSubmit,
    complete: _el.dataset.urlComplete,
};

const SVG_ICONS = {
    image: '<svg viewBox="0 0 24 24" fill="none" stroke="#03a0dc" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>',
    pdf:   '<svg viewBox="0 0 24 24" fill="none" stroke="#03a0dc" stroke-width="1.5"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="13" y2="17"/></svg>',
    doc:   '<svg viewBox="0 0 24 24" fill="none" stroke="#03a0dc" stroke-width="1.5"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="15" y2="17"/></svg>',
    xls:   '<svg viewBox="0 0 24 24" fill="none" stroke="#03a0dc" stroke-width="1.5"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="9" y1="13" x2="11" y2="17"/><line x1="15" y1="13" x2="13" y2="17"/></svg>',
    other: '<svg viewBox="0 0 24 24" fill="none" stroke="#03a0dc" stroke-width="1.5"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>',
};


class KnowledgeCheck {

    constructor() {
        // Состояние
        this.catId       = null;
        this.catSlug     = null;
        this.qId         = null;
        this.qType       = null;
        this.qMulti      = false;
        this.isLast      = false;
        this.isCompleted = false;

        // DOM элементы
        this.elCardsView = document.getElementById('kcCardsView');
        this.elTestView  = document.getElementById('kcTestView');
        this.elTitle     = document.getElementById('kcTestTitle');
        this.elStartBtn  = document.getElementById('kcStartBtn');
        this.elBackBtn   = document.getElementById('kcBackBtn');
        this.elNextBtn   = document.getElementById('kcNextBtn');
        this.elReturnBtn = document.getElementById('kcReturnBtn');
        this.elProgLabel = document.getElementById('kcProgLabel');
        this.elProgPct   = document.getElementById('kcProgPct');
        this.elProgFill  = document.getElementById('kcProgFill');
        this.elQText     = document.getElementById('kcQText');
        this.elAnswerArea= document.getElementById('kcAnswerArea');
        this.elAttach    = document.getElementById('kcAttachments');

        this._bindEvents();
    }


    _bindEvents() {
        // Клики по карточкам категорий
        document.querySelectorAll('.kc-card').forEach(card => {
            card.addEventListener('click', () => this._onCardClick(card));
        });

        // Кнопки управления
        this.elStartBtn.addEventListener('click',  () => this._onStartClick());
        this.elBackBtn.addEventListener('click',   () => this._onBackClick());
        this.elNextBtn.addEventListener('click',   () => this._onNextClick());
        this.elReturnBtn.addEventListener('click', () => this._onBackClick());
    }


    _onCardClick(card) {
        if (card.dataset.can !== 'true') return;

        this.catId   = card.dataset.id;
        this.catSlug = card.dataset.slug;
        this.isCompleted = false;

        this.elTitle.textContent    = card.dataset.name;
        this.elStartBtn.textContent = card.dataset.inProgress === 'true'
            ? 'Продолжить тестирование'
            : 'Начать тестирование';

        this.elCardsView.style.display = 'none';
        this.elTestView.style.display  = 'flex';
        this._showScreen('start');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }


    _onBackClick() {
        if (this.catId) {
            const card = document.querySelector(`.kc-card[data-id="${this.catId}"]`);
            if (card) {
                if (this.isCompleted) {
                    card.classList.add('kc-card--locked');
                    card.dataset.can        = 'false';
                    card.dataset.inProgress = 'false';
                } else {
                    card.dataset.inProgress = 'true';
                    card.dataset.can        = 'true';
                    card.classList.remove('kc-card--locked');
                }
            }
        }
        this.elTestView.style.display  = 'none';
        this.elCardsView.style.display = '';
        this.catId = this.catSlug = null;
        this.isCompleted = false;
    }


    async _onStartClick() {
        const url = URLS.start.replace('SLUG', this.catSlug);
        const res = await this._post(url, {});
        if (!res) return;

        if (res.success) {
            this._showScreen('question');
            await this._loadQuestion();
        } else if (res.error === 'use_resume') {
            await this._resume();
        } else {
            // Сервер отказал — блокируем карточку и возвращаемся
            const card = document.querySelector(`.kc-card[data-id="${this.catId}"]`);
            if (card) {
                card.classList.add('kc-card--locked');
                card.dataset.can = 'false';
            }
            this._onBackClick();
        }
    }

    async _resume() {
        const url = URLS.resume.replace('SLUG', this.catSlug);
        const res = await this._post(url, {});
        if (!res) return;

        if (res.success) {
            this._showScreen('question');
            await this._loadQuestion();
        } else {
            this._onBackClick();
        }
    }


    async _loadQuestion() {
        const res = await this._get(URLS.question + '?category_id=' + this.catId);
        if (!res) return;

        if (res.finished) { await this._complete(); return; }
        if (!res.success) { console.error(res.error); return; }

        const q       = res.question;
        this.qId      = q.id;
        this.qType    = q.type;
        this.qMulti   = q.multiple;
        this.isLast   = res.is_last;

        const pct = Math.round(q.number / q.total * 100);
        this.elProgLabel.textContent = `Вопрос ${q.number} из ${q.total}`;
        this.elProgPct.textContent   = pct + '%';
        this.elProgFill.style.width  = pct + '%';
        this.elQText.textContent     = q.text;

        this._renderAttachments(q.attachments || []);

        this.elAnswerArea.innerHTML  = '';
        this.elNextBtn.disabled      = true;
        this.elNextBtn.textContent   = this.isLast ? 'Завершить' : 'Далее';

        if (q.type === 'text') {
            this._renderTextAnswer();
        } else {
            this._renderChoiceAnswer(q.options, q.multiple);
        }
    }

    _renderTextAnswer() {
        const ta = document.createElement('textarea');
        ta.className   = 'kc-textarea';
        ta.placeholder = 'Введите ваш ответ...';
        ta.addEventListener('input', () => {
            this.elNextBtn.disabled = !ta.value.trim();
        });
        this.elAnswerArea.appendChild(ta);
        ta.focus();
    }

    _renderChoiceAnswer(options, multiple) {
        const wrap  = document.createElement('div');
        wrap.className = 'kc-options';
        const iType = multiple ? 'checkbox' : 'radio';

        options.forEach(opt => {
            const lbl = document.createElement('label');
            lbl.className = 'kc-option';

            const inp = document.createElement('input');
            inp.type  = iType;
            inp.name  = 'kc_opt';
            inp.value = opt.id;
            inp.addEventListener('change', () => {
                wrap.querySelectorAll('.kc-option').forEach(l => {
                    l.classList.toggle('kc-option--sel', l.querySelector('input').checked);
                });
                this.elNextBtn.disabled = !wrap.querySelector('input:checked');
            });

            lbl.appendChild(inp);
            lbl.appendChild(document.createTextNode(' ' + opt.text));
            wrap.appendChild(lbl);
        });

        this.elAnswerArea.appendChild(wrap);
    }


    async _onNextClick() {
        if (this.elNextBtn.disabled) return;

        const payload = { category_id: this.catId, question_id: this.qId };

        if (this.qType === 'text') {
            const ta = this.elAnswerArea.querySelector('textarea');
            payload.answer_text = ta.value.trim();
        } else {
            const checked = this.elAnswerArea.querySelectorAll('input:checked');
            payload.option_ids = Array.from(checked).map(i => parseInt(i.value));
        }

        const res = await this._post(URLS.submit, payload);
        if (!res) return;

        if (res.success) {
            this.isLast ? await this._complete() : await this._loadQuestion();
        } else {
            console.error(res.error);
        }
    }


    async _complete() {
        await this._post(URLS.complete, { category_id: this.catId });

        const card = document.querySelector(`.kc-card[data-id="${this.catId}"]`);
        if (card) {
            card.classList.add('kc-card--locked');
            card.dataset.can        = 'false';
            card.dataset.inProgress = 'false';
        }

        this.isCompleted = true;
        this._showScreen('done');
    }


    _renderAttachments(attachments) {
        this.elAttach.innerHTML = '';
        attachments.forEach(a => {
            const link = document.createElement('a');
            link.href      = a.url;
            link.download  = a.name;
            link.className = 'kc-attach-card';
            link.innerHTML = `${SVG_ICONS[a.type] || SVG_ICONS.other}<span></span>`;
            link.querySelector('span').textContent = a.name;
            this.elAttach.appendChild(link);
        });
    }


    _showScreen(name) {
        const map = { start: 'scrStart', question: 'scrQuestion', done: 'scrDone' };
        Object.values(map).forEach(id => {
            document.getElementById(id).classList.remove('kc-screen--on');
        });
        document.getElementById(map[name]).classList.add('kc-screen--on');
    }


    _csrf() {
        const c = document.cookie.split(';').find(s => s.trim().startsWith('csrftoken='));
        return c ? c.trim().split('=')[1] : '';
    }

    async _get(url) {
        try {
            return await (await fetch(url)).json();
        } catch (e) {
            console.error('[KnowledgeCheck] GET error:', e);
            return null;
        }
    }

    async _post(url, data) {
        try {
            return await (await fetch(url, {
                method:  'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this._csrf() },
                body:    JSON.stringify(data),
            })).json();
        } catch (e) {
            console.error('[KnowledgeCheck] POST error:', e);
            return null;
        }
    }
}



document.addEventListener('DOMContentLoaded', () => {
    new KnowledgeCheck();
});

})();