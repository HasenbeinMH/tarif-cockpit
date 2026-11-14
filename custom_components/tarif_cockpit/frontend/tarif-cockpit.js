/*! tarif-cockpit v0.8.0 - MIT License - https://github.com/HasenbeinMH/tarif-cockpit
    Editor-Baukasten und Assistent nach energy-cockpit, MIT License, Copyright (c) 2026 Musicmaker3112
    Diese Datei wird gebaut: Quellen in src/, Aufruf node tools/build.mjs */
/* ---- common.js ---- */
/* tarif-cockpit: gemeinsame Teile (Farbschemen, Farben, Formatierung, Hilfen für Entitäten).
   Alle Module hängen an einem globalen Objekt window.TarifCockpit (intern TC); der Build fügt sie in fester Reihenfolge zusammen. */
window.TarifCockpit = window.TarifCockpit || {};
(() => {
  const TC = window.TarifCockpit;
  TC.VERSION = '0.8.0';

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


/* ---- i18n.js ---- */
/* Texte auf Deutsch und Englisch. TC.T(key, {name: wert}) setzt {name} ein; fehlt ein Text, gilt Deutsch, dann der Schlüssel. */
(() => {
  const TC = window.TarifCockpit;
  TC.STR = {
    de: {
      'media.strom': 'Strom', 'media.gas': 'Gas', 'media.wasser': 'Wasser', 'media.fernwaerme': 'Fernwärme',
      'card.title': 'Tarife und Abrechnung',
      'verdict.ok': 'Passt', 'verdict.back': 'Rückzahlung', 'verdict.extra': 'Nachzahlung', 'verdict.none': 'Noch keine Prognose',
      'cap.ok': 'Abschlag passt zum Verbrauch', 'cap.back': 'Guthaben erwartet', 'cap.extra': 'Nachzahlung erwartet',
      'row.cost': 'Kosten bisher', 'row.paid': 'Abschläge bisher', 'row.fc': 'Hochrechnung Jahr', 'row.year': 'Abschläge Jahr ({n} ×)',
      'hint.fitting': 'Passender Abschlag: <b>{fit}</b> statt {cur} im Monat.',
      'lbl.advance': ' · Abschlag {v}', 'lbl.from': ' · ab {d}',
      'total.back': 'Guthaben gesamt', 'total.extra': 'Nachzahlung gesamt',
      'period': 'Abrechnungszeitraum {a} – {b}', 'period.tap': 'Antippen, um den Zeitraum zu ändern',
      'note': 'Hochrechnung aus den Prognose-Sensoren, Differenz = Abschläge im Jahr minus Hochrechnung. Keine Abrechnung.',
      'setup.overview': '<b>Noch nicht eingerichtet.</b> Im Karten-Editor führt dich der Assistent durch die Sensoren für Strom, Gas oder Wasser.',
      'setup.analyse': '<b>Noch nicht eingerichtet.</b> Im Karten-Editor wählst du Kennwert, Verbrauch und Außentemperatur.',
      'an.title': 'Auswertung', 'an.kennwert': 'Kennwert', 'an.wait': 'Wartet auf Ablesung', 'an.kw_last': 'Kennwert der letzten Periode',
      'an.cmp': 'Gegenüber der Vorperiode ({p}): <b>{d} %</b> · {t}.',
      'an.same': 'etwa gleich', 'an.more': 'mehr, als das Wetter erklärt', 'an.less': 'weniger, als das Wetter erklärt',
      'an.pending': 'Noch keine Auswertung: Der erste Kennwert kommt mit der nächsten Gas-Ablesung.',
      'an.t_cons': 'Verbrauch letzte Periode', 'an.t_temp': 'Ø Außentemperatur', 'an.t_dd': 'Gradtage',
      'an.nodata': 'Noch keine Verlaufsdaten in der Langzeitstatistik.',
      'an.ch_cons': 'Verbrauch und Außentemperatur je Monat', 'an.leg_cons': 'Verbrauch (kWh)', 'an.leg_temp': 'Ø Außentemperatur (°C)',
      'an.ch_kw': 'Kennwert je Monat (kWh/Kd)',
      'pick.overview.name': 'Tarif-Cockpit',
      'pick.overview.desc': 'Kosten, Abschläge und Prognose für Strom, Gas und Wasser: passt, Nachzahlung oder Rückzahlung auf einen Blick',
      'pick.analyse.name': 'Tarif-Cockpit Auswertung',
      'pick.analyse.desc': 'Heizung: Kennwert je Gradtag, Streudiagramm, Kostenverlauf gegen die Abschläge, Wärmeerzeuger',
      'warn.analysis': 'Der Block "analysis" in tarif-cockpit-card ist veraltet. Bitte die Karte "custom:tarif-cockpit-analyse-card" verwenden (docs/MIGRATION.md).',
      // Editor und Assistent
      'ed.tab_wiz': 'Assistent', 'ed.tab_form': 'Alle Felder', 'ed.tab_integ': 'Integration', 'ed.loading': 'Formular wird geladen …',
      'ei.text': 'Die Karte zeigt die Werte der Integration Tarif-Cockpit. Wähle die Zähler; alles Weitere (Verträge, Preise, Abschläge) stellst du in der Integration ein.',
      'ei.meters': 'Zähler', 'ei.title': 'Titel (optional)', 'ei.theme': 'Farbschema', 'ei.none': 'Noch keine Zähler in der Integration.',
      'ei.sensor_mode': 'Sensor-Modus verwenden (eigene Sensoren statt Integration)',
      'ei.switch': 'Diese Karte nutzt noch den Sensor-Modus. Auf die Integration umstellen? Die Sensorfelder bleiben gespeichert, werden aber nicht mehr verwendet.',
      'ei.switch_btn': 'Auf Integration umstellen', 'ei.colors': 'Farben (optional)',
      'ed.noform': 'Das Formular konnte nicht geladen werden. Bitte den Assistenten oder den YAML-Editor verwenden.',
      'wz.optional': ' (optional)', 'wz.none': '— nicht verwenden —', 'wz.own': 'Eigene Auswahl', 'wz.notfound': '(nicht gefunden)',
      'wz.sug': 'Vorschläge', 'wz.all': 'Alle passenden Entitäten', 'wz.live': 'Aktueller Wert: {v}  ·  {id}', 'wz.take': 'Vorschlag übernehmen: {n}',
      'wz.back': '← Zurück', 'wz.next': 'Weiter →', 'wz.done': 'Fertig: alle Felder anzeigen',
      'wz.name_ph': 'Anzeigename', 'wz.remove': 'Entfernen', 'wz.add': 'Kachel hinzufügen:', 'wz.pick': '— Entität wählen —',
      'wz.unit_ph': 'Einheit (optional)', 'wz.text': 'Text: {v}',
      'th.dunkel': 'Dunkel', 'th.graphit': 'Graphit', 'th.hell': 'Hell', 'th.warm': 'Warm', 'th.auto': 'Automatisch', 'th.ha': 'Home Assistant',
    },
    en: {
      'media.strom': 'Electricity', 'media.gas': 'Gas', 'media.wasser': 'Water', 'media.fernwaerme': 'District heating',
      'card.title': 'Tariffs and billing',
      'verdict.ok': 'On track', 'verdict.back': 'Refund', 'verdict.extra': 'Back payment', 'verdict.none': 'No forecast yet',
      'cap.ok': 'Advance matches consumption', 'cap.back': 'Credit expected', 'cap.extra': 'Back payment expected',
      'row.cost': 'Costs so far', 'row.paid': 'Advances paid so far', 'row.fc': 'Projection for the year', 'row.year': 'Advances for the year ({n} ×)',
      'hint.fitting': 'Matching advance: <b>{fit}</b> instead of {cur} per month.',
      'lbl.advance': ' · advance {v}', 'lbl.from': ' · from {d}',
      'total.back': 'Total credit', 'total.extra': 'Total back payment',
      'period': 'Billing period {a} – {b}', 'period.tap': 'Tap to change the period',
      'note': 'Projection from the forecast sensors, difference = advances for the year minus projection. Not a bill.',
      'setup.overview': '<b>Not set up yet.</b> In the card editor the wizard guides you through the sensors for electricity, gas or water.',
      'setup.analyse': '<b>Not set up yet.</b> In the card editor choose the heat coefficient, consumption and outdoor temperature.',
      'an.title': 'Analysis', 'an.kennwert': 'Heat coefficient', 'an.wait': 'Waiting for a meter reading', 'an.kw_last': 'Coefficient of the last period',
      'an.cmp': 'Compared with the previous period ({p}): <b>{d} %</b> · {t}.',
      'an.same': 'about the same', 'an.more': 'more than the weather explains', 'an.less': 'less than the weather explains',
      'an.pending': 'No analysis yet: the first coefficient arrives with the next gas meter reading.',
      'an.t_cons': 'Consumption last period', 'an.t_temp': 'Ø outdoor temperature', 'an.t_dd': 'Degree days',
      'an.nodata': 'No history in the long-term statistics yet.',
      'an.ch_cons': 'Consumption and outdoor temperature per month', 'an.leg_cons': 'Consumption (kWh)', 'an.leg_temp': 'Ø outdoor temperature (°C)',
      'an.ch_kw': 'Coefficient per month (kWh/Kd)',
      'pick.overview.name': 'Tarif-Cockpit',
      'pick.overview.desc': 'Costs, advance payments and annual forecast for electricity, gas and water: on track, back payment or refund at a glance',
      'pick.analyse.name': 'Tarif-Cockpit analysis',
      'pick.analyse.desc': 'Heating: coefficient per degree day, scatter plot, cost curve against advances, heat generators',
      'warn.analysis': 'The "analysis" block in tarif-cockpit-card is deprecated. Please use the card "custom:tarif-cockpit-analyse-card" (docs/MIGRATION.md).',
      'ed.tab_wiz': 'Wizard', 'ed.tab_form': 'All fields', 'ed.tab_integ': 'Integration', 'ed.loading': 'Loading form …',
      'ei.text': 'The card shows the values of the Tarif-Cockpit integration. Choose the meters; everything else (contracts, prices, advances) is set in the integration.',
      'ei.meters': 'Meters', 'ei.title': 'Title (optional)', 'ei.theme': 'Colour scheme', 'ei.none': 'No meters in the integration yet.',
      'ei.sensor_mode': 'Use sensor mode (own sensors instead of the integration)',
      'ei.switch': 'This card still uses sensor mode. Switch to the integration? The sensor fields stay saved but are no longer used.',
      'ei.switch_btn': 'Switch to the integration', 'ei.colors': 'Colours (optional)',
      'ed.noform': 'The form could not be loaded. Please use the wizard or the YAML editor.',
      'wz.optional': ' (optional)', 'wz.none': '— not used —', 'wz.own': 'Own choice', 'wz.notfound': '(not found)',
      'wz.sug': 'Suggestions', 'wz.all': 'All matching entities', 'wz.live': 'Current value: {v}  ·  {id}', 'wz.take': 'Use suggestion: {n}',
      'wz.back': '← Back', 'wz.next': 'Next →', 'wz.done': 'Done: show all fields',
      'wz.name_ph': 'Display name', 'wz.remove': 'Remove', 'wz.add': 'Add tile:', 'wz.pick': '— choose entity —',
      'wz.unit_ph': 'Unit (optional)', 'wz.text': 'Text: {v}',
      'th.dunkel': 'Dark', 'th.graphit': 'Graphite', 'th.hell': 'Light', 'th.warm': 'Warm', 'th.auto': 'Automatic', 'th.ha': 'Home Assistant',
    },
  };
  TC.addStrings = (lang, map) => { TC.STR[lang] = Object.assign(TC.STR[lang] || {}, map); };
  TC.T = (key, v) => {
    const s = (TC.STR[TC.lang] && TC.STR[TC.lang][key]) || TC.STR.de[key] || key;
    return v ? s.replace(/\{(\w+)\}/g, (m, k) => (k in v ? v[k] : m)) : s;
  };
})();


/* ---- chart.js ---- */
/* Verlauf aus der Langzeitstatistik, SVG-Diagramme und der Auswertungsblock (Kennwert, Kacheln, Verlauf).
   Der Auswertungsblock wird von tarif-cockpit-analyse-card und (veraltet) vom Block "analysis" in tarif-cockpit-card verwendet. */
(() => {
  const TC = window.TarifCockpit;
  const { esc } = TC;

  // Letzte n Monate (ältester zuerst) als Achse für die Verlaufsdiagramme
  TC.months = (n) => {
    const out = [];
    const now = new Date();
    for (let i = n - 1; i >= 0; i--) {
      const x = new Date(now.getFullYear(), now.getMonth() - i, 1);
      out.push({ y: x.getFullYear(), m: x.getMonth(), key: x.getFullYear() + '-' + x.getMonth() });
    }
    return out;
  };

  // Monatsmittel aus der Langzeitstatistik; höchstens einmal pro Stunde je Karte.
  // card: Element mit _h (hass), _histAt, _hist, _last, _render(); a: Auswertungs-Konfiguration
  TC.loadHistory = async (card, a) => {
    if (!a || a.history === false || !card._h || typeof card._h.callWS !== 'function') return;
    const ids = [a.consumption, a.temperature, a.kennwert].filter(Boolean);
    if (!ids.length) return;
    const n = Number(a.months) > 0 ? Math.min(Number(a.months), 36) : 24;
    // Neu laden nur bei anderen Entitäten/Monaten oder nach einer Stunde (der Editor ruft setConfig bei jedem Tastendruck)
    const key = ids.join('|') + '|' + n;
    const now = Date.now();
    if (key === card._histKey && card._histAt && now - card._histAt < 3600e3) return;
    if (key !== card._histKey) card._hist = null;
    card._histKey = key;
    card._histAt = now;
    // Nur die Antwort der jüngsten Anfrage zählt
    const seq = (card._histSeq || 0) + 1;
    card._histSeq = seq;
    const ax = TC.months(n);
    try {
      const r = await card._h.callWS({
        type: 'recorder/statistics_during_period',
        start_time: new Date(ax[0].y, ax[0].m, 1).toISOString(),
        end_time: new Date().toISOString(),
        statistic_ids: ids,
        period: 'month',
        types: ['mean'],
      });
      if (seq !== card._histSeq) return;
      const pick = (id) => {
        const map = {};
        ((r && r[id]) || []).forEach((s) => {
          const d = new Date(s.start);
          if (typeof s.mean === 'number') map[d.getFullYear() + '-' + d.getMonth()] = s.mean;
        });
        return ax.map((x) => (x.key in map ? map[x.key] : null));
      };
      card._hist = { ax, cons: a.consumption ? pick(a.consumption) : [], temp: a.temperature ? pick(a.temperature) : [], kw: a.kennwert ? pick(a.kennwert) : [] };
    } catch (e) {
      if (seq !== card._histSeq) return;
      card._hist = null;
    }
    card._last = null;
    card._render();
  };

  // Diagramm: optional Balken (linke Achse) und Linie (rechte Achse, ohne Balken links)
  TC.svgChart = (ax, bars, line) => {
    const nf = TC.nf;
    const W = 720, H = 170, L = 40, R = bars ? 40 : 10, T = 10, B = 24;
    const n = ax.length, step = (W - L - R) / n, ih = H - T - B;
    const bv = bars ? bars.filter((v) => v !== null) : [];
    const lv = line ? line.filter((v) => v !== null) : [];
    const bmax = bv.length ? Math.max(...bv) * 1.1 || 1 : 1;
    const lmin = lv.length ? Math.floor(Math.min(...lv, 0)) : 0;
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
      const name = new Date(x.y, x.m, 1).toLocaleDateString(TC.loc, { month: 'narrow' });
      s += `<text class="ax" x="${cx}" y="${H - 11}" text-anchor="middle">${name}</text>`;
      if (x.m === 0 || i === 0) s += `<text class="ax" x="${cx}" y="${H - 1}" text-anchor="middle">${x.y}</text>`;
    });
    return s + '</svg>';
  };

  // Auswertung (z. B. Gas witterungsbereinigt): Kennwert, Kacheln, Verlauf.
  // a: Konfiguration, h: hass, hist: geladener Verlauf, label: Überschrift im Panel, cls: zusätzliche Panel-Klasse
  TC.analysisHtml = (a, h, hist, label, cls) => {
    const { nf, T: t, INFO, DARK, MEDIA } = TC;
    if (!a || typeof a !== 'object') return '';
    const c = TC.rgbOf(a.color, MEDIA.gas.color);
    const kw = TC.num(h, a.kennwert);
    const prev = TC.num(h, a.kennwert_previous);
    let pill = '<span class="pill" style="--q:' + INFO + ';--qd:' + DARK[INFO] + '">' + esc(a.wait_text || t('an.wait')) + '</span>';
    let big = '', cmp = '';
    if (kw !== null) {
      pill = '';
      big = `<div class="big" style="--q:${c};--qd:${c}"><span class="num">${nf(kw, 2)}</span><span class="unit">kWh/Kd</span><small>${esc(a.kw_caption || t('an.kw_last'))}</small></div>`;
      if (prev !== null && prev > 0) {
        const p = (kw / prev - 1) * 100;
        const txt = Math.abs(p) < 5 ? t('an.same') : p > 0 ? t('an.more') : t('an.less');
        cmp = `<div class="hint">${t('an.cmp', { p: nf(prev, 2), d: (p >= 0 ? '+' : '') + nf(p, 1), t: esc(txt) })}</div>`;
      }
    }
    const pending = kw === null ? `<div class="hint">${esc(a.pending_text || t('an.pending'))}</div>` : '';
    const tile = (name, id, unit, dec) => {
      if (!id) return '';
      const v = TC.num(h, id);
      return `<div class="stat"><span class="lbl">${esc(name)}</span><b>${v === null ? '—' : nf(v, dec)}<small>${esc(unit)}</small></b></div>`;
    };
    const extras = (Array.isArray(a.extras) ? a.extras : []).map((e) => (e && e.entity ? tile(e.name || e.entity, e.entity, e.unit || '', typeof e.decimals === 'number' ? e.decimals : 1) : '')).join('');
    const tiles = tile(t('an.t_cons'), a.consumption, 'kWh', 0) + tile(t('an.t_temp'), a.temperature, '°C', 1) + tile(t('an.t_dd'), a.degree_days, 'Kd', 1) + extras;
    let charts = '';
    if (a.history !== false && (a.consumption || a.kennwert)) {
      const has = hist && (hist.cons.some((v) => v !== null) || hist.kw.some((v) => v !== null));
      if (!has) charts = `<div class="nodata">${esc(t('an.nodata'))}</div>`;
      else {
        if (a.consumption && hist.cons.some((v) => v !== null)) {
          charts += `<div class="chead" style="--lc:${INFO}"><span class="lbl">${esc(t('an.ch_cons'))}</span><span class="leg" style="--lc:${c}"><i></i>${esc(t('an.leg_cons'))}</span>${a.temperature ? `<span class="leg"><i></i>${esc(t('an.leg_temp'))}</span>` : ''}</div><div style="--c:${c};--lc:${INFO}">${TC.svgChart(hist.ax, hist.cons, a.temperature ? hist.temp : null)}</div>`;
        }
        if (a.kennwert && hist.kw.some((v) => v !== null)) {
          charts += `<div class="chead"><span class="lbl">${esc(t('an.ch_kw'))}</span></div><div style="--lc:${c}">${TC.svgChart(hist.ax, null, hist.kw)}</div>`;
        }
      }
    }
    const explain = a.explain ? `<div class="hint">${esc(a.explain)}</div>` : '';
    const tilesHtml = tiles ? `<div class="tiles">${tiles}</div>` : '';
    return `<div class="panel${cls ? ' ' + cls : ''}" style="--c:${c}">
        <div class="ph"><span class="lbl"><i></i>${esc(label)}</span>${pill}</div>
        ${big}${cmp}${pending}
        ${tilesHtml}${charts}${explain}
      </div>`;
  };
})();


