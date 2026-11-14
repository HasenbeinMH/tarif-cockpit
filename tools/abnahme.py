"""Abnahme-Durchlauf (ab 0.7) in einer frischen Home-Assistant-Test-Instanz (Docker), nur über die Oberfläche, ohne YAML.

Ablauf:
  1. Onboarding per REST (Test-Benutzer mit zufälligem Kennwort, gespeichert in <config>/.abnahme-zugang.json)
  2. Playwright (Chromium): Integration „Tarif-Cockpit“ über die Fragen einrichten, Zähler anlegen,
     Karte über den Karteneditor ins Dashboard, Abschlag über den Dialog der Karte ändern.
  3. Bilder nach docs/img/abnahme-*.png

Vorbereitung (Beispiel, Port 8124):
  docker run -d --name tc-abnahme -p 127.0.0.1:8124:8123 -e TZ=Europe/Berlin \
    -v <leerer-ordner>:/config -v <repo>/custom_components/tarif_cockpit:/config/custom_components/tarif_cockpit:ro \
    ghcr.io/home-assistant/home-assistant:2026.11.1
Aufruf:
  python tools/abnahme.py <leerer-ordner> [http://127.0.0.1:8124] [alles|haushalt|zaehler|karte|dialog|waermeerzeuger|analyse|impulse|uebernahme]
"""
from __future__ import annotations

import json
import pathlib
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from playwright.sync_api import Page, expect, sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
IMG = ROOT / "docs" / "img"


def http(url: str, data=None, token: str | None = None, form: bool = False):
    headers = {}
    body = None
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        return json.loads(raw) if raw else None


def wait_ready(base: str) -> None:
    for _ in range(180):
        try:
            http(f"{base}/manifest.json")
            return
        except Exception:  # noqa: BLE001 - HA startet noch
            time.sleep(1)
    sys.exit("Home Assistant antwortet nicht")


def onboard(base: str, cfg: pathlib.Path) -> dict:
    """Legt den Test-Benutzer an (nur in einer frischen Instanz) und liefert Tokens."""
    store = cfg / ".abnahme-zugang.json"
    client = base + "/"
    try:
        steps = {s["step"]: s["done"] for s in http(f"{base}/api/onboarding")}
    except urllib.error.HTTPError:  # nach dem Neustart einer fertig eingerichteten Instanz
        steps = {"user": True, "core_config": True, "analytics": True, "integration": True}
    if not steps.get("user"):
        cred = {"username": "abnahme", "password": secrets.token_urlsafe(18)}
        store.write_text(json.dumps(cred), encoding="utf-8")
        code = http(f"{base}/api/onboarding/users", {"client_id": client, "name": "Abnahme", "language": "de", **cred})["auth_code"]
    else:
        cred = json.loads(store.read_text(encoding="utf-8"))
        flow = http(f"{base}/auth/login_flow", {"client_id": client, "handler": ["homeassistant", None], "redirect_uri": client})
        code = http(f"{base}/auth/login_flow/{flow['flow_id']}", {"client_id": client, **cred})["result"]
    tok = http(f"{base}/auth/token", {"grant_type": "authorization_code", "code": code, "client_id": client}, form=True)
    t = tok["access_token"]
    if not steps.get("core_config"):
        http(f"{base}/api/onboarding/core_config", {}, t)
    if not steps.get("analytics"):
        http(f"{base}/api/onboarding/analytics", {}, t)
    if not steps.get("integration"):
        http(f"{base}/api/onboarding/integration", {"client_id": client, "redirect_uri": client}, t)
    # Sprache, Währung, Zeitzone
    tok.update({"hassUrl": base, "clientId": client, "expires": int(time.time() * 1000) + tok["expires_in"] * 1000})
    return tok


FIND_DIALOG = """() => {
  const walk = (root) => {
    for (const el of root.querySelectorAll('*')) {
      if (el.tagName === 'DIALOG' || el.getAttribute('role') === 'dialog' || el.getAttribute('part') === 'dialog') {
        const r = el.getBoundingClientRect();
        if (r.width > 200 && r.height > 100) return { x: r.x, y: r.y, width: r.width, height: r.height };
      }
      if (el.shadowRoot) { const f = walk(el.shadowRoot); if (f) return f; }
    }
    return null;
  };
  return walk(document);
}"""


