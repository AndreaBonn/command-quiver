"""Avviso temporaneo sovrapposto in basso alla finestra (GTK4 puro, senza libadwaita)."""

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

TOAST_TIMEOUT_MS = 2500


class ToastOverlay(Gtk.Overlay):
    """Overlay che mostra un messaggio breve in basso al centro, poi lo nasconde.

    Un nuovo messaggio sostituisce quello visibile e riparte il timer.
    Con ``action_label`` l'avviso ha un pulsante (es. "Annulla").
    """

    def __init__(self, child: Gtk.Widget) -> None:
        super().__init__()
        self.set_child(child)
        self._timeout_id = 0
        self._on_action: Callable[[], None] | None = None
        # Messaggio arrivato mentre era visibile un avviso con azione: mostrato dopo
        self._queued: str | None = None

        self._label = Gtk.Label(wrap=True, xalign=0)
        self._action = Gtk.Button(visible=False, valign=Gtk.Align.CENTER)
        self._action.connect("clicked", self._on_action_clicked)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.add_css_class("toast")
        box.append(Gtk.Image(icon_name="object-select-symbolic"))
        box.append(self._label)
        box.append(self._action)

        self._revealer = Gtk.Revealer(
            transition_type=Gtk.RevealerTransitionType.SLIDE_UP,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.END,
            margin_bottom=12,
        )
        self._revealer.set_child(box)
        self.add_overlay(self._revealer)

    @property
    def message(self) -> str:
        """Testo dell'ultimo avviso (vuoto se nascosto)."""
        return self._label.get_label() if self._revealer.get_reveal_child() else ""

    def show_message(
        self,
        text: str,
        action_label: str | None = None,
        on_action: Callable[[], None] | None = None,
        timeout_ms: int = TOAST_TIMEOUT_MS,
    ) -> None:
        """Mostra il messaggio per ``timeout_ms``, con un pulsante d'azione facoltativo.

        Un avviso senza azione non copre quello con azione ancora visibile (es.
        "Annulla" di una cancellazione): resta in coda e compare quando quello si chiude.
        """
        if self._on_action is not None and not (action_label and on_action):
            self._queued = text
            return
        self._label.set_label(text)
        self._on_action = on_action
        self._action.set_label(action_label or "")
        self._action.set_visible(bool(action_label and on_action))
        # Senza pulsante l'avviso non intercetta i clic sulla lista sottostante
        self._revealer.set_can_target(self._action.get_visible())
        self._revealer.set_reveal_child(True)
        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
        self._timeout_id = GLib.timeout_add(timeout_ms, self._hide)

    def _on_action_clicked(self, _button: Gtk.Button) -> None:
        callback, self._on_action = self._on_action, None
        self.cancel()
        self._revealer.set_reveal_child(False)
        if callback:
            callback()
        self._show_queued()

    def _hide(self) -> bool:
        self._timeout_id = 0
        self._on_action = None
        self._revealer.set_reveal_child(False)
        self._show_queued()
        return GLib.SOURCE_REMOVE

    def _show_queued(self) -> None:
        queued, self._queued = self._queued, None
        if queued:
            self.show_message(queued)

    def cancel(self) -> None:
        """Annulla il timer pendente (prima di distruggere la finestra)."""
        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = 0