/* ---- charts2.js ---- */
/* Diagramme der Auswertungskarte (0.8): Streudiagramm Verbrauch über Gradtage, kumulierter Kostenverlauf.
   Die Daten kommen fertig gerechnet aus der Integration (WebSocket tarif_cockpit/reihen); hier wird nur gezeichnet (Regel 2). */
(() => {
  const TC = window.TarifCockpit;

  // "schöne" Achsenschritte
  const niceMax = (v) => {
    if (!(v > 0)) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    const f = v / p;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
  };

  // Streudiagramm: x = Gradtage je Tag, y = Verbrauch je Tag; Ofen-/Klimatage farbig; Gerade y = WW + Kennwert × x
  TC.svgScatter = (sc) => {
    const nf = TC.nf;
    const W = 720, H = 230, L = 44, R = 12, T = 10, B = 34;
    const pts = (sc && sc.punkte) || [];
    const xmax = niceMax(Math.max(1, ...pts.map((p) => p.x), sc && sc.gerade ? sc.gerade.x1 : 0));
    const ymax = niceMax(Math.max(1, ...pts.map((p) => p.y), sc && sc.gerade ? sc.gerade.y1 : 0) * 1.05);
    const iw = W - L - R, ih = H - T - B;
    const X = (v) => L + (v / xmax) * iw;
    const Y = (v) => T + ih - (v / ymax) * ih;
    let s = `<svg class="ch sc" viewBox="0 0 ${W} ${H}" role="img">`;
    for (let g = 0; g <= 4; g++) {
      const y = T + (ih * g) / 4;
      s += `<line class="gl" x1="${L}" x2="${W - R}" y1="${y}" y2="${y}"/>`;
      s += `<text class="ax" x="${L - 5}" y="${y + 3}" text-anchor="end">${nf(ymax * (1 - g / 4), 0)}</text>`;
      const x = L + (iw * g) / 4;
      s += `<text class="ax" x="${x}" y="${H - 18}" text-anchor="middle">${nf((xmax * g) / 4, 0)}</text>`;
    }
    s += `<text class="ax" x="${L + iw / 2}" y="${H - 3}" text-anchor="middle">${TC.T('ch.x_dd')}</text>`;
    pts.forEach((p) => {
      const cls = p.ofen ? 'pt of' : p.klima ? 'pt kl' : 'pt';
      s += `<circle class="${cls}" cx="${X(p.x).toFixed(1)}" cy="${Y(p.y).toFixed(1)}" r="${p.ofen || p.klima ? 3.4 : 2.6}"/>`;
    });
    if (sc && sc.gerade) {
      const g = sc.gerade;
      s += `<line class="rl" x1="${X(g.x0).toFixed(1)}" y1="${Y(g.y0).toFixed(1)}" x2="${X(g.x1).toFixed(1)}" y2="${Y(g.y1).toFixed(1)}"/>`;
    }
    return s + '</svg>';
  };

  const day = (iso) => new Date(iso + 'T00:00:00').getTime();

  // Kostenverlauf: Ist (durchgezogen), Prognose (gestrichelt), Abschlags-Treppe (grün), Linie "heute"
  TC.svgCumul = (k) => {
    const nf = TC.nf;
    const W = 720, H = 200, L = 52, R = 12, T = 10, B = 24;
    const t0 = day(k.beginn), t1 = day(k.ende) + 864e5;
    const all = [...k.ist, ...k.prognose, ...k.abschlaege].map((p) => p[1]);
    const ymax = niceMax(Math.max(1, ...all) * 1.05);
    const iw = W - L - R, ih = H - T - B;
    const X = (iso) => L + ((day(iso) - t0) / (t1 - t0)) * iw;
    const Y = (v) => T + ih - (v / ymax) * ih;
    let s = `<svg class="ch cu" viewBox="0 0 ${W} ${H}" role="img">`;
    for (let g = 0; g <= 4; g++) {
      const y = T + (ih * g) / 4;
      s += `<line class="gl" x1="${L}" x2="${W - R}" y1="${y}" y2="${y}"/>`;
      s += `<text class="ax" x="${L - 5}" y="${y + 3}" text-anchor="end">${nf(ymax * (1 - g / 4), 0)}</text>`;
    }
    // Monatsmarken
    const d = new Date(k.beginn + 'T00:00:00');
    d.setDate(1);
    for (let i = 0; i < 40; i++) {
      const m = new Date(d.getFullYear(), d.getMonth() + i, 1);
      const iso = `${m.getFullYear()}-${String(m.getMonth() + 1).padStart(2, '0')}-01`;
      if (day(iso) < t0) continue;
      if (day(iso) > t1) break;
      const mid = new Date(m.getFullYear(), m.getMonth(), 15);
      const midIso = `${mid.getFullYear()}-${String(mid.getMonth() + 1).padStart(2, '0')}-15`;
      s += `<line class="gl" x1="${X(iso)}" x2="${X(iso)}" y1="${T + ih}" y2="${T + ih + 4}"/>`;
      if (day(midIso) <= t1) s += `<text class="ax" x="${X(midIso)}" y="${H - 8}" text-anchor="middle">${m.toLocaleDateString(TC.loc, { month: 'short' })}</text>`;
    }
    const path = (pts) => pts.map((p, i) => (i ? 'L' : 'M') + X(p[0]).toFixed(1) + ' ' + Y(p[1]).toFixed(1)).join(' ');
    if (k.abschlaege.length) {
      let dpath = '', last = 0;
      k.abschlaege.forEach((p, i) => {
        const x = X(p[0]).toFixed(1);
        dpath += i === 0 ? `M${x} ${Y(p[1]).toFixed(1)}` : ` H${x} V${Y(p[1]).toFixed(1)}`;
        last = p[1];
      });
      dpath += ` H${(L + iw).toFixed(1)}`;
      s += `<path class="st" d="${dpath}"/>`;
      void last;
    }
    if (k.ist.length) s += `<path class="ist" d="${path(k.ist)}"/>`;
    if (k.prognose.length) s += `<path class="fc" d="${path(k.prognose)}"/>`;
    if (k.heute) s += `<line class="today" x1="${X(k.heute)}" x2="${X(k.heute)}" y1="${T}" y2="${T + ih}"/>`;
    return s + '</svg>';
  };

  TC.CHART2_CSS = `
.ch .pt{fill:rgb(var(--c));opacity:.55}
.ch .pt.of{fill:#f87171;opacity:.85}
.ch .pt.kl{fill:#22d3ee;opacity:.85}
.ch .rl{stroke:var(--txt);stroke-width:2;stroke-dasharray:6 4;opacity:.8}
.ch .ist{fill:none;stroke:rgb(var(--c));stroke-width:2.4;stroke-linejoin:round}
.ch .fc{fill:none;stroke:rgb(var(--c));stroke-width:2.4;stroke-dasharray:7 5;opacity:.75}
.ch .st{fill:none;stroke:rgb(var(--adv,52,211,153));stroke-width:2}
.ch .today{stroke:rgb(var(--mut));stroke-width:1;stroke-dasharray:2 3}
.leg i.of{background:#f87171}.leg i.kl{background:#22d3ee}
.leg i.ist{background:rgb(var(--c))}.leg i.fc{background:repeating-linear-gradient(90deg,rgb(var(--c)) 0 4px,transparent 4px 7px)}
.leg i.st{background:rgb(var(--adv,52,211,153))}
.gens{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin-top:14px}
.gen{padding:12px 14px;border-radius:15px;background:rgba(var(--ov),.028);border:1px solid rgba(var(--ov),.04)}
.gen .gh{display:flex;justify-content:space-between;align-items:baseline;font-weight:650;font-size:.85rem}
.gen .gh small{color:rgb(var(--mut));font-weight:500;font-size:.68rem}
.gen dl{display:grid;grid-template-columns:auto 1fr;gap:4px 10px;margin:8px 0 0;font-size:.74rem}
.gen dt{color:rgb(var(--mut))}.gen dd{margin:0;text-align:right;font-variant-numeric:tabular-nums}
.gen dd small{color:rgb(var(--mut));font-size:.66rem}
`;
})();


