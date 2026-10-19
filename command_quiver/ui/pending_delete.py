"""Eliminazione rimandata: la voce sparisce subito, si cancella davvero dopo qualche secondo.

Così "Annulla" non deve ricreare la voce: una voce ricreata avrebbe un UUID
nuovo e la sincronizzazione vedrebbe una cancellazione (tombstone) seguita da
una voce diversa.
"""

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib

UNDO_WINDOW_MS = 5000


class PendingDeletion:
    """Al massimo una cancellazione in attesa; una nuova conferma subito la precedente."""

    def __init__(self, on_commit: Callable[[int], None]) -> None:
        self._on_commit = on_commit
        self._entry_id: int | None = None
        self._timeout_id = 0

    @property
    def entry_id(self) -> int | None:
        """Voce in attesa di cancellazione (nascosta nella lista), o None."""
        return self._entry_id

    def start(self, entry_id: int) -> None:
        """Mette in attesa la cancellazione; una già in attesa diventa definitiva."""
        self.flush()
        self._entry_id = entry_id
        self._timeout_id = GLib.timeout_add(UNDO_WINDOW_MS, self._on_timeout)

    def undo(self) -> int | None:
        """Annulla la cancellazione in attesa e restituisce l'id ripristinato."""
        restored = self._entry_id
        self._clear_timer()
        self._entry_id = None
        return restored

    def flush(self) -> None:
        """Rende definitiva subito la cancellazione in attesa (chiusura, cambio lingua)."""
        self._clear_timer()
        self._commit()

    def _on_timeout(self) -> bool:
        self._timeout_id = 0
        self._commit()
        return GLib.SOURCE_REMOVE

    def _commit(self) -> None:
        entry_id, self._entry_id = self._entry_id, None
        if entry_id is not None:
            self._on_commit(entry_id)

    def _clear_timer(self) -> None:
        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = 0
