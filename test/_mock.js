/* Testdaten für die Testseiten: nachgebautes hass-Objekt und Szenarien. Wird vor ../custom_components/tarif_cockpit/frontend/tarif-cockpit.js geladen.
   URL-Parameter: scene (haus, miete, wasser, nachzahlung, ohne, leer, en, integration, lernt), theme, shot (ohne Knopfleiste), narrow */
(() => {
  // Platzhalter für HA-Elemente
  if (!customElements.get('ha-icon')) customElements.define('ha-icon', class extends HTMLElement { connectedCallback() { this.textContent = '●'; this.style.fontSize = '10px'; } });
  if (!customElements.get('ha-card')) customElements.define('ha-card', class extends HTMLElement {});

  const S = (state, u, n, extra) => ({ state: String(state), attributes: Object.assign({ unit_of_measurement: u || '', friendly_name: n || '' }, extra || {}) });
  const EUR = { device_class: 'monetary' };
  const base = {
    'sensor.kosten_strom_abrechnungsjahr': S(368.26, 'EUR', 'Kosten Strom Abrechnungsjahr', EUR),
    'sensor.abschlage_strom_abrechnungsjahr': S(825, 'EUR', 'Abschläge Strom Abrechnungsjahr', EUR),
    'sensor.prognose_strom_kosten': S(1267.92, 'EUR', 'Prognose Strom Kosten', EUR),
    'sensor.prognose_strom_verbrauch': S(3522, 'kWh', 'Prognose Strom Verbrauch'),
    'input_number.abschlag_strom': S(165, 'EUR/Monat', 'Abschlag Strom'),
    'sensor.kosten_gas_abrechnungsjahr': S(222.88, 'EUR', 'Kosten Gas Abrechnungsjahr', EUR),
    'sensor.abschlage_gas_abrechnungsjahr': S(830, 'EUR', 'Abschläge Gas Abrechnungsjahr', EUR),
    'sensor.prognose_gas_kosten': S(1777.38, 'EUR', 'Prognose Gas Kosten', EUR),
    'sensor.prognose_gas_verbrauch': S(16270, 'kWh', 'Prognose Gas Verbrauch'),
    'input_number.abschlag_gas': S(166, 'EUR/Monat', 'Abschlag Gas'),
    'sensor.kosten_wasser_abrechnungsjahr': S(96.4, 'EUR', 'Kosten Wasser Abrechnungsjahr', EUR),
    'sensor.abschlage_wasser_abrechnungsjahr': S(150, 'EUR', 'Abschläge Wasser Abrechnungsjahr', EUR),
    'sensor.prognose_wasser_kosten': S(412.5, 'EUR', 'Prognose Wasser Kosten', EUR),
    'input_number.abschlag_wasser': S(35, 'EUR/Monat', 'Abschlag Wasser'),
    'sensor.zahler_strombezug': S(6627.4, 'kWh', 'Zähler Strombezug', { device_class: 'energy' }),
    'sensor.zahler_gas': S(9808, 'm³', 'Zähler Gas', { device_class: 'gas' }),
    'sensor.zahler_wasser': S(411.9, 'm³', 'Zähler Wasser', { device_class: 'water' }),
    'input_datetime.zahler_letzte_ablesung': S('2026-11-12 09:11:17', '', 'Letzte Ablesung'),
    'input_number.tarif_strom_arbeitspreis': S(0.3154, 'EUR/kWh', 'Strom Arbeitspreis'),
    'input_number.tarif_gas_arbeitspreis': S(0.0952, 'EUR/kWh', 'Gas Arbeitspreis'),
    'input_datetime.abr_strom': S('2026-07-30', '', 'Abrechnung Strom Beginn'),
    'input_datetime.abr_gas': S('2026-08-15', '', 'Abrechnung Gas Beginn'),
    'sensor.gas_kennwert_je_gradtag': S(6.88, 'kWh/Kd', 'Gas Kennwert je Gradtag'),
    'input_number.gas_kennwert_vorperiode': S(6.05, 'kWh/Kd', 'Gas Kennwert Vorperiode'),
    'sensor.gas_verbrauch_letzte_periode': S(3725, 'kWh', 'Gas Verbrauch letzte Periode', { device_class: 'energy' }),
    'sensor.gas_aussentemperatur_letzte_periode': S(6.5, '°C', 'Gas Außentemperatur letzte Periode', { device_class: 'temperature' }),
    'sensor.gas_gradtage_letzte_periode': S(541, 'Kd', 'Gas Gradtage letzte Periode'),
    'input_number.ofentage_periode': S(0, 'd', 'Ofentage Periode'),
    'input_number.ofen_stunden_periode': S(0, 'h', 'Ofenstunden Periode'),
    'sensor.aussentemperatur': S(4.2, '°C', 'Außentemperatur', { device_class: 'temperature' }),
  };

  // Verlauf: Monatsmittel der letzten 24 Monate, mit Lücken im Sommer (wie in echten Daten)
  const monthly = async (m) => {
    const r = {}; const now = new Date();
    (m.statistic_ids || []).forEach((id) => {
      r[id] = [];
      for (let i = 23; i >= 0; i--) {
        const d = new Date(now.getFullYear(), now.getMonth() - i, 1); const mo = d.getMonth();
        const W = [10, 11, 0, 1, 2, 3]; if (!W.includes(mo)) continue;
        const temp = [8, 4, 1, 2, 6, 9][W.indexOf(mo)];
        const mean = id.includes('verbrauch') ? 3000 + (12 - temp * 1.3) * 160 : id.includes('temperatur') ? temp : id.includes('kennwert') ? 5.2 + (i % 5) * 0.35 : null;
        r[id].push({ start: d.getTime(), end: d.getTime() + 2592e6, mean });
      }
    });
    return r;
  };

  const medium = (k, start) => Object.assign(start ? { start } : {}, {
    cost: `sensor.kosten_${k}_abrechnungsjahr`, advance_paid: `sensor.abschlage_${k}_abrechnungsjahr`,
    forecast_cost: `sensor.prognose_${k}_kosten`, advance: `input_number.abschlag_${k}`,
  }, k === 'wasser' ? {} : { forecast_kwh: `sensor.prognose_${k}_verbrauch` });
  const analysis = {
    title: 'Gas witterungsbereinigt', kennwert: 'sensor.gas_kennwert_je_gradtag', kennwert_previous: 'input_number.gas_kennwert_vorperiode',
    consumption: 'sensor.gas_verbrauch_letzte_periode', temperature: 'sensor.gas_aussentemperatur_letzte_periode', degree_days: 'sensor.gas_gradtage_letzte_periode',
    extras: [{ name: 'Ofentage seit Ablesung', entity: 'input_number.ofentage_periode', unit: 'd', decimals: 0 }, { name: 'Ofenstunden seit Ablesung', entity: 'input_number.ofen_stunden_periode', unit: 'h', decimals: 0 }],
    explain: 'Kennwert = kWh Gas je Gradtag. Bleibt er gleich, hat sich am Heizverhalten nichts geändert. Steigt er, verbrauchst du mehr, als das Wetter erklärt.',
  };
  const footer = [
    { name: 'Strombezug', entity: 'sensor.zahler_strombezug' }, { name: 'Gas', entity: 'sensor.zahler_gas' }, { name: 'Wasser', entity: 'sensor.zahler_wasser' },
    { name: 'Letzte Ablesung', entity: 'input_datetime.zahler_letzte_ablesung', format: 'date' },
    { name: 'Strom Arbeitspreis', entity: 'input_number.tarif_strom_arbeitspreis', scale: 100, unit: 'ct/kWh', decimals: 2 },
    { name: 'Gas Arbeitspreis', entity: 'input_number.tarif_gas_arbeitspreis', scale: 100, unit: 'ct/kWh', decimals: 2 },
  ];
  // Konfiguration aus v0.3 (test/index.html), unverändert: muss weiter funktionieren (Regel 8)
  const legacy = { theme: 'dunkel', title: 'Tarife und Abrechnung', period_start: 'input_datetime.abr_strom', strom: medium('strom'), gas: medium('gas', 'input_datetime.abr_gas'), analysis, footer };

  // ---- Integrations-Modus (0.7): Sensoren der Integration und nachgebauter WebSocket-Befehl
  const sid = (m, k) => `sensor.${m}_${k}`;
  const advList = (a, b, n1, n2) => {
    const l = [];
    for (let i = 0; i < n1 + n2; i++) l.push({ datum: `2026-${String(((7 + i) % 12) + 1).padStart(2, '0')}-01`, betrag: i < n1 ? a : b, status: i < 4 ? 'bezahlt' : 'geplant' });
    return l;
  };
  const integStates = (learn) => ({
    [sid('strom', 'kosten_bisher')]: S(374.51, 'EUR', 'Strom Kosten bisher', EUR),
    [sid('strom', 'abschlaege_bisher')]: S(660, 'EUR', 'Strom Abschläge bisher', EUR),
    [sid('strom', 'abschlag')]: S(165, 'EUR', 'Strom Abschlag', EUR),
    [sid('strom', 'abschlaege_periode')]: S(1980, 'EUR', 'Strom Abschläge Periode', Object.assign({ anzahl: 12, abschlaege: advList(165, 165, 12, 0) }, EUR)),
    [sid('strom', 'prognose_verbrauch')]: S(3522, 'kWh', 'Strom Prognose Verbrauch'),
    [sid('strom', 'prognose_kosten')]: S(1270.93, 'EUR', 'Strom Prognose Kosten', EUR),
    [sid('strom', 'saldo')]: S(709.07, 'EUR', 'Strom Saldo', EUR),
    [sid('strom', 'urteil')]: S('rueckzahlung', '', 'Strom Urteil'),
    [sid('strom', 'abschlag_empfohlen')]: S(110, 'EUR', 'Strom Empfohlener Abschlag', Object.assign({ ab: '2026-12-01', vorlaeufig: false }, EUR)),
    [sid('strom', 'prognose_qualitaet')]: S('gut', '', 'Strom Prognose-Qualität'),
    [sid('strom', 'periode_ende')]: S('2026-11-30', '', 'Strom Periodenende', { beginn: '2026-06-30', schlussperiode: true, lieferant: 'Stadtwerke' }),
    [sid('gas', 'kosten_bisher')]: S(222.88, 'EUR', 'Gas Kosten bisher', EUR),
    [sid('gas', 'abschlaege_bisher')]: S(664, 'EUR', 'Gas Abschläge bisher', EUR),
    [sid('gas', 'abschlag')]: S(180, 'EUR', 'Gas Abschlag', EUR),
    [sid('gas', 'abschlaege_periode')]: S(2104, 'EUR', 'Gas Abschläge Periode', Object.assign({ anzahl: 12, abschlaege: advList(166, 180, 4, 8) }, EUR)),
    [sid('gas', 'prognose_verbrauch')]: learn ? S('unknown') : S(16270, 'kWh', 'Gas Prognose Verbrauch'),
    [sid('gas', 'prognose_kosten')]: learn ? S('unknown') : S(1771.1, 'EUR', 'Gas Prognose Kosten', EUR),
    [sid('gas', 'saldo')]: learn ? S('unknown') : S(-332.9, 'EUR', 'Gas Saldo', EUR),
    [sid('gas', 'urteil')]: learn ? S('unknown') : S('nachzahlung', '', 'Gas Urteil'),
    [sid('gas', 'abschlag_empfohlen')]: learn ? S('unknown') : S(215, 'EUR', 'Gas Empfohlener Abschlag', Object.assign({ ab: '2026-12-01', vorlaeufig: true }, EUR)),
    [sid('gas', 'prognose_qualitaet')]: S(learn ? 'unzureichend' : 'vorlaeufig', '', 'Gas Prognose-Qualität', learn ? {} : { sample_count: 61, r_squared: 0.82 }),
    [sid('gas', 'periode_ende')]: S('2027-08-14', '', 'Gas Periodenende', { beginn: '2026-08-15', lieferant: 'Gasversorger' }),
    [sid('gas', 'kennwert')]: learn ? S('unknown') : S(6.52, 'kWh/Kd', 'Gas Kennwert'),
    [sid('gas', 'ww_grundlast')]: learn ? S('unknown') : S(9.4, 'kWh/d', 'Gas WW-Grundlast'),
    'sensor.haushalt_saldo_gesamt': learn ? S('unknown') : S(376.17, 'EUR', 'Saldo gesamt', EUR),
  });
  const KEYS = ['kosten_bisher', 'abschlaege_bisher', 'abschlag', 'abschlaege_periode', 'prognose_verbrauch', 'prognose_kosten', 'saldo', 'urteil', 'abschlag_empfohlen', 'prognose_qualitaet', 'periode_ende'];
  const sensoren = (m, heat) => { const o = {}; KEYS.concat(heat ? ['kennwert', 'ww_grundlast'] : []).forEach((k) => { o[k] = sid(m, k); }); return o; };
  const META = { haushalte: [{ entry_id: 'e1', name: 'Haus', saldo_gesamt: 'sensor.haushalt_saldo_gesamt', zaehler: [
    { zaehler_id: 'm1', device_id: 'dev_strom', name: 'Strom', medium: 'strom', unit: 'kWh', rolle: 'main', hauptzaehler: null, sensoren: sensoren('strom'),
      vertraege: [{ lieferant: 'Stadtwerke', tarif: '', beginn: '2026-06-30', ende: '2026-11-30' }, { lieferant: 'Neu AG', tarif: 'Öko', beginn: '2026-12-01', ende: null }] },
    { zaehler_id: 'm2', device_id: 'dev_gas', name: 'Gas', medium: 'gas', unit: 'm³', rolle: 'main', hauptzaehler: null, sensoren: sensoren('gas', true),
      vertraege: [{ lieferant: 'Gasversorger', tarif: '', beginn: '2026-08-15', ende: null }] },
  ] }] };
  const calls = [];
  const integHass = (learn) => (hass) => Object.assign(hass, {
    states: Object.assign(hass.states, integStates(learn)),
    config: Object.assign(hass.config, { components: ['sensor', 'tarif_cockpit'] }),
    user: { is_admin: !q.has('user') },
    callWS: async (m) => (m.type === 'tarif_cockpit/zaehler' ? strip(META) : monthly(m)),
    callService: async (domain, service, data) => {
      calls.push({ domain, service, data });
      if (!(data.betrag >= 0)) throw new Error('Betrag fehlt oder ist negativ.');
      if (data.ab < '2026-06-30') throw new Error('Das Datum liegt in einer beendeten Abrechnungsperiode.');
      return {};
    },
  });

  const only = (keys) => { const o = {}; keys.forEach((k) => { o[k] = base[k]; }); return o; };
  const SCENES = {
    haus: { name: 'Haus mit Strom und Gas (Konfiguration aus 0.3)', states: {}, overview: legacy, analyse: Object.assign({}, analysis) },
    neu: { name: 'Haus mit Strom und Gas, Auswertung als eigene Karte', states: {}, overview: Object.assign({}, legacy, { analysis: undefined }), analyse: Object.assign({}, analysis) },
    miete: { name: 'Mietwohnung, nur Strom', states: null, keep: ['sensor.kosten_strom_abrechnungsjahr', 'sensor.abschlage_strom_abrechnungsjahr', 'sensor.prognose_strom_kosten', 'sensor.prognose_strom_verbrauch', 'input_number.abschlag_strom', 'input_datetime.abr_strom', 'sensor.zahler_strombezug'],
      overview: { title: 'Stromabschlag', period_start: 'input_datetime.abr_strom', strom: medium('strom') }, analyse: {} },
    wasser: { name: 'Strom, Gas und Wasser', states: {}, overview: { period_start: 'input_datetime.abr_strom', strom: medium('strom'), gas: medium('gas'), wasser: Object.assign(medium('wasser'), { months: 11 }), footer: footer.slice(0, 3) }, analyse: Object.assign({}, analysis) },
    nachzahlung: { name: 'Nachzahlung erwartet', states: { 'sensor.prognose_strom_kosten': S(2300, 'EUR', 'Prognose Strom Kosten', EUR), 'sensor.prognose_gas_kosten': S(1990, 'EUR', 'Prognose Gas Kosten', EUR) }, overview: Object.assign({}, legacy, { analysis: undefined }), analyse: Object.assign({}, analysis) },
    ohne: { name: 'Prognose nicht verfügbar', states: { 'sensor.prognose_gas_kosten': S('unavailable'), 'sensor.gas_kennwert_je_gradtag': S('unavailable') }, overview: Object.assign({}, legacy, { analysis: undefined }), analyse: Object.assign({}, analysis) },
    leer: { name: 'Frisch hinzugefügt, keine passenden Sensoren (getStubConfig)', states: null, keep: ['sensor.aussentemperatur'], overview: 'stub', analyse: 'stub' },
    vorschlag: { name: 'Frisch hinzugefügt, Vorschlag aus vorhandenen Sensoren (getStubConfig)', states: {}, overview: 'stub', analyse: 'stub' },
    integration: { name: 'Integrations-Modus: Strom mit Anbieterwechsel, Gas mit Abschlagsstufen', states: {}, hook: integHass(false), overview: { integration: true }, analyse: { integration: true } },
    lernt: { name: 'Integrations-Modus: Kennwert wird noch gelernt', states: {}, hook: integHass(true), overview: { integration: true }, analyse: { integration: true } },
    integ_neu: { name: 'Integration vorhanden, Karte frisch hinzugefügt (getStubConfig)', states: {}, hook: integHass(false), overview: 'stub', analyse: 'stub' },
    en: { name: 'Englische Oberfläche', states: {}, lang: 'en', overview: Object.assign({}, legacy, { analysis: undefined, title: 'Tariffs and billing' }), analyse: Object.assign({}, analysis, { title: 'Gas, weather-adjusted', explain: undefined }) },
  };
  const strip = (o) => JSON.parse(JSON.stringify(o));

  const q = new URLSearchParams(location.search);
  const T = {
    q, SCENES, S, calls,
    scene: SCENES[q.get('scene')] ? q.get('scene') : 'haus',
    theme: q.get('theme') || '',
    hass(sc) {
      const s = SCENES[sc];
      const states = s.states === null ? only(s.keep || []) : Object.assign(strip(base), strip(s.states));
      const lang = s.lang || 'de';
      const h = { states, language: lang, locale: { language: lang, number_format: 'language' }, config: { currency: 'EUR' }, themes: { darkMode: true }, callWS: monthly };
      return s.hook ? s.hook(h) : h;
    },
    config(sc, card, tag) {
      const raw = SCENES[sc][card];
      const c = raw === 'stub' ? strip(customElements.get(tag).getStubConfig(T.hass(sc))) : strip(raw || {});
      if (T.theme) c.theme = T.theme;
      return c;
    },
    // Knopfleiste mit Szenarien und Farbschemen
    bar(onPick) {
      const bar = document.getElementById('bar');
      if (!bar) return;
      if (q.has('shot')) { bar.style.display = 'none'; return; }
      const mk = (txt, fn, on) => { const b = document.createElement('button'); b.textContent = txt; if (on) b.className = 'on'; b.onclick = fn; bar.appendChild(b); };
      Object.keys(SCENES).forEach((k) => mk(k, () => { T.scene = k; onPick(); T.mark(); }, k === T.scene));
      bar.appendChild(document.createElement('span'));
      ['dunkel', 'graphit', 'hell', 'warm', 'ha'].forEach((t) => mk(t, () => { T.theme = t; onPick(); T.mark(); }, t === T.theme));
      mk('schmal', () => { document.getElementById('host').classList.toggle('narrow'); });
    },
    mark() {
      const bar = document.getElementById('bar');
      if (!bar) return;
      [...bar.querySelectorAll('button')].forEach((b) => b.classList.toggle('on', b.textContent === T.scene || b.textContent === T.theme));
      document.body.style.background = (T.theme === 'hell' || T.theme === 'warm') ? '#d8dde6' : '#05070d';
      const info = document.getElementById('info');
      if (info) info.textContent = SCENES[T.scene].name;
    },
    mount(tag, card) {
      const host = document.getElementById('host');
      host.innerHTML = '';
      const el = document.createElement(tag);
      el.setConfig(T.config(T.scene, card, tag));
      host.appendChild(el);
      el.hass = T.hass(T.scene);
      return el;
    },
  };
  window.TCTEST = T;
})();
