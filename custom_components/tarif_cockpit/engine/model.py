"""Datenmodell des Tarif-Cockpits (Arbeitspaket Abschnitt 2.2).

Alle Objekte sind Dataclasses mit ``to_dict`` und ``from_dict``. ``from_dict`` repariert nichts still:
Fehler werden gesammelt und zurückgegeben (Regel 3), damit beschädigte Daten gemeldet statt verworfen werden.

Speicherorte (Entscheidung E): Haushalt, Zähler und Wärmeerzeuger kommen aus dem Config Entry bzw. den
Subentries; alles mit zeitlicher Historie steht im ``Dataset`` (persistenter Store).
"""

from __future__ import annotations

from dataclasses import MISSING, dataclass, field, fields, is_dataclass
from datetime import date, datetime
from enum import StrEnum
import types
from typing import Any, TypeVar, Union, get_args, get_origin, get_type_hints
import uuid

from .quality import READING_QUALITIES, Quality

T = TypeVar("T")
# Alias für Felder, die selbst "date" heißen (sonst verdeckt der Feldname den Typ)
_Date = date


def new_id() -> str:
    """Kurze, eindeutige ID für Ablesungen, Verträge, Perioden usw."""
    return uuid.uuid4().hex[:12]


class Medium(StrEnum):
    STROM = "strom"
    GAS = "gas"
    WASSER = "wasser"
    FERNWAERME = "fernwaerme"


class BillingRule(StrEnum):
    CONTRACT_YEAR = "contract_year"  # 12 Monate ab Vertragsbeginn
    CALENDAR_YEAR = "calendar_year"  # Stichtag 01.01., erste Periode Rumpfjahr
    FIXED_DAY = "fixed_day"  # fester Stichtag TT.MM
    MANUAL = "manual"  # Perioden von Hand


class VatMode(StrEnum):
    GROSS = "gross"
    NET = "net"


class PeriodStatus(StrEnum):
    OPEN = "open"
    CLOSING = "closing"  # Ende vorbei, Endablesung fehlt noch
    CLOSED = "closed"


class ReadingSource(StrEnum):
    INITIAL = "initial"  # Startstand aus der Einrichtung
    MANUAL = "manual"  # Service add_ablesung
    SWITCH = "switch"  # Wechselablesung beim Anbieterwechsel
    IMPORT = "import"  # Übernahme (z. B. Migration von v0.3)
    ENTITY = "entity"  # aus dem Zählerstand-Sensor


class PaymentType(StrEnum):
    ADVANCE = "advance"
    ONE_OFF = "one_off"
    CREDIT = "credit"
    FINAL = "final"
    REFUND = "refund"


class PaymentStatus(StrEnum):
    PLANNED = "planned"
    PAID = "paid"
    CANCELLED = "cancelled"


class GeneratorKind(StrEnum):
    GAS_BOILER = "gas_boiler"
    AIR_AIR_HP = "air_air_hp"  # Split-Klima / Luft-Luft-Wärmepumpe
    WATER_HP = "water_hp"
    DISTRICT_HEATING = "district_heating"
    FIREPLACE = "fireplace"
    ELECTRIC = "electric"


class PowerBasis(StrEnum):
    OUTPUT = "output"  # Nennwärmeleistung (Wärmeabgabe)
    INPUT = "input"  # Nennwärmebelastung (Gaseinsatz, Hi)


# ---------------------------------------------------------------- Stammdaten (Config Entry / Subentries)


@dataclass(slots=True)
class Room:
    entity: str
    area_m2: float | None = None


@dataclass(slots=True)
class Household:
    name: str = "Zuhause"
    outdoor_temp_entity: str | None = None
    weather_entity: str | None = None
    heating_limit: float = 15.0
    indoor_ref: float = 20.0
    tolerance_pct: float = 5.0
    rooms: list[Room] = field(default_factory=list)
    # Antworten des Fragen-Assistenten: heating, hot_water, extras, tenure, rhythm (Abschnitt 1a)
    situation: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Conversion:
    """Umrechnung Gas m³ → kWh. Werte ändern sich mit der Rechnung; zeitliche Gültigkeit folgt in P3."""

    calorific: float | None = None  # Brennwert kWh/m³
    z_factor: float | None = None  # Zustandszahl


@dataclass(slots=True)
class Replacement:
    """Zählertausch: alter Endstand, neuer Startstand; der Verbrauch läuft durch."""

    date: _Date
    old_end: float
    new_start: float


