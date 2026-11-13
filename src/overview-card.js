/* Karte 1: tarif-cockpit-card. Kacheln je Medium (Strom/Gas/Wasser) mit Urteil, Betrag, vier Balken und passendem Abschlag.
   Sensor-Modus: Die Karte rechnet keine Prognose, sie bildet nur das Urteil aus Abschlag, Hochrechnung und Toleranz (Regel 2). */
(() => {
  const TC = window.TarifCockpit;
  const { esc } = TC;

  class TarifCockpitCard extends TC.BaseCard {
    static getConfigElement() { return document.createElement('tarif-cockpit-card-editor'); }

    // Vorschläge aus den vorhandenen Entitäten, keine fest eingebauten Namen (Regel 6)
    static getStubConfig(hass) { return TC.overviewStub ? TC.overviewStub(hass) : {}; }

    getCardSize() { return 9; }

    setConfig(c) {
      if (!c || typeof c !== 'object') throw new Error('tarif-cockpit: Konfiguration fehlt');
      this._c = c;
      this._last = null;
      this._build();
      this._render();
      this._afterHass();
    }

    _afterHass() {
      if (this._c && this._c.analysis) TC.loadHistory(this, this._c.analysis);
    }

    // Rechnet ein Medium: Differenz = Abschläge im Jahr minus Hochrechnung (positiv = Guthaben). Unverändert seit v0.3.
    _calc(key, m) {
      const h = this._h;
      const months = Number(m.months) > 0 ? Number(m.months) : 12;
      const cost = TC.num(h, m.cost), paid = TC.num(h, m.advance_paid), fc = TC.num(h, m.forecast_cost);
      const monthly = TC.num(h, m.advance), kwh = TC.num(h, m.forecast_kwh);
      const yearAdv = monthly === null ? null : monthly * months;
      const ok = fc !== null && yearAdv !== null;
      const diff = ok ? yearAdv - fc : null;
      const tol = (typeof this._c.tolerance_pct === 'number' ? this._c.tolerance_pct : 5) / 100;
      let verdict = null;
      if (ok) verdict = Math.abs(diff) < yearAdv * tol ? 'ok' : diff > 0 ? 'back' : 'extra';
      return { key, months, cost, paid, fc, monthly, kwh, yearAdv, diff, verdict, fitting: fc === null ? null : Math.ceil(fc / months) };
    }

    _panel(calc, m) {
      const { nf, eur, T: t, OK, BAD, INFO, DARK } = TC;
      const cur = TC.cur();
      const def = TC.MEDIA[calc.key];
      const c = TC.rgbOf(m.color, def.color);
      const q = calc.verdict === 'back' ? OK : calc.verdict === 'extra' ? BAD : INFO;
      // Farbe der Abschlagsbalken: Standard grün, mit advance_color je Medium oder für die ganze Karte überschreibbar
      const advOwn = TC.rgbOf(m.advance_color, null) || TC.rgbOf(this._c.advance_color, null);
      const adv = advOwn || OK, advd = advOwn || DARK[OK];
      const label = calc.verdict ? t('verdict.' + calc.verdict) : t('verdict.none');
      const cap = calc.verdict ? t('cap.' + calc.verdict) : '';
      const max = Math.max(calc.cost || 0, calc.paid || 0, calc.fc || 0, calc.yearAdv || 0, 1);
      const row = (name, v, isAdv, extra) => {
        if (v === null) return '';
        return `<div class="row"><div class="rh"><span>${esc(name)}</span><b>${eur(v)} ${esc(cur)}${extra ? ' · ' + extra : ''}</b></div><div class="bar"><i class="${isAdv ? 'adv' : ''}" style="width:${Math.max(1, Math.min(100, (v / max) * 100))}%"></i></div></div>`;
      };
      // Hat das Medium einen eigenen Beginn, der vom Gesamtzeitraum abweicht, steht er in der Kachel
      const own = TC.date(this._h, m.start), all = TC.date(this._h, this._c.period_start);
      const startTxt = own && (!all || own.getTime() !== all.getTime()) ? t('lbl.from', { d: TC.fd(own) }) : '';
      const kwhTxt = calc.kwh === null ? '' : nf(calc.kwh, 0) + ' kWh';
      const sign = calc.diff === null ? '' : calc.verdict === 'ok' ? (calc.diff >= 0 ? '+' : '−') : '';
      const big = calc.diff === null
        ? `<span class="num">—</span>`
        : `<span class="num">${sign}${eur(Math.abs(calc.diff))}</span><span class="unit">${esc(cur)}</span><small>${esc(cap)}</small>`;
      const hint = calc.fitting === null || calc.monthly === null ? ''
        : `<div class="hint">${t('hint.fitting', { fit: nf(calc.fitting, 0) + ' ' + esc(cur), cur: nf(calc.monthly, 0) + ' ' + esc(cur) })}</div>`;
      const old = m.stale_hint ? `<div class="warn">${esc(m.stale_hint)}</div>` : '';
      const advTxt = m.advance && calc.monthly !== null ? t('lbl.advance', { v: nf(calc.monthly, 0) + ' ' + cur }) : '';
      // Nicht konfigurierte Zeilen entfallen; konfigurierte, aber nicht verfügbare Sensoren zeigen weiter "—" im Urteil
      return `<div class="panel" style="--c:${c};--q:${q};--qd:${DARK[q]};--adv:${adv};--advd:${advd}">
        <div class="ph"><span class="lbl"><i></i>${esc((m.name || t('media.' + calc.key)) + advTxt + startTxt)}</span><span class="pill">${esc(label)}</span></div>
        <div class="big">${big}</div>
        <div class="rows">
          ${row(t('row.cost'), calc.cost, false, '')}
          ${row(t('row.paid'), calc.paid, true, '')}
          ${row(t('row.fc'), calc.fc, false, kwhTxt)}
          ${row(t('row.year', { n: calc.months }), calc.yearAdv, true, '')}
        </div>${hint}${old}
      </div>`;
    }

    _footer() {
      const list = Array.isArray(this._c.footer) ? this._c.footer : [];
      if (!list.length) return '';
      const h = this._h;
      const tiles = list.map((f) => {
        if (!f || !f.entity) return '';
        const s = h && h.states[f.entity];
        const unit = f.unit !== undefined ? f.unit : (s && s.attributes.unit_of_measurement) || '';
        let val = '—';
        if (s && !['unavailable', 'unknown', ''].includes(s.state)) {
          const v = parseFloat(s.state);
          if (f.format === 'date') {
            const d = new Date(s.state.replace(' ', 'T'));
            val = isNaN(d) ? esc(s.state) : TC.fd(d);
          } else if (isNaN(v)) val = esc(s.state);
          else {
            const dec = typeof f.decimals === 'number' ? f.decimals : Math.abs(v) >= 100 ? 0 : Math.abs(v) >= 10 ? 1 : 2;
            val = TC.nf(f.scale ? v * f.scale : v, dec);
          }
        }
        const showUnit = f.format === 'date' ? '' : unit;
        return `<div class="stat"><span class="lbl">${esc(f.name || (s && s.attributes.friendly_name) || f.entity)}</span><b>${val}<small>${esc(showUnit)}</small></b></div>`;
      }).join('');
      return `<footer>${tiles}</footer>`;
    }

    _render() {
      if (!this._prepare()) return;
      const { T: t, OK, BAD, DARK } = TC;
      const c = this._c;
      const cur = TC.cur();
      const keys = Object.keys(TC.MEDIA).filter((k) => c[k] && typeof c[k] === 'object');
      const calcs = keys.map((k) => this._calc(k, c[k]));
      const sums = calcs.filter((x) => x.diff !== null);
      const total = sums.reduce((a, x) => a + x.diff, 0);
      const totalQ = total >= 0 ? OK : BAD;
      const head = sums.length > 1
        ? `<span class="total" style="--q:${totalQ};--qd:${DARK[totalQ]}">${esc(t(total >= 0 ? 'total.back' : 'total.extra'))}<b>${TC.eur(Math.abs(total))} ${esc(cur)}</b></span>` : '';
      const ps = TC.date(this._h, c.period_start);
      let sub = c.subtitle ? `<small>${esc(c.subtitle)}</small>` : '';
      if (ps) {
        const end = TC.date(this._h, c.period_end) || new Date(ps.getFullYear() + 1, ps.getMonth(), ps.getDate() - 1);
        const id = typeof c.period_start === 'string' && c.period_start.includes('.') && this._h.states[c.period_start] ? c.period_start : '';
        sub = `<small${id ? ` class="tap" data-entity="${esc(id)}" title="${esc(t('period.tap'))}"` : ''}>${esc(t('period', { a: TC.fd(ps), b: TC.fd(end) }))}</small>`;
      }
      const header = this._header(c.icon || 'mdi:receipt-text-outline', c.title || t('card.title'), sub, head);
      if (!keys.length && !c.analysis) {
        this._put(`${header}<div class="setup">${t('setup.overview')}</div>`);
        return;
      }
      // Veraltet: Auswertungsblock in Karte 1, wird weiter angezeigt (Abwärtskompatibilität)
      let analysis = '';
      if (c.analysis && typeof c.analysis === 'object') {
        TC.warnOnce('analysis', t('warn.analysis'));
        analysis = TC.analysisHtml(c.analysis, this._h, this._hist, c.analysis.title || t('an.title'), 'wide');
      }
      const panels = calcs.map((x) => this._panel(x, c[x.key])).join('');
      this._put(`${header}
        ${panels ? `<div class="grid">${panels}</div>` : ''}${analysis}${this._footer()}
        ${keys.length ? `<div class="note">${esc(t('note'))}</div>` : ''}`);
    }
  }

  if (!customElements.get('tarif-cockpit-card')) customElements.define('tarif-cockpit-card', TarifCockpitCard);
  window.customCards = window.customCards || [];
  if (!window.customCards.some((x) => x.type === 'tarif-cockpit-card')) {
    window.customCards.push({
      type: 'tarif-cockpit-card',
      name: TC.T('pick.overview.name'),
      description: TC.T('pick.overview.desc'),
      preview: false,
    });
  }
  // eslint-disable-next-line no-console
  console.info(`%c TARIF-COCKPIT %c ${TC.VERSION} `, 'background:#60a5fa;color:#0b1220;font-weight:700', 'background:#121b30;color:#e8eefc');
})();
