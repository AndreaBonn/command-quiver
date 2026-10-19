"""Riga di stato in fondo alla finestra: dove sono salvate le voci e com'è andata la sync."""

from collections.abc import Callable
from datetime import datetime

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Pango

from command_quiver.core.settings import Settings
from command_quiver.core.sync_engine import SyncResult
from command_quiver.core.sync_status import SyncState, SyncStatusView, describe_sync_status


class SyncStatusBar(Gtk.Box):
    """Pallino colorato + testo + link d'azione (apre la finestra di sincronizzazione).

    Tiene lo stato della sessione (sync in corso, ultimo esito) e lo mostra
    solo in base a esiti reali: mai "sincronizzato" prima di una sync riuscita.
    """

    def __init__(self, settings: Settings, on_open_sync: Callable[[], None]) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._settings = settings
        self._pending = False
        self._outcome: SyncResult | None = None
        self.add_css_class("status-bar")
        self._dot = Gtk.Box(valign=Gtk.Align.CENTER)
        self._dot.add_css_class("status-dot")
        self._label = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        self._label.add_css_class("dim-label")
        self._action = Gtk.Button(visible=False)
        self._action.add_css_class("flat")
        self._action.add_css_class("link")
        self._action.connect("clicked", lambda _: on_open_sync())
        self.append(self._dot)
        self.append(self._label)
        self.append(self._action)
        self.refresh()

    @property
    def text(self) -> str:
        """Testo mostrato (per test e accessibilità)."""
        return self._label.get_label()

    def set_pending(self) -> None:
        """Una sincronizzazione è partita."""
        self._pending = True
        self.refresh()

    def set_result(self, result: SyncResult) -> None:
        """Esito reale di una sincronizzazione; il messaggio d'errore va nel tooltip."""
        self._pending = False
        self._outcome = result
        self.set_tooltip_text(None if result.success else result.message)
        self.refresh()

    def reset(self) -> None:
        """Configurazione cambiata: l'esito precedente non vale più."""
        self._outcome = None
        self.set_tooltip_text(None)
        self.refresh()

    def refresh(self) -> None:
        """Ricalcola testo e colore (anche il tempo relativo dell'ultima sync)."""
        self._show_view(
            describe_sync_status(
                sync=self._settings.sync,
                pending=self._pending,
                outcome=self._outcome,
                now=datetime.now(),
            )
        )

    def _show_view(self, view: SyncStatusView) -> None:
        self._label.set_label(view.text)
        self._action.set_label(view.action)
        self._action.set_visible(bool(view.action))
        for state in SyncState:
            self._dot.remove_css_class(state.value)
        self._dot.add_css_class(view.state.value)
