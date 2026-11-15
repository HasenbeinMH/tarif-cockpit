"""Heizlast und Überdimensionierung (1.1) aus dem gelernten Kennwert.

Der Kennwert k (kWh je Gradtag, bei Gas in kWh Brennwert Hs) beschreibt den Wärmebedarf über der Heizgrenze. Daraus:

- Heizlast (Wärme) = k · Hi/Hs · η · (Innenbezug − Normaußentemperatur) / 24 h
  (Hi/Hs ≈ 0,901 nur bei Gas; η = Wirkungsgrad des Kessels bezogen auf Hi; Fernwärme: k ist schon Wärme)
- Verhältnis = Nennleistung ÷ Heizlast: ≤ 1,2 passend, ≤ 1,8 groß, darüber überdimensioniert
- Taktgrenze = Außentemperatur, ab der der Bedarf unter der kleinsten Leistung liegt:
  Innenbezug − kleinste Leistung · 24 / (k · Hi/Hs · η); über ihr muss der Kessel takten
- Takttage = Anteil der Heiztage (unter der Heizgrenze) im letzten Jahr, die wärmer als die Taktgrenze waren

Warmwasser ist nicht Teil der Heizlast (Grundlast). Nennleistung „Belastung“ (Gaseinsatz Hi) wird mit η auf Wärme
umgerechnet. Ohne nutzbaren Kennwert gibt es keine Aussage (Regel 10).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta

from .model import GeneratorKind, HeatGenerator, PowerBasis
from .regression import HeatModel

HS_TO_HI = 0.901  # Erdgas: Heizwert / Brennwert
RATIO_FITTING, RATIO_LARGE = 1.2, 1.8
DEFAULT_EFFICIENCY = {GeneratorKind.GAS_BOILER: 0.9, GeneratorKind.DISTRICT_HEATING: 1.0}


@dataclass(slots=True)
class HeatLoad:
    heat_load_kw: float
    quality: str
    nominal_kw: float | None = None  # als Wärmeleistung
    min_kw: float | None = None  # als Wärmeleistung
    ratio: float | None = None
    rating: str | None = None  # passend | gross | ueberdimensioniert
    cycling_limit_c: float | None = None
    cycling_days_share: float | None = None
    heating_days: int = 0
    measured_peak_kw: float | None = None  # höchste mittlere Brennerleistung eines Tages (Impulszähler), als Wärme
    design_temp: float = -12.0
    flags: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        r = (lambda v, n=2: None if v is None else round(v, n))
        return {"heizlast_kw": r(self.heat_load_kw), "qualitaet": self.quality, "nennleistung_kw": r(self.nominal_kw),
                "kleinste_leistung_kw": r(self.min_kw), "verhaeltnis": r(self.ratio), "einordnung": self.rating,
                "taktgrenze_c": r(self.cycling_limit_c, 1), "takttage_anteil": r(self.cycling_days_share, 3),
                "heiztage": self.heating_days, "gemessen_max_kw": r(self.measured_peak_kw),
                "normaussentemperatur": self.design_temp, "flags": list(self.flags)}


def _to_heat(gen: HeatGenerator, kw: float | None, eta: float) -> float | None:
    if kw is None:
        return None
    return kw * eta if gen.power_basis == PowerBasis.INPUT else kw


def heat_load(
    model: HeatModel | None,
    gen: HeatGenerator,
    indoor_ref: float,
    heating_limit: float,
    design_temp: float,
    outdoor: Mapping[date, float | None],
    today: date,
    measured_power: Mapping[date, float | None] | None = None,
) -> HeatLoad | None:
    """Heizlast des Erzeugers ``gen`` aus dem Kennwert des Zählers, an dem er hängt. None ohne nutzbaren Kennwert."""
    if model is None or not model.usable or not model.heat_coefficient or model.heat_coefficient <= 0:
        return None
    eta = gen.efficiency or DEFAULT_EFFICIENCY.get(gen.kind, 0.9)
    to_heat = (HS_TO_HI * eta) if gen.kind == GeneratorKind.GAS_BOILER else (1.0 if gen.kind == GeneratorKind.DISTRICT_HEATING else eta)
    k_heat = model.heat_coefficient * to_heat  # kWh Wärme je Gradtag
    load = k_heat * (indoor_ref - design_temp) / 24
    hl = HeatLoad(heat_load_kw=load, quality=model.confidence.value, design_temp=design_temp,
                  nominal_kw=_to_heat(gen, gen.nominal_kw, eta), min_kw=_to_heat(gen, gen.min_kw, eta))
    if hl.nominal_kw:
        hl.ratio = hl.nominal_kw / load
        hl.rating = "passend" if hl.ratio <= RATIO_FITTING else ("gross" if hl.ratio <= RATIO_LARGE else "ueberdimensioniert")
    if hl.min_kw:
        hl.cycling_limit_c = indoor_ref - hl.min_kw * 24 / k_heat
        first = today - timedelta(days=365)
        temps = [t for d, t in outdoor.items() if first <= d < today and t is not None and t < heating_limit]
        hl.heating_days = len(temps)
        if temps:
            hl.cycling_days_share = sum(1 for t in temps if t > hl.cycling_limit_c) / len(temps)
        else:
            hl.flags.append("keine_heiztage")
    if measured_power:
        first = today - timedelta(days=365)
        # nur Heiztage: an warmen Tagen läuft der Brenner fürs Warmwasser mit voller Leistung (keine Heizlast)
        vals = [v for d, v in measured_power.items() if first <= d < today and v is not None
                and outdoor.get(d) is not None and outdoor[d] < heating_limit]
        if vals:
            # Brennerleistung ist Gaseinsatz (Hs) → Wärme wie der Kennwert
            hl.measured_peak_kw = max(vals) * to_heat
    return hl