@dataclass(slots=True)
class IntervalSource:
    """Vorbereitung dynamischer Tarif (Entscheidung J): Quelle für Intervallverbrauch. Aktiv erst nach 1.0."""

    entity: str
    minutes: int = 15
    kind: str = "energy"  # energy | power


@dataclass(slots=True)
class Meter:
    meter_id: str
    medium: Medium
    unit: str
    entity: str | None = None
    name: str | None = None
    conversion: Conversion = field(default_factory=Conversion)
    data_level: int = 1  # 1 = Ablesungen, 2 = Zählerstand-Sensor/Impulse
    pulse_constant: float | None = None  # Impulszähler: Impulse je Einheit bzw. Einheit je Impuls
    pulse_mode: str = "per_unit"  # per_unit | per_pulse
    replacements: list[Replacement] = field(default_factory=list)
    interval: IntervalSource | None = None
    # Ersatzquelle für fehlende Historie (z. B. Bezugszähler des Wechselrichters, solange der Zähler-Sensor neu ist)
    history_entity: str | None = None
    # Rolle: main (Hauptzähler), wallbox (Unterzähler, Sonderverbraucher), garden (Gartenwasser, kein Abwasser)
    role: str = "main"
    parent_meter_id: str | None = None  # bei wallbox/garden: der Hauptzähler
    annual_consumption: float | None = None  # Jahresverbrauch laut letzter Rechnung (Rückfallebene der Prognose)


@dataclass(slots=True)
class HeatGenerator:
    """Wärmeerzeuger (Abschnitt 2.4, Subentry "waermeerzeuger"), ausgewertet ab 0.8.

    ``entities``: energy (eingesetzte Energie kWh, total_increasing), power (Leistung W/kW), modulation (%),
    heat (erzeugte Wärme kWh), state (Betriebszustand, an/aus), room (Raumtemperatur)."""

    generator_id: str
    kind: GeneratorKind
    meter_id: str | None = None  # eigener Zähler
    on_household_power: bool = False  # hängt am Haushaltsstrom
    nominal_kw: float | None = None
    min_kw: float | None = None
    power_basis: PowerBasis = PowerBasis.OUTPUT
    max_dhw_kw: float | None = None
    efficiency: float | None = None
    cop: float | None = None
    central_dhw: bool = False  # macht zentrales Warmwasser
    room_entity: str | None = None
    effective_share: float | None = None
    wood_price: float | None = None
    entities: dict[str, str] = field(default_factory=dict)  # energy, power, modulation, heat, state, room
    name: str | None = None
    # Kaminofen: Betrieb aus der Entität "state" oder selbst aus der Raumtemperatur erkannt
    stove_detection: str = "entity"  # entity | room
    stove_threshold_k: float = 1.5  # Anstieg in 30 Minuten
    wood_price_unit: str = "kg"  # kg | rm (Raummeter)
    kg_per_rm: float = 400.0  # Annahme Buche/Hartholz


# ---------------------------------------------------------------- Historie (Store)


@dataclass(slots=True)
class Reading:
    reading_id: str
    meter_id: str
    timestamp: datetime
    value: float
    quality: Quality = Quality.REAL
    source: ReadingSource = ReadingSource.MANUAL
    note: str | None = None
    superseded_by: str | None = None  # gesetzt, wenn eine Korrektur diese Ablesung ersetzt
    sensor_value: float | None = None  # Stand des Zähler-Sensors zum Ablesezeitpunkt (für den Abgleich, ab 0.9)


@dataclass(slots=True)
class DailyConsumption:
    meter_id: str
    date: _Date
    consumption: float | None = None  # in der Zählereinheit; None = fehlend (nie 0 für fehlend)
    end_value: float | None = None  # Zählerstand am Tagesende (aus der Statistik), Startwert für Perioden
    degree_days: float | None = None
    outdoor_temperature: float | None = None
    indoor_temperature: float | None = None
    heating_hours: float | None = None  # Brennerlaufzeit (Gas mit Impulsen, ab 0.9)
    fireplace_hours: float | None = None
    quality: Quality = Quality.MISSING
    quality_flags: list[str] = field(default_factory=list)
    source: str = "statistics"  # statistics | readings
    raw_consumption: float | None = None  # gemessener Wert vor dem Abgleich mit den Ablesungen (ab 0.9)
    raw_quality: Quality | None = None  # Qualität vor dem Abgleich (zum Zurücksetzen)
    burner_starts: int | None = None  # Brennerstarts (Gas mit Impulsen)
    cycling: bool | None = None  # Brenner taktet (Heizlast unter der kleinsten Modulationsstufe)


