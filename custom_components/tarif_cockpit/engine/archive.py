"""Archiv beendeter Abrechnungsperioden und Prognose gegen Realität (Arbeitspaket 2.3, 3.4, Entscheidung L, Regel 4).

- Beim Periodenwechsel wird das letzte Ergebnis der beendeten Periode **vorläufig** archiviert.
- **Endgültig** (status closed), sobald eine echte Ablesung am Periodenende oder bis 10 Tage danach oder eine Rechnung für die
  Periode erfasst ist, frühestens aber nach Ablauf des ±10-Tage-Fensters für ``set_periodenende`` (11 Tage nach dem Ende),
  spätestens 60 Tage nach dem Ende. Danach ändert sich das Archiv nie mehr.
- Prognose gegen Realität: jeder Prognose-Schnappschuss der Periode gegen die tatsächlichen Kosten und den Saldo.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta, tzinfo

from .balance import MeterResult
from .model import ForecastSnapshot, Invoice, PriceSegment, Reading, to_dict
from .quality import Quality

READING_WINDOW_DAYS = 10
FINAL_AFTER_DAYS = 60


def build_archive(res: MeterResult, snapshots: Iterable[ForecastSnapshot], prices: Iterable[PriceSegment], final: bool,
                  now: datetime, reason: str, values_until: date | None = None) -> dict:
    """Eingefrorene Ergebnisse einer beendeten Periode (nur Zahlen und Texte, JSON-fähig)."""
    bal, pay, act = res.balance, res.payments, res.actual
    spec = res.period
    pid = spec.period_id if spec else None
    contract_id = res.contract.contract_id if res.contract else None
    snaps = sorted((s for s in snapshots if s.period_id == pid), key=lambda s: s.taken_at)
    archive = {
        "stand": "abgeschlossen" if final else "vorlaeufig",
        "grund": reason,
        "erstellt": now.isoformat(),
        "beginn": spec.start_date.isoformat() if spec else None,
        "ende": spec.end_date.isoformat() if spec else None,
        "menge": res.used_billing,
        "kosten": None if act is None else {"gesamt": round(act.gross, 2), "arbeit": round(act.energy, 2), "grund": round(act.base, 2),
                                            "fest": round(act.fixed, 2), "leistung": round(act.demand, 2), "abwasser": round(act.wastewater, 2),
                                            "vollstaendig": act.complete},
        "zahlungen": None if pay is None else {"summe": pay.period_total, "bezahlt": pay.paid_to_date,
                                               "abschlaege": [{"datum": i.date.isoformat(), "betrag": i.amount, "status": i.status} for i in pay.installments],
                                               "sonstige": [{"datum": d.isoformat(), "betrag": a} for d, a in pay.others]},
        "saldo": None if bal is None else bal.saldo,
        "urteil": None if bal is None else bal.verdict,
        "preise": [to_dict(p) for p in prices if p.contract_id == contract_id],
        "prognosen": [to_dict(s) for s in snaps],
    }
    if values_until is not None:
        archive["tageswerte_bis"] = values_until.isoformat()  # Endstand fehlt: Kosten nur bis zu diesem Tag
    archive["prognose_gegen_realitaet"] = forecast_vs_actual(archive)
    return archive


def forecast_vs_actual(archive: dict) -> list[dict]:
    """Je Schnappschuss: Datum, Prognose Kosten/Saldo und Abweichung zur Realität (€ und %)."""
    actual = (archive.get("kosten") or {}).get("gesamt")
    # mit unvollständigen Ist-Kosten (fehlende Tageswerte, fehlender Preis) wäre die Abweichung irreführend
    complete = (archive.get("kosten") or {}).get("vollstaendig", False) and not archive.get("tageswerte_bis")
    out = []
    for s in archive.get("prognosen", []):
        fc = s.get("forecast_cost")
        row = {"datum": s.get("taken_at", "")[:10], "prognose_kosten": fc, "prognose_saldo": s.get("saldo"), "qualitaet": s.get("quality")}
        if fc is not None and actual is not None and complete:
            row["abweichung"] = round(fc - actual, 2)
            row["abweichung_pct"] = round((fc / actual - 1) * 100, 1) if actual else None
        out.append(row)
    return out


def close_criteria(period_end: date, readings: Iterable[Reading], invoices: Iterable[Invoice], contract_id: str,
                   today: date, tz: tzinfo) -> tuple[bool, str, Reading | None]:
    """Ist die Periode endgültig abgeschlossen? (ja/nein, Grund, Endablesung).

    Eine Ablesung zählt nur am Periodenende oder bis 10 Tage danach (eine frühere fehlt der Verbrauch bis zum Ende).
    Solange das Ende noch mit ``set_periodenende`` verschoben werden darf (bis 10 Tage nach dem Ende), bleibt das Archiv
    vorläufig und wird täglich neu gerechnet."""
    best: Reading | None = None
    for r in readings:
        if r.quality != Quality.REAL or r.superseded_by:
            continue
        diff = (r.timestamp.astimezone(tz).date() - period_end).days
        if 0 <= diff <= READING_WINDOW_DAYS + 1 and (best is None or diff < (best.timestamp.astimezone(tz).date() - period_end).days):
            best = r
    invoice = any(i.contract_id == contract_id and i.period_from <= period_end <= i.period_to + timedelta(days=READING_WINDOW_DAYS)
                  for i in invoices)
    waiting = (today - period_end).days <= READING_WINDOW_DAYS
    if (today - period_end).days >= FINAL_AFTER_DAYS:
        return True, "endablesung" if best else "rechnung" if invoice else "frist_60_tage", best
    if best is not None:
        return not waiting, "endablesung", best
    if invoice:
        return not waiting, "rechnung", None
    return False, "wartet_auf_endablesung", None
