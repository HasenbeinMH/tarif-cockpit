"""Screenshots für README und docs aus den Testseiten (test/*.html) mit Playwright und Chromium (headless, auch unter Linux).

Einrichtung (einmalig):
    pip install playwright
    python -m playwright install chromium
Aufruf (vorher node tools/build.mjs):
    python tools/make-screenshots.py            alle Bilder
    python tools/make-screenshots.py hell en    nur Bilder, deren Name einen dieser Teile enthält
Ausgabe: docs/img/<name>.png (Ausschnitt des Karten- bzw. Editor-Elements).
Idee nach energy-cockpit/tools/make-screenshots.py (MIT, Copyright (c) 2026 Musicmaker3112), umgesetzt mit Playwright.
"""
import pathlib
import sys

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs' / 'img'

# (Seite, Bildname, Abfrage, Breite, Element)
CARD = '#host > *'
EDIT = '#dlg'
JOBS = [
    ('overview.html', 'overview-dunkel', 'scene=neu', 1100, CARD),
    ('overview.html', 'overview-graphit', 'scene=neu&theme=graphit', 1100, CARD),
    ('overview.html', 'overview-hell', 'scene=neu&theme=hell', 1100, CARD),
    ('overview.html', 'overview-warm', 'scene=neu&theme=warm', 1100, CARD),
    ('overview.html', 'overview-nachzahlung', 'scene=nachzahlung', 1100, CARD),
    ('overview.html', 'overview-schmal', 'scene=neu&narrow', 420, CARD),
    ('overview.html', 'overview-en', 'scene=en', 1100, CARD),
    ('analyse.html', 'analyse-dunkel', 'scene=haus', 1100, CARD),
    ('analyse.html', 'analyse-hell', 'scene=haus&theme=hell', 1100, CARD),
    ('overview.html', 'beispiel-haus', 'scene=haus', 1100, CARD),
    ('overview.html', 'beispiel-miete', 'scene=miete', 1100, CARD),
    ('overview.html', 'beispiel-wasser', 'scene=wasser', 1100, CARD),
    ('overview.html', 'beispiel-ohne', 'scene=ohne', 1100, CARD),
    ('overview.html', 'beispiel-leer', 'scene=leer', 1100, CARD),
    ('editor.html', 'editor-1-medien', 'scene=vorschlag&cfg=nichts&check=Strom&check=Gas', 600, EDIT),
    ('editor.html', 'editor-2-strom', 'scene=vorschlag&cfg=nichts&check=Strom&step=1', 600, EDIT),
    ('editor.html', 'editor-3-strom-fertig', 'scene=haus&cfg=leer&tab=wiz&step=1', 600, EDIT),
    ('editor.html', 'editor-4-aussehen', 'scene=haus&cfg=leer&tab=wiz&step=5', 600, EDIT),
    ('editor.html', 'editor-5-fertig', 'scene=haus&cfg=leer&tab=wiz&step=7', 600, EDIT),
    ('editor.html', 'editor-alle-felder', 'scene=haus&tab=form', 600, EDIT),
    ('editor.html', 'editor-analyse', 'card=analyse&scene=haus&cfg=nichts', 600, EDIT),
    # Integrations-Modus (0.7)
    ('overview.html', 'integration-uebersicht', 'scene=integration', 1100, CARD),
    ('overview.html', 'integration-lernt', 'scene=lernt', 1100, CARD),
    ('overview.html', 'integration-hell', 'scene=integration&theme=hell', 1100, CARD),
    ('analyse.html', 'integration-analyse', 'scene=integration', 1100, CARD),
    ('editor.html', 'integration-editor', 'scene=integ_neu', 600, EDIT),
    # Wärmeerzeuger und Diagramme (0.8)
    ('analyse.html', 'heizung-analyse', 'scene=heizung', 1100, CARD),
    ('analyse.html', 'heizung-analyse-hell', 'scene=heizung&theme=hell', 1100, CARD),
    ('analyse.html', 'waermepumpe-analyse', 'scene=waermepumpe', 1100, CARD),
    ('analyse.html', 'fernwaerme-analyse', 'scene=fernwaerme', 1100, CARD),
    ('analyse.html', 'heizung-analyse-schmal', 'scene=heizung&narrow', 420, CARD),
]


def main(filters):
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [j for j in JOBS if not filters or any(f in j[1] for f in filters)]
    if not (ROOT / 'custom_components' / 'tarif_cockpit' / 'frontend' / 'tarif-cockpit.js').exists():
        sys.exit('tarif-cockpit.js fehlt: zuerst node tools/build.mjs')
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for page_name, name, query, width, sel in jobs:
            page = browser.new_page(viewport={'width': width, 'height': 1600}, device_scale_factor=1.5 if width < 1000 else 1)
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto((ROOT / 'test' / page_name).as_uri() + '?shot&' + query)
            page.evaluate('document.fonts.ready')
            page.wait_for_timeout(700)
            el = page.locator(sel).first
            el.screenshot(path=str(OUT / f'{name}.png'))
            page.close()
            if errors:
                sys.exit(f'{name}: Fehler auf der Testseite: {errors}')
            print(f'docs/img/{name}.png')
        browser.close()


if __name__ == '__main__':
    main(sys.argv[1:])
