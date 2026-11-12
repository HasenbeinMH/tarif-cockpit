/* tarif-cockpit: Tarife, Kosten und Abschlagsprognose für Strom, Gas und Wasser auf einen Blick.
   Optik angelehnt an energy-cockpit (gleiche Farbschemen). Eine Datei, kein Build nötig. */
(() => {
  const VERSION = '0.3.0';

  const THEMES = {
    dunkel: { ov: '255,255,255', bg0: '#070b14', bg1: '#121b30', panel: '#0c1322', txt: '#e8eefc', mut: '139,151,179', stroke: 'rgba(255,255,255,.08)' },
    graphit: { ov: '255,255,255', bg0: '#101011', bg1: '#242427', panel: '#1b1b1e', txt: '#ececee', mut: '152,152,162', stroke: 'rgba(255,255,255,.09)' },
    hell: { ov: '15,23,42', bg0: '#e6ecf5', bg1: '#ffffff', panel: '#ffffff', txt: '#0f172a', mut: '71,85,105', stroke: 'rgba(15,23,42,.12)' },
    warm: { ov: '60,40,20', bg0: '#ece2d2', bg1: '#fbf6ec', panel: '#fffaf0', txt: '#2b2118', mut: '115,98,82', stroke: 'rgba(60,40,20,.15)' },
    ha: { ov: '128,128,128', bg0: 'var(--card-background-color,#1c1c1c)', bg1: 'var(--card-background-color,#1c1c1c)', panel: 'var(--secondary-background-color,#222)', txt: 'var(--primary-text-color,#e1e1e1)', mut: '128,128,128', stroke: 'rgba(128,128,128,.28)' },
  };
  const vars = (t) => `--ov:${t.ov};--bg0:${t.bg0};--bg1:${t.bg1};--panel:${t.panel};--txt:${t.txt};--mut:${t.mut};--stroke:${t.stroke}`;
  const themeCss = ':host{' + vars(THEMES.dunkel) + '}\n'
    + Object.keys(THEMES).filter((k) => k !== 'dunkel').map((k) => `:host([data-theme="${k}"]){${vars(THEMES[k])}}`).join('\n');

  // Standardfarben je Medium (r,g,b); in der Konfiguration mit color: '#hex' überschreibbar
  const MEDIA = {
    strom: { name: 'Strom', icon: 'mdi:flash', color: '255,197,61' },
    gas: { name: 'Gas', icon: 'mdi:fire', color: '251,146,60' },
    wasser: { name: 'Wasser', icon: 'mdi:water', color: '56,189,248' },
  };
  const OK = '52,211,153', BAD = '255,92,122', INFO = '96,165,250';
  // dunklere Töne für die hellen Farbschemen (Lesbarkeit)
  const DARK = { [OK]: '4,120,87', [BAD]: '190,18,60', [INFO]: '29,78,216' };

  const esc = (s) => String(s === null || s === undefined ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const nf = (v, d) => Number(v).toLocaleString('de-DE', { minimumFractionDigits: d, maximumFractionDigits: d });
  const eur = (v) => (v === null || !isFinite(v) ? '—' : nf(v, Math.abs(v) < 100 ? 2 : 0));
  const rgbOf = (c, def) => {
    if (typeof c !== 'string') return def;
    const m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(c.trim());
    if (m) {
      let h = m[1];
      if (h.length === 3) h = h.split('').map((x) => x + x).join('');
      return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)).join(',');
    }
    return /^\d{1,3},\d{1,3},\d{1,3}$/.test(c.replace(/\s+/g, '')) ? c.replace(/\s+/g, '') : def;
  };

  const CSS = `${themeCss}
:host{display:block}
ha-card{background:radial-gradient(120% 80% at 50% 0%,var(--bg1) 0%,var(--bg0) 65%);border-radius:28px;overflow:hidden;border:1px solid rgba(var(--ov),.06);color:var(--txt);font-family:Inter,var(--ha-font-family-body,system-ui),sans-serif;-webkit-font-smoothing:antialiased}
.wrap{padding:22px;position:relative;box-sizing:border-box}
header{display:flex;align-items:center;flex-wrap:wrap;margin-bottom:18px}
.title{font-size:1.05rem;font-weight:650;margin-right:auto;display:flex;align-items:center}
.title small{display:block;font-size:.72rem;font-weight:500;color:rgb(var(--mut));margin-top:2px}
.ico{width:34px;height:34px;border-radius:11px;display:flex;align-items:center;justify-content:center;background:rgba(var(--c),.16);color:rgb(var(--c));flex:none;margin-right:10px}
.ico ha-icon{--mdc-icon-size:19px;display:flex}
.total{display:flex;align-items:center;padding:7px 14px;border-radius:999px;font-size:.8rem;font-weight:650;background:rgba(var(--q),.14);color:rgb(var(--q));box-shadow:0 0 0 1px rgba(var(--q),.3)}
.total b{font-weight:800;margin-left:6px;font-variant-numeric:tabular-nums}
.panel{position:relative;padding:16px 18px;border-radius:22px;background:linear-gradient(160deg,rgba(var(--ov),.065),rgba(var(--ov),.015)),var(--panel);border:1px solid var(--stroke);min-width:0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}
.ph{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:6px}
.lbl{font-size:.68rem;text-transform:uppercase;letter-spacing:.1em;font-weight:650;color:rgb(var(--mut));display:flex;align-items:center}
.lbl i{width:7px;height:7px;border-radius:50%;background:rgb(var(--c));box-shadow:0 0 0 1px rgba(var(--c),.35);margin-right:7px}
.pill{font-size:.72rem;font-weight:700;padding:4px 11px;border-radius:999px;background:rgba(var(--q),.14);color:rgb(var(--q));box-shadow:0 0 0 1px rgba(var(--q),.3)}
.big{display:flex;align-items:baseline;flex-wrap:wrap;margin-top:12px;color:rgb(var(--q))}
.big .num{font-size:2.3rem;font-weight:800;letter-spacing:-.025em;line-height:1;font-variant-numeric:tabular-nums}
.big .unit{font-size:1rem;font-weight:700;margin-left:6px;opacity:.85}
.big small{font-size:.78rem;color:rgb(var(--mut));margin-left:12px;font-weight:500}
.rows{margin-top:14px}
.row{margin-top:9px}
.rh{display:flex;justify-content:space-between;font-size:.74rem;color:rgb(var(--mut));font-variant-numeric:tabular-nums}
.rh b{color:var(--txt);font-weight:650}
.bar{position:relative;height:9px;border-radius:999px;background:rgba(var(--ov),.07);overflow:hidden;margin-top:5px}
.bar i{position:absolute;left:0;top:0;bottom:0;border-radius:inherit;background:rgb(var(--c))}
.bar i.ref{background:rgba(var(--ov),.32)}
.hint{margin-top:12px;font-size:.74rem;color:rgb(var(--mut));line-height:1.4}
.hint b{color:var(--txt);font-weight:650}
.warn{margin-top:10px;font-size:.72rem;color:#fbbf24}
footer{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-top:14px;padding-top:14px;border-top:1px solid var(--stroke)}
.stat{padding:10px 13px;border-radius:15px;background:rgba(var(--ov),.028);border:1px solid rgba(var(--ov),.04);min-width:0}
.stat .lbl{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block}
.stat b{display:block;margin-top:5px;font-size:1.1rem;font-weight:700;font-variant-numeric:tabular-nums}
.stat small{color:rgb(var(--mut));font-weight:500;font-size:.72rem;margin-left:3px}
.note{margin-top:10px;font-size:.64rem;color:rgba(var(--mut),.8);text-align:center}
:host([data-theme="hell"]) .big,:host([data-theme="warm"]) .big,:host([data-theme="hell"]) .pill,:host([data-theme="warm"]) .pill,:host([data-theme="hell"]) .total,:host([data-theme="warm"]) .total{color:rgb(var(--qd))}
.tap{cursor:pointer;text-decoration:underline dotted;text-underline-offset:3px}
.tap:hover{color:var(--txt)}
.panel.wide{margin-top:14px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-top:14px}
.chead{display:flex;align-items:center;flex-wrap:wrap;margin:16px 0 4px}
.chead .lbl{margin-right:auto}
.leg{display:flex;align-items:center;font-size:.72rem;color:rgb(var(--mut));margin-left:14px}
.leg i{width:10px;height:10px;border-radius:3px;margin-right:6px;background:rgb(var(--lc))}
svg.ch{display:block;width:100%;height:auto}
.ch .ax{fill:rgb(var(--mut));font-size:9px;font-family:inherit}
.ch .gl{stroke:var(--stroke);stroke-width:1}
.ch .cb{fill:rgb(var(--c));opacity:.9}
.ch .ln{fill:none;stroke:rgb(var(--lc));stroke-width:2;stroke-linejoin:round}
.ch .dot{fill:rgb(var(--lc))}
.nodata{font-size:.74rem;color:rgb(var(--mut));padding:14px 0 4px}
.narrow .wrap{padding:16px}
.narrow .big .num{font-size:2rem}
`;

  class TarifCockpitCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: 'open' });
    }

    static getStubConfig() {
      return {
        title: 'Tarife und Abrechnung',
        strom: { cost: 'sensor.kosten_strom_abrechnungsjahr', advance_paid: 'sensor.abschlage_strom_abrechnungsjahr', forecast_cost: 'sensor.prognose_strom_kosten', forecast_kwh: 'sensor.prognose_strom_verbrauch', advance: 'input_number.abschlag_strom' },
        gas: { cost: 'sensor.kosten_gas_abrechnungsjahr', advance_paid: 'sensor.abschlage_gas_abrechnungsjahr', forecast_cost: 'sensor.prognose_gas_kosten', forecast_kwh: 'sensor.prognose_gas_verbrauch', advance: 'input_number.abschlag_gas' },
      };
    }

    getCardSize() { return 9; }

    setConfig(c) {
      if (!c || typeof c !== 'object' || !Object.keys(MEDIA).some((k) => c[k])) {
        throw new Error('tarif-cockpit: mindestens strom, gas oder wasser mit Sensoren angeben');
      }
      this._c = c;
      this._hist = null;
      this._histAt = 0;
      this._build();
      this._render();
      this._loadHistory();
    }

    set hass(h) {
      this._h = h;
      this._render();
      this._loadHistory();
    }

    // Letzte n Monate (ältester zuerst) als Achse für die Verlaufsdiagramme
    _months(n) {
      const out = [];
      const now = new Date();
      for (let i = n - 1; i >= 0; i--) {
        const x = new Date(now.getFullYear(), now.getMonth() - i, 1);
        out.push({ y: x.getFullYear(), m: x.getMonth(), key: x.getFullYear() + '-' + x.getMonth() });
      }
      return out;
    }

    // Monatsmittel aus der Langzeitstatistik; höchstens einmal pro Stunde
    async _loadHistory() {
      const a = this._c && this._c.analysis;
      if (!a || a.history === false || !this._h || typeof this._h.callWS !== 'function') return;
      const now = Date.now();
      if (this._histAt && now - this._histAt < 3600e3) return;
      this._histAt = now;
      const ids = [a.consumption, a.temperature, a.kennwert].filter(Boolean);
      if (!ids.length) return;
      const ax = this._months(Number(a.months) > 0 ? Math.min(Number(a.months), 36) : 24);
      try {
        const r = await this._h.callWS({
          type: 'recorder/statistics_during_period',
          start_time: new Date(ax[0].y, ax[0].m, 1).toISOString(),
          end_time: new Date().toISOString(),
          statistic_ids: ids,
          period: 'month',
          types: ['mean'],
        });
        const pick = (id) => {
          const map = {};
          ((r && r[id]) || []).forEach((s) => {
            const d = new Date(s.start);
            if (typeof s.mean === 'number') map[d.getFullYear() + '-' + d.getMonth()] = s.mean;
          });
          return ax.map((x) => (x.key in map ? map[x.key] : null));
        };
        this._hist = { ax, cons: a.consumption ? pick(a.consumption) : [], temp: a.temperature ? pick(a.temperature) : [], kw: a.kennwert ? pick(a.kennwert) : [] };
      } catch (e) {
        this._hist = null;
      }
      this._last = null;
      this._render();
    }

    // Diagramm: optional Balken (linke Achse) und Linie (rechte Achse, ohne Balken links)
    _svgChart(ax, bars, line, uBar, uLine) {
      const W = 720, H = 170, L = 40, R = bars ? 40 : 10, T = 10, B = 24;
      const n = ax.length, step = (W - L - R) / n, ih = H - T - B;
      const bv = bars ? bars.filter((v) => v !== null) : [];
      const lv = line ? line.filter((v) => v !== null) : [];
      const bmax = bv.length ? Math.max(...bv) * 1.1 || 1 : 1;
      let lmin = lv.length ? Math.floor(Math.min(...lv, 0)) : 0;
      let lmax = lv.length ? Math.ceil(Math.max(...lv) * (bars ? 1 : 1.1) + (bars ? 1 : 0)) : 1;
      if (lmax <= lmin) lmax = lmin + 1;
      const yb = (v) => T + ih - (v / bmax) * ih;
      const yl = (v) => T + ih - ((v - lmin) / (lmax - lmin)) * ih;
      let s = `<svg class="ch" viewBox="0 0 ${W} ${H}" role="img">`;
      for (let g = 0; g <= 4; g++) {
        const y = T + (ih * g) / 4;
        s += `<line class="gl" x1="${L}" x2="${W - R}" y1="${y}" y2="${y}"/>`;
        if (bars) {
          s += `<text class="ax" x="${L - 5}" y="${y + 3}" text-anchor="end">${nf(bmax * (1 - g / 4), 0)}</text>`;
          if (lv.length) s += `<text class="ax" x="${W - R + 5}" y="${y + 3}">${nf(lmax - ((lmax - lmin) * g) / 4, 0)}</text>`;
        } else {
          s += `<text class="ax" x="${L - 5}" y="${y + 3}" text-anchor="end">${nf(lmax - ((lmax - lmin) * g) / 4, 1)}</text>`;
        }
      }
      if (bars) bars.forEach((v, i) => { if (v !== null) s += `<rect class="cb" x="${L + i * step + step * 0.2}" y="${yb(v)}" width="${step * 0.6}" height="${Math.max(1, T + ih - yb(v))}" rx="3"/>`; });
      if (line) {
        let d = '', pen = false;
        line.forEach((v, i) => {
          if (v === null) { pen = false; return; }
          const x = L + i * step + step / 2;
          d += (pen ? 'L' : 'M') + x.toFixed(1) + ' ' + yl(v).toFixed(1) + ' ';
          pen = true;
        });
        if (d) s += `<path class="ln" d="${d}"/>`;
        line.forEach((v, i) => { if (v !== null) s += `<circle class="dot" cx="${L + i * step + step / 2}" cy="${yl(v)}" r="3"/>`; });
      }
      ax.forEach((x, i) => {
        const cx = L + i * step + step / 2;
        const name = new Date(x.y, x.m, 1).toLocaleDateString('de-DE', { month: 'narrow' });
        s += `<text class="ax" x="${cx}" y="${H - 11}" text-anchor="middle">${name}</text>`;
        if (x.m === 0 || i === 0) s += `<text class="ax" x="${cx}" y="${H - 1}" text-anchor="middle">${x.y}</text>`;
      });
      void uBar; void uLine;
      return s + '</svg>';
    }

    // Auswertung (z. B. Gas witterungsbereinigt): Kennwert, Kacheln, Verlauf
    _analysis() {
      const a = this._c.analysis;
      if (!a || typeof a !== 'object') return '';
      const c = rgbOf(a.color, MEDIA.gas.color);
      const kw = this._num(a.kennwert);
      const prev = this._num(a.kennwert_previous);
      let pill = '<span class="pill" style="--q:' + INFO + ';--qd:' + DARK[INFO] + '">Wartet auf Ablesung</span>';
      let big = '', cmp = '';
      if (kw !== null) {
        pill = '';
        big = `<div class="big" style="--q:${c};--qd:${c}"><span class="num">${nf(kw, 2)}</span><span class="unit">kWh/Kd</span><small>Kennwert der letzten Periode</small></div>`;
        if (prev !== null && prev > 0) {
          const p = (kw / prev - 1) * 100;
          const t = Math.abs(p) < 5 ? 'etwa gleich' : p > 0 ? 'mehr, als das Wetter erklärt' : 'weniger, als das Wetter erklärt';
          cmp = `<div class="hint">Gegenüber der Vorperiode (${nf(prev, 2)}): <b>${p >= 0 ? '+' : ''}${nf(p, 1)} %</b> · ${t}.</div>`;
        }
      }
      const pending = kw === null ? `<div class="hint">${esc(a.pending_text || 'Noch keine Auswertung: Der erste Kennwert kommt mit der nächsten Gas-Ablesung.')}</div>` : '';
      const tile = (name, id, unit, dec) => {
        if (!id) return '';
        const v = this._num(id);
        return `<div class="stat"><span class="lbl">${esc(name)}</span><b>${v === null ? '—' : nf(v, dec)}<small>${esc(unit)}</small></b></div>`;
      };
      const extras = (Array.isArray(a.extras) ? a.extras : []).map((e) => (e && e.entity ? tile(e.name || e.entity, e.entity, e.unit || '', typeof e.decimals === 'number' ? e.decimals : 1) : '')).join('');
      const tiles = tile('Verbrauch letzte Periode', a.consumption, 'kWh', 0) + tile('Ø Außentemperatur', a.temperature, '°C', 1) + tile('Gradtage', a.degree_days, 'Kd', 1) + extras;
      let charts = '';
      const h = this._hist;
      if (a.history !== false && (a.consumption || a.kennwert)) {
        const has = h && (h.cons.some((v) => v !== null) || h.kw.some((v) => v !== null));
        if (!has) charts = '<div class="nodata">Noch keine Verlaufsdaten in der Langzeitstatistik.</div>';
        else {
          if (a.consumption && h.cons.some((v) => v !== null)) {
            charts += `<div class="chead" style="--lc:${INFO}"><span class="lbl">Verbrauch und Außentemperatur je Monat</span><span class="leg" style="--lc:${c}"><i></i>Verbrauch (kWh)</span>${a.temperature ? '<span class="leg"><i></i>Ø Außentemperatur (°C)</span>' : ''}</div><div style="--c:${c};--lc:${INFO}">${this._svgChart(h.ax, h.cons, a.temperature ? h.temp : null)}</div>`;
          }
          if (a.kennwert && h.kw.some((v) => v !== null)) {
            charts += `<div class="chead"><span class="lbl">Kennwert je Monat (kWh/Kd)</span></div><div style="--lc:${c}">${this._svgChart(h.ax, null, h.kw)}</div>`;
          }
        }
      }
      const explain = a.explain ? `<div class="hint">${esc(a.explain)}</div>` : '';
      return `<div class="panel wide" style="--c:${c}">
        <div class="ph"><span class="lbl"><i></i>${esc(a.title || 'Auswertung')}</span>${pill}</div>
        ${big}${cmp}${pending}
        <div class="tiles">${tiles}</div>${charts}${explain}
      </div>`;
    }

    _build() {
      this.shadowRoot.innerHTML = `<style>${CSS}</style><ha-card><div class="wrap" id="w"></div></ha-card>`;
      this._w = this.shadowRoot.getElementById('w');
      // Tipp auf den Zeitraum öffnet den Datums-Helfer, dort lässt er sich ändern
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

    disconnectedCallback() { if (this._ro) this._ro.disconnect(); }

    // Datum aus Entität (input_datetime, Sensor) oder als Text "JJJJ-MM-TT"; sonst null
    _date(v) {
      if (!v || typeof v !== 'string') return null;
      const s = /^\d{4}-\d{2}-\d{2}/.test(v) ? v : this._h && this._h.states[v] && this._h.states[v].state;
      const m = typeof s === 'string' && /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
      return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
    }

    _fd(d) {
      return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
    }

    _num(id) {
      if (!id || !this._h) return null;
      const s = this._h.states[id];
      if (!s || ['unavailable', 'unknown', ''].includes(s.state)) return null;
      const v = parseFloat(s.state);
      return isNaN(v) ? null : v;
    }

    _theme() {
      let t = this._c.theme || 'dunkel';
      if (t === 'auto') {
        let dark = true;
        const h = this._h;
        if (h && h.themes && typeof h.themes.darkMode === 'boolean') dark = h.themes.darkMode;
        else if (window.matchMedia) dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        t = dark ? 'dunkel' : 'hell';
      }
      return THEMES[t] ? t : 'dunkel';
    }

    // Rechnet ein Medium: Differenz = Abschläge im Jahr minus Hochrechnung (positiv = Guthaben)
    _calc(key, m) {
      const months = Number(m.months) > 0 ? Number(m.months) : 12;
      const cost = this._num(m.cost), paid = this._num(m.advance_paid), fc = this._num(m.forecast_cost);
      const monthly = this._num(m.advance), kwh = this._num(m.forecast_kwh);
      const yearAdv = monthly === null ? null : monthly * months;
      const ok = fc !== null && yearAdv !== null;
      const diff = ok ? yearAdv - fc : null;
      const tol = (typeof this._c.tolerance_pct === 'number' ? this._c.tolerance_pct : 5) / 100;
      let verdict = null;
      if (ok) verdict = Math.abs(diff) < yearAdv * tol ? 'ok' : diff > 0 ? 'back' : 'extra';
      return { key, months, cost, paid, fc, monthly, kwh, yearAdv, diff, verdict, fitting: fc === null ? null : Math.ceil(fc / months) };
    }

    _panel(calc, m) {
      const def = MEDIA[calc.key];
      const c = rgbOf(m.color, def.color);
      const q = calc.verdict === 'back' ? OK : calc.verdict === 'extra' ? BAD : INFO;
      const label = { ok: 'Passt', back: 'Rückzahlung', extra: 'Nachzahlung' }[calc.verdict] || 'Noch keine Prognose';
      const cap = { ok: 'Abschlag passt zum Verbrauch', back: 'Guthaben erwartet', extra: 'Nachzahlung erwartet' }[calc.verdict] || '';
      const max = Math.max(calc.cost || 0, calc.paid || 0, calc.fc || 0, calc.yearAdv || 0, 1);
      const row = (name, v, ref, extra) => {
        if (v === null) return '';
        return `<div class="row"><div class="rh"><span>${name}</span><b>${eur(v)} €${extra ? ' · ' + extra : ''}</b></div><div class="bar"><i class="${ref ? 'ref' : ''}" style="width:${Math.max(1, Math.min(100, (v / max) * 100))}%"></i></div></div>`;
      };
      // Hat das Medium einen eigenen Beginn, der vom Gesamtzeitraum abweicht, steht er in der Kachel
      const own = this._date(m.start), all = this._date(this._c.period_start);
      const startTxt = own && (!all || own.getTime() !== all.getTime()) ? ' · ab ' + this._fd(own) : '';
      const kwhTxt = calc.kwh === null ? '' : nf(calc.kwh, 0) + ' kWh';
      const sign = calc.diff === null ? '' : calc.verdict === 'ok' ? (calc.diff >= 0 ? '+' : '−') : '';
      const big = calc.diff === null
        ? `<span class="num">—</span>`
        : `<span class="num">${sign}${eur(Math.abs(calc.diff))}</span><span class="unit">€</span><small>${cap}</small>`;
      const hint = calc.fitting === null || calc.monthly === null ? ''
        : `<div class="hint">Passender Abschlag: <b>${nf(calc.fitting, 0)} €</b> statt ${nf(calc.monthly, 0)} € im Monat.</div>`;
      const old = m.stale_hint ? `<div class="warn">${esc(m.stale_hint)}</div>` : '';
      return `<div class="panel" style="--c:${c};--q:${q};--qd:${DARK[q]}">
        <div class="ph"><span class="lbl"><i></i>${esc(m.name || def.name)}${m.advance && calc.monthly !== null ? ' · Abschlag ' + nf(calc.monthly, 0) + ' €' : ''}${startTxt}</span><span class="pill">${label}</span></div>
        <div class="big">${big}</div>
        <div class="rows">
          ${row('Kosten bisher', calc.cost, false, '')}
          ${row('Abschläge bisher', calc.paid, true, '')}
          ${row('Hochrechnung Jahr', calc.fc, false, kwhTxt)}
          ${row('Abschläge Jahr (' + calc.months + ' ×)', calc.yearAdv, true, '')}
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
            val = isNaN(d) ? esc(s.state) : d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
          } else if (isNaN(v)) val = esc(s.state);
          else {
            const dec = typeof f.decimals === 'number' ? f.decimals : Math.abs(v) >= 100 ? 0 : Math.abs(v) >= 10 ? 1 : 2;
            val = nf(f.scale ? v * f.scale : v, dec);
          }
        }
        const showUnit = f.format === 'date' ? '' : unit;
        return `<div class="stat"><span class="lbl">${esc(f.name || (s && s.attributes.friendly_name) || f.entity)}</span><b>${val}<small>${esc(showUnit)}</small></b></div>`;
      }).join('');
      return `<footer>${tiles}</footer>`;
    }

    _render() {
      if (!this._c || !this._w || !this._h) return;
      const c = this._c;
      const card = this.shadowRoot.querySelector('ha-card');
      const t = this._theme();
      if (this.getAttribute('data-theme') !== t) this.setAttribute('data-theme', t);

      const calcs = Object.keys(MEDIA).filter((k) => c[k]).map((k) => this._calc(k, c[k]));
      const sums = calcs.filter((x) => x.diff !== null);
      const total = sums.reduce((a, x) => a + x.diff, 0);
      const totalQ = total >= 0 ? OK : BAD;
      const head = sums.length > 1
        ? `<span class="total" style="--q:${totalQ};--qd:${DARK[totalQ]}">${total >= 0 ? 'Guthaben' : 'Nachzahlung'} gesamt<b>${eur(Math.abs(total))} €</b></span>` : '';
      const ps = this._date(c.period_start);
      let sub = c.subtitle ? `<small>${esc(c.subtitle)}</small>` : '';
      if (ps) {
        const end = this._date(c.period_end) || new Date(ps.getFullYear() + 1, ps.getMonth(), ps.getDate() - 1);
        const id = typeof c.period_start === 'string' && c.period_start.includes('.') && this._h.states[c.period_start] ? c.period_start : '';
        sub = `<small${id ? ` class="tap" data-entity="${esc(id)}" title="Antippen, um den Zeitraum zu ändern"` : ''}>Abrechnungszeitraum ${this._fd(ps)} – ${this._fd(end)}</small>`;
      }
      const panels = calcs.map((x) => this._panel(x, c[x.key])).join('');
      const html = `<header><div class="title"><span class="ico" style="--c:${INFO}"><ha-icon icon="${esc(c.icon || 'mdi:receipt-text-outline')}"></ha-icon></span><div>${esc(c.title || 'Tarife und Abrechnung')}${sub}</div></div>${head}</header>
        <div class="grid">${panels}</div>${this._analysis()}${this._footer()}
        <div class="note">Hochrechnung aus den Prognose-Sensoren, Differenz = Abschläge im Jahr minus Hochrechnung. Keine Abrechnung.</div>`;
      if (html !== this._last) { this._w.innerHTML = html; this._last = html; }
      void card;
    }
  }

  if (!customElements.get('tarif-cockpit-card')) customElements.define('tarif-cockpit-card', TarifCockpitCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: 'tarif-cockpit-card',
    name: 'Tarif-Cockpit',
    description: 'Kosten, Abschläge und Jahresprognose für Strom, Gas und Wasser: passt, Nachzahlung oder Rückzahlung auf einen Blick',
    preview: false,
  });
  // eslint-disable-next-line no-console
  console.info(`%c TARIF-COCKPIT %c ${VERSION} `, 'background:#60a5fa;color:#0b1220;font-weight:700', 'background:#121b30;color:#e8eefc');
})();