@dataclass(slots=True)
class PeriodSpan:
    start: date
    end: date


@dataclass(slots=True)
class Contract:
    contract_id: str
    meter_id: str
    supplier: str
    start_date: date
    billing_rule: BillingRule
    tariff: str | None = None
    end_date: date | None = None
    fixed_day: str | None = None  # "TT.MM" bei billing_rule fixed_day
    manual_periods: list[PeriodSpan] = field(default_factory=list)  # bei billing_rule manual
    vat_mode: VatMode = VatMode.GROSS
    vat_rate: float = 19.0
    min_term_months: int | None = None
    notice_period_weeks: int | None = None
    bonus: float | None = None


@dataclass(slots=True)
class BillingPeriod:
    period_id: str
    contract_id: str
    start_date: date
    end_date: date
    status: PeriodStatus = PeriodStatus.OPEN
    is_partial: bool = False  # Rumpfjahr
    is_final: bool = False  # Schlussrechnung (Vertragsende)
    regular_end: date | None = None  # Ende nach Regel, wenn der tatsächliche Ablesetermin abweicht
    start_reading: str | None = None  # reading_id
    end_reading: str | None = None
    archived_at: datetime | None = None
    archive: dict[str, Any] = field(default_factory=dict)  # eingefrorene Ergebnisse (ab 0.6/1.0)


@dataclass(slots=True)
class PriceSegment:
    contract_id: str
    valid_from: date
    work_price: float  # je kWh bzw. m³
    base_price: float  # je Monat
    valid_to: date | None = None
    components: dict[str, float] = field(default_factory=dict)  # energy, grid_fee, taxes_levies
    demand_price: float | None = None  # Fernwärme: Leistungspreis je kW und Jahr
    metering_price: float | None = None  # Messpreis je Monat
    calorific: float | None = None  # Gas: Brennwert in diesem Abschnitt (sonst vom Zähler)
    z_factor: float | None = None  # Gas: Zustandszahl in diesem Abschnitt
    wastewater_price: float | None = None  # Wasser: Abwasser je m³
    fixed_yearly: float | None = None  # feste Jahresbeträge, z. B. Niederschlagswasser
    demand_kw: float | None = None  # Fernwärme: Anschlussleistung kW für den Leistungspreis


@dataclass(slots=True)
class AdvanceStep:
    from_date: date
    amount: float
    pay_day: int | None = None  # ab dieser Stufe anderer Zahltag (sonst der des Plans)
    rhythm: int | None = None  # ab dieser Stufe anderer Rhythmus (sonst der des Plans)


@dataclass(slots=True)
class AdvancePlan:
    contract_id: str
    steps: list[AdvanceStep] = field(default_factory=list)
    pay_day: int = 1
    rhythm: int = 1  # 1, 2 oder 3 Monate
    max_per_period: int | None = None  # z. B. 11 Abschläge je Abrechnungsjahr


@dataclass(slots=True)
class Payment:
    payment_id: str
    contract_id: str
    date: _Date
    amount: float
    type: PaymentType = PaymentType.ADVANCE
    status: PaymentStatus = PaymentStatus.PAID


@dataclass(slots=True)
class Invoice:
    invoice_id: str
    contract_id: str
    invoice_date: date
    period_from: date
    period_to: date
    amount: float
    period_id: str | None = None
    is_correction: bool = False
    corrects_invoice_id: str | None = None


@dataclass(slots=True)
class ForecastSnapshot:
    period_id: str
    taken_at: datetime
    quality: str  # Prognose-Qualität (annahme | unzureichend | vorlaeufig | gut | sehr_gut)
    forecast_kwh: float | None = None
    forecast_cost: float | None = None
    recommended_advance: float | None = None


@dataclass(slots=True)
class IntervalConsumption:
    """Vorbereitung dynamischer Tarif: Verbrauch je Intervall (Viertelstunde)."""

    meter_id: str
    start: datetime
    minutes: int
    energy: float | None = None
    quality: Quality = Quality.MISSING


@dataclass(slots=True)
class SensorReset:
    """Neustart eines Impulszählers (Stand fiel auf 0): ab ``at`` zählt der Sensor ab ``prev_raw`` weiter (Einheit)."""

    meter_id: str
    at: datetime
    prev_raw: float


