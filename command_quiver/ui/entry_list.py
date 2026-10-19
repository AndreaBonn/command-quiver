"""Widget lista voci con azioni copia/esegui, anteprima e tag."""

import logging
from collections.abc import Callable
from dataclasses import dataclass

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk, Pango

from command_quiver.core.clipboard import copy_to_clipboard
from command_quiver.core.executor import TerminalNotFoundError, execute_in_terminal
from command_quiver.core.i18n import t
from command_quiver.core.presentation import content_preview, split_tags
from command_quiver.db.models import Entry
from command_quiver.ui.row_dnd import build_drag_handle, install_drop_target

logger = logging.getLogger(__name__)

_COPY_FEEDBACK_MS = 1500
_MOVE_KEYS = {Gdk.KEY_Up: -1, Gdk.KEY_Down: 1}
_TOOLTIP_PREVIEW_LENGTH = 200


@dataclass
class RowCallbacks:
    """Azioni che una riga delega al contenitore. Tutte facoltative tranne on_edit."""

    on_edit: Callable[[Entry], None]
    on_move: Callable[[int, int], None] | None = None
    on_use: Callable[[int], None] | None = None
    on_copied: Callable[[Entry], None] | None = None
    # Se presente, decide lui se e come eseguire (es. con conferma); altrimenti esegue subito
    on_run: Callable[[Entry], None] | None = None
    on_tag: Callable[[str], None] | None = None
    # Trascinamento nell'ordine Personale: (voce trascinata, voce di destinazione)
    on_reorder: Callable[[int, int], None] | None = None


def _flat_button(icon_name: str, tooltip: str) -> Gtk.Button:
    button = Gtk.Button(icon_name=icon_name, tooltip_text=tooltip, valign=Gtk.Align.CENTER)
    button.add_css_class("flat")
    button.add_css_class("entry-action")
    return button


