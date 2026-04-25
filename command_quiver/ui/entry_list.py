"""Widget lista voci con azioni copia/esegui e ordinamento."""

import logging
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from command_quiver.core.clipboard import copy_to_clipboard
from command_quiver.core.executor import TerminalNotFoundError, execute_in_terminal
from command_quiver.core.i18n import t
from command_quiver.db.queries import Entry

logger = logging.getLogger(__name__)


class EntryRow(Gtk.Box):
    """Riga singola nella lista voci: nome, badge tipo, bottoni azione."""

    def __init__(
        self,
        entry: Entry,
        on_click: Callable,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.entry = entry
        self._on_click = on_click

        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(4)
        self.set_margin_bottom(4)

        # Nome voce (troncato a 40 caratteri)
        display_name = entry.name[:40] + "\u2026" if len(entry.name) > 40 else entry.name
        name_label = Gtk.Label(label=display_name, xalign=0)
        name_label.set_hexpand(True)
        name_label.add_css_class("entry-name")
        self.append(name_label)

        # Badge tipo (SHELL verde, PROMPT blu)
        badge = Gtk.Label(label=entry.type.upper())
        badge.add_css_class("entry-badge")
        badge.add_css_class(f"badge-{entry.type}")
        self.append(badge)

        # Bottone copia
        self._copy_btn = Gtk.Button(
            icon_name="edit-copy-symbolic",
            tooltip_text=t("entry_list.copy_tooltip"),
        )
        self._copy_btn.add_css_class("flat")
        self._copy_btn.connect("clicked", self._on_copy)
        self.append(self._copy_btn)

        # Bottone esegui (solo per comandi shell)
        if entry.type == "shell":
            exec_btn = Gtk.Button(
                icon_name="media-playback-start-symbolic",
                tooltip_text=t("entry_list.execute_tooltip"),
            )
            exec_btn.add_css_class("flat")
            exec_btn.connect("clicked", self._on_execute)
            self.append(exec_btn)

    def _on_copy(self, _button: Gtk.Button) -> None:
        """Copia il contenuto negli appunti con feedback visivo."""
        if copy_to_clipboard(self.entry.content):
            # Feedback visivo: cambia icona per 1.5 secondi
            self._copy_btn.set_icon_name("object-select-symbolic")
            self._copy_btn.add_css_class("copy-success")
            GLib.timeout_add(1500, self._reset_copy_icon)

    def _reset_copy_icon(self) -> bool:
        """Ripristina l'icona del bottone copia."""
        self._copy_btn.set_icon_name("edit-copy-symbolic")
        self._copy_btn.remove_css_class("copy-success")
        return GLib.SOURCE_REMOVE

    def _on_execute(self, _button: Gtk.Button) -> None:
        """Esegue il comando in gnome-terminal."""
        try:
            execute_in_terminal(self.entry.content)
        except TerminalNotFoundError as err:
            self._show_terminal_error(str(err))

    def _show_terminal_error(self, message: str) -> None:
        """Mostra un dialog di errore per gnome-terminal mancante."""
        window = self.get_root()
        if not isinstance(window, Gtk.Window):
            return

        dialog = Gtk.AlertDialog(
            message=t("entry_list.terminal_not_found"),
            detail=message,
        )
        dialog.show(window)


class EntryListWidget(Gtk.Box):
    """Widget contenente la lista scrollabile delle voci con ordinamento."""

    def __init__(self, on_entry_click: Callable) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_entry_click = on_entry_click
        self._entries: list[Entry] = []

        # Container scrollabile per la lista
        self._scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        self._scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list_box.add_css_class("entry-list")
        self._list_box.connect("row-activated", self._on_row_activated)
        self._scrolled.set_child(self._list_box)
        self.append(self._scrolled)

        # Placeholder per lista vuota
        self._list_box.set_placeholder(self._create_placeholder())

    def _create_placeholder(self) -> Gtk.Box:
        """Crea il widget placeholder per la lista vuota."""
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            valign=Gtk.Align.CENTER,
        )
        box.set_margin_top(40)
        box.set_margin_bottom(40)

        icon = Gtk.Image(icon_name="document-new-symbolic", pixel_size=48)
        icon.add_css_class("dim-label")
        box.append(icon)

        label = Gtk.Label(label=t("entry_list.empty_title"))
        label.add_css_class("dim-label")
        box.append(label)

        hint = Gtk.Label(label=t("entry_list.empty_hint"))
        hint.add_css_class("dim-label")
        hint.add_css_class("caption")
        box.append(hint)

        return box

    def update_entries(self, entries: list[Entry]) -> None:
        """Aggiorna la lista con le voci fornite."""
        self._entries = entries

        # Rimuovi tutte le righe esistenti
        while True:
            row = self._list_box.get_row_at_index(0)
            if row is None:
                break
            self._list_box.remove(row)

        # Aggiungi le nuove righe
        for entry in entries:
            row_widget = EntryRow(
                entry=entry,
                on_click=self._on_entry_click,
            )
            self._list_box.append(row_widget)

    def _on_row_activated(self, _list_box: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        """Gestisce il click su una riga -> apre l'editor."""
        child = row.get_child()
        if isinstance(child, EntryRow):
            self._on_entry_click(child.entry)