@dataclass(slots=True)
class GeneratorDaily:
    """Tageswerte je Wärmeerzeuger (Abschnitt 2.4, Entscheidung I): Eingang, Wärme und Entlastung getrennt.
    Befüllt ab 0.8."""

    generator_id: str
    date: _Date
    energy_input: float | None = None  # eingesetzte Energie (Gas, Strom, Holz), kWh
    thermal_output: float | None = None  # gemessene Wärme (nur mit Wärmemengenzähler)
    estimated_thermal_output: float | None = None  # geschätzte Wärme (Strom × COP, Ofenstunden × Leistung × Anteil)
    avoided_energy: float | None = None  # tatsächliche Entlastung anderer Erzeuger, nur aus Daten gelernt
    measurement_quality: Quality = Quality.MISSING
    hours: float | None = None  # Betriebsstunden des Tages


@dataclass(slots=True)
class Dataset:
    """Alles, was im persistenten Store liegt."""

    readings: list[Reading] = field(default_factory=list)
    daily: list[DailyConsumption] = field(default_factory=list)
    contracts: list[Contract] = field(default_factory=list)
    periods: list[BillingPeriod] = field(default_factory=list)
    prices: list[PriceSegment] = field(default_factory=list)
    advance_plans: list[AdvancePlan] = field(default_factory=list)
    payments: list[Payment] = field(default_factory=list)
    invoices: list[Invoice] = field(default_factory=list)
    snapshots: list[ForecastSnapshot] = field(default_factory=list)
    intervals: list[IntervalConsumption] = field(default_factory=list)
    generator_daily: list[GeneratorDaily] = field(default_factory=list)
    sensor_resets: list[SensorReset] = field(default_factory=list)  # Neustarts von Impulszählern (0.9)
    sensor_last_raw: dict[str, float] = field(default_factory=dict)  # letzter Rohstand je Impulszähler (Einheit)
    # Zähler, deren Startdaten aus der Einrichtung schon übernommen wurden
    imported_meters: list[str] = field(default_factory=list)
    # Zähler, deren Tageswerte nach dem Update auf 0.6 einmal neu aus der Statistik geholt wurden (Zählerstand am Tagesende)
    reaggregated_meters: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return to_dict(self)

    @classmethod
    def from_dict(cls, data: Any) -> tuple[Dataset | None, list[str]]:
        obj, errors = from_dict(cls, data)
        if obj is not None:
            errors += check_consistency(obj)
        return (obj if not errors else None), errors


# ---------------------------------------------------------------- Umwandlung


def _enc(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: _enc(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [_enc(v) for v in value]
    if isinstance(value, dict):
        return {k: _enc(v) for k, v in value.items()}
    return value


def to_dict(obj: Any) -> dict[str, Any]:
    """Dataclass → JSON-fähiges dict."""
    return _enc(obj)


def _dec(tp: Any, value: Any, path: str, errors: list[str]) -> Any:
    origin = get_origin(tp)
    if origin in (Union, types.UnionType):
        args = [a for a in get_args(tp) if a is not type(None)]
        if value is None:
            return None
        return _dec(args[0], value, path, errors)
    if value is None:
        errors.append(f"{path}: Wert fehlt")
        return None
    if origin is list:
        if not isinstance(value, list):
            errors.append(f"{path}: Liste erwartet")
            return []
        (item,) = get_args(tp)
        return [_dec(item, v, f"{path}[{i}]", errors) for i, v in enumerate(value)]
    if origin is dict:
        if not isinstance(value, dict):
            errors.append(f"{path}: Objekt erwartet")
            return {}
        _, vt = get_args(tp)
        return {str(k): _dec(vt, v, f"{path}.{k}", errors) for k, v in value.items()}
    if tp is Any:
        return value
    if is_dataclass(tp):
        obj, sub = from_dict(tp, value, path)
        errors.extend(sub)
        return obj
    if isinstance(tp, type) and issubclass(tp, StrEnum):
        try:
            return tp(value)
        except ValueError:
            errors.append(f"{path}: unbekannter Wert {value!r}")
            return None
    if tp is datetime:
        try:
            dt = datetime.fromisoformat(value)
        except (TypeError, ValueError):
            errors.append(f"{path}: Zeitpunkt erwartet, nicht {value!r}")
            return None
        if dt.tzinfo is None:
            errors.append(f"{path}: Zeitpunkt ohne Zeitzone")
        return dt
    if tp is date:
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError):
            errors.append(f"{path}: Datum erwartet, nicht {value!r}")
            return None
    if tp is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"{path}: Zahl erwartet, nicht {value!r}")
            return None
        return float(value)
    if tp is int:
        if isinstance(value, bool) or not isinstance(value, int):
            errors.append(f"{path}: ganze Zahl erwartet, nicht {value!r}")
            return None
        return value
    if tp is bool:
        if not isinstance(value, bool):
            errors.append(f"{path}: ja/nein erwartet, nicht {value!r}")
            return None
        return value
    if tp is str:
        if not isinstance(value, str):
            errors.append(f"{path}: Text erwartet, nicht {value!r}")
            return None
        return value
    return value


