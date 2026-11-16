/* Karte 3: tarif-cockpit-ablesung-card (1.2.4). Zählerstände und Holz am Kaminofen eintragen, auch für Benutzer ohne Admin-Rechte.
   Die Karte rechnet nichts (Regel 2): Die letzte Ablesung kommt aus dem Sensor „Letzte Ablesung“, Verbrauch seit der letzten Ablesung,
   Warnung und gelernte Ofenleistung aus der Antwort der Aktionen tarif_cockpit.add_ablesung bzw. tarif_cockpit.holz_erfassen. */
(() => {
  const TC = window.TarifCockpit;
  const { esc } = TC;

  TC.addStrings('de', {
    'ab.title': 'Ablesung', 'ab.last': 'Letzte Ablesung: {v} · {d}', 'ab.none': 'Noch keine Ablesung',
    'ab.value': 'Neuer Stand', 'ab.time': 'Zeitpunkt (leer = jetzt)', 'ab.replace': 'Ersetzt die Ablesung {v} vom {d} (Tippfehler)', 'ab.invalid_time': 'Bitte einen gültigen Zeitpunkt eingeben.',
    'ab.bigger': 'Größer als die folgende Ablesung ({v}). Zeitpunkt prüfen.', 'ab.same_time': 'Zum selben Zeitpunkt gibt es schon eine Ablesung; die spätere gilt.',
    'ab.save': 'Speichern', 'ab.busy': 'Speichert …', 'ab.invalid': 'Bitte eine Zahl eingeben, z. B. 9812,4 oder 9.812,4.',
    'ab.saved': 'Gespeichert: {v}.', 'ab.since': '{d} seit {t}.', 'ab.smaller': 'Kleiner als die letzte Ablesung ({v}). Vertippt? Den richtigen Stand mit dem Haken „Ersetzt die Ablesung …“ speichern.',
    'ab.sensor': 'Zähler-Sensor zeigt {v} (Abweichung {d}).',
    'ab.wood': 'Holz heute', 'ab.wood_none': 'Heute noch nichts eingetragen', 'ab.wood_today': 'Heute: {v}',
    'ab.kg_ph': 'Holz in kg', 'ab.logs': 'oder Scheite', 'ab.per_log': '× {v} je Scheit', 'ab.per_log_in': 'à',
    'ab.wood_saved': 'Gespeichert: heute {v} (zählt ab morgen mit).', 'ab.wood_saved_day': 'Gespeichert: {v} am {d}.',
    'ab.wood_rate': 'Gelernt: {k} je Brennstunde, {p} ({q}).', 'ab.wood_learn': 'Die Ofenleistung lernt das Tarif-Cockpit ab 3 gewogenen Tagen.',
    'ab.wood_invalid': 'Bitte kg oder eine ganze Zahl Scheite eingeben.', 'ab.no_meters': '<b>Keine Zähler ausgewählt.</b> Im Karten-Editor Zähler auswählen.',
    'ab.note': 'Ablesungen werden angehängt; eine Korrektur ersetzt die letzte, ohne sie zu löschen. Ohne Admin-Rechte höchstens 14 Tage zurück.',
    'pick.ablesung.name': 'Tarif-Cockpit Ablesung',
    'pick.ablesung.desc': 'Zählerstände und Holz am Kaminofen eintragen, mit Verbrauch seit der letzten Ablesung',
    'ee.wood': 'Holz am Kaminofen anzeigen', 'ee.time': 'Feld für den Zeitpunkt anzeigen',
  });
  TC.addStrings('en', {
    'ab.title': 'Meter reading', 'ab.last': 'Last reading: {v} · {d}', 'ab.none': 'No reading yet',
    'ab.value': 'New reading', 'ab.time': 'Time (empty = now)', 'ab.replace': 'Replaces the reading {v} of {d} (typo)', 'ab.invalid_time': 'Please enter a valid time.',
    'ab.bigger': 'Higher than the following reading ({v}). Check the time.', 'ab.same_time': 'There is already a reading at the same time; the later one counts.',
    'ab.save': 'Save', 'ab.busy': 'Saving …', 'ab.invalid': 'Please enter a number, e.g. 9812.4.',
    'ab.saved': 'Saved: {v}.', 'ab.since': '{d} since {t}.', 'ab.smaller': 'Lower than the last reading ({v}). Typo? Save the correct value with the “Replaces the reading …” box ticked.',
    'ab.sensor': 'Meter sensor shows {v} (difference {d}).',
    'ab.wood': 'Firewood today', 'ab.wood_none': 'Nothing logged today', 'ab.wood_today': 'Today: {v}',
    'ab.kg_ph': 'Wood in kg', 'ab.logs': 'or logs', 'ab.per_log': '× {v} per log', 'ab.per_log_in': 'at',
    'ab.wood_saved': 'Saved: today {v} (counts from tomorrow).', 'ab.wood_saved_day': 'Saved: {v} on {d}.',
    'ab.wood_rate': 'Learned: {k} per burning hour, {p} ({q}).', 'ab.wood_learn': 'Tarif-Cockpit learns the stove output from 3 weighed days.',
    'ab.wood_invalid': 'Please enter kg or a whole number of logs.', 'ab.no_meters': '<b>No meters selected.</b> Choose meters in the card editor.',
    'ab.note': 'Readings are appended; a correction replaces the last one without deleting it. Without admin rights at most 14 days back.',
    'pick.ablesung.name': 'Tarif-Cockpit meter reading',
    'pick.ablesung.desc': 'Enter meter readings and firewood for the stove, with consumption since the last reading',
    'ee.wood': 'Show firewood for the stove', 'ee.time': 'Show the time field',
  });

  // Eingabe lesen (keine Fachrechnung): „9.812,4“, „9812,4“, „9812.4“, „21.500“ (deutsch: Tausenderpunkt) bzw. „9,812.4“ (englisch).
  // Nur Ziffern mit Punkt/Komma; Exponenten oder Hex werden abgelehnt.
  const decimalComma = () => TC.nf(1.5, 1).includes(',');
  const parseNum = (raw) => {
    let s = String(raw === undefined || raw === null ? '' : raw).trim().replace(/[\s  ']/g, '');
    if (!s) return null;
    if (!/^[0-9.,]+$/.test(s)) return NaN;
    if (s.includes(',') && s.includes('.')) {
      // beide Zeichen: das letzte trennt die Nachkommastellen
      s = s.lastIndexOf(',') > s.lastIndexOf('.') ? s.replace(/\./g, '').replace(',', '.') : s.replace(/,/g, '');
    } else if (decimalComma()) {
      if (s.includes(',')) s = s.replace(',', '.');
      else if (/^\d{1,3}(\.\d{3})+$/.test(s)) s = s.replace(/\./g, '');
    } else if (/^\d{1,3}(,\d{3})+$/.test(s)) s = s.replace(/,/g, '');
    else s = s.replace(',', '.');
    if (!/^\d+(\.\d+)?$/.test(s)) return NaN;
    return Number(s);
  };
  const decimals = (unit) => (/m³|m3|mwh/i.test(unit || '') ? 3 : 1);
  const fmt = (v, unit, d) => (v === null || v === undefined || !Number.isFinite(Number(v)) ? '—' : `${TC.nf(Number(v), d === undefined ? decimals(unit) : d)} ${unit || ''}`.trim());
  const signed = (v, unit) => (Number(v) > 0 ? '+' : '') + fmt(v, unit);
  const fdt = (iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? '' : d.toLocaleString(TC.loc, { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  };
  const fd = (iso) => (iso ? TC.fd(new Date(iso.length <= 10 ? iso + 'T00:00:00' : iso)) : '');
  const localDay = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

  const ABL_CSS = `
.abl{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}
.ab .ph{flex-direction:column;align-items:flex-start;gap:4px}
.ab .last{font-size:.72rem;color:rgb(var(--mut))}
.ab .last[data-entity]{cursor:pointer}
.inrow{display:flex;align-items:center;gap:8px;margin-top:12px}
.inrow input{flex:1 1 0;min-width:0;padding:10px 12px;border-radius:12px;border:1px solid var(--stroke);background:rgba(var(--ov),.05);color:var(--txt);font:inherit;font-size:1rem;font-variant-numeric:tabular-nums}
.inrow .u{font-size:.8rem;color:rgb(var(--mut));white-space:nowrap}
.inrow.two{margin-top:8px}
.inrow.two input{flex:0 0 72px;padding:8px 10px;font-size:.9rem}
.ab button.pri{padding:10px 14px;border-radius:12px;border:none;background:rgb(var(--c));color:#0b1220;font:inherit;font-weight:700;cursor:pointer;white-space:nowrap}
.ab button.pri[disabled]{opacity:.6;cursor:default}
.ab label.sm{display:block;font-size:.72rem;color:rgb(var(--mut));margin-top:10px}
.ab label.sm input{display:block;width:100%;box-sizing:border-box;margin-top:4px;padding:8px 10px;border-radius:10px;border:1px solid var(--stroke);background:rgba(var(--ov),.05);color:var(--txt);font:inherit}
.ab label.chk{display:flex;align-items:center;gap:8px;font-size:.74rem;color:rgb(var(--mut));margin-top:10px;cursor:pointer}
.ab .hint{margin-top:8px}
`;

  class TarifCockpitAblesungCard extends TC.BaseCard {
    static getConfigElement() { return document.createElement('tarif-cockpit-ablesung-card-editor'); }

    static getStubConfig() { return {}; }

    getCardSize() { return 4; }

    setConfig(c) {
      if (!c || typeof c !== 'object') throw new Error('tarif-cockpit-ablesung-card: Konfiguration fehlt');
      // I.load arbeitet mit integration: true; die Karte gibt es nur im Integrations-Modus
      this._c = Object.assign({}, c, { integration: true });
      this._vals = this._vals || {};
      this._msg = this._msg || {};
      this._busy = this._busy || {};
      this._own = this._own || {}; // zuletzt über diese Karte gespeicherte Ablesung je Zähler (für die Korrektur)
      this._last = null;
      this._build();
      this._wire();
      this._render();
      this._afterHass();
    }

    // eigene Styles nur in dieser Karte
    _build() {
      super._build();
      const st = document.createElement('style');
      st.textContent = ABL_CSS;
      this.shadowRoot.appendChild(st);
    }

    _afterHass() {
      if (!this._c || !TC.integ) return;
      TC.integ.load(this);
      const h = this._h;
      if (h && !this._trLoaded && typeof h.loadBackendTranslation === 'function') {
        this._trLoaded = true;
        try { h.loadBackendTranslation('exceptions', 'tarif_cockpit'); } catch (e) { /* Fehlertexte dann auf Englisch */ }
      }
    }

    _wire() {
      const w = this._w;
      const keep = (e) => { const k = e.target.dataset && e.target.dataset.in; if (k) this._vals[k] = e.target.type === 'checkbox' ? e.target.checked : e.target.value; };
      w.addEventListener('input', keep);
      w.addEventListener('change', keep);
      w.addEventListener('keydown', (e) => {
        if (e.key !== 'Enter' || !e.target.dataset || !e.target.dataset.in || e.target.type === 'checkbox') return;
        const key = e.target.dataset.in.split(':').slice(1).join(':');
        const kind = e.target.dataset.in.startsWith('w') ? 'w' : 'm';
        e.preventDefault();
        this._save(`${kind}:${key}`);
      });
      w.addEventListener('click', (e) => {
        const b = e.target.closest && e.target.closest('[data-save]');
        if (b) this._save(b.getAttribute('data-save'));
      });
    }

    // Eingaben stehen nicht im HTML: neue Sensorwerte bauen die Karte nur neu, wenn sich Angezeigtes ändert; danach
    // werden Eingaben und Fokus wiederhergestellt
    _put(html) {
      if (html === this._last) return;
      const a = this.shadowRoot.activeElement;
      const key = a && a.dataset ? a.dataset.in : null;
      let sel = null;
      try { sel = a && typeof a.selectionStart === 'number' ? [a.selectionStart, a.selectionEnd] : null; } catch (e) { sel = null; }
      this._w.innerHTML = html;
      this._last = html;
      this._w.querySelectorAll('[data-in]').forEach((n) => {
        const v = this._vals[n.dataset.in];
        if (n.type === 'checkbox') n.checked = !!v;
        else if (v !== undefined && v !== null) n.value = v;
      });
      if (key) {
        const n = [...this._w.querySelectorAll('[data-in]')].find((x) => x.dataset.in === key);
        if (n) { n.focus(); if (sel && n.setSelectionRange) { try { n.setSelectionRange(sel[0], sel[1]); } catch (err) { /* datetime-local */ } } }
      }
    }

    _hh() { return this._meta && this._meta.haushalte && this._meta.haushalte[0]; }

    // ohne Auswahl alle Zähler (auch Unterzähler wie Gartenwasser), mit Auswahl nur diese
    _meters() {
      const hh = this._hh();
      if (!hh) return [];
      const want = Array.isArray(this._c.zaehler) && this._c.zaehler.length ? this._c.zaehler : null;
      return hh.zaehler.filter((m) => m.device_id && (!want || want.includes(m.device_id) || want.includes(m.zaehler_id)));
    }

    _render() {
      if (!this._prepare()) return;
      const t = TC.T;
      const c = this._c;
      const h = this._h;
      const I = TC.integ;
      const header = this._header(c.icon || 'mdi:counter', c.title || t('ab.title'), '', '');
      if (!I || !I.available(h)) { this._put(`${header}<div class="setup">${t('in.missing')}</div>`); return; }
      if (!this._meta) { this._put(`${header}<div class="setup">${esc(t('in.loading'))}</div>`); return; }
      const hh = this._hh();
      if (!hh) { this._put(`${header}<div class="setup">${t('in.missing')}</div>`); return; }
      const meters = this._meters();
      const stoves = c.holz === false ? [] : (hh.waermeerzeuger || []).filter((g) => g.typ === 'fireplace' && g.device_id);
      if (!meters.length && !stoves.length) { this._put(`${header}<div class="setup">${t('ab.no_meters')}</div>`); return; }
      const body = meters.map((m) => this._meterHtml(m)).join('') + stoves.map((g) => this._stoveHtml(g)).join('');
      this._put(`${header}<div class="abl">${body}</div><div class="note">${esc(t('ab.note'))}</div>`);
    }

    _msgHtml(key) {
      const m = this._msg[key];
      if (!m) return '';
      return m.lines.map((l) => `<div class="${l.warn ? 'warn' : 'hint'}">${esc(l.text)}</div>`).join('');
    }

    // Welche Ablesung „Korrigiert die letzte Ablesung“ ersetzt: die eben über die Karte gespeicherte, sonst die letzte laut Sensor
    _target(m) {
      const own = this._own[m.device_id];
      if (own) return own;
      const s = m.sensoren || {};
      const last = s.letzte_ablesung && this._h.states[s.letzte_ablesung];
      if (!last || !last.attributes || last.attributes.stand === undefined || last.attributes.stand === null || ['unknown', 'unavailable'].includes(last.state)) return null;
      return { id: last.attributes.ablesung_id, stand: last.attributes.stand, zeit: last.state };
    }

    _meterHtml(m) {
      const t = TC.T;
      const s = m.sensoren || {};
      const tgt = this._target(m);
      const color = TC.rgbOf((this._c.colors || {})[m.medium], (TC.MEDIA[m.medium] || {}).color || TC.INFO);
      const dev = m.device_id;
      const busy = !!this._busy[`m:${dev}`];
      const maxTime = `${localDay(new Date())}T23:59`;
      return `<div class="panel ab" style="--c:${color}">
        <div class="ph"><span class="lbl"><i></i>${esc(m.name)}</span>
          <small class="last"${tgt && s.letzte_ablesung ? ` data-entity="${esc(s.letzte_ablesung)}"` : ''}>${esc(tgt ? t('ab.last', { v: fmt(tgt.stand, m.unit), d: fdt(tgt.zeit) }) : t('ab.none'))}</small></div>
        <div class="inrow"><input data-in="v:${esc(dev)}" inputmode="decimal" autocomplete="off" placeholder="${esc(t('ab.value'))}"><span class="u">${esc(m.unit || '')}</span>
          <button data-save="m:${esc(dev)}" class="pri"${busy ? ' disabled' : ''}>${esc(busy ? t('ab.busy') : t('ab.save'))}</button></div>
        ${this._c.zeitpunkt === false ? '' : `<label class="sm">${esc(t('ab.time'))}<input type="datetime-local" data-in="t:${esc(dev)}" max="${maxTime}"></label>`}
        ${tgt && tgt.id ? `<label class="chk"><input type="checkbox" data-in="r:${esc(dev)}">${esc(t('ab.replace', { v: fmt(tgt.stand, m.unit), d: fdt(tgt.zeit) }))}</label>` : ''}
        ${this._msgHtml(`m:${dev}`)}
      </div>`;
    }

    _stoveHtml(g) {
      const t = TC.T;
      const dev = g.device_id;
      const holz = g.holz || {};
      const busy = !!this._busy[`w:${dev}`];
      const perLog = holz.kg_je_scheit;
      // „heute“ nur, wenn der Wert wirklich von heute ist (die Zählerliste wird nicht laufend neu geholt)
      const today = holz.datum === localDay(new Date()) ? holz.heute : null;
      return `<div class="panel ab" style="--c:251,146,60">
        <div class="ph"><span class="lbl"><i></i>${esc(t('ab.wood'))} · ${esc(g.name)}</span>
          <small class="last">${esc(today !== null && today !== undefined ? t('ab.wood_today', { v: fmt(today, 'kg') }) : t('ab.wood_none'))}</small></div>
        <div class="inrow"><input data-in="wkg:${esc(dev)}" inputmode="decimal" autocomplete="off" placeholder="${esc(t('ab.kg_ph'))}"><span class="u">kg</span>
          <button data-save="w:${esc(dev)}" class="pri"${busy ? ' disabled' : ''}>${esc(busy ? t('ab.busy') : t('ab.save'))}</button></div>
        <div class="inrow two"><span class="u">${esc(t('ab.logs'))}</span><input data-in="wn:${esc(dev)}" inputmode="numeric" autocomplete="off">
          ${perLog ? `<span class="u">${esc(t('ab.per_log', { v: fmt(perLog, 'kg', 2) }))}</span>`
            : `<span class="u">${esc(t('ab.per_log_in'))}</span><input data-in="wp:${esc(dev)}" inputmode="decimal" autocomplete="off"><span class="u">kg</span>`}</div>
        ${this._msgHtml(`w:${dev}`)}
      </div>`;
    }

    async _save(key) {
      if (this._busy[key]) return;
      const [kind, dev] = [key.slice(0, 1), key.slice(2)];
      if (kind === 'm') await this._saveReading(dev);
      else if (kind === 'w') await this._saveWood(dev);
    }

    async _call(service, data) {
      const res = await this._h.callService('tarif_cockpit', service, data, undefined, false, true);
      return res && res.response ? res.response : null;
    }

    // Fehler der Integration in der Sprache der Oberfläche (Übersetzung aus translations/*.json)
    _errText(err) {
      const h = this._h;
      if (err && err.translation_key && h && typeof h.localize === 'function') {
        const txt = h.localize(`component.tarif_cockpit.exceptions.${err.translation_key}.message`, err.translation_placeholders || {});
        if (txt) return txt;
      }
      return (err && err.message) || String(err);
    }

    _done(key, lines) {
      this._busy[key] = false;
      this._msg[key] = { lines };
      this._last = null;
      this._render();
    }

    async _saveReading(dev) {
      const t = TC.T;
      const key = `m:${dev}`;
      const value = parseNum(this._vals[`v:${dev}`]);
      if (value === null || Number.isNaN(value)) { this._done(key, [{ text: t('ab.invalid'), warn: true }]); return; }
      const m = this._meters().find((x) => x.device_id === dev);
      const unit = m ? m.unit : '';
      const data = { zaehler: dev, stand: value, notiz: 'Ablese-Karte' };
      const ts = this._vals[`t:${dev}`];
      if (ts) {
        const d = new Date(ts); // Ortszeit des Browsers, mit Zeitzone gesendet
        if (Number.isNaN(d.getTime())) { this._done(key, [{ text: t('ab.invalid_time'), warn: true }]); return; }
        data.zeitpunkt = d.toISOString();
      }
      const tgt = this._vals[`r:${dev}`] && m ? this._target(m) : null;
      if (tgt && tgt.id) data.ersetzt = tgt.id;
      this._busy[key] = true; this._msg[key] = null; this._last = null; this._render();
      try {
        const r = await this._call('add_ablesung', data);
        const lines = [{ text: t('ab.saved', { v: fmt(value, unit) }) }];
        if (r) {
          if (r.verbrauch_seit !== null && r.verbrauch_seit !== undefined) {
            lines.push(r.kleiner_als_vorher ? { text: t('ab.smaller', { v: fmt(r.vorher_stand, unit) }), warn: true }
              : { text: t('ab.since', { d: signed(r.verbrauch_seit, unit), t: fdt(r.vorher_zeitpunkt) }) });
          }
          if (r.groesser_als_nachher) lines.push({ text: t('ab.bigger', { v: fmt(r.nachher_stand, unit) }), warn: true });
          if (r.gleicher_zeitpunkt) lines.push({ text: t('ab.same_time'), warn: true });
          if (r.sensor_stand !== null && r.sensor_stand !== undefined) lines.push({ text: t('ab.sensor', { v: fmt(r.sensor_stand, unit), d: signed(r.abweichung_sensor, unit) }) });
          if (r.ablesung_id) this._own[dev] = { id: r.ablesung_id, stand: r.stand, zeit: r.zeitpunkt || new Date().toISOString() };
        }
        this._vals[`v:${dev}`] = ''; this._vals[`t:${dev}`] = ''; this._vals[`r:${dev}`] = false;
        this._done(key, lines);
      } catch (err) {
        this._done(key, [{ text: this._errText(err), warn: true }]);
      }
    }

    async _saveWood(dev) {
      const t = TC.T;
      const key = `w:${dev}`;
      const kg = parseNum(this._vals[`wkg:${dev}`]);
      const logs = parseNum(this._vals[`wn:${dev}`]);
      const perLog = parseNum(this._vals[`wp:${dev}`]);
      const bad = (x) => x !== null && Number.isNaN(x);
      if ((kg === null && logs === null) || bad(kg) || bad(logs) || bad(perLog) || (logs !== null && !Number.isInteger(logs))) {
        this._done(key, [{ text: t('ab.wood_invalid'), warn: true }]);
        return;
      }
      const data = { erzeuger: dev, notiz: 'Ablese-Karte' };
      if (kg !== null) data.kg = kg;
      if (logs !== null) data.scheite = logs;
      if (perLog !== null && kg === null) data.kg_je_scheit = perLog;
      this._busy[key] = true; this._msg[key] = null; this._last = null; this._render();
      try {
        const r = await this._call('holz_erfassen', data);
        const lines = [];
        if (r) {
          const today = r.zaehlt_ab && r.datum && r.zaehlt_ab !== r.datum;
          lines.push({ text: today ? t('ab.wood_saved', { v: fmt(r.kg_tag, 'kg') }) : t('ab.wood_saved_day', { v: fmt(r.kg_tag, 'kg'), d: fd(r.datum) }) });
          lines.push({ text: r.leistung_kw ? t('ab.wood_rate', { k: fmt(r.kg_je_brennstunde, 'kg', 2), p: `${TC.nf(r.leistung_kw, 1)} kW`, q: t('q.' + r.qualitaet) }) : t('ab.wood_learn') });
        } else lines.push({ text: t('dlg.saved') });
        this._vals[`wkg:${dev}`] = ''; this._vals[`wn:${dev}`] = ''; this._vals[`wp:${dev}`] = '';
        this._metaAt = null; // „Holz heute“ und Gewicht je Scheit neu holen
        TC.integ.load(this, true);
        this._done(key, lines);
      } catch (err) {
        this._done(key, [{ text: this._errText(err), warn: true }]);
      }
    }
  }

  if (!customElements.get('tarif-cockpit-ablesung-card')) customElements.define('tarif-cockpit-ablesung-card', TarifCockpitAblesungCard);
  window.customCards = window.customCards || [];
  if (!window.customCards.some((x) => x.type === 'tarif-cockpit-ablesung-card')) {
    window.customCards.push({
      type: 'tarif-cockpit-ablesung-card',
      name: TC.T('pick.ablesung.name'),
      description: TC.T('pick.ablesung.desc'),
      preview: false,
    });
  }

  // Editor: Zählerauswahl, Titel und Farbschema wie bei den anderen Karten, dazu Holz und Zeitpunkt
  class AblesungEditor extends HTMLElement {
    setConfig(c) {
      const s = JSON.stringify(c || {});
      if (this._lastCfg === s) return;
      this._cfg = JSON.parse(s);
      this._draw();
    }

    set hass(h) {
      const first = !this._hass;
      this._hass = h;
      TC.useHass(h);
      if (first && this._cfg) this._draw();
    }

    _emit(cfg) {
      const out = TC.prune(JSON.parse(JSON.stringify(cfg)));
      if (this._cfg && this._cfg.type) out.type = this._cfg.type;
      delete out.integration;
      this._cfg = out;
      this._lastCfg = JSON.stringify(out);
      this.dispatchEvent(new CustomEvent('config-changed', { detail: { config: JSON.parse(this._lastCfg) }, bubbles: true, composed: true }));
    }

    _draw() {
      if (!this._cfg) return;
      if (!this._root) { this._root = document.createElement('div'); this.appendChild(this._root); }
      const root = this._root;
      root.innerHTML = '';
      const t = TC.T;
      const tab = document.createElement('div');
      root.appendChild(tab);
      TC.integTab({ titleKey: 'ab.title', noSensorMode: true, filter: () => true })(tab, {
        config: () => Object.assign({}, this._cfg, { integration: true }), hass: () => this._hass,
        emit: (c) => this._emit(c), rerender: () => this._draw(), setTab: () => {},
      });
      [['holz', 'ee.wood'], ['zeitpunkt', 'ee.time']].forEach(([k, lbl]) => {
        const l = document.createElement('label');
        l.style.cssText = 'display:flex;align-items:center;gap:8px;margin:10px 0 0';
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = this._cfg[k] !== false;
        cb.addEventListener('change', () => { const next = Object.assign({}, this._cfg); if (cb.checked) delete next[k]; else next[k] = false; this._emit(next); });
        l.appendChild(cb);
        l.appendChild(document.createTextNode(t(lbl)));
        root.appendChild(l);
      });
    }
  }
  if (!customElements.get('tarif-cockpit-ablesung-card-editor')) customElements.define('tarif-cockpit-ablesung-card-editor', AblesungEditor);
})();
