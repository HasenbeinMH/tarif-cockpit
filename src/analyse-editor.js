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
    needsSetup: (c) => !(c.kennwert || c.consumption),
    steps,
    form,
  });
})();
