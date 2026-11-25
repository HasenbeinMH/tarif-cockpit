"""Wärmeerzeuger (Arbeitspaket 2.4, Entscheidung I): eingesetzte Energie, Wärme und Entlastung strikt getrennt.

- ``energy_input``: eingesetzte Energie (Gas, Strom, Holz) in kWh; gemessen (Energie-Entität, eigener Zähler),
  geschätzt (Leistung × Zeit) oder Annahme (Ofenstunden × Nennleistung ÷ Wirkungsgrad)
- ``thermal_output``: nur mit Wärmemengenzähler
- ``estimated_thermal_output``: Strom × COP, Ofenstunden × Nennleistung, Gas × Wirkungsgrad (immer als geschätzt)
- ``avoided_energy``: Entlastung des Wärmezählers (Gas/Fernwärme) – nur aus der Regression gelernt; beim Kaminofen vor
  genug Vergleichstagen als gekennzeichnete Annahme (Entscheidung C). Eine Wärmepumpe mit COP 4 spart nicht
  automatisch 4 kWh Gas je kWh Strom.

Umrechnungswege für die Leistungsangabe (Typschild, Heizbetrieb):
- Nennwärmebelastung (Gaseinsatz, Heizwert Hi) × Hs/Hi = Gaseinsatz nach Brennwert (wie der Gaszähler misst)
- Nennwärmeleistung (Wärmeabgabe) ÷ Wirkungsgrad × Hs/Hi
Alle Annahmen sind als solche gekennzeichnet.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta

from .model import GeneratorDaily, GeneratorKind, HeatGenerator, Medium, PowerBasis, WoodEntry
from .quality import Quality
from .regression import USABLE_FOR_FORECAST, HeatModel, ModelQuality

HS_HI = 1.11  # Brennwert/Heizwert Erdgas (Annahme)
BOILER_EFFICIENCY = 0.9  # Wirkungsgrad Gastherme bezogen auf Hi (Annahme)
WOOD_KWH_PER_KG = 4.2  # Heizwert lufttrockenes Holz (Annahme)
STOVE_EFFICIENCY = 0.75  # Wirkungsgrad Kaminofen, wenn keiner angegeben ist (Annahme)
# Gewogenes Holz (1.2.2): ab so vielen Tagen mit Holz und Brennstunden gilt die gelernte Leistung je Brennstunde
WOOD_RATE_MIN_DAYS = 3  # vorläufig
WOOD_RATE_GOOD_DAYS = 7  # gut
WOOD_RATE_MIN_HOURS = 1.0  # Tage mit weniger Brennstunden zählen nicht (Anzünden, Fehlerkennung)

# Vorschläge je Typ (Nennleistung Heizbetrieb kW, Wirkungsgrad bzw. COP, wirksamer Anteil beim Ofen)
KIND_DEFAULTS: dict[GeneratorKind, dict[str, float]] = {
    GeneratorKind.GAS_BOILER: {"nominal_kw": 15.0, "efficiency": BOILER_EFFICIENCY},
    GeneratorKind.AIR_AIR_HP: {"nominal_kw": 3.5, "cop": 3.5},
    GeneratorKind.WATER_HP: {"nominal_kw": 8.0, "cop": 3.5},
    GeneratorKind.DISTRICT_HEATING: {"nominal_kw": 10.0, "efficiency": 1.0},
    GeneratorKind.FIREPLACE: {"nominal_kw": 6.0, "efficiency": 0.75, "effective_share": 0.6},
    GeneratorKind.ELECTRIC: {"nominal_kw": 2.0, "efficiency": 1.0},
}

# Antworten "Womit heizt du?" → vorgeschlagene Erzeuger
SITUATION_KINDS: dict[str, GeneratorKind] = {
    "gas": GeneratorKind.GAS_BOILER,
    "fernwaerme": GeneratorKind.DISTRICT_HEATING,
    "waermepumpe": GeneratorKind.WATER_HP,
    "strom": GeneratorKind.AIR_AIR_HP,
    "kaminofen": GeneratorKind.FIREPLACE,
}

HEAT_PUMPS = (GeneratorKind.AIR_AIR_HP, GeneratorKind.WATER_HP)
ON_POWER_KINDS = (GeneratorKind.AIR_AIR_HP, GeneratorKind.WATER_HP, GeneratorKind.ELECTRIC)


def suggested_kinds(situation: Mapping) -> list[GeneratorKind]:
    out: list[GeneratorKind] = []
    for h in situation.get("heating", []) or []:
        k = SITUATION_KINDS.get(h)
        if k is not None and k not in out:
            out.append(k)
    return out


def default(gen: HeatGenerator, key: str) -> float | None:
    """Wert des Erzeugers oder der Vorschlag für seinen Typ (dann ist es eine Annahme)."""
    v = getattr(gen, key, None)
    return v if v is not None else KIND_DEFAULTS.get(gen.kind, {}).get(key)


def gas_per_hour(gen: HeatGenerator) -> float | None:
    """Gaseinsatz nach Brennwert (kWh Hs je Volllaststunde) aus der Typschild-Angabe."""
    nominal = gen.nominal_kw
    if nominal is None:
        return None
    if gen.power_basis == PowerBasis.INPUT:
        return nominal * HS_HI
    return nominal / (default(gen, "efficiency") or BOILER_EFFICIENCY) * HS_HI


def stove_relief_per_hour(gen: HeatGenerator, relieved: Medium, heat_kw: float | None = None) -> float | None:
    """Annahme: Entlastung des Wärmezählers je Ofenstunde (kWh in dessen Einheit nach Brennwert).
    Ofen-Nennleistung × wirksamer Anteil = Wärme, die sonst die Heizung liefern müsste; bei Gas ÷ Wirkungsgrad × Hs/Hi.
    ``heat_kw``: aus gewogenem Holz gelernte Wärme je Brennstunde (1.2.2), ersetzt die Nennleistung; der wirksame
    Anteil gilt weiter."""
    share = default(gen, "effective_share")
    nominal = heat_kw or default(gen, "nominal_kw")
    if not nominal or not share:
        return None
    heat = nominal * share
    if relieved == Medium.GAS:
        return heat / BOILER_EFFICIENCY * HS_HI
    return heat


def build_generator_day(
    gen: HeatGenerator,
    day: date,
    *,
    energy: float | None = None,
    power_mean_kw: float | None = None,
    heat: float | None = None,
    hours: float | None = None,
    meter_kwh: float | None = None,
    power_coverage: float = 1.0,
) -> GeneratorDaily:
    """Tageswert eines Erzeugers aus den gemessenen Größen (fehlend bleibt fehlend, nie 0)."""
    g = GeneratorDaily(generator_id=gen.generator_id, date=day, hours=hours)
    if energy is not None:
        g.energy_input, g.measurement_quality = energy, Quality.REAL
    elif meter_kwh is not None and not gen.on_household_power:
        g.energy_input, g.measurement_quality = meter_kwh, Quality.REAL
    elif power_mean_kw is not None and power_coverage >= 0.75:
        g.energy_input, g.measurement_quality = power_mean_kw * 24.0, Quality.ESTIMATED
    elif gen.kind == GeneratorKind.FIREPLACE and hours is not None:
        nominal = default(gen, "nominal_kw")
        eff = default(gen, "efficiency")
        if nominal and eff:
            g.energy_input, g.measurement_quality = hours * nominal / eff, Quality.ASSUMPTION
    if heat is not None:
        g.thermal_output = heat
        if g.measurement_quality == Quality.MISSING:
            g.measurement_quality = Quality.REAL
    elif gen.kind == GeneratorKind.FIREPLACE and hours is not None and default(gen, "nominal_kw"):
        # Ofenstunden × Nennleistung × wirksamer Anteil (Arbeitspaket 2.4)
        g.estimated_thermal_output = hours * (default(gen, "nominal_kw") or 0.0) * (default(gen, "effective_share") or 1.0)
    elif g.energy_input is not None:
        if gen.kind in HEAT_PUMPS:
            g.estimated_thermal_output = g.energy_input * (default(gen, "cop") or 1.0)
        elif gen.kind == GeneratorKind.GAS_BOILER:
            g.estimated_thermal_output = g.energy_input / HS_HI * (default(gen, "efficiency") or BOILER_EFFICIENCY)
        else:
            g.estimated_thermal_output = g.energy_input * (default(gen, "efficiency") or 1.0)
    return g


# ---------------------------------------------------------------- Gewogenes Holz (1.2.2)


@dataclass(slots=True, frozen=True)
class WoodRate:
    """Aus gewogenem Holz gelernt: kg je Brennstunde und die Wärme, die der Ofen dabei abgibt."""

    kg_per_hour: float
    heat_kw: float  # kg/h × Heizwert × Wirkungsgrad
    days: int
    hours: float
    kg: float
    quality: str  # vorlaeufig | gut


def wood_by_day(entries: Iterable[WoodEntry], generator_id: str) -> dict[date, float]:
    """Summe der gewogenen kg je Tag eines Ofens."""
    out: dict[date, float] = {}
    for w in entries:
        if w.generator_id == generator_id:
            out[w.date] = out.get(w.date, 0.0) + w.kg
    return out


def stove_efficiency(gen: HeatGenerator) -> float:
    return default(gen, "efficiency") or STOVE_EFFICIENCY


def wood_rate(gen: HeatGenerator, dailies: Mapping[date, GeneratorDaily], wood: Mapping[date, float]) -> WoodRate | None:
    """kg je Brennstunde aus den Tagen mit gewogenem Holz und erkannten Brennstunden (Summe kg ÷ Summe Stunden).
    Tage ohne Stunden, mit weniger als einer Stunde oder mit 0 kg zählen nicht. Zu wenige Tage → None (Regel 10)."""
    if gen.kind != GeneratorKind.FIREPLACE:
        return None
    kg = hours = 0.0
    n = 0
    for d, w in wood.items():
        g = dailies.get(d)
        if w <= 0 or g is None or g.hours is None or g.hours < WOOD_RATE_MIN_HOURS:
            continue
        kg += w
        hours += g.hours
        n += 1
    if n < WOOD_RATE_MIN_DAYS or hours <= 0:
        return None
    kgph = kg / hours
    return WoodRate(kg_per_hour=round(kgph, 3), heat_kw=round(kgph * WOOD_KWH_PER_KG * stove_efficiency(gen), 2), days=n,
                    hours=round(hours, 2), kg=round(kg, 1), quality="gut" if n >= WOOD_RATE_GOOD_DAYS else "vorlaeufig")


def apply_wood(gen: HeatGenerator, dailies: Mapping[date, GeneratorDaily], wood: Mapping[date, float],
               rate: WoodRate | None) -> dict[date, GeneratorDaily]:
    """Tageswerte mit dem gewogenen Holz: an gewogenen Tagen eingesetzte Energie = kg × Heizwert (Schätzung, die Menge ist
    gemessen). An den übrigen Tagen mit Brennstunden, deren Energie bisher nur aus der Nennleistung angenommen war, mit der
    gelernten Menge je Brennstunde (Qualität „geschätzt“ erst bei einer guten Rate, vorher weiter „Annahme“).
    Geschätzte Wärme wie bisher als wirksame Wärme: Ofenwärme (Energie × Wirkungsgrad) × wirksamer Anteil.
    Gemessene Werte (Energie-Entität, Wärmemengenzähler) bleiben unverändert."""
    out = dict(dailies)
    if gen.kind != GeneratorKind.FIREPLACE:
        return out
    factor = stove_efficiency(gen) * (default(gen, "effective_share") or 1.0)
    for d, kg in wood.items():
        base = out.get(d) or GeneratorDaily(generator_id=gen.generator_id, date=d)
        if base.measurement_quality == Quality.REAL and base.energy_input is not None:
            continue  # eigene Messung geht vor
        e = kg * WOOD_KWH_PER_KG
        measured_heat = base.thermal_output is not None
        out[d] = replace(base, energy_input=round(e, 3),
                         measurement_quality=base.measurement_quality if measured_heat else Quality.ESTIMATED,
                         estimated_thermal_output=base.estimated_thermal_output if measured_heat else round(e * factor, 3))
    if rate is not None:
        quality = Quality.ESTIMATED if rate.quality == "gut" else Quality.ASSUMPTION
        for d, g in list(out.items()):
            if d in wood or g.hours is None or g.measurement_quality not in (Quality.ASSUMPTION, Quality.MISSING):
                continue
            e = g.hours * rate.kg_per_hour * WOOD_KWH_PER_KG
            out[d] = replace(g, energy_input=round(e, 3), measurement_quality=quality,
                             estimated_thermal_output=round(e * factor, 3) if g.thermal_output is None else g.estimated_thermal_output)
    return out


@dataclass(slots=True)
class GeneratorResult:
    generator_id: str
    energy_input: float | None = None
    thermal_output: float | None = None
    estimated_thermal_output: float | None = None
    avoided_energy: float | None = None
    avoided_quality: str | None = None  # gut … / vorlaeufig / annahme; None = nicht gelernt
    hours: float | None = None
    days_on: int = 0
    wood_kg: float | None = None
    wood_cost: float | None = None
    wood_weighed_kg: float | None = None  # davon gewogen (1.2.2)
    wood_days: int = 0  # Tage mit gewogenem Holz in der Periode
    wood_rate: WoodRate | None = None  # gelernte Menge und Wärme je Brennstunde
    measurement_quality: Quality = Quality.MISSING
    days_with_data: int = 0
    days_total: int = 0
    flags: list[str] = field(default_factory=list)


def evaluate_generator(
    gen: HeatGenerator,
    dailies: Mapping[date, GeneratorDaily],
    start: date,
    end_excl: date,
    relieved_model: HeatModel | None = None,
    wood: Mapping[date, float] | None = None,
) -> GeneratorResult:
    """Summen der laufenden Periode (``start`` bis vor ``end_excl``) und die Entlastung des Wärmezählers.
    ``wood``: gewogenes Holz je Tag (Kaminofen, 1.2.2); die Menge je Brennstunde wird aus allen Tagen gelernt."""
    res = GeneratorResult(generator_id=gen.generator_id)
    if wood and gen.kind == GeneratorKind.FIREPLACE:
        res.wood_rate = wood_rate(gen, dailies, wood)
        dailies = apply_wood(gen, dailies, wood, res.wood_rate)
        in_period = [w for d, w in wood.items() if start <= d < end_excl]
        res.wood_days = len(in_period)
        res.wood_weighed_kg = round(sum(in_period), 1) if in_period else None
        res.flags.append("holz_gewogen" if res.wood_rate is None else "holz_leistung_gelernt")
    days = [dailies[d] for d in sorted(dailies) if start <= d < end_excl]
    res.days_total = max((end_excl - start).days, 0)
    if not days:
        res.flags.append("keine_tageswerte")
        return res
    qualities: list[Quality] = []

    def add(attr: str, v: float | None) -> None:
        if v is not None:
            setattr(res, attr, (getattr(res, attr) or 0.0) + v)

    for g in days:
        add("energy_input", g.energy_input)
        add("thermal_output", g.thermal_output)
        add("estimated_thermal_output", g.estimated_thermal_output)
        add("hours", g.hours)
        if g.hours is not None and g.hours >= 1.0:
            res.days_on += 1
        if g.energy_input is not None or g.thermal_output is not None or g.hours is not None:
            res.days_with_data += 1
            qualities.append(g.measurement_quality)
    if qualities:
        order = [Quality.REAL, Quality.ESTIMATED, Quality.ASSUMPTION, Quality.MISSING]
        res.measurement_quality = max(qualities, key=lambda q: order.index(q) if q in order else len(order))
    if res.days_with_data < res.days_total:
        res.flags.append("tageswerte_luecken")

    # Entlastung: Kaminofen über Ofenstunden, Wärmepumpe/Klima am Hausstrom über deren Strom – nur aus dem Modell
    m = relieved_model if relieved_model is not None and relieved_model.usable else None  # Regel 10: nur mit belastbarem Modell
    if gen.kind == GeneratorKind.FIREPLACE and not gen.relieves_heating:
        res.flags.append("entlastet_heizung_nicht")  # 1.2.8: heizt bewusst zusätzlich, nichts wird dem Gas gutgeschrieben
    elif m is not None and gen.kind == GeneratorKind.FIREPLACE and m.stove_coefficient is not None and res.hours is not None:
        res.avoided_energy = round(res.hours * m.stove_coefficient, 3)
        res.avoided_quality = (m.stove_quality or ModelQuality.ASSUMPTION).value
    elif (m is not None and gen.kind in ON_POWER_KINDS and m.hp_avoided_per_kwh and m.hp_quality in USABLE_FOR_FORECAST
          and res.energy_input is not None):
        res.avoided_energy = round(res.energy_input * m.hp_avoided_per_kwh, 3)
        res.avoided_quality = m.hp_quality.value
    elif gen.kind in (GeneratorKind.FIREPLACE, *ON_POWER_KINDS):
        res.flags.append("entlastung_noch_nicht_gelernt")

    # Holz (nur Schätzung): eingesetzte Energie ÷ Heizwert, Preis je kg oder je Raummeter
    if gen.kind == GeneratorKind.FIREPLACE and res.energy_input is not None:
        res.wood_kg = round(res.energy_input / WOOD_KWH_PER_KG, 1)
        if gen.wood_price is not None:
            per_kg = gen.wood_price if gen.wood_price_unit == "kg" else gen.wood_price / (gen.kg_per_rm or 400.0)
            res.wood_cost = round(res.wood_kg * per_kg, 2)
    for attr in ("energy_input", "thermal_output", "estimated_thermal_output", "hours"):
        v = getattr(res, attr)
        if v is not None:
            setattr(res, attr, round(v, 3))
    return res


# ---------------------------------------------------------------- Betriebsstunden

ON_STATES = ("on", "heat", "heating", "true", "an", "läuft")


def is_on(state: str | None) -> bool | None:
    """Zustand einer Betriebszustand-Entität: an/aus; Zahlen (Leistung) > 0 gelten als an. None = unbekannt."""
    if state is None or state in ("unknown", "unavailable", ""):
        return None
    s = str(state).strip().lower()
    if s in ON_STATES:
        return True
    try:
        return float(s) > 0
    except ValueError:
        return False


def on_hours(changes: list[tuple[datetime, bool | None]], start: datetime, end: datetime) -> float | None:
    """Betriebsstunden zwischen ``start`` und ``end`` aus Zustandswechseln (Zeitpunkt, an/aus/unbekannt).
    Der Zustand vor ``start`` muss als erster Eintrag (≤ start) enthalten sein. Ohne bekannten Zustand: None."""
    pts = sorted(changes, key=lambda c: c[0])
    if not pts:
        return None
    total = 0.0
    known = 0.0
    for i, (ts, on) in enumerate(pts):
        a = max(ts, start)
        b = min(pts[i + 1][0] if i + 1 < len(pts) else end, end)
        if b <= a:
            continue
        dur = (b - a).total_seconds() / 3600
        if on is not None:
            known += dur
            if on:
                total += dur
    span = (end - start).total_seconds() / 3600
    if span <= 0 or known < 0.75 * span:
        return None  # zu viel unbekannt: fehlend, nicht 0 (Regel 5)
    return round(total, 3)


def stove_hours_from_room(series: list[tuple[datetime, float]], threshold_k: float = 1.5, window_min: int = 30,
                          drop_k: float = 0.5) -> float | None:
    """Ofenbetrieb aus der Raumtemperatur am Aufstellort (5-Minuten-Werte): Start bei einem Anstieg ≥ ``threshold_k`` in
    ``window_min`` Minuten, Ende, sobald die Temperatur um ``drop_k`` unter das Maximum seit dem Start fällt.
    Nur aufrufen, wenn der Tag in der Heizperiode liegt. Zu wenige Werte → None."""
    pts = sorted(series, key=lambda p: p[0])
    if len(pts) < 12:
        return None
    on_minutes = 0.0
    running = False
    peak = 0.0

    for i, (ts, t) in enumerate(pts):
        if i == 0:
            continue
        step = (ts - pts[i - 1][0]).total_seconds() / 60
        if running:
            on_minutes += step
            peak = max(peak, t)
            if t <= peak - drop_k:
                running = False
            continue
        # Anstieg im Fenster: frühester Wert, der höchstens window_min zurückliegt
        j = i
        while j > 0 and ts - pts[j - 1][0] <= timedelta(minutes=window_min):
            j -= 1
        if j < i and t - pts[j][1] >= threshold_k:
            running = True
            peak = t
            on_minutes += (ts - pts[j][0]).total_seconds() / 60
    return round(on_minutes / 60, 3)
