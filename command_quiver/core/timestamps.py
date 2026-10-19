"""Timestamp confrontabili fra formati storici diversi e fra dispositivi in fusi diversi.

Nel database convivono tre formati: ``CURRENT_TIMESTAMP`` di SQLite (UTC, con
spazio), ``datetime.now().isoformat()`` delle versioni precedenti (ora locale,
con "T", senza offset) e l'ISO UTC con offset scritto da ``utc_now_iso``.
Confrontarli come stringhe sbaglia l'ordine: il last-write-wins del sync passa
quindi sempre da ``parse_timestamp``.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Più vecchio di qualsiasi data reale: un timestamp mancante perde ogni confronto
_OLDEST = datetime.min.replace(tzinfo=timezone.utc)


def parse_timestamp(value: str | None) -> datetime:
    """Converte un timestamp salvato in un istante UTC confrontabile.

    Parameters
    ----------
    value : str | None
        Timestamp in uno dei formati storici. Senza offset, il separatore
        decide il fuso: spazio = UTC (SQLite), "T" = ora locale (Python).

    Returns
    -------
    datetime
        Istante con fuso UTC; per valori assenti o non validi un istante
        più vecchio di qualsiasi data reale.
    """
    if not value:
        return _OLDEST
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        # Un valore corrotto perde ogni confronto last-write-wins: va lasciata traccia
        logger.warning("Timestamp non leggibile, trattato come il più vecchio: %r", value)
        return _OLDEST
    if moment.tzinfo is not None:
        return moment.astimezone(timezone.utc)
    if "T" in value:
        # astimezone() su un datetime naive lo interpreta come ora locale
        return moment.astimezone(timezone.utc)
    return moment.replace(tzinfo=timezone.utc)


def utc_now_iso() -> str:
    """Istante corrente in ISO 8601 UTC con offset: il formato unico delle nuove scritture."""
    return datetime.now(timezone.utc).isoformat()