def shot(page: Page, name: str, sel: str | None = None) -> None:
    """Bild nach docs/img/abnahme-<name>.png; ohne sel der offene Dialog, sonst das Element."""
    IMG.mkdir(parents=True, exist_ok=True)
    path = str(IMG / f"abnahme-{name}.png")
    if sel:
        page.locator(sel).first.screenshot(path=path)
    else:
        clip = page.evaluate(FIND_DIALOG)
        page.screenshot(path=path, clip=clip) if clip else page.screenshot(path=path)
    print("Bild", name)


def dialog(page: Page):
    return page.locator("dialog-data-entry-flow")


def ok(page: Page, name: str = "OK") -> None:
    dialog(page).get_by_role("button", name=name, exact=True).last.click()
    page.wait_for_timeout(1500)


def fill(page: Page, label: str, value: str) -> None:
    f = dialog(page).get_by_label(label, exact=False).first
    f.fill(value)


SCR = None  # Ordner für Zwischenbilder (nur zur Fehlersuche)


def dbg(page: Page, name: str) -> None:
    if SCR:
        page.screenshot(path=str(SCR / f"{name}.png"))


def step_haushalt(page: Page, base: str) -> None:
    page.goto(f"{base}/config/integrations/dashboard/add?domain=tarif_cockpit")
    page.get_by_role("button", name="OK").click()
    page.wait_for_timeout(2500)
    d = dialog(page)
    name = d.get_by_role("textbox").first
    name.fill("Haus")
    page.set_viewport_size({"width": 1280, "height": 1500})
    page.wait_for_timeout(500)
    shot(page, "1-haushalt-fragen")
    ok(page)
    shot(page, "2-haushalt-klima")
    ok(page)
    shot(page, "3-haushalt-abschluss")
    ok(page)
    page.get_by_role("button", name="Überspringen und fertigstellen").click()
    page.set_viewport_size({"width": 1280, "height": 900})


def step_zaehler(page: Page, base: str) -> None:
    page.goto(f"{base}/config/integrations/integration/tarif_cockpit")
    page.wait_for_timeout(2500)
    page.get_by_role("button", name="Zähler hinzufügen").first.click()
    page.wait_for_timeout(2000)
    page.set_viewport_size({"width": 1280, "height": 1300})
    shot(page, "4-zaehler-medium")
    ok(page)
    shot(page, "5-zaehler-quelle")
    ok(page)
    d = dialog(page)
    d.get_by_role("spinbutton").last.fill("3500")  # Jahresverbrauch (ohne Sensor: Schätzung)
    d.get_by_role("spinbutton").last.press("Tab")
    page.wait_for_timeout(400)
    shot(page, "6-zaehler-einheit")
    ok(page)
    # Vertrag: Beginn heute (vorbelegt), fester Stichtag 30.07.
    tb(page, "Lieferant").fill("Stadtwerke")
    choose(page, "Abrechnung", "Fester Stichtag")
    tb(page, "Stichtag").fill("30.07")
    tb(page, "Stichtag").press("Tab")
    page.wait_for_timeout(600)
    shot(page, "7-zaehler-vertrag")
    ok(page)
    num(page, "Arbeitspreis").fill("0.3154")
    num(page, "Grundpreis").fill("13.09")
    num(page, "Grundpreis").press("Tab")
    page.wait_for_timeout(400)
    shot(page, "8-zaehler-preis")
    ok(page)
    num(page, "Abschlag").fill("85")
    num(page, "Abschlag").press("Tab")
    page.wait_for_timeout(400)
    shot(page, "9-zaehler-abschlag")
    ok(page)
    num(page, "Zählerstand").fill("6645.9")
    num(page, "Zählerstand").press("Tab")
    page.wait_for_timeout(400)
    shot(page, "10-zaehler-startstand")
    ok(page)
    page.wait_for_timeout(1500)
    shot(page, "11-zaehler-zusammenfassung")
    ok(page)
    page.set_viewport_size({"width": 1280, "height": 900})


