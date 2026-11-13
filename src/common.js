/* tarif-cockpit: gemeinsame Teile (Farbschemen, Farben, Formatierung, Hilfen für Entitäten).
   Alle Module hängen an einem globalen Objekt window.TarifCockpit (intern TC); der Build fügt sie in fester Reihenfolge zusammen. */
window.TarifCockpit = window.TarifCockpit || {};
(() => {
  const TC = window.TarifCockpit;
  TC.VERSION = '__VERSION__';

  // Farbschemen wie bei energy-cockpit
  TC.THEMES = {
    dunkel: { ov: '255,255,255', bg0: '#070b14', bg1: '#121b30', panel: '#0c1322', txt: '#e8eefc', mut: '139,151,179', stroke: 'rgba(255,255,255,.08)' },
    graphit: { ov: '255,255,255', bg0: '#101011', bg1: '#242427', panel: '#1b1b1e', txt: '#ececee', mut: '152,152,162', stroke: 'rgba(255,255,255,.09)' },
    hell: { ov: '15,23,42', bg0: '#e6ecf5', bg1: '#ffffff', panel: '#ffffff', txt: '#0f172a', mut: '71,85,105', stroke: 'rgba(15,23,42,.12)' },
    warm: { ov: '60,40,20', bg0: '#ece2d2', bg1: '#fbf6ec', panel: '#fffaf0', txt: '#2b2118', mut: '115,98,82', stroke: 'rgba(60,40,20,.15)' },
    ha: { ov: '128,128,128', bg0: 'var(--card-background-color,#1c1c1c)', bg1: 'var(--card-background-color,#1c1c1c)', panel: 'var(--secondary-background-color,#222)', txt: 'var(--primary-text-color,#e1e1e1)', mut: '128,128,128', stroke: 'rgba(128,128,128,.28)' },
  };
  TC.THEME_KEYS = ['dunkel', 'graphit', 'hell', 'warm', 'auto', 'ha'];
  const vars = (t) => `--ov:${t.ov};--bg0:${t.bg0};--bg1:${t.bg1};--panel:${t.panel};--txt:${t.txt};--mut:${t.mut};--stroke:${t.stroke}`;
  TC.themeCss = ':host{' + vars(TC.THEMES.dunkel) + '}\n'
    + Object.keys(TC.THEMES).filter((k) => k !== 'dunkel').map((k) => `:host([data-theme="${k}"]){${vars(TC.THEMES[k])}}`).join('\n');

  // Standardfarben je Medium (r,g,b); in der Konfiguration mit color: '#hex' überschreibbar
  TC.MEDIA = {
    strom: { icon: 'mdi:flash', color: '255,197,61' },
    gas: { icon: 'mdi:fire', color: '251,146,60' },
    wasser: { icon: 'mdi:water', color: '56,189,248' },
    fernwaerme: { icon: 'mdi:heating-coil', color: '244,114,182' },
  };
  TC.OK = '52,211,153';
  TC.BAD = '255,92,122';
  TC.INFO = '96,165,250';
  // dunklere Töne für die hellen Farbschemen (Lesbarkeit)
  TC.DARK = { [TC.OK]: '4,120,87', [TC.BAD]: '190,18,60', [TC.INFO]: '29,78,216' };

  TC.esc = (s) => String(s === null || s === undefined ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // Sprache, Zahlenformat und Währung aus Home Assistant (TC.useHass bei jedem Rendern)
  TC.loc = 'de-DE';
  // Bis hass da ist (z. B. in der Kartenauswahl): Sprache des Browsers
  const nav = (typeof document !== 'undefined' && document.documentElement && document.documentElement.lang) || (typeof navigator !== 'undefined' && navigator.language) || 'de';
  TC.lang = /^de/i.test(nav) ? 'de' : 'en';
  TC.currency = 'EUR';
  TC.useHass = (h) => {
    if (!h) return;
    const l = h.locale || {};
    const lang = String(l.language || h.language || 'de');
    TC.lang = /^de/i.test(lang) ? 'de' : 'en';
    const nfm = l.number_format;
    // "none": Punkt als Dezimalzeichen, keine Tausendertrennung
    TC.group = nfm !== 'none';
    if (nfm === 'comma_decimal' || nfm === 'none') TC.loc = 'en-US';
    else if (nfm === 'decimal_comma') TC.loc = 'de-DE';
    else if (nfm === 'space_comma') TC.loc = 'fr-FR';
    else if (nfm === 'system') TC.loc = undefined;
    else TC.loc = lang === 'de' ? 'de-DE' : lang;
    TC.currency = (h.config && h.config.currency) || 'EUR';
  };
  const symCache = {};
  TC.cur = () => {
    const k = TC.currency + '|' + TC.loc;
    if (!(k in symCache)) {
      try {
        const p = new Intl.NumberFormat(TC.loc, { style: 'currency', currency: TC.currency }).formatToParts(0).find((x) => x.type === 'currency');
        symCache[k] = p ? p.value : TC.currency;
      } catch (e) { symCache[k] = TC.currency; }
    }
    return symCache[k];
  };
  TC.nf = (v, d) => {
    try { return Number(v).toLocaleString(TC.loc, { minimumFractionDigits: d, maximumFractionDigits: d, useGrouping: TC.group !== false }); } catch (e) { return Number(v).toFixed(d); }
  };
  TC.eur = (v) => (v === null || !isFinite(v) ? '—' : TC.nf(v, Math.abs(v) < 100 ? 2 : 0));
  TC.fd = (d) => d.toLocaleDateString(TC.loc, { day: '2-digit', month: '2-digit', year: 'numeric' });

  // Farbe aus '#hex', '#abc' oder 'r,g,b'; sonst def
  TC.rgbOf = (c, def) => {
    if (typeof c !== 'string') return def;
    const m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(c.trim());
    if (m) {
      let h = m[1];
      if (h.length === 3) h = h.split('').map((x) => x + x).join('');
      return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)).join(',');
    }
    return /^\d{1,3},\d{1,3},\d{1,3}$/.test(c.replace(/\s+/g, '')) ? c.replace(/\s+/g, '') : def;
  };

  const NA = ['unavailable', 'unknown', ''];
  // Zahlenwert einer Entität; null, wenn sie fehlt oder nicht verfügbar ist
  TC.num = (h, id) => {
    if (!id || !h || !h.states) return null;
    const s = h.states[id];
    if (!s || NA.includes(s.state)) return null;
    const v = parseFloat(s.state);
    return isNaN(v) ? null : v;
  };
  // Datum aus Entität (input_datetime, Sensor) oder als Text "JJJJ-MM-TT"; sonst null
  TC.date = (h, v) => {
    if (!v || typeof v !== 'string') return null;
    const s = /^\d{4}-\d{2}-\d{2}/.test(v) ? v : h && h.states && h.states[v] && h.states[v].state;
    const m = typeof s === 'string' && /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
    return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
  };

  // Farbschema: auto folgt dem hellen/dunklen Design von Home Assistant
  TC.resolveTheme = (cfg, h) => {
    let t = (cfg && cfg.theme) || 'dunkel';
    if (t === 'auto') {
      let dark = true;
      if (h && h.themes && typeof h.themes.darkMode === 'boolean') dark = h.themes.darkMode;
      else if (window.matchMedia) dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      t = dark ? 'dunkel' : 'hell';
    }
    return TC.THEMES[t] ? t : 'dunkel';
  };

  // Einmalige Hinweise in der Browser-Konsole
  const warned = {};
  TC.warnOnce = (key, msg) => {
    if (warned[key]) return;
    warned[key] = true;
    // eslint-disable-next-line no-console
    console.warn('tarif-cockpit: ' + msg);
  };

  TC.CSS = `${TC.themeCss}
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
.bar i.adv{background:rgb(var(--adv))}
:host([data-theme="hell"]) .bar i.adv,:host([data-theme="warm"]) .bar i.adv{background:rgb(var(--advd))}
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
.setup{padding:18px 4px 6px;font-size:.85rem;color:rgb(var(--mut));line-height:1.5}
.setup b{color:var(--txt)}
.narrow .wrap{padding:16px}
.narrow .big .num{font-size:2rem}
`;
})();
