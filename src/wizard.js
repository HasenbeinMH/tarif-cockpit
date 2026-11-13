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