class EntryRow(Gtk.Box):
    """Riga singola: nome, anteprima, tag, badge tipo e bottoni azione."""

    def __init__(
        self,
        entry: Entry,
        callbacks: RowCallbacks,
        show_move: bool = False,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.entry = entry
        self._callbacks = callbacks
        self.add_css_class("entry-row")
        self.set_tooltip_text(self._tooltip_text())

        self.drag_handle: Gtk.Image | None = None
        if show_move and self._callbacks.on_reorder:
            self.drag_handle = build_drag_handle(self, entry.id)
            self.append(self.drag_handle)
            install_drop_target(self, entry.id, self._callbacks.on_reorder)
        self.append(self._build_text_column())
        self.append(self._build_badge())
        self._append_actions()

    def _tooltip_text(self) -> str:
        preview = content_preview(self.entry.content, max_length=_TOOLTIP_PREVIEW_LENGTH)
        return f"{self.entry.name}\n{preview}\n\n{t('entry_list.row_tooltip')}"

    def _build_text_column(self) -> Gtk.Box:
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
        column.set_valign(Gtk.Align.CENTER)
        # Troncato sulla larghezza reale, non a un numero fisso di caratteri
        name_label = Gtk.Label(label=self.entry.name, xalign=0, ellipsize=Pango.EllipsizeMode.END)
        name_label.add_css_class("entry-name")
        column.append(name_label)

        preview = Gtk.Label(
            label=content_preview(self.entry.content),
            xalign=0,
            ellipsize=Pango.EllipsizeMode.END,
        )
        preview.add_css_class("entry-preview")
        column.append(preview)

        tags = split_tags(self.entry.tags)
        if tags:
            column.append(self._build_tags(tags))
        return column

    def _build_tags(self, tags: list[str]) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        for tag in tags:
            chip = Gtk.Button(label=tag, tooltip_text=t("entry_list.tag_tooltip", tag=tag))
            chip.add_css_class("entry-tag")
            chip.connect("clicked", self._on_tag_clicked, tag)
            box.append(chip)
        return box

    def _build_badge(self) -> Gtk.Label:
        kind = "shell" if self.entry.type == "shell" else "prompt"
        badge = Gtk.Label(label=t(f"badge.{kind}"), valign=Gtk.Align.CENTER)
        badge.add_css_class("entry-badge")
        badge.add_css_class(f"badge-{kind}")
        return badge

    def _append_actions(self) -> None:
        edit_btn = _flat_button("document-edit-symbolic", t("entry_list.edit_tooltip"))
        edit_btn.connect("clicked", self._on_edit_clicked)
        self.append(edit_btn)

        self._copy_btn = _flat_button("edit-copy-symbolic", t("entry_list.copy_tooltip"))
        self._copy_btn.connect("clicked", self._on_copy)
        self.append(self._copy_btn)

        if self.entry.type == "shell":
            exec_btn = _flat_button(
                "media-playback-start-symbolic", t("entry_list.execute_tooltip")
            )
            exec_btn.connect("clicked", self._on_execute)
            self.append(exec_btn)

    def _on_tag_clicked(self, _button: Gtk.Button, tag: str) -> None:
        if self._callbacks.on_tag:
            self._callbacks.on_tag(tag)

    def _on_edit_clicked(self, _button: Gtk.Button | None) -> None:
        """Apre l'editor per questa voce."""
        self._callbacks.on_edit(self.entry)

    def _on_copy(self, _button: Gtk.Button | None) -> None:
        """Copia il contenuto negli appunti con feedback visivo."""
        if not copy_to_clipboard(self.entry.content):
            return
        if self._callbacks.on_use:
            self._callbacks.on_use(self.entry.id)
        if self._callbacks.on_copied:
            self._callbacks.on_copied(self.entry)
        self._copy_btn.set_icon_name("object-select-symbolic")
        self._copy_btn.add_css_class("copy-success")
        GLib.timeout_add(_COPY_FEEDBACK_MS, self._reset_copy_icon)

    def _reset_copy_icon(self) -> bool:
        """Ripristina l'icona del bottone copia."""
        self._copy_btn.set_icon_name("edit-copy-symbolic")
        self._copy_btn.remove_css_class("copy-success")
        return GLib.SOURCE_REMOVE

    def _on_execute(self, _button: Gtk.Button | None) -> None:
        """Esegue il comando, passando prima dalla conferma se il contenitore la gestisce."""
        if self._callbacks.on_run:
            self._callbacks.on_run(self.entry)
            return
        run_entry(self.entry, on_use=self._callbacks.on_use, parent=self.get_root())

    def _show_terminal_error(self, message: str) -> None:
        """Mostra un dialog di errore per gnome-terminal mancante."""
        show_terminal_error(parent=self.get_root(), message=message)


def run_entry(
    entry: Entry,
    on_use: Callable[[int], None] | None,
    parent: Gtk.Root | None,
) -> None:
    """Lancia il comando nel terminale e registra l'uso; mostra l'errore se manca il terminale."""
    try:
        execute_in_terminal(entry.content)
        if on_use:
            on_use(entry.id)
    except TerminalNotFoundError as err:
        show_terminal_error(parent=parent, message=str(err))


def show_terminal_error(parent: Gtk.Root | None, message: str) -> None:
    """Dialog di errore per gnome-terminal mancante (no-op senza finestra)."""
    if not isinstance(parent, Gtk.Window):
        return
    dialog = Gtk.AlertDialog(message=t("entry_list.terminal_not_found"), detail=message)
    dialog.show(parent)


class EntryListWidget(Gtk.Box):
    """Lista scrollabile delle voci con stato vuoto fornito dal contenitore."""

    def __init__(self, callbacks: RowCallbacks) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._callbacks = callbacks
        self._entries: list[Entry] = []
        self._empty_state: Gtk.Widget | None = None
        self._show_move = False

        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list_box.add_css_class("entry-list")
        self._list_box.connect("row-activated", self._on_row_activated)
        # Alt+↑/↓ sposta la riga selezionata nell'ordine Personale (alternativa alla maniglia)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key_pressed)
        self._list_box.add_controller(keys)
        scrolled.set_child(self._list_box)
        self.append(scrolled)

    @property
    def entries(self) -> list[Entry]:
        """Restituisce le voci attualmente visualizzate (sola lettura)."""
        return self._entries

    @property
    def empty_state(self) -> Gtk.Widget | None:
        """Stato vuoto mostrato ora (GtkListBox non espone il placeholder)."""
        return self._empty_state

    def update_entries(
        self,
        entries: list[Entry],
        show_move: bool = False,
        empty_state: Gtk.Widget | None = None,
    ) -> None:
        """Sostituisce le righe; ``empty_state`` è mostrato quando la lista è vuota."""
        self._entries = entries
        self._empty_state = empty_state
        self._list_box.remove_all()
        self._list_box.set_placeholder(empty_state)

        self._show_move = show_move
        for entry in entries:
            self._list_box.append(
                EntryRow(entry=entry, callbacks=self._callbacks, show_move=show_move)
            )

    def _on_key_pressed(
        self, _controller: Gtk.EventControllerKey | None, keyval: int, _keycode: int, state
    ) -> bool:
        direction = _MOVE_KEYS.get(keyval)
        if direction is None or not state & Gdk.ModifierType.ALT_MASK:
            return False
        row = self._list_box.get_focus_child()
        child = row.get_child() if isinstance(row, Gtk.ListBoxRow) else None
        if not self._show_move or self._callbacks.on_move is None:
            return False
        if not isinstance(child, EntryRow):
            return False
        moved_id = child.entry.id
        self._callbacks.on_move(moved_id, direction)
        self._focus_entry(moved_id)
        return True

    def _focus_entry(self, entry_id: int) -> None:
        """Dopo il riordino la lista è ricostruita: il focus torna sulla voce spostata."""
        index = 0
        while (row := self._list_box.get_row_at_index(index)) is not None:
            if row.get_child().entry.id == entry_id:
                row.grab_focus()
                return
            index += 1

    def copy_first(self) -> bool:
        """Copia la prima voce visibile (Invio nella ricerca). False se la lista è vuota."""
        row = self._list_box.get_row_at_index(0)
        if row is None:
            return False
        child = row.get_child()
        if isinstance(child, EntryRow):
            child._on_copy(None)
            return True
        return False

    def _on_row_activated(self, _list_box: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        """Gestisce il click su una riga -> copia il contenuto."""
        child = row.get_child()
        if isinstance(child, EntryRow):
            child._on_copy(None)
