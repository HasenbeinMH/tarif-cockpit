/* Karte 2: tarif-cockpit-analyse-card. Auswertung (z. B. Gas witterungsbereinigt): Kennwert, Vergleich, Kacheln, Verlauf.
   Die Felder entsprechen dem früheren Block "analysis" der Karte 1, hier auf oberster Ebene. Die Karte rechnet nichts (Regel 2). */
(() => {
  const TC = window.TarifCockpit;
  const { esc } = TC;

  class TarifCockpitAnalyseCard extends TC.BaseCard {
    static getConfigElement() { return document.createElement('tarif-cockpit-analyse-card-editor'); }

    static getStubConfig(hass) { return TC.analyseStub ? TC.analyseStub(hass) : {}; }

    getCardSize() { return 7; }

    setConfig(c) {
      if (!c || typeof c !== 'object') throw new Error('tarif-cockpit-analyse-card: Konfiguration fehlt');
      this._c = c;
      this._last = null;
      this._build();
      this._render();
      this._afterHass();
    }

    _afterHass() { if (this._c) TC.loadHistory(this, this._c); }

    _render() {
      if (!this._prepare()) return;
      const t = TC.T;
      const c = this._c;
      const sub = c.subtitle ? `<small>${esc(c.subtitle)}</small>` : '';
      const header = this._header(c.icon || 'mdi:chart-bell-curve-cumulative', c.title || t('an.title'), sub, '');
      const any = ['kennwert', 'consumption', 'temperature', 'degree_days'].some((k) => c[k]) || (Array.isArray(c.extras) && c.extras.length);
      if (!any) {
        this._put(`${header}<div class="setup">${t('setup.analyse')}</div>`);
        return;
      }
      this._put(header + TC.analysisHtml(c, this._h, this._hist, c.label || t('an.kennwert'), ''));
    }
  }

  if (!customElements.get('tarif-cockpit-analyse-card')) customElements.define('tarif-cockpit-analyse-card', TarifCockpitAnalyseCard);
  window.customCards = window.customCards || [];
  if (!window.customCards.some((x) => x.type === 'tarif-cockpit-analyse-card')) {
    window.customCards.push({
      type: 'tarif-cockpit-analyse-card',
      name: TC.T('pick.analyse.name'),
      description: TC.T('pick.analyse.desc'),
      preview: false,
    });
  }
})();