HASS = "document.querySelector('home-assistant').hass"


def step_karte(page: Page, base: str) -> None:
    have = page.evaluate(f"async () => (await {HASS}.callWS({{type: 'lovelace/dashboards/list'}})).some((d) => d.url_path === 'dashboard-tarife')")
    if not have:
        page.goto(f"{base}/config/lovelace/dashboards")
        page.wait_for_timeout(2500)
        page.get_by_role("button", name="Dashboard hinzufügen").click()
        page.wait_for_timeout(1500)
        page.get_by_role("button", name="Neues Dashboard von Grund auf").click()
        page.wait_for_timeout(1500)
        page.get_by_role("textbox", name="Titel").first.fill("Tarife")
        page.wait_for_timeout(300)
        page.get_by_role("button", name="Erstellen").click()
        page.wait_for_timeout(2000)
    page.goto(f"{base}/dashboard-tarife/0")
    page.wait_for_timeout(3000)
    page.get_by_role("button", name="Dashboard bearbeiten").click()
    page.wait_for_timeout(1500)
    page.get_by_role("button", name="Karte hinzufügen").first.click()
    page.wait_for_timeout(2000)
    page.get_by_role("tab", name="Nach Karte").click()
    page.wait_for_timeout(1000)
    page.get_by_role("textbox").locator("visible=true").last.fill("Tarif")
    page.wait_for_timeout(1500)
    shot(page, "12-karte-auswahl")
    click_center(page, page.get_by_text("Kosten, Abschläge und Prognose", exact=False).first)
    page.wait_for_timeout(3500)
    expect(page.get_by_role("button", name="Integration", exact=True)).to_be_visible()
    shot(page, "13-karte-editor")
    page.get_by_role("button", name="Speichern").click()
    page.wait_for_timeout(2000)
    page.get_by_role("button", name="Fertig").click()
    page.wait_for_timeout(2500)
    card = page.locator("tarif-cockpit-card").first
    expect(card).to_contain_text("Nachzahlung")
    shot(page, "14-karte-dashboard", "tarif-cockpit-card")


def step_dialog(page: Page, base: str) -> None:
    page.goto(f"{base}/dashboard-tarife/0")
    page.wait_for_timeout(3500)
    card = page.locator("tarif-cockpit-card").first
    card.locator("[data-advance]").first.click()
    page.wait_for_timeout(800)
    amount = card.locator('[data-dlg="amount"]')
    expect(amount).to_have_value("112")  # vorbelegt mit dem empfohlenen Abschlag
    shot(page, "15-abschlag-dialog", "tarif-cockpit-card")
    card.locator('[data-dlg="save"]').click()
    page.wait_for_timeout(3000)
    expect(card.locator(".dlg")).to_have_count(0)
    expect(card).to_contain_text("Abschlag 112")
    shot(page, "16-karte-nach-aenderung", "tarif-cockpit-card")


