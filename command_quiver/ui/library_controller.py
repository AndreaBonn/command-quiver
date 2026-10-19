"""Operazioni sulle voci avviate dalla finestra principale: salva, elimina, riordina, file."""

from collections.abc import Callable
from dataclasses import dataclass

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from command_quiver.core.i18n import t
from command_quiver.core.ordering import reorder_positions
from command_quiver.core.presentation import collect_tags
from command_quiver.db.entry_repository import EntryRepository
from command_quiver.db.models import Entry, EntryCreate, EntryUpdate
from command_quiver.db.section_repository import SectionRepository
from command_quiver.ui import library_actions
from command_quiver.ui.entry_editor import EntryEditorDialog
from command_quiver.ui.pending_delete import UNDO_WINDOW_MS, PendingDeletion
from command_quiver.ui.toast import ToastOverlay


@dataclass
class LibraryView:
    """Ciò che il controller chiede alla finestra: ricaricare, avvisare, conoscere le righe."""

    window: Gtk.Window
    toast: ToastOverlay
    refresh_all: Callable[[], None]
    refresh_entries: Callable[[], None]
    visible_entries: Callable[[], list[Entry]]
    notify_changed: Callable[[], None]


class LibraryController:
    """Modifica la libreria e tiene in attesa l'eventuale cancellazione annullabile (E7)."""

    def __init__(
        self, entry_repo: EntryRepository, section_repo: SectionRepository, view: LibraryView
    ) -> None:
        self._entries = entry_repo
        self._sections = section_repo
        self._view = view
        self.pending_delete = PendingDeletion(on_commit=self.commit_delete)
        self.pending_entry: Entry | None = None

    def open_editor(self, entry: Entry | None, initial_section_id: int | None) -> None:
        """Editor di una voce (o nuova), con i tag già usati come suggerimenti."""
        all_entries = self._entries.get_all(section_id=None, search="", sort_order="alpha_asc")
        EntryEditorDialog(
            parent=self._view.window,
            sections=self._sections.get_all(),
            entry=entry,
            on_save=self.save,
            on_delete=self.delete if entry else None,
            initial_section_id=initial_section_id,
            known_tags=collect_tags([e.tags for e in all_entries]),
        ).present()

    def save(self, data: EntryCreate | EntryUpdate) -> None:
        if isinstance(data, EntryUpdate):
            self._entries.update(data)
        else:
            self._entries.create(data)
        self._view.refresh_all()
        self._view.notify_changed()

    def delete(self, entry_id: int) -> None:
        """Nasconde subito la voce; la cancella davvero solo se non si preme "Annulla"."""
        entry = self._entries.get_by_id(entry_id)
        if entry is None:
            return
        self.pending_delete.start(entry_id)
        self.pending_entry = entry
        self._view.refresh_all()
        self._view.toast.show_message(
            t("toast.deleted", name=entry.name),
            action_label=t("toast.undo"),
            on_action=self.undo_delete,
            timeout_ms=UNDO_WINDOW_MS,
        )

    def undo_delete(self) -> None:
        self.pending_delete.undo()
        self.pending_entry = None
        self._view.refresh_all()

    def commit_delete(self, entry_id: int) -> None:
        self._entries.delete(entry_id)
        if self.pending_entry is not None and self.pending_entry.id == entry_id:
            self.pending_entry = None
        self._view.refresh_all()
        self._view.notify_changed()

    def reorder(self, moved_id: int, target_id: int) -> None:
        """Trascinamento: la voce prende il posto di quella su cui è rilasciata."""
        rows = [(e.id, e.personal_pos) for e in self._view.visible_entries()]
        changes = reorder_positions(rows, moved_id=moved_id, target_id=target_id)
        for entry_id, position in changes.items():
            self._entries.update_position(entry_id=entry_id, new_position=position)
        if changes:
            self._view.refresh_entries()

    def move(self, entry_id: int, direction: int) -> None:
        """Sposta una voce su (-1) o giù (+1) nell'ordinamento personale (Alt+↑/↓)."""
        entries = self._view.visible_entries()
        idx = next((i for i, e in enumerate(entries) if e.id == entry_id), None)
        if idx is None or not 0 <= idx + direction < len(entries):
            return
        # Stesso calcolo del trascinamento: gestisce anche le posizioni duplicate
        # della vista "Tutti" (ogni sezione numera le proprie voci da 0)
        self.reorder(entry_id, entries[idx + direction].id)

    def add_samples(self) -> None:
        count = library_actions.add_sample_entries(self._entries, self._sections)
        self._view.refresh_all()
        self._view.toast.show_message(t("toast.samples_added", count=count))
        self._view.notify_changed()

    def import_file(self) -> None:
        def on_done(message: str, changed: bool) -> None:
            self._view.toast.show_message(message)
            if changed:
                self._view.refresh_all()
                self._view.notify_changed()

        library_actions.import_library(self._view.window, self._entries, self._sections, on_done)

    def export_file(self) -> None:
        library_actions.export_library(
            self._view.window, self._entries, self._view.toast.show_message
        )