/* ---- base-card.js ---- */
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
      this.shadowRoot.innerHTML = `<style>${TC.CSS}${TC.integ ? TC.integ.CSS : ''}${TC.CHART2_CSS || ''}</style><ha-card><div class="wrap" id="w"></div></ha-card>`;
      this._w = this.shadowRoot.getElementById('w');
      // Tipp auf ein Element mit data-entity öffnet den Dialog der Entität (z. B. Datums-Helfer des Zeitraums)
      this._w.addEventListener('click', (e) => {
        // Integrations-Modus: Abschlagsdialog
        if (this._c && this._c.integration && TC.integ && (e.target.closest('[data-advance]') || e.target.closest('[data-dlg]'))) {
          TC.integ.onClick(this, e);
          return;
        }
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


/* ---- integration.js ---- */
/* Integrations-Modus der Karten (0.7): Daten kommen fertig gerechnet aus der Integration tarif_cockpit.
   Die Karte holt per WebSocket nur, welche Sensoren zu welchem Zähler gehören, und liest dann hass.states.
   Sie rechnet nichts (Regel 2); Abschlagsänderungen gehen über die Aktion tarif_cockpit.set_abschlag. */
(() => {
  const TC = window.TarifCockpit;
  const { esc } = TC;
  const I = (TC.integ = {});

  TC.addStrings('de', {
    'in.loading': 'Daten der Integration werden geladen …',
    'in.missing': '<b>Integration nicht gefunden.</b> Unter Einstellungen → Geräte & Dienste „Tarif-Cockpit“ hinzufügen und einen Zähler anlegen.',
    'in.no_meters': '<b>Noch keine Zähler.</b> Beim Eintrag „Tarif-Cockpit“ über „Zähler hinzufügen“ anlegen.',
    'in.row_fc': 'Prognose Periode', 'in.row_period': 'Abschläge Periode ({n} ×)',
    'in.recommended': 'Empfohlener Abschlag ab {d}: <b>{v}</b>', 'in.prelim': ' (vorläufig)',
    'in.quality': 'Qualität: {q}', 'in.no_fc': 'Noch keine Prognose',
    'in.why_heat': 'Der Kennwert wird noch gelernt: Es braucht genug Tage mit unterschiedlicher Außentemperatur.',
    'in.why': 'Noch zu wenig Daten für eine Prognose.',
    'in.final': 'Vertrag bei {s} endet am {d} (Schlussrechnung).', 'in.next': 'Danach: {s} ab {d}.',
    'in.steps': 'Abschläge: {t}', 'in.advance_tap': 'Antippen, um den Abschlag zu ändern',
    'in.note': 'Werte der Integration Tarif-Cockpit. Keine Abrechnung.',
    'in.total_incomplete': 'Gesamt erst, wenn alle Zähler eine Prognose haben',
    'q.annahme': 'Annahme', 'q.unzureichend': 'unzureichend', 'q.vorlaeufig': 'vorläufig', 'q.gut': 'gut', 'q.sehr_gut': 'sehr gut',
    'dlg.title': 'Abschlag ändern: {m}', 'dlg.amount': 'Neuer Abschlag', 'dlg.from': 'Gültig ab', 'dlg.hint': 'Empfohlen: {v}',
    'dlg.cancel': 'Abbrechen', 'dlg.save': 'Speichern', 'dlg.saved': 'Gespeichert.',
    'dlg.invalid': 'Bitte einen Betrag (0 oder mehr) und ein Datum eingeben.',
    'in.no_heat': '<b>Kein Wärmezähler.</b> Die Auswertung braucht einen Gas- oder Fernwärmezähler in der Integration.',
    'in.learning': 'Wird gelernt', 'in.kw_learned': 'gelernt aus den Tageswerten',
    'in.kw_indoor': 'Kennwert temperaturbereinigt', 'in.pct_k': '{p} % je Kelvin Raumtemperatur',
    'in.split': 'Gegenüber dem Vorjahr {g}: davon {r} durch die Raumtemperatur ({k}), {v} Mehr-/Minderverbrauch.',
    'ch.scatter': 'Verbrauch je Tag über Gradtage', 'ch.x_dd': 'Gradtage je Tag (Kd)', 'ch.days': 'Tage', 'ch.periods': 'Ableseperioden (Mittel je Tag)',
    'ch.stove_days': 'Ofentage', 'ch.hp_days': 'Klimatage', 'ch.line': 'Gerade: {ww} + {k} × Gradtage',
    'ch.cost': 'Kosten der Periode', 'ch.ist': 'Kosten bisher', 'ch.fc': 'Prognose', 'ch.adv': 'Abschläge',
    'g.input': 'Eingesetzt', 'g.heat': 'Wärme', 'g.heat_est': 'Wärme (geschätzt)', 'g.avoided': 'Entlastung', 'g.not_learned': 'noch nicht gelernt',
    'g.hours': 'Betrieb', 'g.wood': 'Holz (geschätzt)', 'g.title': 'Wärmeerzeuger in dieser Periode',
    'g.kind.gas_boiler': 'Gastherme', 'g.kind.air_air_hp': 'Split-Klima', 'g.kind.water_hp': 'Wärmepumpe', 'g.kind.district_heating': 'Fernwärme',
    'g.kind.fireplace': 'Kaminofen', 'g.kind.electric': 'Elektroheizung', 'in.ww': 'WW-Grundlast', 'in.days': 'Tage im Modell', 'in.r2': 'Bestimmtheit R²',
    'in.an_pending': 'Der Kennwert erscheint, sobald die Integration genug Tage mit unterschiedlicher Außentemperatur gesehen hat.',
  });
  TC.addStrings('en', {
    'in.loading': 'Loading data from the integration …',
    'in.missing': '<b>Integration not found.</b> Add “Tarif-Cockpit” under Settings → Devices & services and add a meter.',
    'in.no_meters': '<b>No meters yet.</b> Add them via “Add meter” on the “Tarif-Cockpit” entry.',
    'in.row_fc': 'Forecast for the period', 'in.row_period': 'Advances for the period ({n} ×)',
    'in.recommended': 'Recommended advance from {d}: <b>{v}</b>', 'in.prelim': ' (preliminary)',
    'in.quality': 'Quality: {q}', 'in.no_fc': 'No forecast yet',
    'in.why_heat': 'The heat coefficient is still being learned: it needs enough days with different outdoor temperatures.',
    'in.why': 'Not enough data for a forecast yet.',
    'in.final': 'Contract with {s} ends on {d} (final bill).', 'in.next': 'Then: {s} from {d}.',
    'in.steps': 'Advances: {t}', 'in.advance_tap': 'Tap to change the advance payment',
    'in.note': 'Values from the Tarif-Cockpit integration. Not a bill.',
    'in.total_incomplete': 'Total once every meter has a forecast',
    'q.annahme': 'assumption', 'q.unzureichend': 'insufficient', 'q.vorlaeufig': 'preliminary', 'q.gut': 'good', 'q.sehr_gut': 'very good',
    'dlg.title': 'Change advance: {m}', 'dlg.amount': 'New advance', 'dlg.from': 'Valid from', 'dlg.hint': 'Recommended: {v}',
    'dlg.cancel': 'Cancel', 'dlg.save': 'Save', 'dlg.saved': 'Saved.',
    'dlg.invalid': 'Please enter an amount (0 or more) and a date.',
    'in.no_heat': '<b>No heat meter.</b> The analysis needs a gas or district heating meter in the integration.',
    'in.learning': 'Being learned', 'in.kw_learned': 'learned from daily values',
    'in.kw_indoor': 'Heat coefficient (indoor-adjusted)', 'in.pct_k': '{p} % per kelvin room temperature',
    'in.split': 'Compared with last year {g}: of which {r} due to room temperature ({k}), {v} more/less consumption.',
    'ch.scatter': 'Consumption per day over degree days', 'ch.x_dd': 'Degree days per day (Kd)', 'ch.days': 'Days', 'ch.periods': 'Reading periods (mean per day)',
    'ch.stove_days': 'Stove days', 'ch.hp_days': 'Air-con days', 'ch.line': 'Line: {ww} + {k} × degree days',
    'ch.cost': 'Costs of the period', 'ch.ist': 'Costs so far', 'ch.fc': 'Forecast', 'ch.adv': 'Advances',
    'g.input': 'Input', 'g.heat': 'Heat', 'g.heat_est': 'Heat (estimated)', 'g.avoided': 'Relief', 'g.not_learned': 'not learned yet',
    'g.hours': 'Operation', 'g.wood': 'Wood (estimated)', 'g.title': 'Heat generators in this period',
    'g.kind.gas_boiler': 'Gas boiler', 'g.kind.air_air_hp': 'Split air-con', 'g.kind.water_hp': 'Heat pump', 'g.kind.district_heating': 'District heating',
    'g.kind.fireplace': 'Wood stove', 'g.kind.electric': 'Electric heating', 'in.ww': 'Hot water baseload', 'in.days': 'Days in the model', 'in.r2': 'Coefficient of determination R²',
    'in.an_pending': 'The coefficient appears once the integration has seen enough days with different outdoor temperatures.',
  });

  I.available = (h) => !!(h && h.config && Array.isArray(h.config.components) && h.config.components.includes('tarif_cockpit'));

  // Zähler und Sensoren holen (höchstens alle 10 Minuten neu; sofort, wenn ein Sensor fehlt)
  I.load = async (card, force) => {
    const h = card._h;
    if (!h || typeof h.callWS !== 'function' || card._metaLoading) return;
    if (card._metaAt) {
      const age = Date.now() - card._metaAt;
      const wait = card._metaErr ? 60e3 : force ? 30e3 : 600e3;
      if (age < wait) return;
    }
    card._metaLoading = true;
    try {
      card._meta = await h.callWS({ type: 'tarif_cockpit/zaehler' });
      card._metaErr = null;
    } catch (e) {
      card._meta = null;
      card._metaErr = e;
    }
    card._metaAt = Date.now();
    card._metaLoading = false;
    card._last = null;
    card._render();
  };

  I.meters = (card) => {
    const hh = card._meta && card._meta.haushalte && card._meta.haushalte[0];
    if (!hh) return [];
    const want = Array.isArray(card._c.zaehler) && card._c.zaehler.length ? card._c.zaehler : null;
    return hh.zaehler.filter((m) => (want ? want.includes(m.device_id) || want.includes(m.zaehler_id) : m.rolle === 'main'));
  };

  const st = (h, id) => (id && h.states[id]) || null;
  const val = (h, id) => TC.num(h, id);
  const attr = (h, id, k) => { const s = st(h, id); return s && s.attributes ? s.attributes[k] : undefined; };
  const QUAL = ['annahme', 'unzureichend', 'vorlaeufig', 'gut', 'sehr_gut'];
  const isAdmin = (h) => !!(h && h.user && h.user.is_admin);
  const localIso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  const money = (v) => (v === null || v === undefined ? '—' : TC.eur(v) + ' ' + TC.cur());
  const dd = (iso) => (iso ? TC.fd(new Date(iso + 'T00:00:00')) : '');

  // "4 × 165 € + 8 × 180 €" aus der Abschlagsliste (aufeinanderfolgende gleiche Beträge zusammengefasst)
  I.stepsText = (list) => {
    const items = (list || []).filter((i) => i.status !== 'storniert');
    const groups = [];
    items.forEach((i) => {
      const g = groups[groups.length - 1];
      if (g && g.amount === i.betrag) g.n += 1; else groups.push({ amount: i.betrag, n: 1 });
    });
    return groups.map((g) => `${g.n} × ${TC.nf(g.amount, Math.abs(g.amount) < 100 ? 2 : 0)} ${TC.cur()}`).join(' + ');
  };

  I.panel = (card, m) => {
    const h = card._h;
    const t = TC.T;
    const s = m.sensoren || {};
    const med = TC.MEDIA[m.medium] || TC.MEDIA.strom;
    const c = TC.rgbOf((card._c.colors || {})[m.medium], med.color);
    const verdict = (st(h, s.urteil) || {}).state;
    const vKey = { passt: 'ok', rueckzahlung: 'back', nachzahlung: 'extra' }[verdict] || null;
    const q = vKey === 'back' ? TC.OK : vKey === 'extra' ? TC.BAD : TC.INFO;
    const advOwn = TC.rgbOf(card._c.advance_color, null);
    const adv = advOwn || TC.OK, advd = advOwn || TC.DARK[TC.OK];
    const saldo = val(h, s.saldo), cost = val(h, s.kosten_bisher), paid = val(h, s.abschlaege_bisher);
    const fcCost = val(h, s.prognose_kosten), fcQty = val(h, s.prognose_verbrauch), period = val(h, s.abschlaege_periode);
    const current = val(h, s.abschlag);
    const qs = (st(h, s.prognose_qualitaet) || {}).state;
    const quality = QUAL.includes(qs) ? qs : 'unzureichend';
    const list = attr(h, s.abschlaege_periode, 'abschlaege') || [];
    const n = attr(h, s.abschlaege_periode, 'anzahl');
    const max = Math.max(cost || 0, paid || 0, fcCost || 0, period || 0, 1);
    const row = (name, v, isAdv, extra) => (v === null ? '' : `<div class="row"><div class="rh"><span>${esc(name)}</span><b>${money(v)}${extra ? ' · ' + extra : ''}</b></div><div class="bar"><i class="${isAdv ? 'adv' : ''}" style="width:${Math.max(1, Math.min(100, (v / max) * 100))}%"></i></div></div>`);
    const unit = attr(h, s.prognose_verbrauch, 'unit_of_measurement') || m.unit || (m.medium === 'wasser' ? 'm³' : 'kWh');
    const big = saldo === null ? '<span class="num">—</span>'
      : `<span class="num">${verdict === 'passt' ? (saldo >= 0 ? '+' : '−') : ''}${TC.eur(Math.abs(saldo))}</span><span class="unit">${esc(TC.cur())}</span>${vKey ? `<small>${esc(t('cap.' + vKey))}</small>` : ''}`;
    const supplier = m.vertraege && m.vertraege.length ? (attr(h, s.periode_ende, 'lieferant') || '') : '';
    // Abschlag ändern nur für Administratoren (die Aktion ist eine Admin-Aktion)
    const advLabel = current !== null && !isAdmin(h)
      ? `<span>${esc(t('lbl.advance', { v: TC.nf(current, 0) + ' ' + TC.cur() }).replace(/^ /, '\u00a0'))}</span>`
      : current !== null ? `<span class="tap" data-advance="${esc(m.device_id)}" title="${esc(t('in.advance_tap'))}">${esc(t('lbl.advance', { v: TC.nf(current, 0) + ' ' + TC.cur() }).replace(/^ /, '\u00a0'))}</span>` : '';
    const hints = [];
    const steps = I.stepsText(list);
    if (steps && steps.includes('+')) hints.push(esc(t('in.steps', { t: steps })));
    const rec = val(h, s.abschlag_empfohlen);
    if (rec !== null) {
      const ab = attr(h, s.abschlag_empfohlen, 'ab');
      const prelim = attr(h, s.abschlag_empfohlen, 'vorlaeufig');
      hints.push(t('in.recommended', { d: esc(dd(ab)), v: money(rec) }) + (prelim ? esc(t('in.prelim')) : ''));
    }
    if (saldo === null && fcCost === null) {
      hints.push(esc(m.medium === 'gas' || m.medium === 'fernwaerme' ? t('in.why_heat') : t('in.why')));
    }
    // Anbieterwechsel in der laufenden Periode: alter Vertrag bis zum Wechsel, danach der neue
    if (attr(h, s.periode_ende, 'schlussperiode')) {
      const end = (st(h, s.periode_ende) || {}).state;
      hints.push(esc(t('in.final', { s: supplier, d: dd(end) })));
      const next = (m.vertraege || []).find((v) => end && v.beginn > end);
      if (next) hints.push(esc(t('in.next', { s: next.lieferant, d: dd(next.beginn) })));
    }
    return `<div class="panel" style="--c:${c};--q:${q};--qd:${TC.DARK[q]};--adv:${adv};--advd:${advd}">
      <div class="ph"><span class="lbl"><i></i>${esc(m.name)}${advLabel}${supplier ? esc('\u00a0· ' + supplier) : ''}</span><span class="pill">${esc(vKey ? t('verdict.' + vKey) : t('in.no_fc'))}</span></div>
      <div class="big">${big}</div>
      <div class="rows">
        ${row(t('row.cost'), cost, false, '')}
        ${row(t('row.paid'), paid, true, '')}
        ${row(t('in.row_fc'), fcCost, false, fcQty !== null ? TC.nf(fcQty, 0) + ' ' + unit : '')}
        ${row(t('in.row_period', { n: n || '–' }), period, true, '')}
      </div>
      ${hints.map((x) => `<div class="hint">${x}</div>`).join('')}
      <div class="qual">${esc(t('in.quality', { q: t('q.' + quality) }))}</div>
    </div>`;
  };

  I.render = (card) => {
    const h = card._h;
    const t = TC.T;
    const c = card._c;
    if (!card._meta) {
      I.load(card);
      const msg = card._metaErr ? t('in.missing') : esc(t('in.loading'));
      return card._header(c.icon || 'mdi:receipt-text-outline', c.title || t('card.title'), '', '') + `<div class="setup">${msg}</div>`;
    }
    I.load(card); // regelmäßig auffrischen
    I.keepDialogInput(card);
    const meters = I.meters(card);
    const hh = card._meta.haushalte[0];
    if (!hh || !meters.length) {
      I.load(card, true);
      return card._header(c.icon || 'mdi:receipt-text-outline', c.title || t('card.title'), '', '') + `<div class="setup">${t('in.no_meters')}</div>`;
    }
    // fehlt ein Sensor im Zustand (z. B. nach dem Anlegen), Zuordnung neu holen
    if (meters.some((m) => Object.values(m.sensoren || {}).some((id) => !h.states[id]))) I.load(card, true);
    const first = meters[0].sensoren || {};
    const beginn = attr(h, first.periode_ende, 'beginn');
    const ende = (st(h, first.periode_ende) || {}).state;
    const sub = beginn && ende ? `<small>${esc(t('period', { a: dd(beginn), b: dd(ende) }))}</small>` : '';
    const total = val(h, hh.saldo_gesamt);
    let head = '';
    const allMains = hh.zaehler.filter((m) => m.rolle === 'main').length;
    if (meters.length > 1 && meters.length >= allMains) {
      head = total === null
        ? `<span class="total" style="--q:${TC.INFO};--qd:${TC.DARK[TC.INFO]}" title="${esc(t('in.total_incomplete'))}">${esc(t('in.no_fc'))}</span>`
        : `<span class="total" style="--q:${total >= 0 ? TC.OK : TC.BAD};--qd:${TC.DARK[total >= 0 ? TC.OK : TC.BAD]}">${esc(t(total >= 0 ? 'total.back' : 'total.extra'))}<b>${TC.eur(Math.abs(total))} ${esc(TC.cur())}</b></span>`;
    }
    return `${card._header(c.icon || 'mdi:receipt-text-outline', c.title || t('card.title'), sub, head)}
      <div class="grid">${meters.map((m) => I.panel(card, m)).join('')}</div>${card._footer()}
      <div class="note">${esc(t('in.note'))}</div>${card._dlg ? I.dialogHtml(card) : ''}`;
  };

  // ---------------------------------------------------------------- Karte 2 (Auswertung)

  const HEAT = ['gas', 'fernwaerme', 'waerme'];
  I.heatMeter = (card) => {
    const hh = card._meta && card._meta.haushalte && card._meta.haushalte[0];
    if (!hh) return null;
    const want = Array.isArray(card._c.zaehler) && card._c.zaehler.length ? card._c.zaehler : null;
    if (want) return hh.zaehler.find((m) => want.includes(m.device_id) || want.includes(m.zaehler_id)) || null;
    const heat = hh.zaehler.find((m) => m.rolle === 'main' && HEAT.includes(m.medium));
    if (heat) return heat;
    // ohne Gas/Fernwärme: Stromzähler mit Wärmepumpe/Split-Klima (eigener Zähler zuerst, sonst Haushaltsstrom)
    const gens = (hh.waermeerzeuger || []).filter((g) => ['water_hp', 'air_air_hp', 'electric'].includes(g.typ));
    const own = gens.map((g) => g.zaehler_id).filter(Boolean);
    return hh.zaehler.find((m) => own.includes(m.zaehler_id))
      || (gens.some((g) => g.am_haushaltsstrom) ? hh.zaehler.find((m) => m.rolle === 'main' && m.medium === 'strom') : null) || null;
  };

  // Felder der Sensor-Karte aus den Sensoren der Integration (Verlauf und Darstellung wie bisher)
  I.analyseConfig = (card) => {
    const m = I.heatMeter(card);
    if (!m) return null;
    const s = m.sensoren || {};
    const c = card._c;
    // Warmwasser-Kachel nur, wenn Warmwasser über diese Heizung läuft
    const wwOn = m.ww_heizung !== false; // entscheidet die Integration (Regel 2)
    const extras = [];
    if (s.ww_grundlast && wwOn) extras.push({ name: TC.T('in.ww'), entity: s.ww_grundlast, unit: 'kWh/d', decimals: 1 });
    if (s.kennwert_temperaturbereinigt && TC.num(card._h, s.kennwert_temperaturbereinigt) !== null) {
      extras.push({ name: TC.T('in.kw_indoor'), entity: s.kennwert_temperaturbereinigt, unit: 'kWh/Kd', decimals: 2 });
    }
    return {
      kennwert: s.kennwert,
      // Farbe des Mediums (Hex aus colors/color, sonst die Standardfarbe als #rrggbb)
      color: (c.colors || {})[m.medium] || c.color || '#' + (TC.MEDIA[m.medium] || TC.MEDIA.gas).color.split(',').map((x) => Number(x).toString(16).padStart(2, '0')).join(''),
      months: c.months, history: c.history,
      extras,
      pending_text: TC.T('in.an_pending'), wait_text: TC.T('in.learning'), kw_caption: TC.T('in.kw_learned'),
    };
  };

  I.renderAnalyse = (card) => {
    const h = card._h;
    const t = TC.T;
    const c = card._c;
    const head = (sub) => card._header(c.icon || 'mdi:chart-bell-curve-cumulative', c.title || t('an.title'), sub, '');
    if (!card._meta) {
      I.load(card);
      return head('') + `<div class="setup">${card._metaErr ? t('in.missing') : esc(t('in.loading'))}</div>`;
    }
    I.load(card);
    const m = I.heatMeter(card);
    if (!m) return head('') + `<div class="setup">${t('in.no_heat')}</div>`;
    const s = m.sensoren || {};
    if (Object.values(s).some((id) => !h.states[id])) I.load(card, true);
    const a = I.analyseConfig(card);
    // Qualität des Kennwerts (Attribute des Kennwert-Sensors; bei Gas gleich der Prognose-Qualität)
    const kq = attr(h, s.kennwert, 'confidence');
    const qs = kq || (st(h, s.prognose_qualitaet) || {}).state;
    const quality = QUAL.includes(qs) ? qs : 'unzureichend';
    const days = kq ? attr(h, s.kennwert, 'sample_count') : attr(h, s.prognose_qualitaet, 'sample_count');
    const r2 = kq ? attr(h, s.kennwert, 'r_squared') : attr(h, s.prognose_qualitaet, 'r_squared');
    const facts = [t('in.quality', { q: t('q.' + quality) })];
    if (typeof days === 'number') facts.push(`${t('in.days')}: ${days}`);
    if (typeof r2 === 'number') facts.push(`${t('in.r2')}: ${TC.nf(r2, 2)}`);
    // Verlauf erst laden, wenn die Zuordnung da ist
    if (!card._histKey) TC.loadHistory(card, a);
    I.loadSeries(card, m.zaehler_id);
    const hints = [];
    const pct = attr(h, s.kennwert_temperaturbereinigt, 'prozent_je_kelvin');
    const pctQ = attr(h, s.kennwert_temperaturbereinigt, 'prozent_je_kelvin_qualitaet');
    if (typeof pct === 'number' && pctQ && pctQ !== 'annahme') hints.push(esc(t('in.pct_k', { p: TC.nf(pct, 1) })));
    const split = attr(h, s.kennwert_temperaturbereinigt, 'vorjahr');
    if (split && typeof split.gesamt_pct === 'number') {
      const sg = (v) => (v >= 0 ? '+' : '−') + TC.nf(Math.abs(v), 1) + ' %';
      hints.push(esc(t('in.split', { g: sg(split.gesamt_pct), r: sg(split.raumtemperatur_pct), v: sg(split.verhalten_pct),
        k: (split.innen_aenderung_k >= 0 ? '+' : '−') + TC.nf(Math.abs(split.innen_aenderung_k), 1) + ' K' })));
    }
    return head(`<small>${esc(m.name)}</small>`) + TC.analysisHtml(a, h, card._hist, t('an.kennwert'), '')
      + `<div class="qual">${esc(facts.join(' · '))}</div>`
      + hints.map((x) => `<div class="hint">${x}</div>`).join('')
      + I.seriesHtml(card, m) + I.genHtml(card);
  };

  // Reihen für die Diagramme (Streudiagramm, Kostenverlauf): gedrosselt wie die Zuordnung
  I.loadSeries = async (card, meterId) => {
    const h = card._h;
    if (!h || typeof h.callWS !== 'function' || card._seriesLoading || card._c.diagramme === false) return;
    if (card._seriesAt && card._seriesKey === meterId) {
      const age = Date.now() - card._seriesAt;
      if (age < (card._seriesErr ? 60e3 : 600e3)) return;
    }
    card._seriesLoading = true;
    card._seriesKey = meterId;
    try {
      card._series = await h.callWS({ type: 'tarif_cockpit/reihen', zaehler: meterId });
      card._seriesErr = null;
    } catch (e) {
      card._series = null;
      card._seriesErr = e;
    }
    card._seriesAt = Date.now();
    card._seriesLoading = false;
    card._last = null;
    card._render();
  };

  I.seriesHtml = (card, m) => {
    const t = TC.T;
    const r = card._series;
    if (!r || r.zaehler_id !== m.zaehler_id) return '';
    const med = TC.MEDIA[m.medium] || TC.MEDIA.gas;
    const c = TC.rgbOf((card._c.colors || {})[m.medium] || card._c.color, med.color);
    const adv = TC.rgbOf(card._c.advance_color, TC.OK);
    let out = '';
    const sc = r.streuung;
    if (sc && sc.punkte && sc.punkte.length) {
      const leg = [`<span class="leg"><i></i>${esc(sc.je_periode ? t('ch.periods') : t('ch.days'))}</span>`];
      if (sc.punkte.some((p) => p.ofen)) leg.push(`<span class="leg"><i class="of"></i>${esc(t('ch.stove_days'))}</span>`);
      if (sc.punkte.some((p) => p.klima)) leg.push(`<span class="leg"><i class="kl"></i>${esc(t('ch.hp_days'))}</span>`);
      const line = sc.kennwert !== null ? t('ch.line', { ww: TC.nf(sc.ww || 0, 1), k: TC.nf(sc.kennwert, 2) }) : '';
      out += `<div class="panel wide" style="--c:${c};--lc:${c}"><div class="chead"><span class="lbl">${esc(t('ch.scatter'))}</span>${leg.join('')}</div>`
        + TC.svgScatter(sc)
        + `<div class="qual">${esc([line, t('in.quality', { q: t('q.' + sc.qualitaet) }), sc.r2 !== null ? `R² ${TC.nf(sc.r2, 2)}` : ''].filter(Boolean).join(' · '))}</div></div>`;
    }
    const k = r.kosten;
    if (k && (k.ist.length || k.abschlaege.length)) {
      const leg = `<span class="leg"><i class="ist"></i>${esc(t('ch.ist'))}</span>`
        + (k.prognose.length ? `<span class="leg"><i class="fc"></i>${esc(t('ch.fc'))}</span>` : '')
        + (k.abschlaege.length ? `<span class="leg"><i class="st"></i>${esc(t('ch.adv'))}</span>` : '');
      out += `<div class="panel wide" style="--c:${c};--adv:${adv}"><div class="chead"><span class="lbl">${esc(t('ch.cost'))}</span>${leg}</div>${TC.svgCumul(k)}</div>`;
    }
    return out;
  };

  // Kacheln je Wärmeerzeuger: Eingang, Wärme, Entlastung (mit Qualität), Betrieb; Ofen zusätzlich Holz
  I.genHtml = (card) => {
    const h = card._h;
    const t = TC.T;
    const hh = card._meta && card._meta.haushalte && card._meta.haushalte[0];
    const gens = (hh && hh.waermeerzeuger) || [];
    if (!gens.length || card._c.erzeuger === false) return '';
    const kwh = (v) => (v === null ? '—' : TC.nf(v, 0) + ' kWh');
    // Entlastung nur, wenn es einen Wärmezähler gibt, der entlastet werden kann (Gas, Fernwärme)
    const relievable = hh.zaehler.some((m) => m.rolle === 'main' && HEAT.includes(m.medium));
    const items = gens.map((g) => {
      const s = g.sensoren || {};
      const hours = val(h, s.betriebsstunden);
      if (g.typ === 'fireplace' && !(hours > 0)) return ''; // Ofen-Kachel nur, wenn der Ofen gelaufen ist
      const input = val(h, s.energie_eingang), heat = val(h, s.waerme), avoided = val(h, s.entlastung);
      const est = attr(h, s.waerme, 'geschaetzt');
      const aq = attr(h, s.entlastung, 'qualitaet');
      const rows = [];
      if (input !== null) rows.push([t('g.input'), kwh(input)]);
      if (heat !== null) rows.push([est ? t('g.heat_est') : t('g.heat'), kwh(heat)]);
      if (relievable && ['fireplace', 'air_air_hp', 'water_hp', 'electric'].includes(g.typ)) {
        rows.push([t('g.avoided'), avoided === null ? `<small>${esc(t('g.not_learned'))}</small>` : `${kwh(avoided)} <small>${esc(t('q.' + (aq || 'annahme')))}</small>`]);
      }
      if (hours !== null) rows.push([t('g.hours'), `${TC.nf(hours, 0)} h · ${TC.nf(val(h, s.betriebstage) || 0, 0)} d`]);
      const kg = val(h, s.holz_geschaetzt), cost = val(h, s.holzkosten_geschaetzt);
      if (kg !== null) rows.push([t('g.wood'), `${TC.nf(kg, 0)} kg${cost !== null ? ' · ' + money(cost) : ''}`]);
      if (!rows.length) return '';
      return `<div class="gen"><div class="gh"><span>${esc(g.name)}</span><small>${esc(t('g.kind.' + g.typ))}</small></div><dl>${rows.map(([a, b]) => `<dt>${esc(a)}</dt><dd>${b}</dd>`).join('')}</dl></div>`;
    }).join('');
    return items ? `<div class="chead"><span class="lbl">${esc(t('g.title'))}</span></div><div class="gens">${items}</div>` : '';
  };

  // ---------------------------------------------------------------- Abschlagsdialog (Entscheidung B)

  I.openDialog = (card, deviceId) => {
    const m = I.meters(card).find((x) => x.device_id === deviceId);
    if (!m) return;
    const h = card._h;
    const s = m.sensoren || {};
    const rec = val(h, s.abschlag_empfohlen);
    const cur = val(h, s.abschlag);
    const ab = attr(h, s.abschlag_empfohlen, 'ab') || localIso(new Date());
    card._dlg = { device: deviceId, name: m.name, amount: rec !== null ? rec : cur, from: ab, rec, msg: '', busy: false };
    card._last = null;
    card._render();
  };

  // Werte im offenen Dialog nicht durch ein Neuzeichnen (neue Sensorwerte) zurücksetzen
  I.keepDialogInput = (card) => {
    if (!card._dlg || !card.shadowRoot) return;
    const a = card.shadowRoot.querySelector('[data-dlg="amount"]');
    const f = card.shadowRoot.querySelector('[data-dlg="from"]');
    if (a) card._dlg.amount = a.value === '' ? null : a.value;
    if (f) card._dlg.from = f.value;
  };

  I.dialogHtml = (card) => {
    const d = card._dlg;
    const t = TC.T;
    return `<div class="dlgbg"><div class="dlg" role="dialog">
      <div class="dlgt">${esc(t('dlg.title', { m: d.name }))}</div>
      <label>${esc(t('dlg.amount'))}<input type="number" step="1" min="0" data-dlg="amount" value="${d.amount === null || d.amount === undefined ? '' : d.amount}"></label>
      <label>${esc(t('dlg.from'))}<input type="date" data-dlg="from" value="${esc(d.from)}"></label>
      ${d.rec !== null && d.rec !== undefined ? `<div class="hint">${esc(t('dlg.hint', { v: money(d.rec) }))}</div>` : ''}
      ${d.msg ? `<div class="warn">${esc(d.msg)}</div>` : ''}
      <div class="dlgb"><button data-dlg="cancel">${esc(t('dlg.cancel'))}</button><button data-dlg="save" class="pri"${d.busy ? ' disabled' : ''}>${esc(t('dlg.save'))}</button></div>
    </div></div>`;
  };

  I.onClick = async (card, e) => {
    const adv = e.target.closest && e.target.closest('[data-advance]');
    if (adv) { I.openDialog(card, adv.getAttribute('data-advance')); return true; }
    const btn = e.target.closest && e.target.closest('[data-dlg]');
    if (!btn || !card._dlg || btn.tagName !== 'BUTTON') return false;
    const kind = btn.getAttribute('data-dlg');
    if (kind === 'cancel') { card._dlg = null; card._last = null; card._render(); return true; }
    const root = card.shadowRoot;
    const raw = root.querySelector('[data-dlg="amount"]').value;
    const amount = parseFloat(raw);
    const from = root.querySelector('[data-dlg="from"]').value;
    if (!(amount >= 0) || !from) {
      card._dlg = Object.assign(card._dlg, { amount: raw, from, msg: TC.T('dlg.invalid') });
      card._last = null; card._render();
      return true;
    }
    card._dlg = Object.assign(card._dlg, { amount, from, busy: true, msg: '' });
    card._last = null; card._render();
    try {
      await card._h.callService('tarif_cockpit', 'set_abschlag', { zaehler: card._dlg.device, ab: from, betrag: amount });
      card._dlg = null;
    } catch (err) {
      card._dlg.busy = false;
      card._dlg.msg = (err && err.message) || String(err);
    }
    card._last = null; card._render();
    return true;
  };

  I.CSS = `
.qual{margin-top:8px;font-size:.66rem;color:rgba(var(--mut),.9);text-transform:uppercase;letter-spacing:.06em}
.dlgbg{position:absolute;inset:0;background:rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center;z-index:5;border-radius:inherit}
.dlg{background:var(--panel);color:var(--txt);border:1px solid var(--stroke);border-radius:18px;padding:18px;min-width:260px;max-width:90%;box-shadow:0 10px 40px rgba(0,0,0,.4)}
.dlgt{font-weight:700;margin-bottom:10px}
.dlg label{display:block;font-size:.78rem;color:rgb(var(--mut));margin-top:10px}
.dlg input{display:block;width:100%;box-sizing:border-box;margin-top:4px;padding:8px;border-radius:10px;border:1px solid var(--stroke);background:rgba(var(--ov),.05);color:var(--txt);font:inherit}
.dlgb{display:flex;justify-content:flex-end;gap:8px;margin-top:14px}
.dlg button{padding:8px 14px;border-radius:10px;border:1px solid var(--stroke);background:transparent;color:var(--txt);font:inherit;cursor:pointer}
.dlg button.pri{background:rgb(var(--c,96,165,250));border-color:transparent;color:#0b1220;font-weight:700}
`;
})();


/* ---- wizard.js ---- */
/* Einrichtungsassistent: Schritt für Schritt Entitäten auswählen, mit Vorschlägen aus den vorhandenen Entitäten.
   Nur Standard-HTML (select, input), damit er auch ohne die Formular-Bausteine von Home Assistant funktioniert.
   Nach energy-cockpit/src/wizard.js, MIT License, Copyright (c) 2026 Musicmaker3112. Angepasst: Arten für Tarife,
   Schritte mit Bedingung (when), Auswahl der Medien, Texte über TC.T (Deutsch/Englisch). */
(() => {
  const TC = window.TarifCockpit;
  const ENERGY_UNITS = ['Wh', 'kWh', 'MWh'];
  const QTY_UNITS = ENERGY_UNITS.concat(['m³', 'm3', 'L', 'l']);
  const NUMERIC = ['sensor', 'input_number', 'number'];

  // Liste aller passenden Entitäten je Art
  const list = (hass, kind) => {
    const out = [];
    if (!hass || !hass.states) return out;
    Object.keys(hass.states).forEach((id) => {
      const s = hass.states[id], a = s.attributes || {}, u = a.unit_of_measurement || '', dc = a.device_class || '';
      const dom = id.split('.')[0];
      const txt = id + ' ' + (a.friendly_name || '');
      let ok = false;
      if (kind === 'money') ok = NUMERIC.includes(dom) && (/€|eur|chf|\$|£|usd|gbp/i.test(u) || dc === 'monetary' || /kosten|cost|abschl|advance|betrag|amount/i.test(txt));
      else if (kind === 'quantity') ok = dom === 'sensor' && (QTY_UNITS.includes(u) || dc === 'energy' || dc === 'gas' || dc === 'water' || dc === 'volume');
      else if (kind === 'energy') ok = dom === 'sensor' && (ENERGY_UNITS.includes(u) || dc === 'energy');
      else if (kind === 'temp') ok = dom === 'sensor' && (u === '°C' || u === '°F' || dc === 'temperature');
      else if (kind === 'date') ok = dom === 'input_datetime' || (dom === 'sensor' && (dc === 'date' || dc === 'timestamp'));
      else if (kind === 'value') ok = NUMERIC.includes(dom) && s.state !== '' && !isNaN(parseFloat(s.state));
      else if (kind === 'any') ok = ['sensor', 'input_number', 'number', 'input_datetime', 'input_text', 'counter'].includes(dom);
      if (ok) out.push({ id, name: a.friendly_name || id, state: s.state, unit: u });
    });
    return out.sort((x, y) => x.name.localeCompare(y.name, TC.lang));
  };

  // Treffer nach Stichwörtern sortieren: Vorschläge zuerst. hints: Liste von RegExp, frühere zählen mehr.
  // need: RegExp, die zusätzlich passen muss (z. B. das Medium), sonst kein Vorschlag
  const score = (e, hints, need) => {
    const t = (e.id + ' ' + e.name).toLowerCase();
    if (need && !need.test(t)) return 0;
    let s = 0;
    (hints || []).forEach((re, i) => { if (re.test(t)) s += 10 - i; });
    return s;
  };
  const suggest = (hass, kind, hints, need, exclude) => list(hass, kind)
    .filter((e) => !(exclude || []).includes(e.id) && score(e, hints, need) > 0)
    .sort((a, b) => score(b, hints, need) - score(a, hints, need));

  const getPath = (o, p) => p.split('.').reduce((a, k) => (a === undefined || a === null ? undefined : a[k]), o);
  // keep: auch false speichern (z. B. history: false)
  const setPath = (o, p, v, keep) => {
    const ks = p.split('.');
    let c = o;
    ks.slice(0, -1).forEach((k) => { if (typeof c[k] !== 'object' || c[k] === null) c[k] = {}; c = c[k]; });
    const last = ks[ks.length - 1];
    if (v === '' || v === undefined || v === null || (v === false && !keep)) delete c[last]; else c[last] = v;
  };
  const prune = (o) => {
    Object.keys(o).forEach((k) => {
      if (o[k] && typeof o[k] === 'object' && !Array.isArray(o[k])) { prune(o[k]); if (!Object.keys(o[k]).length) delete o[k]; }
    });
    return o;
  };

  // Entität, die nicht zum Filter passt (z. B. im YAML eingetragen), mit Name und Wert
  const own = (hass, id) => {
    const s = hass && id && hass.states && hass.states[id];
    return s ? { id, name: (s.attributes && s.attributes.friendly_name) || id, state: s.state, unit: (s.attributes && s.attributes.unit_of_measurement) || '' } : null;
  };
  const fmtState = (e) => (e ? `${e.state}${e.unit ? ' ' + e.unit : ''}` : '');
  // Listen können als Array oder als Objekt {0:…, 1:…} vorliegen (so speichert sie das Formular von Home Assistant)
  const arr = (v) => (Array.isArray(v) ? v : (v && typeof v === 'object' ? Object.keys(v).sort((a, b) => a - b).map((k) => v[k]) : []));

  // Baut den Assistenten. opts: { steps, hass, config, onChange(config), done }
  // Schritt: { short, title, text, fields, summary(cfg, hass), when(cfg, ui) }
  // Feld: { path, label, kind, hints, need, optional, auto, help, options, step, invert, itemKey, listKind, max }
  TC.createWizard = (opts) => {
    const t = TC.T;
    const root = document.createElement('div');
    root.style.cssText = 'font:inherit;color:var(--primary-text-color,inherit)';
    let cfg = JSON.parse(JSON.stringify(opts.config || {}));
    let hass = opts.hass;
    let step = 0;
    // Zwischenspeicher für abgewählte Medien: erneutes Anhaken stellt die Felder wieder her
    const stash = {};
    const ui = {};

    const emit = () => { prune(cfg); opts.onChange(JSON.parse(JSON.stringify(cfg))); };
    const css = {
      box: 'padding:10px 12px;margin:8px 0;border:1px solid var(--divider-color,#444);border-radius:10px',
      btn: 'cursor:pointer;margin:4px 6px 4px 0;padding:8px 14px;border-radius:8px;border:1px solid var(--divider-color,#555);background:var(--secondary-background-color,#222);color:var(--primary-text-color,#fff);font:inherit',
      primary: 'cursor:pointer;margin:4px 6px 4px 0;padding:8px 14px;border-radius:8px;border:0;background:var(--primary-color,#03a9f4);color:var(--text-primary-color,#fff);font:inherit;font-weight:600',
      input: 'width:100%;box-sizing:border-box;padding:8px;border-radius:8px;border:1px solid var(--divider-color,#555);background:var(--card-background-color,#111);color:var(--primary-text-color,#fff);font:inherit',
      label: 'display:block;font-weight:600;margin:12px 0 4px',
      help: 'font-size:.85em;opacity:.7;margin:2px 0 4px',
    };
    const el = (tag, style, text) => { const e = document.createElement(tag); if (style) e.style.cssText = style; if (text !== undefined) e.textContent = text; return e; };
    const opt = (v, txt) => { const o = document.createElement('option'); o.value = v; o.textContent = txt; return o; };
    const head = (wrap, f) => {
      wrap.appendChild(el('label', css.label, f.label + (f.optional ? t('wz.optional') : '')));
      if (f.help) wrap.appendChild(el('div', css.help, f.help));
    };

    const fieldSelect = (f) => {
      const wrap = el('div');
      head(wrap, f);
      const sel = el('select', css.input);
      const all = list(hass, f.kind || 'value');
      const cur = getPath(cfg, f.path) || '';
      const sug = all.filter((e) => score(e, f.hints, f.need) > 0).sort((a, b) => score(b, f.hints, f.need) - score(a, f.hints, f.need));
      // Nur die ersten 12 Vorschläge stehen oben, alle übrigen Treffer bleiben unten wählbar
      const top = sug.slice(0, 12);
      const rest = all.filter((e) => top.indexOf(e) < 0);
      sel.appendChild(opt('', t('wz.none')));
      const inList = cur && all.find((e) => e.id === cur);
      const mine = cur && !inList ? own(hass, cur) : null;
      if (mine) {
        const g0 = document.createElement('optgroup'); g0.label = t('wz.own');
        g0.appendChild(opt(cur, `${mine.name} (${fmtState(mine)})`));
        sel.appendChild(g0);
      } else if (cur && !inList) {
        // z. B. ein Datum als Text (period_start: 2026-07-30)
        sel.appendChild(opt(cur, /^\d{4}-\d{2}-\d{2}/.test(cur) ? t('wz.text', { v: cur }) : cur + ' ' + t('wz.notfound')));
      }
      const pool = mine ? all.concat([mine]) : all;
      if (top.length) {
        const g = document.createElement('optgroup'); g.label = t('wz.sug');
        top.forEach((e) => g.appendChild(opt(e.id, `${e.name} (${fmtState(e)})`)));
        sel.appendChild(g);
      }
      const g2 = document.createElement('optgroup'); g2.label = t('wz.all');
      rest.forEach((e) => g2.appendChild(opt(e.id, `${e.name} (${fmtState(e)})`)));
      sel.appendChild(g2);
      sel.value = cur;
      const live = el('div', css.help, '');
      const upd = () => { const e = pool.find((x) => x.id === sel.value); live.textContent = e ? t('wz.live', { v: fmtState(e), id: e.id }) : ''; };
      sel.addEventListener('change', () => { setPath(cfg, f.path, sel.value); upd(); emit(); });
      upd();
      wrap.appendChild(sel);
      wrap.appendChild(live);
      if (!cur && sug.length && f.auto !== false && !f.optional) {
        const b = el('button', css.btn, t('wz.take', { n: sug[0].name }));
        b.type = 'button';
        b.addEventListener('click', () => { setPath(cfg, f.path, sug[0].id); emit(); render(); });
        wrap.appendChild(b);
      }
      return wrap;
    };

    // invert: angehakt bedeutet "false speichern" (z. B. "Verlauf ausblenden" → history: false)
    const fieldBool = (f) => {
      const wrap = el('div');
      const l = el('label', css.label + ';display:flex;align-items:center;gap:8px;font-weight:500');
      const c = document.createElement('input'); c.type = 'checkbox';
      const v = getPath(cfg, f.path);
      c.checked = f.invert ? v === false : !!v;
      c.addEventListener('change', () => {
        if (f.invert) setPath(cfg, f.path, c.checked ? false : '', true); else setPath(cfg, f.path, c.checked ? true : '');
        emit();
      });
      l.appendChild(c); l.appendChild(document.createTextNode(f.label));
      wrap.appendChild(l);
      if (f.help) wrap.appendChild(el('div', css.help, f.help));
      return wrap;
    };

    // Auswahl der Medien: Anhaken legt den Abschnitt an, Abwählen entfernt ihn (bleibt im Zwischenspeicher)
    const fieldMedia = (f) => {
      const wrap = el('div');
      head(wrap, f);
      f.options.forEach((o) => {
        const l = el('label', 'display:flex;align-items:center;gap:8px;margin:8px 0;font-weight:500');
        const c = document.createElement('input'); c.type = 'checkbox';
        c.checked = !!ui[o.value];
        c.addEventListener('change', () => {
          ui[o.value] = c.checked;
          if (c.checked) cfg[o.value] = Object.assign({}, stash[o.value] || {}, cfg[o.value] || {});
          else { if (cfg[o.value]) stash[o.value] = cfg[o.value]; delete cfg[o.value]; }
          emit(); render();
        });
        l.appendChild(c); l.appendChild(document.createTextNode(o.label));
        wrap.appendChild(l);
      });
      return wrap;
    };

    // Farbschema: Kacheln mit Vorschau
    const fieldTheme = (f) => {
      const wrap = el('div');
      head(wrap, f);
      const grid = el('div', 'display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px');
      const cur = getPath(cfg, f.path) || 'dunkel';
      const T = TC.THEMES;
      TC.THEME_KEYS.forEach((k) => {
        const bg = k === 'auto' ? `linear-gradient(110deg,${T.dunkel.bg1} 0 50%,${T.hell.bg1} 50% 100%)` : k === 'ha' ? 'var(--card-background-color,#222)' : T[k].bg1;
        const fg = k === 'auto' ? '#8b97b3' : T[k].txt;
        const tile = el('button', `cursor:pointer;text-align:left;padding:10px;border-radius:10px;font:inherit;border:2px solid ${cur === k ? 'var(--primary-color,#03a9f4)' : 'var(--divider-color,#555)'};background:${bg};color:${fg}`);
        tile.type = 'button';
        tile.appendChild(el('div', k === 'auto' ? 'font-weight:700;display:inline-block;padding:1px 7px;border-radius:6px;background:rgba(15,23,42,.8);color:#fff' : 'font-weight:700', t('th.' + k)));
        const dots = el('div', 'display:flex;gap:4px;margin-top:6px');
        [TC.MEDIA.strom.color, TC.OK, TC.BAD].forEach((c) => dots.appendChild(el('span', `width:14px;height:14px;border-radius:50%;background:rgb(${c})`)));
        tile.appendChild(dots);
        tile.addEventListener('click', () => { setPath(cfg, f.path, k === 'dunkel' ? '' : k); emit(); render(); });
        grid.appendChild(tile);
      });
      wrap.appendChild(grid);
      return wrap;
    };

    const fieldChoice = (f) => {
      const wrap = el('div');
      head(wrap, f);
      const sel = el('select', css.input);
      f.options.forEach((o) => sel.appendChild(opt(o.value, o.label)));
      sel.value = getPath(cfg, f.path) || f.options[0].value;
      sel.addEventListener('change', () => { setPath(cfg, f.path, sel.value); emit(); });
      wrap.appendChild(sel);
      return wrap;
    };

    const fieldInput = (f, type) => {
      const wrap = el('div');
      head(wrap, f);
      const i = el('input', css.input);
      i.type = type;
      if (type === 'number') { i.step = f.step || '0.1'; i.min = f.min !== undefined ? f.min : '0'; }
      if (f.placeholder) i.placeholder = f.placeholder;
      const cur = getPath(cfg, f.path);
      i.value = cur === undefined ? '' : cur;
      i.addEventListener('change', () => { const v = type === 'number' ? (i.value === '' ? '' : parseFloat(i.value)) : i.value; setPath(cfg, f.path, v); emit(); });
      wrap.appendChild(i);
      return wrap;
    };

    // Dynamische Liste (Fußzeilen-Kacheln, Zusatzkacheln): Entität + Name (+ Einheit) je Zeile
    const fieldList = (f) => {
      const wrap = el('div');
      head(wrap, f);
      const KEY = f.itemKey || 'entity';
      const all = list(hass, f.listKind || 'any');
      const items = arr(getPath(cfg, f.path)).filter((x) => x && typeof x === 'object');
      const used = items.map((x) => x[KEY]);
      const write = (a) => { const v = a.filter((x) => x[KEY]); setPath(cfg, f.path, v.length ? v : ''); emit(); };
      items.forEach((it, i) => {
        const row = el('div', css.box);
        const sel = el('select', css.input);
        sel.appendChild(opt(it[KEY] || '', (all.find((e) => e.id === it[KEY]) || own(hass, it[KEY]) || { name: it[KEY] || '—' }).name));
        all.forEach((e) => { if (e.id !== it[KEY]) sel.appendChild(opt(e.id, `${e.name} (${fmtState(e)})`)); });
        sel.value = it[KEY] || '';
        sel.addEventListener('change', () => { it[KEY] = sel.value; write(items); render(); });
        const nm = el('input', css.input + ';margin-top:6px');
        nm.placeholder = t('wz.name_ph');
        nm.value = it.name || '';
        nm.addEventListener('change', () => { if (nm.value) it.name = nm.value; else delete it.name; write(items); });
        row.appendChild(sel); row.appendChild(nm);
        if (f.unitKey) {
          const un = el('input', css.input + ';margin-top:6px');
          un.placeholder = t('wz.unit_ph');
          un.value = it[f.unitKey] || '';
          un.addEventListener('change', () => { if (un.value) it[f.unitKey] = un.value; else delete it[f.unitKey]; write(items); });
          row.appendChild(un);
        }
        const rm = el('button', css.btn, t('wz.remove')); rm.type = 'button';
        rm.addEventListener('click', () => { items.splice(i, 1); write(items); render(); });
        row.appendChild(rm);
        wrap.appendChild(row);
      });
      if (items.length < (f.max || 12)) {
        const add = el('div', css.box);
        add.appendChild(el('div', css.help, t('wz.add')));
        const sel = el('select', css.input);
        sel.appendChild(opt('', t('wz.pick')));
        all.filter((e) => used.indexOf(e.id) < 0).forEach((e) => sel.appendChild(opt(e.id, `${e.name} (${fmtState(e)})`)));
        sel.addEventListener('change', () => {
          if (!sel.value) return;
          items.push({ [KEY]: sel.value });
          write(items); render();
        });
        add.appendChild(sel);
        wrap.appendChild(add);
      }
      return wrap;
    };

    const visible = () => opts.steps.filter((s) => !s.when || s.when(cfg, ui));

    function render() {
      root.innerHTML = '';
      const steps = visible();
      if (step >= steps.length) step = steps.length - 1;
      const st = steps[step];
      // Fortschritt
      const prog = el('div', 'display:flex;gap:6px;margin:4px 0 10px;flex-wrap:wrap');
      steps.forEach((s, i) => {
        const b = el('button', 'cursor:pointer;padding:4px 10px;border-radius:999px;border:1px solid var(--divider-color,#555);background:' + (i === step ? 'var(--primary-color,#03a9f4)' : 'transparent') + ';color:' + (i === step ? 'var(--text-primary-color,#fff)' : 'inherit') + ';font:inherit;font-size:.85em', `${i + 1}. ${s.short || s.title}`);
        b.type = 'button';
        b.addEventListener('click', () => { step = i; render(); });
        prog.appendChild(b);
      });
      root.appendChild(prog);
      root.appendChild(el('div', 'font-size:1.15em;font-weight:700;margin:6px 0', st.title));
      if (st.text) root.appendChild(el('div', css.help + ';font-size:.95em', st.text));
      (st.fields || []).forEach((f) => {
        if (f.kind === 'bool') root.appendChild(fieldBool(f));
        else if (f.kind === 'number') root.appendChild(fieldInput(f, 'number'));
        else if (f.kind === 'text') root.appendChild(fieldInput(f, 'text'));
        else if (f.kind === 'list') root.appendChild(fieldList(f));
        else if (f.kind === 'choice') root.appendChild(fieldChoice(f));
        else if (f.kind === 'theme') root.appendChild(fieldTheme(f));
        else if (f.kind === 'media') root.appendChild(fieldMedia(f));
        else root.appendChild(fieldSelect(f));
      });
      if (st.summary) {
        const rows = st.summary(cfg, hass);
        const b = el('div', css.box);
        rows.forEach((r) => b.appendChild(el('div', 'margin:2px 0', r)));
        root.appendChild(b);
      }
      const nav = el('div', 'margin-top:14px');
      if (step > 0) { const b = el('button', css.btn, t('wz.back')); b.type = 'button'; b.addEventListener('click', () => { step--; render(); }); nav.appendChild(b); }
      if (step < steps.length - 1) { const b = el('button', css.primary, t('wz.next')); b.type = 'button'; b.addEventListener('click', () => { step++; render(); }); nav.appendChild(b); }
      else if (opts.done) { const b = el('button', css.primary, t('wz.done')); b.type = 'button'; b.addEventListener('click', () => opts.done()); nav.appendChild(b); }
      root.appendChild(nav);
    }
    const initUi = () => { Object.keys(TC.MEDIA).forEach((k) => { ui[k] = !!(cfg[k] && typeof cfg[k] === 'object'); }); };
    initUi();
    if (opts.step) step = opts.step;
    render();
    return {
      el: root,
      // Kommen die Entitäten erst nach dem Aufbau (Home Assistant setzt oft zuerst die Konfiguration), einmal neu zeichnen
      setHass(h) { const first = !hass || !hass.states; hass = h; if (first && h && h.states) render(); },
      setConfig(c) { cfg = JSON.parse(JSON.stringify(c || {})); initUi(); render(); },
      goto(i) { step = i; render(); },
    };
  };

  TC.wizardList = list;
  TC.wizardScore = score;
  TC.suggest = suggest;
  TC.toList = arr;
  TC.prune = prune;
})();


/* ---- editor-kit.js ---- */
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


/* ---- overview-card.js ---- */
/* Karte 1: tarif-cockpit-card. Kacheln je Medium (Strom/Gas/Wasser) mit Urteil, Betrag, vier Balken und passendem Abschlag.
   Sensor-Modus: Die Karte rechnet keine Prognose, sie bildet nur das Urteil aus Abschlag, Hochrechnung und Toleranz (Regel 2). */
(() => {
  const TC = window.TarifCockpit;
  const { esc } = TC;

  class TarifCockpitCard extends TC.BaseCard {
    static getConfigElement() { return document.createElement('tarif-cockpit-card-editor'); }

    // Vorschläge aus den vorhandenen Entitäten, keine fest eingebauten Namen (Regel 6)
    static getStubConfig(hass) {
      // Mit eingerichteter Integration: Integrations-Modus (keine Entitätsnamen nötig)
      if (TC.integ && TC.integ.available(hass)) return { integration: true };
      return TC.overviewStub ? TC.overviewStub(hass) : {};
    }

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
      if (this._c.integration && TC.integ) {
        this._put(TC.integ.render(this));
        return;
      }
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


/* ---- overview-editor.js ---- */
/* Editor der Karte 1 (tarif-cockpit-card): Assistent, Formular und Vorschläge für getStubConfig. Sensor-Modus. */
(() => {
  const TC = window.TarifCockpit;
  const { txt, icon, ent, numb, sec, theme } = TC.sf;

  TC.addStrings('de', {
    'ov.s_media': 'Medien', 'ov.t_media': 'Was soll die Karte zeigen?',
    'ov.x_media': 'Wähle die Medien, für die du Abschläge zahlst. Für jedes Medium folgt ein Schritt mit seinen Sensoren.',
    'ov.f_media': 'Medien',
    'ov.x_medium': 'Die Karte rechnet nicht selbst. Sie zeigt, was diese Sensoren liefern, und bildet daraus das Urteil: Abschlag × Monate − Hochrechnung. Wie man die Sensoren baut, steht in docs/SENSOR-MODUS.md.',
    'ov.cost': 'Kosten bisher (seit Beginn des Abrechnungszeitraums)', 'ov.advance_paid': 'Bisher gezahlte Abschläge',
    'ov.forecast_cost': 'Hochrechnung der Kosten bis zum Ende des Zeitraums', 'ov.forecast_kwh': 'Hochrechnung des Verbrauchs (kWh)',
    'ov.advance': 'Monatlicher Abschlag', 'ov.months': 'Abschläge pro Jahr', 'ov.months_h': 'Standard 12. Bei 11 Abschlägen hier 11 eintragen.',
    'ov.name': 'Anzeigename', 'ov.color': 'Farbe (z. B. #fb923c)', 'ov.start': 'Eigener Beginn (Datum oder Datums-Helfer)',
    'ov.stale_hint': 'Hinweistext (z. B. "Ablesung überfällig")', 'ov.advance_color_m': 'Farbe der Abschlagsbalken (nur dieses Medium)',
    'ov.s_period': 'Zeitraum', 'ov.t_period': 'Abrechnungszeitraum und Kopfzeile',
    'ov.x_period': 'Mit einem Datums-Helfer (input_datetime) lässt sich der Beginn später per Tipp auf der Karte ändern.',
    'ov.period_start': 'Beginn des Abrechnungszeitraums', 'ov.period_end': 'Ende (sonst ein Jahr nach dem Beginn)',
    'ov.title': 'Titel', 'ov.subtitle': 'Untertitel (wird durch den Zeitraum ersetzt)', 'ov.icon': 'Symbol',
    'ov.tolerance_pct': 'Toleranz für "Passt" in %', 'ov.tolerance_h': 'Standard 5. Liegt die Differenz darunter, steht dort "Passt".',
    'ov.s_look': 'Aussehen', 'ov.t_look': 'Farbschema',
    'ov.x_look': 'Dunkel ist die Voreinstellung. "Automatisch" folgt dem hellen oder dunklen Design von Home Assistant, "Home Assistant" übernimmt dessen Farben.',
    'ov.theme': 'Farbschema', 'ov.advance_color': 'Farbe der Abschlagsbalken (Standard grün, z. B. #34d399)',
    'ov.s_footer': 'Fußzeile', 'ov.t_footer': 'Kacheln unten',
    'ov.x_footer': 'Beliebige Werte unter den Medien, zum Beispiel Zählerstände, Tarife oder die letzte Ablesung. Weitere Optionen (decimals, scale, format: date) im YAML.',
    'ov.footer': 'Kacheln',
    'ov.s_done': 'Fertig', 'ov.t_done': 'Zusammenfassung', 'ov.x_done': 'Alles ist gespeichert.',
    'ov.sum_media': 'Medien: {v}', 'ov.sum_none': 'keine', 'ov.sum_period': 'Zeitraum: {v}', 'ov.sum_period_none': 'nicht gesetzt',
    'ov.sum_missing': '{m}: es fehlt {f}', 'ov.sum_ok': '{m}: vollständig',
    'ov.sec': 'Sensoren {m}', 'ov.footer_form': 'Die Fußzeilen-Kacheln werden im Assistenten oder im YAML bearbeitet.',
  });
  TC.addStrings('en', {
    'ov.s_media': 'Utilities', 'ov.t_media': 'What should the card show?',
    'ov.x_media': 'Choose the utilities you pay advances for. Each one gets a step with its sensors.',
    'ov.f_media': 'Utilities',
    'ov.x_medium': 'The card does not calculate anything itself. It shows what these sensors provide and forms the verdict: advance × months − projection. How to build the sensors is described in docs/SENSOR-MODUS.md.',
    'ov.cost': 'Costs so far (since the start of the billing period)', 'ov.advance_paid': 'Advances paid so far',
    'ov.forecast_cost': 'Projected costs up to the end of the period', 'ov.forecast_kwh': 'Projected consumption (kWh)',
    'ov.advance': 'Monthly advance', 'ov.months': 'Advances per year', 'ov.months_h': 'Default 12. Enter 11 if you pay 11 advances.',
    'ov.name': 'Display name', 'ov.color': 'Colour (e.g. #fb923c)', 'ov.start': 'Own start (date or date helper)',
    'ov.stale_hint': 'Hint text (e.g. "meter reading overdue")', 'ov.advance_color_m': 'Colour of the advance bars (this utility only)',
    'ov.s_period': 'Period', 'ov.t_period': 'Billing period and header',
    'ov.x_period': 'With a date helper (input_datetime) the start can later be changed by tapping it on the card.',
    'ov.period_start': 'Start of the billing period', 'ov.period_end': 'End (otherwise one year after the start)',
    'ov.title': 'Title', 'ov.subtitle': 'Subtitle (replaced by the period)', 'ov.icon': 'Icon',
    'ov.tolerance_pct': 'Tolerance for "on track" in %', 'ov.tolerance_h': 'Default 5. Below this difference the card shows "on track".',
    'ov.s_look': 'Look', 'ov.t_look': 'Colour scheme',
    'ov.x_look': 'Dark is the default. "Automatic" follows the light or dark theme of Home Assistant, "Home Assistant" uses its colours.',
    'ov.theme': 'Colour scheme', 'ov.advance_color': 'Colour of the advance bars (default green, e.g. #34d399)',
    'ov.s_footer': 'Footer', 'ov.t_footer': 'Tiles at the bottom',
    'ov.x_footer': 'Any values below the utilities, for example meter readings, prices or the last reading. More options (decimals, scale, format: date) in YAML.',
    'ov.footer': 'Tiles',
    'ov.s_done': 'Done', 'ov.t_done': 'Summary', 'ov.x_done': 'Everything is saved.',
    'ov.sum_media': 'Utilities: {v}', 'ov.sum_none': 'none', 'ov.sum_period': 'Period: {v}', 'ov.sum_period_none': 'not set',
    'ov.sum_missing': '{m}: missing {f}', 'ov.sum_ok': '{m}: complete',
    'ov.sec': 'Sensors {m}', 'ov.footer_form': 'Footer tiles are edited in the wizard or in YAML.',
  });

  // Stichwörter je Medium und Feld (deutsch und englisch). Vorschläge verlangen immer das Medium (need).
  const MW = { strom: /strom|electric|elec/i, gas: /(^|[^a-z])gas/i, wasser: /wasser|water/i };
  const H = {
    cost: [/kosten|cost/i, /bisher|so_far|period|abrechnung|billing|jahr|year/i],
    advance_paid: [/abschl[aä]g\w*_?(bisher|gezahlt|abrechnung|jahr)|advances?_?paid|paid/i, /abschl|advance/i],
    forecast_cost: [/prognose|forecast|hochrechn|projection/i, /kosten|cost/i],
    forecast_kwh: [/prognose|forecast|hochrechn|projection/i, /verbrauch|consumption|kwh/i],
    advance: [/abschlag|advance|installment|vorauszahl/i],
  };
  const KIND = { cost: 'money', advance_paid: 'money', forecast_cost: 'money', forecast_kwh: 'quantity', advance: 'money' };
  // Felder, die für das Urteil gebraucht werden
  const NEED = ['forecast_cost', 'advance'];
  const FIELDS = ['cost', 'advance_paid', 'forecast_cost', 'forecast_kwh', 'advance'];
  // Ausschluss: "Prognose-Kosten" ist kein "Kosten bisher", der Abschlag selbst ist kein "Abschläge bisher"
  const NOT = { cost: /prognose|forecast|hochrechn|abschl|advance/i, advance_paid: /prognose|forecast/i, advance: /bisher|paid|gezahlt|jahr|year|prognose|forecast/i };

  const pick = (hass, k, f, used) => {
    const s = TC.suggest(hass, KIND[f], H[f], MW[k], used).filter((e) => !(NOT[f] && NOT[f].test(e.id + ' ' + e.name)));
    return s.length ? s[0].id : null;
  };

  // getStubConfig: nur übernehmen, was eindeutig zu einem Medium passt; ohne Treffer {} (Karte zeigt "Im Editor einrichten")
  TC.overviewStub = (hass) => {
    const out = {};
    if (!hass || !hass.states) return out;
    const used = [];
    Object.keys(TC.MEDIA).forEach((k) => {
      const m = {};
      FIELDS.forEach((f) => { const id = pick(hass, k, f, used); if (id) { m[f] = id; used.push(id); } });
      if (NEED.every((f) => m[f])) out[k] = m;
    });
    return out;
  };

  const mediumStep = (k) => ({
    short: TC.T('media.' + k), title: TC.T('media.' + k), text: TC.T('ov.x_medium'),
    when: (cfg, ui) => !!ui[k],
    fields: [
      { path: k + '.cost', label: TC.T('ov.cost'), kind: 'money', hints: H.cost, need: MW[k] },
      { path: k + '.advance_paid', label: TC.T('ov.advance_paid'), kind: 'money', hints: H.advance_paid, need: MW[k] },
      { path: k + '.forecast_cost', label: TC.T('ov.forecast_cost'), kind: 'money', hints: H.forecast_cost, need: MW[k] },
      { path: k + '.forecast_kwh', label: TC.T('ov.forecast_kwh'), kind: 'quantity', hints: H.forecast_kwh, need: MW[k], optional: true },
      { path: k + '.advance', label: TC.T('ov.advance'), kind: 'money', hints: H.advance, need: MW[k] },
      { path: k + '.months', label: TC.T('ov.months'), kind: 'number', step: '1', min: 1, optional: true, help: TC.T('ov.months_h') },
      { path: k + '.name', label: TC.T('ov.name'), kind: 'text', optional: true, placeholder: TC.T('media.' + k) },
    ],
  });

  const steps = () => {
    const t = TC.T;
    return [
      { short: t('ov.s_media'), title: t('ov.t_media'), text: t('ov.x_media'), fields: [
        { path: '_media', label: t('ov.f_media'), kind: 'media', options: Object.keys(TC.MEDIA).map((k) => ({ value: k, label: t('media.' + k) })) },
      ] },
      mediumStep('strom'), mediumStep('gas'), mediumStep('wasser'),
      { short: t('ov.s_period'), title: t('ov.t_period'), text: t('ov.x_period'), fields: [
        { path: 'period_start', label: t('ov.period_start'), kind: 'date', optional: true, hints: [/abrechnung|billing|beginn|start/i] },
        { path: 'period_end', label: t('ov.period_end'), kind: 'date', optional: true, hints: [/abrechnung|billing/i, /ende|end/i] },
        { path: 'title', label: t('ov.title'), kind: 'text', optional: true, placeholder: t('card.title') },
        { path: 'tolerance_pct', label: t('ov.tolerance_pct'), kind: 'number', step: '1', optional: true, help: t('ov.tolerance_h') },
      ] },
      { short: t('ov.s_look'), title: t('ov.t_look'), text: t('ov.x_look'), fields: [
        { path: 'theme', label: t('ov.theme'), kind: 'theme' },
        { path: 'advance_color', label: t('ov.advance_color'), kind: 'text', optional: true },
      ] },
      { short: t('ov.s_footer'), title: t('ov.t_footer'), text: t('ov.x_footer'), fields: [
        { path: 'footer', label: t('ov.footer'), kind: 'list', listKind: 'any', itemKey: 'entity', unitKey: 'unit', max: 12 },
      ] },
      { short: t('ov.s_done'), title: t('ov.t_done'), text: t('ov.x_done'), summary: (c) => {
        const ks = Object.keys(TC.MEDIA).filter((k) => c[k]);
        const rows = [t('ov.sum_media', { v: ks.length ? ks.map((k) => t('media.' + k)).join(', ') : t('ov.sum_none') })];
        ks.forEach((k) => {
          const miss = NEED.concat(['cost', 'advance_paid']).filter((f) => !c[k][f]);
          rows.push(miss.length ? t('ov.sum_missing', { m: t('media.' + k), f: miss.map((f) => t('ov.' + f)).join(', ') }) : t('ov.sum_ok', { m: t('media.' + k) }));
        });
        rows.push(t('ov.sum_period', { v: c.period_start || t('ov.sum_period_none') }));
        return rows;
      } },
    ];
  };

  const LABEL_KEYS = ['title', 'subtitle', 'icon', 'period_start', 'period_end', 'theme', 'tolerance_pct', 'advance_color',
    'cost', 'advance_paid', 'forecast_cost', 'forecast_kwh', 'advance', 'months', 'name', 'color', 'start', 'stale_hint'];
  const form = () => {
    const t = TC.T;
    const medium = (k) => sec(k, t('ov.sec', { m: t('media.' + k) }), [
      ent('cost', ['sensor', 'input_number', 'number']), ent('advance_paid', ['sensor', 'input_number', 'number']),
      ent('forecast_cost', ['sensor', 'input_number', 'number']), ent('forecast_kwh', ['sensor', 'input_number', 'number']),
      ent('advance', ['input_number', 'sensor', 'number']), numb('months', 1, 12, 1),
      txt('name'), txt('color'), txt('start'), txt('stale_hint'), Object.assign(txt('advance_color'), { _m: true }),
    ]);
    return {
      schema: [
        txt('title'), txt('subtitle'), icon('icon'),
        txt('period_start'), txt('period_end'), numb('tolerance_pct', 0, 50, 1),
        theme('theme'), txt('advance_color'),
        medium('strom'), medium('gas'), medium('wasser'),
      ],
      computeLabel: (s) => (s.name === 'advance_color' && s._m ? t('ov.advance_color_m') : LABEL_KEYS.includes(s.name) ? t('ov.' + s.name) : s.title || s.name),
      computeHelper: (s) => (s.name === 'months' ? t('ov.months_h') : s.name === 'tolerance_pct' ? t('ov.tolerance_h') : s.name === 'period_start' ? t('ov.x_period') : s.name === 'title' ? t('ov.footer_form') : undefined),
    };
  };

  // Reiter "Integration": nur Zähler wählen und Darstellung (Abschnitt 7)
  TC.integTab = (opts) => (root, api) => {
    const single = !!(opts && opts.single);
    const pick = (opts && opts.filter) || ((m) => m.rolle === 'main');
    const t = TC.T;
    const h = api.hass();
    const cfg = api.config();
    const el = (tag, style, text) => { const e = document.createElement(tag); if (style) e.style.cssText = style; if (text !== undefined) e.textContent = text; return e; };
    root.appendChild(el('div', 'opacity:.75;margin:4px 0 10px', t('ei.text')));
    const box = el('div');
    root.appendChild(box);
    if (!cfg.integration) {
      box.appendChild(el('div', 'margin:6px 0 10px', t('ei.switch')));
      const go = el('button', 'cursor:pointer;padding:8px 14px;border-radius:8px;border:none;background:var(--primary-color,#03a9f4);color:var(--text-primary-color,#fff);font:inherit', t('ei.switch_btn'));
      go.type = 'button';
      go.addEventListener('click', () => { api.emit(Object.assign({}, api.config(), { integration: true })); api.rerender(); });
      box.appendChild(go);
      return;
    }
    const draw = (meta) => {
      box.innerHTML = '';
      const hh = meta && meta.haushalte && meta.haushalte[0];
      const mains = hh ? hh.zaehler.filter((m) => pick(m, hh)) : [];
      box.appendChild(el('div', 'font-weight:600;margin:8px 0 4px', t('ei.meters')));
      if (!mains.length) box.appendChild(el('div', 'opacity:.7', t('ei.none')));
      const chosen = Array.isArray(cfg.zaehler) && cfg.zaehler.length ? cfg.zaehler : single ? mains.slice(0, 1).map((m) => m.device_id) : mains.map((m) => m.device_id);
      mains.forEach((m) => {
        const l = el('label', 'display:flex;align-items:center;gap:8px;margin:6px 0');
        const c = document.createElement('input'); c.type = single ? 'radio' : 'checkbox'; c.name = 'tcm'; c.checked = chosen.includes(m.device_id); c.dataset.meter = m.device_id;
        c.addEventListener('change', () => {
          const ids = [...box.querySelectorAll('input[data-meter]')].filter((x) => x.checked).map((x) => x.dataset.meter);
          const next = Object.assign({}, api.config(), { integration: true });
          if (ids.length && (single || ids.length < mains.length)) next.zaehler = ids; else delete next.zaehler;
          api.emit(next);
        });
        l.appendChild(c); const ml = t('media.' + m.medium); l.appendChild(document.createTextNode(m.name === ml ? m.name : `${m.name} (${ml})`));
        box.appendChild(l);
      });
      box.appendChild(el('div', 'font-weight:600;margin:12px 0 4px', t('ei.title')));
      const ti = el('input', 'width:100%;box-sizing:border-box;padding:8px;border-radius:8px;border:1px solid var(--divider-color,#555);background:var(--card-background-color,#111);color:var(--primary-text-color,#fff);font:inherit');
      ti.value = cfg.title || ''; ti.placeholder = t((opts && opts.titleKey) || 'card.title');
      ti.addEventListener('change', () => { const next = Object.assign({}, api.config(), { integration: true, title: ti.value }); if (!ti.value) delete next.title; api.emit(next); });
      box.appendChild(ti);
      box.appendChild(el('div', 'font-weight:600;margin:12px 0 4px', t('ei.theme')));
      const sel = el('select', 'width:100%;padding:8px;border-radius:8px;border:1px solid var(--divider-color,#555);background:var(--card-background-color,#111);color:var(--primary-text-color,#fff);font:inherit');
      TC.THEME_KEYS.forEach((k) => { const o = document.createElement('option'); o.value = k; o.textContent = t('th.' + k); sel.appendChild(o); });
      sel.value = cfg.theme || 'dunkel';
      sel.addEventListener('change', () => { const next = Object.assign({}, api.config(), { integration: true, theme: sel.value }); if (sel.value === 'dunkel') delete next.theme; api.emit(next); });
      box.appendChild(sel);
      // Farben je Medium der gewählten Zähler
      const media = [...new Set(mains.map((m) => m.medium))];
      if (media.length) {
        box.appendChild(el('div', 'font-weight:600;margin:12px 0 4px', t('ei.colors')));
        const row = el('div', 'display:flex;gap:14px;flex-wrap:wrap');
        media.forEach((md) => {
          const lab = el('label', 'display:flex;align-items:center;gap:6px');
          const inp = document.createElement('input'); inp.type = 'color'; inp.dataset.color = md;
          const cur = (cfg.colors || {})[md];
          const rgb = (TC.MEDIA[md] || TC.MEDIA.strom).color.split(',').map((x) => Number(x).toString(16).padStart(2, '0')).join('');
          inp.value = typeof cur === 'string' && /^#[0-9a-f]{6}$/i.test(cur) ? cur : '#' + rgb;
          inp.addEventListener('change', () => {
            const next = Object.assign({}, api.config(), { integration: true });
            next.colors = Object.assign({}, next.colors || {}, { [md]: inp.value });
            api.emit(next);
          });
          lab.appendChild(inp); lab.appendChild(document.createTextNode(t('media.' + md)));
          row.appendChild(lab);
        });
        box.appendChild(row);
      }
      const sm = el('button', 'cursor:pointer;margin-top:14px;padding:8px 14px;border-radius:8px;border:1px solid var(--divider-color,#555);background:transparent;color:inherit;font:inherit', t('ei.sensor_mode'));
      sm.type = 'button';
      sm.addEventListener('click', () => { const next = Object.assign({}, api.config()); delete next.integration; delete next.zaehler; api.emit(next); api.setTab('form'); });
      box.appendChild(sm);
    };
    if (h && typeof h.callWS === 'function') {
      box.textContent = TC.T('in.loading');
      h.callWS({ type: 'tarif_cockpit/zaehler' }).then(draw).catch(() => { box.innerHTML = TC.T('in.missing'); });
    } else draw(null);
  };

  TC.defineEditor('tarif-cockpit-card-editor', {
    integTab: TC.integTab(),
    needsSetup: (c) => !Object.keys(TC.MEDIA).some((k) => c[k] && typeof c[k] === 'object' && Object.keys(c[k]).length),
    steps,
    form,
  });
})();


/* ---- analyse-card.js ---- */
/* Karte 2: tarif-cockpit-analyse-card. Auswertung (z. B. Gas witterungsbereinigt): Kennwert, Vergleich, Kacheln, Verlauf.
   Die Felder entsprechen dem früheren Block "analysis" der Karte 1, hier auf oberster Ebene. Die Karte rechnet nichts (Regel 2). */
(() => {
  const TC = window.TarifCockpit;
  const { esc } = TC;

  class TarifCockpitAnalyseCard extends TC.BaseCard {
    static getConfigElement() { return document.createElement('tarif-cockpit-analyse-card-editor'); }

    static getStubConfig(hass) {
      if (TC.integ && TC.integ.available(hass)) return { integration: true };
      return TC.analyseStub ? TC.analyseStub(hass) : {};
    }

    getCardSize() { return 7; }

    setConfig(c) {
      if (!c || typeof c !== 'object') throw new Error('tarif-cockpit-analyse-card: Konfiguration fehlt');
      this._c = c;
      this._last = null;
      this._build();
      this._render();
      this._afterHass();
    }

    _afterHass() {
      if (!this._c) return;
      if (this._c.integration && TC.integ) {
        const a = TC.integ.analyseConfig(this);
        if (a) TC.loadHistory(this, a);
        return;
      }
      TC.loadHistory(this, this._c);
    }

    _render() {
      if (!this._prepare()) return;
      const t = TC.T;
      const c = this._c;
      if (c.integration && TC.integ) {
        this._put(TC.integ.renderAnalyse(this));
        return;
      }
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


/* ---- analyse-editor.js ---- */
/* Editor der Karte 2 (tarif-cockpit-analyse-card): Assistent, Formular und Vorschläge für getStubConfig. */
(() => {
  const TC = window.TarifCockpit;
  const { txt, icon, ent, numb, theme } = TC.sf;

  TC.addStrings('de', {
    'ae.s_kw': 'Kennwert', 'ae.t_kw': 'Kennwert je Gradtag',
    'ae.x_kw': 'Der Kennwert sagt, wie viel kWh Gas je Gradtag gebraucht werden. Er kommt aus deinen Sensoren (siehe docs/SENSOR-MODUS.md), die Karte rechnet ihn nicht.',
    'ae.kennwert': 'Kennwert (kWh/Kd)', 'ae.kennwert_previous': 'Kennwert der Vorperiode (für den Vergleich)',
    'ae.s_period': 'Periode', 'ae.t_period': 'Werte der letzten Ableseperiode',
    'ae.x_period': 'Diese Werte erscheinen als Kacheln. Verbrauch und Außentemperatur liefern auch den Verlauf aus der Langzeitstatistik.',
    'ae.consumption': 'Verbrauch letzte Periode (kWh)', 'ae.temperature': 'Ø Außentemperatur letzte Periode (°C)', 'ae.degree_days': 'Gradtage letzte Periode',
    'ae.s_extras': 'Zusatz', 'ae.t_extras': 'Weitere Kacheln', 'ae.x_extras': 'Zum Beispiel Ofentage oder Ofenstunden seit der letzten Ablesung.', 'ae.extras': 'Kacheln',
    'ae.s_look': 'Darstellung', 'ae.t_look': 'Verlauf und Aussehen', 'ae.x_look': 'Der Verlauf zeigt Monatsmittel der Langzeitstatistik.',
    'ae.months': 'Monate im Verlauf (höchstens 36)', 'ae.history': 'Verlauf ausblenden', 'ae.title': 'Titel', 'ae.subtitle': 'Untertitel', 'ae.icon': 'Symbol',
    'ae.explain': 'Erklärtext unter der Auswertung', 'ae.pending_text': 'Text, solange kein Kennwert vorliegt', 'ae.color': 'Farbe (z. B. #fb923c)', 'ae.theme': 'Farbschema', 'ae.label': 'Überschrift im Panel',
    'ae.s_done': 'Fertig', 'ae.t_done': 'Zusammenfassung', 'ae.x_done': 'Alles ist gespeichert.',
    'ae.sum_kw': 'Kennwert: {v}', 'ae.sum_tiles': 'Kacheln: {v}', 'ae.sum_hist': 'Verlauf: {v}', 'ae.on': 'an', 'ae.off': 'aus', 'ae.none': 'nicht gesetzt',
  });
  TC.addStrings('en', {
    'ae.s_kw': 'Coefficient', 'ae.t_kw': 'Coefficient per degree day',
    'ae.x_kw': 'The coefficient tells how many kWh of gas are needed per degree day. It comes from your sensors (see docs/SENSOR-MODUS.md); the card does not calculate it.',
    'ae.kennwert': 'Coefficient (kWh/Kd)', 'ae.kennwert_previous': 'Coefficient of the previous period (for comparison)',
    'ae.s_period': 'Period', 'ae.t_period': 'Values of the last reading period',
    'ae.x_period': 'These values appear as tiles. Consumption and outdoor temperature also provide the history from the long-term statistics.',
    'ae.consumption': 'Consumption last period (kWh)', 'ae.temperature': 'Ø outdoor temperature last period (°C)', 'ae.degree_days': 'Degree days last period',
    'ae.s_extras': 'Extras', 'ae.t_extras': 'More tiles', 'ae.x_extras': 'For example stove days or stove hours since the last reading.', 'ae.extras': 'Tiles',
    'ae.s_look': 'Display', 'ae.t_look': 'History and look', 'ae.x_look': 'The history shows monthly means from the long-term statistics.',
    'ae.months': 'Months in the history (at most 36)', 'ae.history': 'Hide history', 'ae.title': 'Title', 'ae.subtitle': 'Subtitle', 'ae.icon': 'Icon',
    'ae.explain': 'Explanation below the analysis', 'ae.pending_text': 'Text while no coefficient is available', 'ae.color': 'Colour (e.g. #fb923c)', 'ae.theme': 'Colour scheme', 'ae.label': 'Heading in the panel',
    'ae.s_done': 'Done', 'ae.t_done': 'Summary', 'ae.x_done': 'Everything is saved.',
    'ae.sum_kw': 'Coefficient: {v}', 'ae.sum_tiles': 'Tiles: {v}', 'ae.sum_hist': 'History: {v}', 'ae.on': 'on', 'ae.off': 'off', 'ae.none': 'not set',
  });

  const H = {
    kennwert: [/kennwert|coefficient|heat_?index/i, /gradtag|degree/i],
    kennwert_previous: [/vorperiode|previous|vorjahr|last/i, /kennwert|coefficient/i],
    consumption: [/verbrauch|consumption/i, /periode|period/i, /gas/i],
    temperature: [/au(ss|ß)en|outdoor|outside/i, /periode|period|mittel|mean/i],
    degree_days: [/gradtag|degree_?day|heating_?degree/i],
  };

  // getStubConfig: nur einen eindeutig passenden Kennwert vorschlagen, sonst {}
  TC.analyseStub = (hass) => {
    if (!hass || !hass.states) return {};
    const kw = TC.suggest(hass, 'value', H.kennwert, /kennwert|coefficient/i).filter((e) => !/vorperiode|previous/i.test(e.id));
    return kw.length ? { kennwert: kw[0].id } : {};
  };

  const steps = () => {
    const t = TC.T;
    return [
      { short: t('ae.s_kw'), title: t('ae.t_kw'), text: t('ae.x_kw'), fields: [
        { path: 'kennwert', label: t('ae.kennwert'), kind: 'value', hints: H.kennwert },
        { path: 'kennwert_previous', label: t('ae.kennwert_previous'), kind: 'value', hints: H.kennwert_previous, optional: true },
      ] },
      { short: t('ae.s_period'), title: t('ae.t_period'), text: t('ae.x_period'), fields: [
        { path: 'consumption', label: t('ae.consumption'), kind: 'quantity', hints: H.consumption, optional: true },
        { path: 'temperature', label: t('ae.temperature'), kind: 'temp', hints: H.temperature, optional: true },
        { path: 'degree_days', label: t('ae.degree_days'), kind: 'value', hints: H.degree_days, optional: true },
      ] },
      { short: t('ae.s_extras'), title: t('ae.t_extras'), text: t('ae.x_extras'), fields: [
        { path: 'extras', label: t('ae.extras'), kind: 'list', listKind: 'value', itemKey: 'entity', unitKey: 'unit', max: 8 },
      ] },
      { short: t('ae.s_look'), title: t('ae.t_look'), text: t('ae.x_look'), fields: [
        { path: 'title', label: t('ae.title'), kind: 'text', optional: true, placeholder: t('an.title') },
        { path: 'months', label: t('ae.months'), kind: 'number', step: '1', min: 1, optional: true, placeholder: '24' },
        { path: 'history', label: t('ae.history'), kind: 'bool', invert: true },
        { path: 'explain', label: t('ae.explain'), kind: 'text', optional: true },
        { path: 'theme', label: t('ae.theme'), kind: 'theme' },
      ] },
      { short: t('ae.s_done'), title: t('ae.t_done'), text: t('ae.x_done'), summary: (c) => [
        t('ae.sum_kw', { v: c.kennwert || t('ae.none') }),
        t('ae.sum_tiles', { v: [c.consumption, c.temperature, c.degree_days].filter(Boolean).length + (Array.isArray(c.extras) ? c.extras.length : 0) }),
        t('ae.sum_hist', { v: c.history === false ? t('ae.off') : t('ae.on') }),
      ] },
    ];
  };

  const LABEL_KEYS = ['kennwert', 'kennwert_previous', 'consumption', 'temperature', 'degree_days', 'months', 'title', 'subtitle', 'icon', 'explain', 'pending_text', 'color', 'theme', 'label'];
  const form = () => {
    const t = TC.T;
    return {
      schema: [
        txt('title'), txt('subtitle'), icon('icon'),
        ent('kennwert', ['sensor', 'input_number']), ent('kennwert_previous', ['sensor', 'input_number']),
        ent('consumption', ['sensor', 'input_number']), ent('temperature', ['sensor', 'input_number']), ent('degree_days', ['sensor', 'input_number']),
        // "Verlauf ausblenden" (history: false) und Zusatzkacheln stehen im Assistenten bzw. im YAML
        numb('months', 1, 36, 1),
        txt('explain'), txt('pending_text'), txt('label'), txt('color'), theme('theme'),
      ],
      computeLabel: (s) => (LABEL_KEYS.includes(s.name) ? t('ae.' + s.name) : s.name),
    };
  };

  TC.defineEditor('tarif-cockpit-analyse-card-editor', {
    integTab: TC.integTab({ single: true, titleKey: 'an.title', filter: (m, hh) => m.rolle === 'main' && (['gas', 'fernwaerme', 'waerme'].includes(m.medium)
      || (m.medium === 'strom' && (hh.waermeerzeuger || []).some((g) => ['water_hp', 'air_air_hp', 'electric'].includes(g.typ) && (g.zaehler_id === m.zaehler_id || g.am_haushaltsstrom)))) }),
    needsSetup: (c) => !(c.kennwert || c.consumption),
    steps,
    form,
  });
})();

