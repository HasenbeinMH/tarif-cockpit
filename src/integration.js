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
    'in.reconcile': 'Sensor weicht {p} von der Ablesung ab{a}.', 'in.reconciled': ', angeglichen',
    'in.band': 'Wird der Rest so kalt wie im kältesten Vorjahr: {k}, so mild wie im wärmsten: {w}.',
    'in.notice': 'Wer zum Vertragsende wechseln will, muss bis {d} kündigen (noch {n} Tage).',
    'ar.title': 'Prognose gegen Realität', 'ar.prelim': 'vorläufig', 'ar.final': 'abgeschlossen',
    'ar.actual': 'Tatsächlich {v} · Saldo {s}', 'ar.partial': 'Ist-Kosten unvollständig (Tageswerte bis {d})', 'ar.date': 'Stand', 'ar.fc': 'Prognose', 'ar.dev': 'Abweichung',
    'in.burner_h': 'Brennerlaufzeit', 'in.burner_n': 'Brennerstarts', 'in.gas_kw': 'Gasleistung',
    'in.cycling': 'Der Brenner hat gestern getaktet: Die Heizlast lag unter der kleinsten Modulationsstufe.',
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
    'in.reconcile': 'Sensor differs {p} from the reading{a}.', 'in.reconciled': ', adjusted',
    'in.band': 'If the rest is as cold as the coldest previous year: {k}; as mild as the warmest: {w}.',
    'in.notice': 'To switch at the end of the contract, cancel by {d} ({n} days left).',
    'ar.title': 'Forecast vs. reality', 'ar.prelim': 'provisional', 'ar.final': 'final',
    'ar.actual': 'Actual {v} · balance {s}', 'ar.partial': 'Actual costs incomplete (daily values until {d})', 'ar.date': 'As of', 'ar.fc': 'Forecast', 'ar.dev': 'Deviation',
    'in.burner_h': 'Burner run time', 'in.burner_n': 'Burner starts', 'in.gas_kw': 'Gas power',
    'in.cycling': 'The burner cycled yesterday: the heat load was below the lowest modulation level.',
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
    const rc = val(h, s.abgleich);
    if (rc !== null && attr(h, s.abgleich, 'hinweis')) { // Schwelle entscheidet die Integration (Regel 2)
      hints.push(esc(t('in.reconcile', { p: (rc >= 0 ? '+' : '−') + TC.nf(Math.abs(rc), 1) + ' %', a: attr(h, s.abgleich, 'angeglichen') ? t('in.reconciled') : '' })));
    }
    const signed = (v) => t(v >= 0 ? 'verdict.back' : 'verdict.extra') + ' ' + TC.eur(Math.abs(v)) + ' ' + TC.cur();
    const sk = attr(h, s.saldo, 'saldo_kalt'), sw = attr(h, s.saldo, 'saldo_warm');
    if (typeof sk === 'number' && typeof sw === 'number') hints.push(esc(t('in.band', { k: signed(sk), w: signed(sw) })));
    const nd = attr(h, s.periode_ende, 'tage_bis_kuendigung');
    if (attr(h, s.periode_ende, 'kuendigung_hinweis') && typeof nd === 'number') hints.push(esc(t('in.notice', { d: dd(attr(h, s.periode_ende, 'kuendigung_bis')), n: nd })));
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
    if (s.gasleistung) extras.push({ name: TC.T('in.gas_kw'), entity: s.gasleistung, unit: 'kW', decimals: 1 });
    if (s.brennerlaufzeit) extras.push({ name: TC.T('in.burner_h'), entity: s.brennerlaufzeit, unit: 'h', decimals: 0 });
    if (s.brennerstarts) extras.push({ name: TC.T('in.burner_n'), entity: s.brennerstarts, unit: '', decimals: 0 });
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
    I.loadArchive(card, m.device_id);
    const hints = [];
    const pct = attr(h, s.kennwert_temperaturbereinigt, 'prozent_je_kelvin');
    const pctQ = attr(h, s.kennwert_temperaturbereinigt, 'prozent_je_kelvin_qualitaet');
    if (typeof pct === 'number' && pctQ && pctQ !== 'annahme') hints.push(esc(t('in.pct_k', { p: TC.nf(pct, 1) })));
    if (attr(h, s.brennerstarts, 'taktet_gestern')) hints.push(esc(t('in.cycling')));
    const split = attr(h, s.kennwert_temperaturbereinigt, 'vorjahr');
    if (split && typeof split.gesamt_pct === 'number') {
      const sg = (v) => (v >= 0 ? '+' : '−') + TC.nf(Math.abs(v), 1) + ' %';
      hints.push(esc(t('in.split', { g: sg(split.gesamt_pct), r: sg(split.raumtemperatur_pct), v: sg(split.verhalten_pct),
        k: (split.innen_aenderung_k >= 0 ? '+' : '−') + TC.nf(Math.abs(split.innen_aenderung_k), 1) + ' K' })));
    }
    return head(`<small>${esc(m.name)}</small>`) + TC.analysisHtml(a, h, card._hist, t('an.kennwert'), '')
      + `<div class="qual">${esc(facts.join(' · '))}</div>`
      + hints.map((x) => `<div class="hint">${x}</div>`).join('')
      + I.seriesHtml(card, m) + I.archiveHtml(card, m) + I.genHtml(card);
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

  // Archiv beendeter Perioden (Prognose gegen Realität), selten: alle 30 Minuten
  I.loadArchive = async (card, deviceId) => {
    const h = card._h;
    if (!h || typeof h.callWS !== 'function' || card._archLoading || card._c.archiv === false) return;
    if (card._archAt && card._archKey === deviceId && Date.now() - card._archAt < (card._archErr ? 60e3 : 1800e3)) return;
    card._archLoading = true;
    card._archKey = deviceId;
    try {
      card._arch = await h.callWS({ type: 'tarif_cockpit/archiv', zaehler: deviceId });
      card._archErr = null;
    } catch (e) {
      card._arch = null;
      card._archErr = e;
    }
    card._archAt = Date.now();
    card._archLoading = false;
    card._last = null;
    card._render();
  };

  I.archiveHtml = (card, m) => {
    const t = TC.T;
    const r = card._arch;
    if (card._c.archiv === false || !r || r.zaehler_id !== m.zaehler_id || !r.perioden || !r.perioden.length) return '';
    const a = r.perioden[0].archiv;
    const rows = (a.prognose_gegen_realitaet || []).filter((x) => x.prognose_kosten !== null && x.prognose_kosten !== undefined);
    if (!rows.length || !a.kosten) return '';
    const dev = (x) => (x.abweichung === undefined || x.abweichung === null ? '—'
      : `${x.abweichung >= 0 ? '+' : '−'}${TC.eur(Math.abs(x.abweichung))} ${TC.cur()}${typeof x.abweichung_pct === 'number' ? ` <small>${x.abweichung_pct >= 0 ? '+' : '−'}${TC.nf(Math.abs(x.abweichung_pct), 1)} %</small>` : ''}`);
    const saldo = a.saldo === null || a.saldo === undefined ? '—' : `${a.saldo >= 0 ? '+' : '−'}${TC.eur(Math.abs(a.saldo))} ${TC.cur()}`;
    const stand = a.stand === 'abgeschlossen' ? t('ar.final') : t('ar.prelim');
    return `<div class="panel wide arch"><div class="chead"><span class="lbl">${esc(t('ar.title'))}</span><span class="leg">${esc(t('period', { a: dd(a.beginn), b: dd(a.ende) }))} · ${esc(stand)}</span></div>
      <table><thead><tr><th>${esc(t('ar.date'))}</th><th>${esc(t('ar.fc'))}</th><th>${esc(t('ar.dev'))}</th></tr></thead><tbody>
      ${rows.map((x) => `<tr><td>${esc(dd(x.datum))}</td><td>${money(x.prognose_kosten)}</td><td>${dev(x)}</td></tr>`).join('')}
      </tbody></table><div class="qual">${esc(t('ar.actual', { v: TC.eur(a.kosten.gesamt) + ' ' + TC.cur(), s: saldo }))}</div>`
      + (a.tageswerte_bis || !a.kosten.vollstaendig ? `<div class="hint">${esc(t('ar.partial', { d: dd(a.tageswerte_bis || a.ende) }))}</div>` : '') + '</div>';
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
.arch table{width:100%;border-collapse:collapse;font-size:.76rem;font-variant-numeric:tabular-nums;margin-top:6px}
.arch th{text-align:right;color:rgb(var(--mut));font-weight:500;font-size:.66rem;text-transform:uppercase;letter-spacing:.05em;padding:4px 6px}
.arch td{text-align:right;padding:5px 6px;border-top:1px solid rgba(var(--ov),.06)}
.arch th:first-child,.arch td:first-child{text-align:left}
.arch td small{color:rgb(var(--mut));font-size:.66rem}
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
