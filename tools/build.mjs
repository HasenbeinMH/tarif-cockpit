// Baut tarif-cockpit.js (Hauptverzeichnis, so erwartet es der Marketplace/HACS) aus den Dateien in src/.
// Aufruf: node tools/build.mjs   (keine Abhängigkeiten, die Dateien werden in fester Reihenfolge aneinandergefügt)
// Aufbau nach energy-cockpit/tools/build.mjs (MIT, Copyright (c) 2026 Musicmaker3112).
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const pkg = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'));

// Reihenfolge: gemeinsame Teile zuerst, dann Karten und Editoren.
const ORDER = [
  'common.js',
  'i18n.js',
  'chart.js',
  'base-card.js',
  'wizard.js',
  'editor-kit.js',
  'overview-card.js',
  'overview-editor.js',
  'analyse-card.js',
  'analyse-editor.js',
];

const missing = ORDER.filter((f) => !existsSync(join(root, 'src', f)));
if (missing.length) {
  console.error('Fehlende Quelldateien in src/: ' + missing.join(', '));
  process.exit(1);
}
// Die Version steht nur in package.json und wird hier eingesetzt
const src = readFileSync(join(root, 'src', 'common.js'), 'utf8');
if (!src.includes('__VERSION__')) {
  console.error('src/common.js: Platzhalter __VERSION__ fehlt.');
  process.exit(1);
}
const parts = ORDER.map((f) => `/* ---- ${f} ---- */\n` + readFileSync(join(root, 'src', f), 'utf8').replace(/__VERSION__/g, pkg.version).replace(/\r\n/g, '\n'));
const banner = `/*! tarif-cockpit v${pkg.version} - MIT License - https://github.com/HasenbeinMH/tarif-cockpit\n`
  + `    Editor-Baukasten und Assistent nach energy-cockpit, MIT License, Copyright (c) 2026 Musicmaker3112\n`
  + `    Diese Datei wird gebaut: Quellen in src/, Aufruf node tools/build.mjs */\n`;
writeFileSync(join(root, 'tarif-cockpit.js'), banner + parts.join('\n\n') + '\n');
console.log(`tarif-cockpit.js gebaut (${parts.length} Teile, v${pkg.version})`);
