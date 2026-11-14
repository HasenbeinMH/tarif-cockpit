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
