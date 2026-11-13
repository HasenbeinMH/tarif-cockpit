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
    let pill = '<span class="pill" style="--q:' + INFO + ';--qd:' + DARK[INFO] + '">' + esc(t('an.wait')) + '</span>';
    let big = '', cmp = '';
    if (kw !== null) {
      pill = '';
      big = `<div class="big" style="--q:${c};--qd:${c}"><span class="num">${nf(kw, 2)}</span><span class="unit">kWh/Kd</span><small>${esc(t('an.kw_last'))}</small></div>`;
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