def step_waermeerzeuger(page: Page, base: str) -> None:
    """Kaminofen mit Betriebszustand-Entität und Split-Klima am Haushaltsstrom (0.8)."""
    # Testhilfe: ein Schalter als "Kaminofen läuft" (Helfer über die API, wie über Einstellungen → Helfer)
    page.evaluate(f"async () => {{ const s = await {HASS}.callWS({{type: 'input_boolean/list'}}); "
                  f"if (!s.some((x) => x.name === 'Kaminofen läuft')) await {HASS}.callWS({{type: 'input_boolean/create', name: 'Kaminofen läuft'}}); }}")
    page.goto(f"{base}/config/integrations/integration/tarif_cockpit")
    page.wait_for_timeout(2500)
    page.set_viewport_size({"width": 1280, "height": 1400})
    page.get_by_role("button", name="Wärmeerzeuger hinzufügen").first.click()
    page.wait_for_timeout(2000)
    choose(page, "Art", "Kaminofen")
    tb(page, "Name").fill("Kaminofen")
    page.wait_for_timeout(300)
    shot(page, "17-erzeuger-typ")
    ok(page)
    shot(page, "18-erzeuger-leistung")
    ok(page)
    pick_entity(page, "Betriebszustand", "Kaminofen läuft")
    shot(page, "19-erzeuger-messwerte")
    ok(page)
    shot(page, "20-erzeuger-ofen")
    ok(page)
    shot(page, "21-erzeuger-zusammenfassung")
    ok(page)
    # Split-Klima am Haushaltsstrom: Zuordnung "Haushaltsstrom" ist vorbelegt
    page.goto(f"{base}/config/integrations/integration/tarif_cockpit")
    page.wait_for_timeout(2500)
    page.get_by_role("button", name="Wärmeerzeuger hinzufügen").first.click()
    page.wait_for_timeout(2000)
    choose(page, "Art", "Split-Klima / Luft-Luft-Wärmepumpe")
    tb(page, "Name").fill("Split-Klima Wohnzimmer")
    ok(page)
    shot(page, "22-erzeuger-zuordnung")
    ok(page)
    ok(page)  # Leistung: Vorschläge übernehmen
    ok(page)  # Messwerte: keine
    ok(page)  # Zusammenfassung
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(f"{base}/config/integrations/integration/tarif_cockpit")
    page.wait_for_timeout(2500)
    expect(page.get_by_text("Kaminofen").first).to_be_visible()
    expect(page.get_by_text("Split-Klima Wohnzimmer").first).to_be_visible()
    shot(page, "23-erzeuger-liste", "ha-config-integration-page")


def step_analyse(page: Page, base: str) -> None:
    """Auswertungskarte über den Karteneditor: Integration, Kostenverlauf (0.8)."""
    page.goto(f"{base}/dashboard-tarife/0")
    page.wait_for_timeout(3000)
    page.get_by_role("button", name="Dashboard bearbeiten").click()
    page.wait_for_timeout(1500)
    page.get_by_role("button", name="Karte hinzufügen").first.click()
    page.wait_for_timeout(2000)
    page.get_by_role("tab", name="Nach Karte").click()
    page.wait_for_timeout(1000)
    page.get_by_role("textbox").locator("visible=true").last.fill("Tarif")
    page.wait_for_timeout(1500)
    click_center(page, page.get_by_text("Kennwert je Gradtag, Streudiagramm", exact=False).first)
    page.wait_for_timeout(3500)
    expect(page.get_by_role("button", name="Integration", exact=True)).to_be_visible()
    shot(page, "24-analyse-editor")
    page.get_by_role("button", name="Speichern").click()
    page.wait_for_timeout(2000)
    page.get_by_role("button", name="Fertig").click()
    page.wait_for_timeout(3500)
    card = page.locator("tarif-cockpit-analyse-card").first
    expect(card).to_contain_text("Kosten der Periode")
    shot(page, "25-analyse-dashboard", "tarif-cockpit-analyse-card")


