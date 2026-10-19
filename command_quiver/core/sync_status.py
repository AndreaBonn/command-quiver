"""Testo dello stato di sincronizzazione mostrato in fondo alla finestra."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from command_quiver.core.i18n import t
from command_quiver.core.presentation import format_relative_time


class SyncState(Enum):
    """Stato mostrato: deciso solo da esiti reali, mai prima che una sync sia avvenuta."""

    LOCAL = "local"
    PENDING = "pending"
    OK = "ok"
    ERROR = "error"


@dataclass
class SyncStatusView:
    """Cosa mostrare: stato, testo e etichetta del link d'azione."""

    state: SyncState
    text: str
    action: str


def describe_sync_status(
    enabled: bool,
    pending: bool,
    outcome: tuple[bool, int, int] | None,
    last_sync: str,
    now: datetime,
) -> SyncStatusView:
    """Descrive lo stato di sincronizzazione in parole.

    Parameters
    ----------
    enabled : bool
        Sincronizzazione configurata e attiva.
    pending : bool
        Una sincronizzazione è in corso.
    outcome : tuple[bool, int, int] | None
        Ultimo esito di questa sessione: (successo, ricevute, inviate); None se non ancora.
    last_sync : str
        Timestamp ISO dell'ultima sincronizzazione riuscita (anche di sessioni precedenti).
    now : datetime
        Istante corrente, per il tempo relativo.
    """
    if not enabled:
        return SyncStatusView(SyncState.LOCAL, t("status.local"), t("status.local_action"))
    if pending:
        return SyncStatusView(SyncState.PENDING, t("status.pending"), "")
    if outcome is not None and not outcome[0]:
        return SyncStatusView(SyncState.ERROR, t("status.error"), t("status.details"))
    when = format_relative_time(iso=last_sync, now=now)
    if not when:
        return SyncStatusView(SyncState.PENDING, t("sync.never"), "")
    if outcome is not None and (outcome[1] or outcome[2]):
        text = t("status.ok_counts", when=when, pulled=outcome[1], pushed=outcome[2])
        return SyncStatusView(SyncState.OK, text, "")
    return SyncStatusView(SyncState.OK, t("status.ok", when=when), "")
