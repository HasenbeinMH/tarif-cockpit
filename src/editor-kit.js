/* Editor-Baukasten: Reiter "Assistent" (Schritt für Schritt) und "Alle Felder" (Formular von Home Assistant).
   Nach energy-cockpit/src/editor-kit.js, MIT License, Copyright (c) 2026 Musicmaker3112. Angepasst: Texte über TC.T,
   leere Abschnitte werden vor dem Speichern entfernt. */
(() => {
  const TC = window.TarifCockpit;

  // ha-form ist in Home Assistant nicht immer geladen: über die Karten-Helfer nachladen
  TC.ensureForm = async () => {
    if (customElements.get('ha-form')) return true;
    try {
      const h = await window.loadCardHelpers();
      const c = await h.createCardElement({ type: 'entities', entities: [] });
      if (c && c.constructor && c.constructor.getConfigElement) await c.constructor.getConfigElement();
    } catch (e) { /* weiter mit Wartezeit */ }
    await Promise.race([customElements.whenDefined('ha-form'), new Promise((r) => setTimeout(r, 4000))]);
    return !!customElements.get('ha-form');
  };

  // def: { needsSetup(config), steps(), form(), extra?(root, api) }
  TC.defineEditor = (tag, def) => {
    class Editor extends HTMLElement {
      setConfig(c) {
        const s = JSON.stringify(c || {});
        if (this._last === s) return; // eigene Änderung: nicht neu aufbauen (Eingabefokus bleibt erhalten)
        this._c = JSON.parse(s);
        if (!this._tab) this._tab = def.integTab && this._c.integration ? 'integ' : def.needsSetup(this._c) ? 'wiz' : 'form';
        this._wiz = null;
        this._render();
      }
      set hass(h) {
        const first = !this._hass;
        this._hass = h;
        TC.useHass(h);
        if (this._wiz) this._wiz.setHass(h);
        if (this._form) this._form.hass = h;
        // Mit Integration und noch leerer Karte: gleich den Reiter "Integration" zeigen
        if (first && this._c && def.integTab && TC.integ && TC.integ.available(h) && def.needsSetup(this._c) && !this._c.integration) this._tab = 'integ';
        // Sprache steht erst mit hass fest: Reiter einmal neu beschriften
        if (first && this._c) this._render();
      }
      _emit(cfg) {
        const out = TC.prune(JSON.parse(JSON.stringify(cfg)));
        if (this._c && this._c.type) out.type = this._c.type;
        this._c = out;
        this._last = JSON.stringify(out);
        this.dispatchEvent(new CustomEvent('config-changed', { detail: { config: JSON.parse(this._last) }, bubbles: true, composed: true }));
      }
      _render() {
        if (!this._root) { this._root = document.createElement('div'); this.appendChild(this._root); }
        const root = this._root;
        const t = TC.T;
        root.innerHTML = '';
        const bar = document.createElement('div');
        bar.style.cssText = 'display:flex;gap:6px;margin-bottom:10px';
        const tabs = [['wiz', t('ed.tab_wiz')], ['form', t('ed.tab_form')]];
        if (def.integTab && (this._c.integration || (TC.integ && TC.integ.available(this._hass)))) tabs.unshift(['integ', t('ed.tab_integ')]);
        tabs.forEach(([k, txt]) => {
          const b = document.createElement('button');
          b.type = 'button';
          b.textContent = txt;
          b.dataset.tab = k;
          b.style.cssText = 'cursor:pointer;padding:8px 14px;border-radius:8px;font:inherit;border:1px solid var(--divider-color,#555);background:' + (this._tab === k ? 'var(--primary-color,#03a9f4)' : 'var(--secondary-background-color,#222)') + ';color:' + (this._tab === k ? 'var(--text-primary-color,#fff)' : 'var(--primary-text-color,#fff)');
          b.addEventListener('click', () => { this._tab = k; this._wiz = null; this._form = null; this._render(); });
          bar.appendChild(b);
        });
        root.appendChild(bar);
        if (this._tab === 'integ' && def.integTab) {
          def.integTab(root, {
            config: () => this._c, hass: () => this._hass, emit: (c) => this._emit(c), rerender: () => this._render(),
            setTab: (k) => { this._tab = k; this._wiz = null; this._form = null; this._render(); },
          });
          return;
        }
        if (this._tab === 'wiz') {
          this._wiz = TC.createWizard({
            steps: def.steps(), hass: this._hass, config: this._c,
            onChange: (cfg) => this._emit(cfg),
            done: () => { this._tab = 'form'; this._wiz = null; this._render(); },
          });
          root.appendChild(this._wiz.el);
          return;
        }
        if (def.extra) def.extra(root, { config: () => this._c, hass: () => this._hass, emit: (c) => { this._emit(c); this._render(); } });
        const holder = document.createElement('div');
        root.appendChild(holder);
        holder.textContent = t('ed.loading');
        TC.ensureForm().then((ok) => {
          holder.textContent = '';
          if (!ok) { holder.textContent = t('ed.noform'); return; }
          const f = def.form();
          const form = document.createElement('ha-form');
          form.schema = f.schema;
          form.computeLabel = f.computeLabel;
          if (f.computeHelper) form.computeHelper = f.computeHelper;
          form.data = this._c;
          if (this._hass) form.hass = this._hass;
          form.addEventListener('value-changed', (ev) => { ev.stopPropagation(); this._emit(ev.detail.value); });
          this._form = form;
          holder.appendChild(form);
        });
      }
    }
    if (!customElements.get(tag)) customElements.define(tag, Editor);
  };

  // Hilfen für ha-form-Schemata
  TC.sf = {
    txt: (name) => ({ name, selector: { text: {} } }),
    icon: (name) => ({ name, selector: { icon: {} } }),
    ent: (name, domains) => ({ name, selector: { entity: domains ? { domain: domains } : {} } }),
    numb: (name, min, max, step) => ({ name, selector: { number: { min, max, step: step || 1, mode: 'box' } } }),
    bool: (name) => ({ name, selector: { boolean: {} } }),
    sec: (name, title, schema) => ({ type: 'expandable', name, title, schema }),
    theme: (name) => ({ name, selector: { select: { mode: 'dropdown', options: TC.THEME_KEYS.map((k) => ({ value: k, label: TC.T('th.' + k) })) } } }),
  };
})();
