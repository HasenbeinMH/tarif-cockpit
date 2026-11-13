/* Gemeinsame Grundlage beider Karten: Shadow-DOM, Farbschema, schmale Darstellung, Tipp auf Entitäten öffnet den Dialog. */
(() => {
  const TC = window.TarifCockpit;

  TC.BaseCard = class extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: 'open' });
    }

    set hass(h) {
      this._h = h;
      this._render();
      this._afterHass();
    }

    _afterHass() {}

    _build() {
      this.shadowRoot.innerHTML = `<style>${TC.CSS}</style><ha-card><div class="wrap" id="w"></div></ha-card>`;
      this._w = this.shadowRoot.getElementById('w');
      // Tipp auf ein Element mit data-entity öffnet den Dialog der Entität (z. B. Datums-Helfer des Zeitraums)
      this._w.addEventListener('click', (e) => {
        const t = e.target.closest && e.target.closest('[data-entity]');
        if (t) this.dispatchEvent(new CustomEvent('hass-more-info', { detail: { entityId: t.getAttribute('data-entity') }, bubbles: true, composed: true }));
      });
      if (typeof ResizeObserver !== 'undefined') {
        if (this._ro) this._ro.disconnect();
        this._ro = new ResizeObserver((e) => {
          const narrow = e[0].contentRect.width < 420;
          this.shadowRoot.querySelector('ha-card').classList.toggle('narrow', narrow);
        });
        this._ro.observe(this);
      }
    }

    connectedCallback() { if (this._ro && this._w) this._ro.observe(this); }

    disconnectedCallback() { if (this._ro) this._ro.disconnect(); }

    // Vor jedem Rendern: Sprache/Format aus hass, Farbschema als Attribut
    _prepare() {
      if (!this._c || !this._w || !this._h) return false;
      TC.useHass(this._h);
      const t = TC.resolveTheme(this._c, this._h);
      if (this.getAttribute('data-theme') !== t) this.setAttribute('data-theme', t);
      return true;
    }

    _put(html) {
      if (html !== this._last) { this._w.innerHTML = html; this._last = html; }
    }

    _header(icon, title, sub, right) {
      const { esc, INFO } = TC;
      return `<header><div class="title"><span class="ico" style="--c:${INFO}"><ha-icon icon="${esc(icon)}"></ha-icon></span><div>${esc(title)}${sub || ''}</div></div>${right || ''}</header>`;
    }
  };
})();