def step_impulse(page: Page, base: str) -> None:
    """Gaszähler mit Impulszähler über die Oberfläche (0.9): Impulskonstante, Abgleich-Sensor."""
    page.evaluate(f"async () => {{ const s = await {HASS}.callWS({{type: 'counter/list'}}); "
                  f"if (!s.some((x) => x.name === 'Gas Impulse')) await {HASS}.callWS({{type: 'counter/create', name: 'Gas Impulse', initial: 0, step: 1}}); }}")
    page.goto(f"{base}/config/integrations/integration/tarif_cockpit")
    page.wait_for_timeout(2500)
    page.set_viewport_size({"width": 1280, "height": 1400})
    page.get_by_role("button", name="Zähler hinzufügen").first.click()
    page.wait_for_timeout(2000)
    choose(page, "Medium", "Gas")
    ok(page)
    pick_entity(page, "Impulszähler", "Gas Impulse")
    shot(page, "26-impuls-quelle")
    ok(page)
    num(page, "Brennwert").fill("11.2")
    num(page, "Zustandszahl").fill("0.95")
    num(page, "Impulskonstante").fill("0.01")
    choose(page, "Angabe als", "Einheit je Impuls (z. B. 0,01 m³/Imp)")
    page.wait_for_timeout(300)
    shot(page, "27-impuls-einheit")
    ok(page)
    tb(page, "Lieferant").fill("Gasversorger")
    ok(page)
    num(page, "Arbeitspreis").fill("0.10")
    num(page, "Grundpreis").fill("15")
    ok(page)
    num(page, "Abschlag").fill("150")
    ok(page)
    num(page, "Zählerstand").fill("9800")
    ok(page)
    page.wait_for_timeout(1500)
    ok(page)
    page.set_viewport_size({"width": 1280, "height": 900})
    page.wait_for_timeout(2500)
    found = page.evaluate(f"() => Object.keys({HASS}.states).filter((e) => e.startsWith('sensor.gas') && "
                          f"({HASS}.states[e].attributes.friendly_name || '').includes('Abgleich'))")
    assert found, "Abgleich-Sensor fehlt"
    print("Abgleich-Sensor:", found[0])
    # Abgleich: Ablesung jetzt (merkt den Sensorstand), 50 Impulse (0,5 m³), Ablesung 0,6 m³ später → −16,7 %
    dev = page.evaluate(f"async () => (await {HASS}.callWS({{type: 'config/device_registry/list'}}))"
                        f".find((d) => d.name === 'Gas' && d.manufacturer === 'Tarif-Cockpit').id")
    page.evaluate(f"async () => {HASS}.callService('tarif_cockpit', 'add_ablesung', {{zaehler: '{dev}', stand: 9800.0}})")
    page.wait_for_timeout(1500)
    page.evaluate(f"async () => {{ for (let i = 0; i < 50; i++) await {HASS}.callService('counter', 'increment', "
                  f"{{entity_id: 'counter.gas_impulse'}}); }}")
    page.wait_for_timeout(1500)
    page.evaluate(f"async () => {HASS}.callService('tarif_cockpit', 'add_ablesung', {{zaehler: '{dev}', stand: 9800.6}})")
    page.wait_for_timeout(3000)
    val = float(page.evaluate(f"() => {HASS}.states['{found[0]}'].state"))
    assert abs(val + 16.67) < 0.1, val
    print("Abgleich:", val, "%")
    page.goto(f"{base}/config/repairs")
    page.wait_for_timeout(2500)
    expect(page.get_by_text("Sensor weicht von der Ablesung ab").first).to_be_visible()
    shot(page, "28-abgleich-reparatur", "ha-config-repairs-dashboard")


def step_uebernahme(page: Page, base: str) -> None:
    """Übernahme aus 0.3 (1.0): Helfer wie in der Template-Version anlegen, Aktion uebernahme_v03 für den Gaszähler aufrufen."""
    helpers = {"Abschlag Gas": 185, "Zahltag Gas": 15, "Arbeitspreis Gas": 0.1123, "Grundpreis Gas": 14.9}
    for name, value in helpers.items():
        page.evaluate(f"async () => {{ const l = await {HASS}.callWS({{type: 'input_number/list'}}); "
                      f"if (!l.some((x) => x.name === '{name}')) await {HASS}.callWS({{type: 'input_number/create', name: '{name}', min: 0, max: 10000, step: 0.0001, mode: 'box'}}); }}")
        page.wait_for_timeout(500)
        eid = "input_number." + name.lower().replace(" ", "_")
        page.evaluate(f"async () => {HASS}.callService('input_number', 'set_value', {{entity_id: '{eid}', value: {value}}})")
    page.wait_for_timeout(1000)
    dev = page.evaluate(f"async () => (await {HASS}.callWS({{type: 'config/device_registry/list'}}))"
                        f".find((d) => d.name === 'Gas' && d.manufacturer === 'Tarif-Cockpit').id")
    resp = page.evaluate(f"""async () => (await {HASS}.callWS({{type: 'execute_script', sequence: [{{action: 'tarif_cockpit.uebernahme_v03',
        data: {{zaehler: '{dev}', abschlag: 'input_number.abschlag_gas', zahltag: 'input_number.zahltag_gas',
                arbeitspreis: 'input_number.arbeitspreis_gas', grundpreis: 'input_number.grundpreis_gas'}}, response_variable: 'r'}},
        {{stop: 'ok', response_variable: 'r'}}]}})).response""")
    print("Übernahme:", resp)
    assert set(resp["uebernommen"]) >= {"abschlag", "zahltag", "arbeitspreis", "grundpreis"}, resp
    page.wait_for_timeout(2000)
    adv = page.evaluate(f"() => Object.keys({HASS}.states).filter((e) => e.startsWith('sensor.gas') && "
                        f"({HASS}.states[e].attributes.friendly_name || '').endsWith('Abschlag')).map((e) => {HASS}.states[e].state)")
    assert "185.0" in adv or "185" in adv, adv
    print("Abschlag-Sensor:", adv)


