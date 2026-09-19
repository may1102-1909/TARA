/**
 * React Bits PromptBar Vanilla Component
 * Implements the full React Bits PromptBar specification in pure Vanilla JS & CSS.
 * Provides SVG path morphing (Arrow ↔ Stop Square with squash & tilt),
 * Canvas drifting particle sparks on Max effort, interactive menus (@, /, models, effort slider),
 * dynamic auto-growing textarea, file attachment chips, and voice dictation.
 */

(function () {
  const ARROW_UP = [12, 4.5, 18.5, 11, 14.25, 11, 14.25, 19.5, 9.75, 19.5, 9.75, 11, 5.5, 11];
  const SQUARE = [12, 6, 18, 6, 18, 12, 18, 18, 6, 18, 6, 12, 6, 6];
  const LINE = 20;
  const EDGE = 11;

  const mix = (a, b, t) => a + (b - a) * t;
  const pathAt = (a, b, t) => {
    let d = '';
    for (let i = 0; i < a.length; i += 2) {
      d += `${i ? 'L' : 'M'}${mix(a[i], b[i], t).toFixed(2)} ${mix(a[i + 1], b[i + 1], t).toFixed(2)}`;
    }
    return `${d}Z`;
  };

  const ICONS = {
    plus: `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>`,
    arrowDown: `<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><polyline points="6 9 12 15 18 9"></polyline></svg>`,
    sparkles: `<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 2L14.4 7.6L20 10L14.4 12.4L12 18L9.6 12.4L4 10L9.6 7.6z"></path></svg>`,
    mic: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="23"></line><line x1="8" y1="23" x2="16" y2="23"></line></svg>`,
    attachment: `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path></svg>`,
    globe: `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>`,
    file: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>`,
    code: `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>`,
    check: `<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`,
    cancel: `<svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`,
    help: `<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>`,
  };

  const DEFAULT_SOURCES = [
    { key: 'files', name: 'Attach Workspace File', description: 'Select from workspace or disk', icon: ICONS.attachment, attach: true },
    { key: 'active_file', name: 'Current Editor File', description: 'Attach open tab in Monaco', icon: ICONS.file },
    { key: 'web', name: 'Web Search', description: 'Live Google & docs search', icon: ICONS.globe },
    { key: 'sast', name: 'Security Audit', description: 'Scan OWASP Top 10 vulnerabilities', icon: ICONS.code },
  ];

  const DEFAULT_COMMANDS = [
    { key: 'summarize', name: '/summarize', description: 'Digest workspace code and changes' },
    { key: 'refactor', name: '/refactor', description: 'Refactor selected module with best practices' },
    { key: 'test', name: '/test', description: 'Generate comprehensive pytest suite' },
    { key: 'sast', name: '/sast', description: 'Run Bandit & Flake8 SAST scan' },
    { key: 'explain', name: '/explain', description: 'Explain code architecture step-by-step' },
  ];

  const DEFAULT_MODELS = [
    { key: 'gemini-3.5-flash', name: 'Gemini 3.5 Flash', tag: 'Recommended' },
    { key: 'gemini-3.5-flash-lite', name: 'Gemini 3.5 Lite', tag: 'Fast' },
    { key: 'gemini-3.8-flash', name: 'Gemini 3.8 Flash', tag: 'Preview' },
  ];

  const DEFAULT_EFFORTS = ['Low', 'Medium', 'High', 'Extra', 'Max'];

  class PromptBarComponent {
    constructor(container, options = {}) {
      this.container = typeof container === 'string' ? document.querySelector(container) : container;
      if (!this.container) return;

      this.options = {
        placeholder: 'Ask TARA to inspect, edit, or generate code…',
        sources: DEFAULT_SOURCES,
        commands: DEFAULT_COMMANDS,
        models: DEFAULT_MODELS,
        efforts: DEFAULT_EFFORTS,
        defaultModel: 'gemini-3.5-flash',
        defaultEffort: 'High',
        sparkColor: '#b39dff',
        morphDuration: 240,
        squash: 0.12,
        tilt: 8,
        maxRows: 5,
        onSend: null,
        onStop: null,
        onAttach: null,
        ...options,
      };

      this.draft = '';
      this.attachments = [];
      this.modelKey = this.options.defaultModel;
      this.effortIndex = this.options.efforts.indexOf(this.options.defaultEffort);
      if (this.effortIndex < 0) this.effortIndex = 2;

      this.openMenu = null; // 'at' | 'slash' | 'model' | 'effort' | null
      this.menuActiveIndex = 0;
      this.busy = false;
      this.listening = false;
      this.morphProgress = 0; // 0 = arrow, 1 = stop square
      this.targetFile = 'main.py';

      this.initDOM();
      this.initEvents();
      this.initCanvasSparks();
      this.render();
    }

    initDOM() {
      this.container.innerHTML = `
        <div class="prompt-bar" id="pb-root">
          <!-- Floating Menu Popup -->
          <div class="prompt-bar__menu" id="pb-menu" style="display: none;"></div>

          <!-- Main Input Field Container -->
          <div class="prompt-bar__field" id="pb-field">
            <canvas class="prompt-bar__sparks" id="pb-canvas"></canvas>

            <!-- Attachment Chips -->
            <div class="prompt-bar__chips" id="pb-chips" style="display: none;"></div>

            <!-- Auto-growing Textarea -->
            <textarea
              class="prompt-bar__input"
              id="pb-input"
              rows="1"
              placeholder="${this.options.placeholder}"
              aria-label="Prompt"
            ></textarea>

            <!-- Bottom Action Bar -->
            <div class="prompt-bar__bar">
              <button type="button" class="prompt-bar__tool" id="pb-btn-plus" title="Add files and sources">
                ${ICONS.plus}
              </button>

              <button type="button" class="prompt-bar__pick" id="pb-btn-model" title="Choose AI model">
                <span id="pb-model-name">Gemini 3.5 Flash</span>
                ${ICONS.arrowDown}
              </button>

              <button type="button" class="prompt-bar__pick" id="pb-btn-effort" title="Set thinking effort">
                ${ICONS.sparkles}
                <span id="pb-effort-name">High</span>
              </button>

              <span class="prompt-bar__spacer"></span>

              <button type="button" class="prompt-bar__tool" id="pb-btn-mic" title="Dictate prompt">
                <span class="prompt-bar__eq" id="pb-eq" style="display: none;" aria-hidden="true">
                  <i></i><i></i><i></i>
                </span>
                <span id="pb-mic-icon">${ICONS.mic}</span>
              </button>

              <button type="button" class="prompt-bar__send" id="pb-btn-send" title="Send (Enter)">
                <svg class="prompt-bar__glyph" id="pb-glyph-svg" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linejoin="round">
                  <path id="pb-glyph-path" d="${pathAt(ARROW_UP, SQUARE, 0)}"></path>
                </svg>
              </button>
            </div>
          </div>

          <!-- Hidden File Upload Input -->
          <input type="file" id="pb-file-picker" multiple style="display: none;" />
        </div>
      `;

      this.rootEl = this.container.querySelector('#pb-root');
      this.menuEl = this.container.querySelector('#pb-menu');
      this.fieldEl = this.container.querySelector('#pb-field');
      this.canvasEl = this.container.querySelector('#pb-canvas');
      this.chipsEl = this.container.querySelector('#pb-chips');
      this.inputEl = this.container.querySelector('#pb-input');
      this.btnPlus = this.container.querySelector('#pb-btn-plus');
      this.btnModel = this.container.querySelector('#pb-btn-model');
      this.modelNameEl = this.container.querySelector('#pb-model-name');
      this.btnEffort = this.container.querySelector('#pb-btn-effort');
      this.effortNameEl = this.container.querySelector('#pb-effort-name');
      this.btnMic = this.container.querySelector('#pb-btn-mic');
      this.micIconEl = this.container.querySelector('#pb-mic-icon');
      this.eqEl = this.container.querySelector('#pb-eq');
      this.btnSend = this.container.querySelector('#pb-btn-send');
      this.glyphSvg = this.container.querySelector('#pb-glyph-svg');
      this.glyphPath = this.container.querySelector('#pb-glyph-path');
      this.filePicker = this.container.querySelector('#pb-file-picker');
    }

    initEvents() {
      // Auto-growing textarea
      this.inputEl.addEventListener('input', () => {
        this.draft = this.inputEl.value;
        this.adjustHeight();
        this.checkTokenTrigger();
        this.updateSendArmed();
      });

      // Keyboard navigation
      this.inputEl.addEventListener('keydown', (e) => this.handleKeyDown(e));

      // Buttons
      this.btnPlus.addEventListener('click', (e) => {
        e.stopPropagation();
        this.toggleMenu('at');
      });

      this.btnModel.addEventListener('click', (e) => {
        e.stopPropagation();
        this.toggleMenu('model');
      });

      this.btnEffort.addEventListener('click', (e) => {
        e.stopPropagation();
        this.toggleMenu('effort');
      });

      this.btnMic.addEventListener('click', (e) => {
        e.stopPropagation();
        this.toggleDictation();
      });

      this.btnSend.addEventListener('click', () => {
        if (this.busy) {
          this.stop();
        } else {
          this.send();
        }
      });

      // File picker
      this.filePicker.addEventListener('change', () => {
        const files = Array.from(this.filePicker.files || []);
        files.forEach((f) => this.addAttachment(f.name));
        this.filePicker.value = '';
      });

      // Outside click closes menus
      document.addEventListener('pointerdown', (e) => {
        if (!this.rootEl.contains(e.target)) {
          this.closeMenu();
        }
      });
    }

    adjustHeight() {
      this.inputEl.style.height = '0px';
      const max = LINE * this.options.maxRows;
      const scrollH = this.inputEl.scrollHeight;
      this.inputEl.style.height = `${Math.min(scrollH, max)}px`;
      this.inputEl.style.overflowY = scrollH > max ? 'auto' : 'hidden';
    }

    checkTokenTrigger() {
      const val = this.draft;
      const m = /(^|\s)([@/])([\w-]*)$/.exec(val);
      if (m) {
        const kind = m[2] === '@' ? 'at' : 'slash';
        this.query = m[3].toLowerCase();
        this.openMenu = kind;
        this.renderMenu();
      } else if (this.openMenu === 'at' || this.openMenu === 'slash') {
        this.closeMenu();
      }
    }

    updateSendArmed() {
      const canSend = this.draft.trim().length > 0 || this.attachments.length > 0;
      if (canSend || this.busy) {
        this.btnSend.removeAttribute('disabled');
        this.btnSend.setAttribute('data-armed', '');
      } else {
        this.btnSend.setAttribute('disabled', 'true');
        this.btnSend.removeAttribute('data-armed');
      }
    }

    setTargetFile(filename) {
      this.targetFile = filename;
      const targetDisplay = document.getElementById('copilot-target-display');
      if (targetDisplay) targetDisplay.textContent = filename;
    }

    setDraft(text) {
      this.draft = text;
      this.inputEl.value = text;
      this.adjustHeight();
      this.updateSendArmed();
      this.inputEl.focus();
    }

    addAttachment(name) {
      if (!this.attachments.includes(name)) {
        this.attachments.push(name);
        this.renderChips();
        this.updateSendArmed();
      }
    }

    removeAttachment(index) {
      this.attachments.splice(index, 1);
      this.renderChips();
      this.updateSendArmed();
    }

    renderChips() {
      if (this.attachments.length === 0) {
        this.chipsEl.style.display = 'none';
        this.chipsEl.innerHTML = '';
        return;
      }
      this.chipsEl.style.display = 'flex';
      this.chipsEl.innerHTML = this.attachments
        .map(
          (name, i) => `
          <span class="prompt-bar__chip">
            ${ICONS.file}
            <span class="prompt-bar__chip-name">${name}</span>
            <button type="button" class="prompt-bar__chip-x" data-index="${i}" title="Remove file">
              ${ICONS.cancel}
            </button>
          </span>
        `
        )
        .join('');

      this.chipsEl.querySelectorAll('.prompt-bar__chip-x').forEach((btn) => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          const idx = parseInt(btn.dataset.index, 10);
          this.removeAttachment(idx);
        });
      });
    }

    toggleMenu(kind) {
      if (this.openMenu === kind) {
        this.closeMenu();
      } else {
        this.openMenu = kind;
        this.query = '';
        this.menuActiveIndex = 0;
        this.renderMenu();
      }
    }

    closeMenu() {
      this.openMenu = null;
      this.menuEl.style.display = 'none';
      this.btnPlus.removeAttribute('data-on');
      this.btnModel.removeAttribute('data-on');
      this.btnEffort.removeAttribute('data-on');
    }

    renderMenu() {
      if (!this.openMenu) {
        this.menuEl.style.display = 'none';
        return;
      }

      this.menuEl.style.display = 'block';
      this.menuEl.setAttribute('data-kind', this.openMenu);

      if (this.openMenu === 'at') {
        this.btnPlus.setAttribute('data-on', '');
        const items = this.options.sources.filter((s) => !this.query || s.name.toLowerCase().includes(this.query));
        this.menuEl.innerHTML = items
          .map(
            (item, i) => `
            <button type="button" class="prompt-bar__row" data-key="${item.key}" aria-selected="${i === this.menuActiveIndex}">
              <span class="prompt-bar__row-icon">${item.icon}</span>
              <span class="prompt-bar__row-name">${item.name}</span>
              <span class="prompt-bar__row-desc">${item.description}</span>
            </button>
          `
          )
          .join('');

        this.attachRowEvents(items, (selected) => {
          if (selected.attach) {
            this.filePicker.click();
          } else if (selected.key === 'active_file') {
            this.addAttachment(this.targetFile || 'main.py');
          } else {
            this.setDraft(`${this.draft}@${selected.name} `);
          }
          this.closeMenu();
        });
      } else if (this.openMenu === 'slash') {
        const items = this.options.commands.filter((c) => !this.query || c.name.toLowerCase().includes(this.query));
        this.menuEl.innerHTML = items
          .map(
            (item, i) => `
            <button type="button" class="prompt-bar__row" data-key="${item.key}" aria-selected="${i === this.menuActiveIndex}">
              <span class="prompt-bar__row-icon">${ICONS.code}</span>
              <span class="prompt-bar__row-name">${item.name}</span>
              <span class="prompt-bar__row-desc">${item.description}</span>
            </button>
          `
          )
          .join('');

        this.attachRowEvents(items, (selected) => {
          this.setDraft(`${selected.name} `);
          this.closeMenu();
        });
      } else if (this.openMenu === 'model') {
        this.btnModel.setAttribute('data-on', '');
        this.menuEl.innerHTML = this.options.models
          .map(
            (m, i) => `
            <button type="button" class="prompt-bar__row" data-key="${m.key}" aria-selected="${i === this.menuActiveIndex}">
              <span class="prompt-bar__row-name">${m.name}</span>
              <span class="prompt-bar__row-tag">${m.tag}</span>
              <span class="prompt-bar__row-check" ${m.key === this.modelKey ? 'data-on' : ''}>
                ${ICONS.check}
              </span>
            </button>
          `
          )
          .join('');

        this.attachRowEvents(this.options.models, (selected) => {
          this.modelKey = selected.key;
          this.modelNameEl.textContent = selected.name;
          this.closeMenu();
        });
      } else if (this.openMenu === 'effort') {
        this.btnEffort.setAttribute('data-on', '');
        const level = this.options.efforts[this.effortIndex];
        const stepPct = (this.effortIndex / (this.options.efforts.length - 1)) * 100;

        this.menuEl.innerHTML = `
          <div class="prompt-bar__effort-head">
            <span class="prompt-bar__effort-title">Effort</span>
            <span class="prompt-bar__effort-level">${level}</span>
            <span class="prompt-bar__effort-help" title="Higher effort gives the Antigravity agent longer reasoning depth">${ICONS.help}</span>
          </div>
          <div class="prompt-bar__effort-ends">
            <span>Faster</span>
            <span>Smarter</span>
          </div>
          <div class="prompt-bar__effort-track" id="pb-track" style="--pb-effort-x: ${stepPct}%; --pb-effort-fill: ${stepPct}%;">
            <span class="prompt-bar__effort-fill" style="width: ${stepPct}%;"></span>
            ${this.options.efforts.map((_, i) => `<i class="prompt-bar__effort-dot" style="left: ${(i / (this.options.efforts.length - 1)) * 100}%;"></i>`).join('')}
            <span class="prompt-bar__effort-thumb" style="left: ${stepPct}%;"></span>
          </div>
        `;

        const track = this.menuEl.querySelector('#pb-track');
        if (track) {
          const updateFromPointer = (e) => {
            const rect = track.getBoundingClientRect();
            const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            const newIndex = Math.round(ratio * (this.options.efforts.length - 1));
            this.setEffort(newIndex);
          };

          track.addEventListener('pointerdown', (e) => {
            updateFromPointer(e);
            const onMove = (me) => updateFromPointer(me);
            const onUp = () => {
              window.removeEventListener('pointermove', onMove);
              window.removeEventListener('pointerup', onUp);
            };
            window.addEventListener('pointermove', onMove);
            window.addEventListener('pointerup', onUp);
          });
        }
      }
    }

    attachRowEvents(items, callback) {
      const rows = this.menuEl.querySelectorAll('.prompt-bar__row');
      rows.forEach((row, i) => {
        row.addEventListener('click', (e) => {
          e.stopPropagation();
          callback(items[i]);
        });
        row.addEventListener('pointerenter', () => {
          this.menuActiveIndex = i;
          rows.forEach((r, idx) => r.setAttribute('aria-selected', idx === i));
        });
      });
    }

    setEffort(index) {
      this.effortIndex = Math.max(0, Math.min(this.options.efforts.length - 1, index));
      const level = this.options.efforts[this.effortIndex];
      this.effortNameEl.textContent = level;

      const isMax = this.effortIndex === this.options.efforts.length - 1;
      if (isMax) {
        this.rootEl.setAttribute('data-max', '');
        this.fieldEl.setAttribute('data-max', '');
        this.btnEffort.setAttribute('data-max', '');
      } else {
        this.rootEl.removeAttribute('data-max');
        this.fieldEl.removeAttribute('data-max');
        this.btnEffort.removeAttribute('data-max');
      }

      if (this.openMenu === 'effort') {
        this.renderMenu();
      }
    }

    handleKeyDown(e) {
      if (this.openMenu && (this.openMenu === 'at' || this.openMenu === 'slash' || this.openMenu === 'model')) {
        const rows = Array.from(this.menuEl.querySelectorAll('.prompt-bar__row'));
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          this.menuActiveIndex = (this.menuActiveIndex + 1) % rows.length;
          rows.forEach((r, i) => r.setAttribute('aria-selected', i === this.menuActiveIndex));
          return;
        }
        if (e.key === 'ArrowUp') {
          e.preventDefault();
          this.menuActiveIndex = (this.menuActiveIndex - 1 + rows.length) % rows.length;
          rows.forEach((r, i) => r.setAttribute('aria-selected', i === this.menuActiveIndex));
          return;
        }
        if (e.key === 'Enter' || e.key === 'Tab') {
          e.preventDefault();
          if (rows[this.menuActiveIndex]) {
            rows[this.menuActiveIndex].click();
          }
          return;
        }
        if (e.key === 'Escape') {
          e.preventDefault();
          this.closeMenu();
          return;
        }
      }

      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.send();
      }
    }

    initCanvasSparks() {
      const canvas = this.canvasEl;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      let w = 0;
      let h = 0;
      const parts = [];

      const resize = () => {
        const rect = canvas.getBoundingClientRect();
        const dpr = Math.min(2, window.devicePixelRatio || 1);
        w = rect.width;
        h = rect.height;
        canvas.width = Math.round(w * dpr);
        canvas.height = Math.round(h * dpr);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      };

      const spawn = (burst) => {
        parts.push({
          x: Math.random() * w,
          y: burst ? h * (0.2 + Math.random() * 0.8) : h + 3,
          r: 0.9 + Math.random() * 1.1,
          vy: -(6 + Math.random() * 8),
          sway: (Math.random() - 0.5) * 8,
          phase: Math.random() * Math.PI * 2,
          life: burst ? Math.random() * 1.2 : 0,
          span: 2.2 + Math.random() * 2.2,
        });
      };

      let last = performance.now();
      let due = 0;

      const loop = (now) => {
        const isMax = this.effortIndex === this.options.efforts.length - 1;
        if (isMax) {
          const dt = Math.min(0.05, (now - last) / 1000);
          last = now;
          due += dt;
          while (due > 0.14) {
            due -= 0.14;
            if (parts.length < 32) spawn(false);
          }

          ctx.clearRect(0, 0, w, h);
          ctx.fillStyle = this.options.sparkColor;
          ctx.shadowColor = this.options.sparkColor;
          ctx.shadowBlur = 6;

          for (let i = parts.length - 1; i >= 0; i--) {
            const p = parts[i];
            p.life += dt;
            if (p.life > p.span) {
              parts.splice(i, 1);
              continue;
            }
            const k = p.life / p.span;
            const twinkle = 0.7 + 0.3 * Math.sin(now / 160 + p.phase);
            p.y += p.vy * dt;
            ctx.globalAlpha = Math.sin(k * Math.PI) * 0.9 * twinkle;
            ctx.beginPath();
            ctx.arc(p.x + Math.sin(now / 900 + p.phase) * p.sway, p.y, p.r * twinkle, 0, Math.PI * 2);
            ctx.fill();
          }
        } else {
          ctx.clearRect(0, 0, w, h);
          parts.length = 0;
        }
        requestAnimationFrame(loop);
      };

      resize();
      window.addEventListener('resize', resize);
      for (let i = 0; i < 20; i++) spawn(true);
      requestAnimationFrame(loop);
    }

    setBusy(busy) {
      this.busy = Boolean(busy);
      const target = this.busy ? 1 : 0;
      const start = this.morphProgress;
      const duration = this.options.morphDuration;
      const startTime = performance.now();

      if (this.busy) {
        this.rootEl.setAttribute('data-busy', '');
        this.btnSend.setAttribute('data-busy', '');
        this.btnSend.setAttribute('title', 'Stop response (Esc)');
      } else {
        this.rootEl.removeAttribute('data-busy');
        this.btnSend.removeAttribute('data-busy');
        this.btnSend.setAttribute('title', 'Send (Enter)');
      }

      const animateMorph = (now) => {
        const elapsed = now - startTime;
        const progress = Math.min(1, elapsed / duration);
        // ease in-out
        const ease = progress < 0.5 ? 2 * progress * progress : -1 + (4 - 2 * progress) * progress;
        this.morphProgress = start + (target - start) * ease;

        const path = pathAt(ARROW_UP, SQUARE, this.morphProgress);
        this.glyphPath.setAttribute('d', path);

        const goo = Math.sin(this.morphProgress * Math.PI);
        const sx = 1 - this.options.squash * goo;
        const rot = (this.busy ? 1 : -1) * this.options.tilt * goo;
        this.glyphSvg.style.transform = goo ? `rotate(${rot}deg) scale(${sx}, ${1 / sx})` : '';

        if (progress < 1) {
          requestAnimationFrame(animateMorph);
        } else {
          this.morphProgress = target;
          this.glyphPath.setAttribute('d', pathAt(ARROW_UP, SQUARE, target));
          this.glyphSvg.style.transform = '';
        }
      };

      requestAnimationFrame(animateMorph);
      this.updateSendArmed();
    }

    toggleDictation() {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) {
        alert('Voice dictation is not supported in this browser. Please use Chrome or Edge.');
        return;
      }

      if (this.listening) {
        if (this.recognition) this.recognition.stop();
        this.setListening(false);
        return;
      }

      try {
        this.recognition = new SpeechRecognition();
        this.recognition.continuous = false;
        this.recognition.interimResults = false;
        this.recognition.lang = 'en-US';

        this.recognition.onstart = () => this.setListening(true);
        this.recognition.onresult = (e) => {
          const transcript = e.results[0][0].transcript;
          if (transcript) {
            this.setDraft(this.draft.trim() ? `${this.draft.trim()} ${transcript}` : transcript);
          }
        };
        this.recognition.onerror = () => this.setListening(false);
        this.recognition.onend = () => this.setListening(false);

        this.recognition.start();
      } catch (err) {
        console.warn('Dictation error:', err);
        this.setListening(false);
      }
    }

    setListening(listening) {
      this.listening = Boolean(listening);
      if (this.listening) {
        this.btnMic.setAttribute('data-on', '');
        this.eqEl.style.display = 'flex';
        this.micIconEl.style.display = 'none';
        this.inputEl.placeholder = 'Listening…';
      } else {
        this.btnMic.removeAttribute('data-on');
        this.eqEl.style.display = 'none';
        this.micIconEl.style.display = 'block';
        this.inputEl.placeholder = this.options.placeholder;
      }
    }

    send() {
      const text = this.draft.trim();
      const hasFiles = this.attachments.length > 0;
      if (!text && !hasFiles) return;

      const payload = {
        prompt: text,
        attachments: [...this.attachments],
        model: this.modelKey,
        effort: this.options.efforts[this.effortIndex],
        targetFile: this.targetFile,
      };

      if (typeof this.options.onSend === 'function') {
        this.options.onSend(text, payload);
      }

      this.draft = '';
      this.inputEl.value = '';
      this.attachments = [];
      this.renderChips();
      this.adjustHeight();
      this.closeMenu();
      this.updateSendArmed();
    }

    stop() {
      if (typeof this.options.onStop === 'function') {
        this.options.onStop();
      }
      this.setBusy(false);
    }

    render() {
      this.setEffort(this.effortIndex);
      this.adjustHeight();
      this.updateSendArmed();
    }
  }

  // Export to window
  window.PromptBarComponent = PromptBarComponent;
})();