_HINTS: dict[type, dict[str, Any]] = {}


def from_dict(cls: type[T], data: Any, path: str | None = None) -> tuple[T | None, list[str]]:
    """dict → Dataclass. Liefert (Objekt, Fehler). Unbekannte Felder sind ein Fehler (keine stillen Verluste)."""
    path = path or cls.__name__
    errors: list[str] = []
    if not isinstance(data, dict):
        return None, [f"{path}: Objekt erwartet"]
    hints = _HINTS.get(cls)
    if hints is None:
        hints = _HINTS[cls] = get_type_hints(cls)
    kwargs: dict[str, Any] = {}
    known = set()
    for f in fields(cls):
        known.add(f.name)
        if f.name not in data:
            if f.default is MISSING and f.default_factory is MISSING:
                errors.append(f"{path}.{f.name}: Pflichtfeld fehlt")
            continue
        kwargs[f.name] = _dec(hints[f.name], data[f.name], f"{path}.{f.name}", errors)
    for extra in set(data) - known:
        errors.append(f"{path}.{extra}: unbekanntes Feld")
    if errors:
        return None, errors
    return cls(**kwargs), []


def check_consistency(ds: Dataset) -> list[str]:
    """Querprüfungen: eindeutige IDs, Bezüge auf vorhandene Verträge und Ablesungen."""
    errors: list[str] = []

    def unique(items: list[Any], attr: str, name: str) -> set[str]:
        seen: set[str] = set()
        for it in items:
            key = getattr(it, attr)
            if key in seen:
                errors.append(f"{name}: ID {key} doppelt")
            seen.add(key)
        return seen

    readings = unique(ds.readings, "reading_id", "Ablesungen")
    contracts = unique(ds.contracts, "contract_id", "Verträge")
    periods = unique(ds.periods, "period_id", "Perioden")
    unique(ds.payments, "payment_id", "Zahlungen")
    unique(ds.invoices, "invoice_id", "Rechnungen")
    days: set[tuple[str, date]] = set()
    for d in ds.daily:
        if (d.meter_id, d.date) in days:
            errors.append(f"Tageswerte: {d.meter_id} {d.date} doppelt")
        days.add((d.meter_id, d.date))
        if d.quality in (Quality.MISSING, Quality.INVALID) and d.consumption is not None:
            errors.append(f"Tageswerte: {d.meter_id} {d.date} ist {d.quality} und hat trotzdem einen Verbrauch")
    for r in ds.readings:
        if r.quality not in READING_QUALITIES:
            errors.append(f"Ablesung {r.reading_id}: Qualität {r.quality} ist für Ablesungen nicht zulässig")
        if r.superseded_by and r.superseded_by not in readings:
            errors.append(f"Ablesung {r.reading_id}: Ersatz {r.superseded_by} fehlt")
    for c in ds.contracts:
        if c.end_date and c.end_date < c.start_date:
            errors.append(f"Vertrag {c.contract_id}: Ende vor Beginn")
    for p in ds.periods:
        if p.contract_id not in contracts:
            errors.append(f"Periode {p.period_id}: Vertrag {p.contract_id} fehlt")
        if p.end_date < p.start_date:
            errors.append(f"Periode {p.period_id}: Ende vor Beginn")
        for rid in (p.start_reading, p.end_reading):
            if rid and rid not in readings:
                errors.append(f"Periode {p.period_id}: Ablesung {rid} fehlt")
    for group, name in ((ds.prices, "Preis"), (ds.advance_plans, "Abschlagsplan"), (ds.payments, "Zahlung"), (ds.invoices, "Rechnung")):
        for it in group:
            if it.contract_id not in contracts:
                errors.append(f"{name}: Vertrag {it.contract_id} fehlt")
    gen_days: set[tuple[str, date]] = set()
    for g in ds.generator_daily:
        if (g.generator_id, g.date) in gen_days:
            errors.append(f"Erzeuger-Tageswerte: {g.generator_id} {g.date} doppelt")
        gen_days.add((g.generator_id, g.date))
    del periods  # Schnappschüsse dürfen auf die laufende, noch nicht gespeicherte Periode verweisen
    return errors
