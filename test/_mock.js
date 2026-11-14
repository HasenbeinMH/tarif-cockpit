/* Testdaten für die Testseiten: nachgebautes hass-Objekt und Szenarien. Wird vor ../custom_components/tarif_cockpit/frontend/tarif-cockpit.js geladen.
   URL-Parameter: scene (haus, miete, wasser, nachzahlung, ohne, leer, en, integration, lernt, heizung, waermepumpe, impulse, archiv, fernwaerme), user (kein Admin), theme, shot (ohne Knopfleiste), narrow */
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

  // ---- 0.8: Wärmeerzeuger und Diagramme (Streudiagramm, Kostenverlauf) über tarif_cockpit/reihen
  const gsid = (g, k) => `sensor.${g}_${k}`;
  const GKEYS = ['energie_eingang', 'waerme', 'entlastung', 'betriebsstunden', 'betriebstage', 'holz_geschaetzt', 'holzkosten_geschaetzt'];
  const gsens = (g) => { const o = {}; GKEYS.forEach((k) => { o[k] = gsid(g, k); }); return o; };
  const scatterData = (k, ww, stove, klima) => {
    const pts = [];
    for (let i = 0; i < 300; i++) {
      const t = 9 - 9 * Math.cos((2 * Math.PI * (i + 280)) / 365) + 1.5 * Math.sin(i * 0.9);
      const dd = t < 15 ? 20 - t : 0;
      let y = ww + k * dd + ((i * 37) % 11 - 5) * 0.6;
      const p = { x: +dd.toFixed(2), y: 0 };
      if (stove && dd > 8 && i % 3 === 0) { p.ofen = 4; y -= 24; }
      if (klima && dd > 2 && dd < 10 && i % 5 === 0) { p.klima = +(0.6 * dd).toFixed(1); y -= 1.5 * 0.6 * dd; }
      p.y = +Math.max(y, 0).toFixed(2);
      pts.push(p);
    }
    return { punkte: pts, gerade: { x0: 0, y0: ww, x1: 25, y1: ww + k * 25 }, kennwert: k, ww, r2: 0.91, qualitaet: 'gut', je_periode: false,
      ofen_effekt: stove ? 6 : null, ofen_qualitaet: stove ? 'gut' : null };
  };
  const costData = (beginn, ende, heute, perMonth, adv) => {
    const ist = [[beginn, 0]], prognose = [], abschlaege = [[beginn, 0]];
    let d = new Date(beginn + 'T00:00:00'), cum = 0, acum = 0, i = 0;
    const iso = (x) => `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}-${String(x.getDate()).padStart(2, '0')}`;
    while (iso(d) <= ende && i < 14) {
      const mEnd = new Date(d.getFullYear(), d.getMonth() + 1, 0);
      const winter = [10, 11, 0, 1, 2].includes(d.getMonth()) ? 1.8 : [3, 9].includes(d.getMonth()) ? 1 : 0.35;
      cum += perMonth * winter;
      const stamp = iso(mEnd) > ende ? ende : iso(mEnd);
      if (stamp < heute) ist.push([stamp, +cum.toFixed(2)]);
      else { if (!prognose.length) prognose.push([heute, ist[ist.length - 1][1]]); prognose.push([stamp, +cum.toFixed(2)]); }
      acum += adv;
      abschlaege.push([iso(new Date(d.getFullYear(), d.getMonth(), 1)) < beginn ? beginn : iso(new Date(d.getFullYear(), d.getMonth() + 1, 1)), +acum.toFixed(2)]);
      d = new Date(d.getFullYear(), d.getMonth() + 1, 1);
      i += 1;
    }
    return { beginn, ende, heute, ist, prognose, abschlaege: abschlaege.filter((x) => x[0] <= ende) };
  };
  const HEAT_SCENES = {
    heizung: {
      meta: () => {
        const m = strip(META);
        m.haushalte[0].warmwasser = 'heizung';
        m.haushalte[0].zaehler[1].sensoren.kennwert_temperaturbereinigt = sid('gas', 'kennwert_temperaturbereinigt');
        m.haushalte[0].waermeerzeuger = [
          { erzeuger_id: 'o1', device_id: 'dev_ofen', name: 'Kaminofen', typ: 'fireplace', zaehler_id: null, am_haushaltsstrom: false, ww_zentral: false, sensoren: gsens('ofen') },
          { erzeuger_id: 'k1', device_id: 'dev_klima', name: 'Split-Klima Wohnzimmer', typ: 'air_air_hp', zaehler_id: null, am_haushaltsstrom: true, ww_zentral: false, sensoren: gsens('klima') },
        ];
        return m;
      },
      states: {
        [sid('gas', 'kennwert_temperaturbereinigt')]: S(6.1, 'kWh/Kd', 'Kennwert temperaturbereinigt', { prozent_je_kelvin: 6.8, prozent_je_kelvin_qualitaet: 'gut',
          vorjahr: { gesamt_pct: 8.2, raumtemperatur_pct: 3.4, verhalten_pct: 4.8, innen_aenderung_k: 0.5, tage: 92 } }),
        [gsid('ofen', 'energie_eingang')]: S(1640, 'kWh', 'Ofen Eingang'), [gsid('ofen', 'waerme')]: S(1230, 'kWh', 'Ofen Wärme', { geschaetzt: true }),
        [gsid('ofen', 'entlastung')]: S(1140, 'kWh', 'Ofen Entlastung', { qualitaet: 'gut' }), [gsid('ofen', 'betriebsstunden')]: S(205, 'h', 'Ofen Stunden'),
        [gsid('ofen', 'betriebstage')]: S(48, 'd', 'Ofen Tage'), [gsid('ofen', 'holz_geschaetzt')]: S(390, 'kg', 'Holz'),
        [gsid('ofen', 'holzkosten_geschaetzt')]: S(117, 'EUR', 'Holzkosten', EUR),
        [gsid('klima', 'energie_eingang')]: S(212, 'kWh', 'Klima Eingang'), [gsid('klima', 'waerme')]: S(742, 'kWh', 'Klima Wärme', { geschaetzt: true }),
        [gsid('klima', 'entlastung')]: S('unknown'), [gsid('klima', 'betriebsstunden')]: S(96, 'h', 'Klima Stunden'), [gsid('klima', 'betriebstage')]: S(21, 'd', 'Klima Tage'),
      },
      series: { zaehler_id: 'm2', streuung: scatterData(6.4, 9, true, true), kosten: costData('2026-08-15', '2027-08-14', '2026-11-13', 95, 175) },
    },
    waermepumpe: {
      meta: () => ({ haushalte: [{ entry_id: 'e1', name: 'Haus', saldo_gesamt: null, warmwasser: 'waermepumpe', zaehler: [
        { zaehler_id: 'm3', device_id: 'dev_wp', name: 'Wärmepumpe', medium: 'strom', unit: 'kWh', rolle: 'main', hauptzaehler: null,
          sensoren: Object.assign(sensoren('wp'), { kennwert: sid('wp', 'kennwert') }), vertraege: [{ lieferant: 'Stadtwerke', tarif: 'WP-Tarif', beginn: '2026-01-01', ende: null }] },
      ], waermeerzeuger: [{ erzeuger_id: 'w1', device_id: 'dev_wpg', name: 'Wärmepumpe', typ: 'water_hp', zaehler_id: 'm3', am_haushaltsstrom: false, ww_zentral: true, sensoren: gsens('wp_gen') }] }] }),
      states: {
        [sid('wp', 'kennwert')]: S(1.82, 'kWh/Kd', 'WP Kennwert'), [sid('wp', 'prognose_qualitaet')]: S('gut', '', 'WP Qualität', { sample_count: 312, r_squared: 0.93 }),
        [gsid('wp_gen', 'energie_eingang')]: S(3120, 'kWh', 'WP Eingang'), [gsid('wp_gen', 'waerme')]: S(10920, 'kWh', 'WP Wärme', { geschaetzt: true }),
        [gsid('wp_gen', 'entlastung')]: S('unknown'),
      },
      series: { zaehler_id: 'm3', streuung: scatterData(1.8, 2.5, false, false), kosten: costData('2026-01-01', '2026-12-31', '2026-11-13', 70, 95) },
    },
    impulse: {
      meta: () => {
        const m = strip(META);
        Object.assign(m.haushalte[0].zaehler[1].sensoren, { abgleich: sid('gas', 'abgleich'), gasleistung: sid('gas', 'gasleistung'),
          brennerlaufzeit: sid('gas', 'brennerlaufzeit'), brennerstarts: sid('gas', 'brennerstarts') });
        m.haushalte[0].waermeerzeuger = [];
        return m;
      },
      states: {
        [sid('gas', 'abgleich')]: S(-4.8, '%', 'Abgleich', { angeglichen: true, hinweis: true, faktor: 1.05, fehlende_menge: 14.2 }),
        [sid('gas', 'gasleistung')]: S(7.4, 'kW', 'Gasleistung'),
        [sid('gas', 'brennerlaufzeit')]: S(412, 'h', 'Brennerlaufzeit', { taktet_gestern: true, taktet_tage: ['2026-11-12'] }),
        [sid('gas', 'brennerstarts')]: S(388, '', 'Brennerstarts', { taktet_gestern: true }),
      },
      series: { zaehler_id: 'm2', streuung: scatterData(6.4, 9, false, false), kosten: costData('2026-08-15', '2027-08-14', '2026-11-13', 95, 175) },
    },
    fernwaerme: {
      meta: () => ({ haushalte: [{ entry_id: 'e1', name: 'Wohnung', saldo_gesamt: null, warmwasser: 'heizung', zaehler: [
        { zaehler_id: 'f1', device_id: 'dev_fw', name: 'Fernwärme', medium: 'fernwaerme', unit: 'MWh', rolle: 'main', hauptzaehler: null,
          sensoren: sensoren('fw', true), vertraege: [{ lieferant: 'Fernwärme GmbH', tarif: '', beginn: '2026-01-01', ende: null }] },
      ], waermeerzeuger: [] }] }),
      states: {
        [sid('fw', 'kennwert')]: S(5.1, 'kWh/Kd', 'FW Kennwert'), [sid('fw', 'ww_grundlast')]: S(6.2, 'kWh/d', 'FW WW'),
        [sid('fw', 'prognose_qualitaet')]: S('sehr_gut', '', 'FW Qualität', { sample_count: 340, r_squared: 0.95 }),
      },
      series: { zaehler_id: 'f1', streuung: scatterData(5.1, 6.2, false, false), kosten: costData('2026-01-01', '2026-12-31', '2026-11-13', 110, 140) },
    },
  };
  // ---- 1.0: Archiv (Prognose gegen Realität), Band kalt/warm, Kündigungsfrist
  const ARCH = { zaehler_id: 'm2', waehrung: 'EUR', perioden: [{ beginn: '2025-08-15', ende: '2026-08-14', status: 'closed', archiv: {
    stand: 'abgeschlossen', grund: 'endablesung', beginn: '2025-08-15', ende: '2026-08-14', menge: 14820, saldo: 143.2, urteil: 'rueckzahlung',
    kosten: { gesamt: 1956.8, arbeit: 1712.4, grund: 244.4, fest: 0, leistung: 0, abwasser: 0, vollstaendig: true },
    prognose_gegen_realitaet: [
      { datum: '2025-09-01', prognose_kosten: 2240, prognose_saldo: -140, qualitaet: 'vorlaeufig', abweichung: 283.2, abweichung_pct: 14.5 },
      { datum: '2025-12-01', prognose_kosten: 2105, prognose_saldo: -5, qualitaet: 'gut', abweichung: 148.2, abweichung_pct: 7.6 },
      { datum: '2026-03-01', prognose_kosten: 1990, prognose_saldo: 110, qualitaet: 'gut', abweichung: 33.2, abweichung_pct: 1.7 },
      { datum: '2026-06-01', prognose_kosten: 1962, prognose_saldo: 138, qualitaet: 'sehr_gut', abweichung: 5.2, abweichung_pct: 0.3 },
      { datum: '2026-08-14', prognose_kosten: 1958, prognose_saldo: 142, qualitaet: 'sehr_gut', abweichung: 1.2, abweichung_pct: 0.1 },
    ] } }] };
  HEAT_SCENES.archiv = Object.assign({}, HEAT_SCENES.heizung, {
    archive: ARCH,
    states: Object.assign({}, HEAT_SCENES.heizung.states, {
      [sid('gas', 'saldo')]: S(-332.9, 'EUR', 'Gas Saldo', Object.assign({ saldo_kalt: -515.4, saldo_warm: -164.0 }, EUR)),
      [sid('gas', 'periode_ende')]: S('2027-08-14', '', 'Gas Periodenende', { beginn: '2026-08-15', lieferant: 'Gasversorger', kuendigung_bis: '2026-12-02', tage_bis_kuendigung: 19, kuendigung_hinweis: true, vertragsende: '2027-01-13', kuendigung: 'termin' }),
    }),
  });
  const heatHass = (key) => (hass) => {
    const sc = HEAT_SCENES[key];
    integHass(false)(hass);
    Object.assign(hass.states, strip(sc.states));
    const meta = sc.meta();
    hass.callWS = async (m) => {
      if (m.type === 'tarif_cockpit/zaehler') return strip(meta);
      if (m.type === 'tarif_cockpit/reihen') return strip(sc.series);
      if (m.type === 'tarif_cockpit/archiv') { if (sc.archive) return strip(sc.archive); throw new Error('not_found'); }
      return monthly(m);
    };
    return hass;
  };

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
    heizung: { name: 'Gas mit Kaminofen und Split-Klima (Wärmeerzeuger, Diagramme)', states: {}, hook: heatHass('heizung'), overview: { integration: true }, analyse: { integration: true } },
    waermepumpe: { name: 'Wärmepumpe am eigenen Zähler', states: {}, hook: heatHass('waermepumpe'), overview: { integration: true }, analyse: { integration: true } },
    impulse: { name: 'Gas mit Impulszähler: Abgleich, Gasleistung, Brenner', states: {}, hook: heatHass('impulse'), overview: { integration: true }, analyse: { integration: true } },
    archiv: { name: 'Prognose gegen Realität (Archiv), Band kalt/warm, Kündigungsfrist', states: {}, hook: heatHass('archiv'), overview: { integration: true }, analyse: { integration: true } },
    fernwaerme: { name: 'Fernwärme in MWh', states: {}, hook: heatHass('fernwaerme'), overview: { integration: true }, analyse: { integration: true } },
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
