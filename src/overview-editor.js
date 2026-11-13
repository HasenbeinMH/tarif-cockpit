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

  TC.defineEditor('tarif-cockpit-card-editor', {
    needsSetup: (c) => !Object.keys(TC.MEDIA).some((k) => c[k] && typeof c[k] === 'object' && Object.keys(c[k]).length),
    steps,
    form,
  });
})();
