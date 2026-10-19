"""Riga di ricerca con l'ordinamento accanto (non più in fondo alla lista)."""

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from command_quiver.core.i18n import t

SORT_VALUES = (
    "chronological_desc",
    "chronological_asc",
    "alpha_asc",
    "alpha_desc",
    "personal",
    "usage",
)
_SEARCH_DEBOUNCE_MS = 250
_SORT_LABEL_KEYS = (
    "sidebar.sort_recent_desc",
    "sidebar.sort_oldest_asc",
    "sidebar.sort_alpha_asc",
    "sidebar.sort_alpha_desc",
    "sidebar.sort_personal",
    "sidebar.sort_usage",
)


class SearchBar(Gtk.Box):
    """Campo di ricerca + menu di ordinamento.

    ``on_search`` riceve il testo con debounce, per non interrogare il DB a ogni tasto.
    """

    def __init__(self, sort_order: str, on_search: Callable[[str], None]) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._on_search = on_search
        self._debounce_id = 0
        self.add_css_class("search-row")
        self.entry = Gtk.SearchEntry(placeholder_text=t("sidebar.search_placeholder"), hexpand=True)
        # Esc dentro il campo lo svuota
        self.entry.connect("stop-search", lambda entry: entry.set_text(""))
        # "changed" e non "search-changed": quest'ultimo ha un suo ritardo interno, che
        # sommato al debounce lo riarmava anche dopo cancel(). Il debounce resta uno solo.
        self.entry.connect("changed", self._on_changed)
        self.append(self.entry)

        self.sort_dropdown = Gtk.DropDown(tooltip_text=t("sidebar.sort_tooltip"))
        self.sort_dropdown.set_model(Gtk.StringList.new([t(key) for key in _SORT_LABEL_KEYS]))
        self.sort_dropdown.set_selected(SORT_VALUES.index(sort_order))
        self.append(self.sort_dropdown)

    @property
    def sort_order(self) -> str:
        """Valore di ordinamento selezionato (come salvato nelle impostazioni)."""
        return SORT_VALUES[self.sort_dropdown.get_selected()]

    def cancel(self) -> None:
        """Annulla la ricerca in attesa (prima di distruggere la finestra)."""
        if self._debounce_id:
            GLib.source_remove(self._debounce_id)
            self._debounce_id = 0

    def _on_changed(self, _entry: Gtk.Editable) -> None:
        self.cancel()
        self._debounce_id = GLib.timeout_add(_SEARCH_DEBOUNCE_MS, self._fire)

    def _fire(self) -> bool:
        self._debounce_id = 0
        self._on_search(self.entry.get_text().strip())
        return GLib.SOURCE_REMOVE
