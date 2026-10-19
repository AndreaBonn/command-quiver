"""Testo dello stato di sincronizzazione mostrato in fondo alla finestra."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from command_quiver.core.i18n import t
from command_quiver.core.presentation import format_relative_time

if TYPE_CHECKING:
    # Solo per i tipi: a runtime il modulo resta puro, senza rete né DB
    from command_quiver.core.settings import SyncSettings
    from command_quiver.core.sync_engine import SyncResult


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
    sync: SyncSettings,
    *,
    pending: bool,
    outcome: SyncResult | None,
    now: datetime,
) -> SyncStatusView:
    """Descrive lo stato di sincronizzazione in parole.

    Parameters
    ----------
    sync : SyncSettings
        Configurazione: se la sync è attiva e quando è riuscita l'ultima volta
        (anche in sessioni precedenti).
    pending : bool
        Una sincronizzazione è in corso.
    outcome : SyncResult | None
        Ultimo esito di questa sessione; None se non ancora.
    now : datetime
        Istante corrente, per il tempo relativo.
    """
    if not sync.enabled:
        return SyncStatusView(SyncState.LOCAL, t("status.local"), t("status.local_action"))
    if pending:
        return SyncStatusView(SyncState.PENDING, t("status.pending"), "")
    if outcome is not None and not outcome.success:
        return SyncStatusView(SyncState.ERROR, t("status.error"), t("status.details"))
    when = format_relative_time(iso=sync.last_sync, now=now)
    if not when:
        return SyncStatusView(SyncState.PENDING, t("sync.never"), "")
    if outcome is not None and (outcome.entries_pulled or outcome.entries_pushed):
        text = t(
            "status.ok_counts",
            when=when,
            pulled=outcome.entries_pulled,
            pushed=outcome.entries_pushed,
        )
        return SyncStatusView(SyncState.OK, text, "")
    return SyncStatusView(SyncState.OK, t("status.ok", when=when), "")