def pick_entity(page: Page, label: str, name: str) -> None:
    """Entitätsauswahl im Dialog: Feld öffnen, Namen suchen, Treffer wählen."""
    d = dialog(page)
    d.get_by_role("button", name=re.compile("^" + re.escape(label) + ".*Entität auswählen")).first.click()
    page.wait_for_timeout(1200)
    popup = d.get_by_role("dialog", name=re.compile("^" + re.escape(label)))
    popup.get_by_placeholder("Durchsuchen").fill(name)
    page.wait_for_timeout(800)
    popup.get_by_role("option", name=re.compile("^" + re.escape(name))).first.click()
    page.wait_for_timeout(800)


def click_center(page: Page, loc) -> None:
    """Klick auf die Mitte (Kartenwähler: eine Überlagerung fängt den Klick ab)."""
    b = loc.bounding_box()
    page.mouse.click(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)


def step_alles(page: Page, base: str) -> None:
    for name in ("haushalt", "zaehler", "karte", "dialog", "waermeerzeuger", "analyse", "impulse", "uebernahme"):
        print("Schritt", name)
        globals()[f"step_{name}"](page, base)
    print("Abnahme bestanden: Einrichtung ohne YAML bis zur Karte, Abschlag über den Dialog, Wärmeerzeuger, Auswertungskarte, Impulszähler, Übernahme aus 0.3.")


def tb(page: Page, label: str):
    return dialog(page).get_by_role("textbox", name=re.compile("^" + re.escape(label))).first


def num(page: Page, label: str):
    return dialog(page).get_by_role("spinbutton", name=re.compile("^" + re.escape(label))).first


def choose(page: Page, label: str, option: str) -> None:
    dialog(page).get_by_role("button", name=re.compile("^" + re.escape(label))).first.click()
    page.wait_for_timeout(400)
    dialog(page).get_by_text(option, exact=True).locator("visible=true").last.click()
    page.wait_for_timeout(400)


def main(cfg: pathlib.Path, base: str, step: str) -> None:
    wait_ready(base)
    tok = onboard(base, cfg)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 900}, locale="de-DE", device_scale_factor=1)
        ctx.add_init_script(f"localStorage.setItem('hassTokens', {json.dumps(json.dumps(tok))}); localStorage.setItem('selectedLanguage', '\"de\"');")
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "tarif" in m.text.lower() else None)
        page.goto(f"{base}/config/integrations/dashboard")
        page.wait_for_timeout(3000)
        global SCR
        SCR = cfg
        # Systemsprache Deutsch (wie bei einer deutschen Installation; Texte in Platzhaltern folgen ihr)
        page.wait_for_function("() => document.querySelector('home-assistant')?.hass?.connection")
        page.evaluate("() => document.querySelector('home-assistant').hass.callWS({type: 'config/core/update', language: 'de', country: 'DE', currency: 'EUR', time_zone: 'Europe/Berlin', unit_system: 'metric'})")
        if step == "probe":
            return
        globals()[f"step_{step}"](page, base)
        print("Konsolenfehler:", errors or "keine")
        browser.close()


if __name__ == "__main__":
    main(pathlib.Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8124", sys.argv[3] if len(sys.argv) > 3 else "alles")
