"""Widget pannello sezioni con lista, creazione, rinomina ed eliminazione."""

import logging
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from command_quiver.core.i18n import t
from command_quiver.db.queries import (
    DuplicateSectionError,
    EntryRepository,
    Section,
    SectionRepository,
)
from command_quiver.ui.section_manager import (
    SectionCreateDialog,
    SectionRenameDialog,
    show_delete_section_dialog,
)

logger = logging.getLogger(__name__)


class SectionRow(Gtk.Box):
    """Riga nella lista sezioni con attributi tipizzati."""

    def __init__(
        self,
        label: str,
        section_id: int | None,
        section: Section | None = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.add_css_class("section-row")
        self.section_id = section_id
        self.section = section

        name_label = Gtk.Label(label=label, xalign=0)
        name_label.set_hexpand(True)
        self.append(name_label)


class SectionPanelWidget(Gtk.Box):
    """Pannello sezioni: lista sezioni con selezione, menu contestuale e CRUD.

    Parameters
    ----------
    section_repo : SectionRepository
        Repository per operazioni CRUD sulle sezioni.
    entry_repo : EntryRepository
        Repository per conteggio voci totali.
    on_section_changed : Callable[[int | None], None]
        Callback invocato quando la sezione selezionata cambia.
    """

    def __init__(
        self,
        section_repo: SectionRepository,
        entry_repo: EntryRepository,
        on_section_changed: Callable[[int | None], None],
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._section_repo = section_repo
        self._entry_repo = entry_repo
        self._on_section_changed = on_section_changed
        self._current_section_id: int | None = None

        self._build_ui()

    @property
    def current_section_id(self) -> int | None:
        return self._current_section_id

    @current_section_id.setter
    def current_section_id(self, value: int | None) -> None:
        self._current_section_id = value

    def _build_ui(self) -> None:
        """Costruisce il pannello sezioni."""
        section_header = Gtk.Label(label=t("sidebar.sections_header"), xalign=0)
        section_header.add_css_class("caption")
        section_header.set_margin_start(12)
        section_header.set_margin_top(8)
        section_header.set_margin_bottom(4)
        self.append(section_header)

        # Lista sezioni scrollabile
        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._section_list = Gtk.ListBox()
        self._section_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._section_list.add_css_class("section-list")
        self._section_list.connect("row-selected", self._on_section_selected)
        scrolled.set_child(self._section_list)
        self.append(scrolled)

        # Bottone nuova sezione
        add_section_btn = Gtk.Button(label=t("sidebar.new_section"))
        add_section_btn.add_css_class("flat")
        add_section_btn.set_margin_start(8)
        add_section_btn.set_margin_end(8)
        add_section_btn.set_margin_bottom(4)
        add_section_btn.connect("clicked", self._on_new_section)
        self.append(add_section_btn)

    def refresh(self) -> None:
        """Ricarica la lista sezioni dal database."""
        sections = self._section_repo.get_all()
        total_count = self._entry_repo.count_all()

        # Pulisci lista
        while True:
            row = self._section_list.get_row_at_index(0)
            if row is None:
                break
            self._section_list.remove(row)

        # Voce "Tutti"
        all_row = self._create_row(
            label=t("sidebar.all_entries", count=total_count),
            section_id=None,
        )
        self._section_list.append(all_row)

        # Sezioni dal database
        for section in sections:
            row = self._create_row(
                label=t("sidebar.section_row", name=section.name, count=section.entry_count),
                section_id=section.id,
                section=section,
            )
            self._section_list.append(row)

        # Seleziona la sezione attiva
        self._select_current()

    def _create_row(
        self,
        label: str,
        section_id: int | None,
        section: Section | None = None,
    ) -> SectionRow:
        """Crea una riga nella lista sezioni."""
        row = SectionRow(label=label, section_id=section_id, section=section)

        # Menu contestuale (tasto destro) per rinomina/elimina
        if section is not None:
            gesture = Gtk.GestureClick(button=3)
            gesture.connect("pressed", self._on_right_click, section)
            row.add_controller(gesture)

        return row

    def _select_current(self) -> None:
        """Seleziona la riga della sezione attualmente attiva."""
        idx = 0
        i = 0
        while True:
            row = self._section_list.get_row_at_index(i)
            if row is None:
                break
            child = row.get_child()
            if isinstance(child, SectionRow) and child.section_id == self._current_section_id:
                idx = i
                break
            i += 1
        target_row = self._section_list.get_row_at_index(idx)
        if target_row:
            self._section_list.select_row(target_row)

    # --- Handler eventi ---

    def _on_section_selected(self, _list_box: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        """Aggiorna la sezione corrente e notifica il parent."""
        if row is None:
            return
        child = row.get_child()
        if isinstance(child, SectionRow):
            self._current_section_id = child.section_id
            self._on_section_changed(self._current_section_id)

    def _on_new_section(self, _button: Gtk.Button) -> None:
        """Apre il dialog per creare una nuova sezione."""
        parent = self.get_root()
        dialog = SectionCreateDialog(
            parent=parent,
            on_create=self._on_section_created,
        )
        dialog.present()

    def _on_section_created(self, name: str) -> str | None:
        """Callback creazione sezione. Restituisce messaggio errore o None."""
        try:
            self._section_repo.create(name)
        except DuplicateSectionError:
            return t("section.error_name_duplicate", name=name)
        self.refresh()
        return None

    def _on_right_click(
        self,
        gesture: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
        section: Section,
    ) -> None:
        """Mostra il menu contestuale per una sezione (rinomina/elimina)."""
        popup = Gtk.Popover()
        popup_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        popup_box.set_margin_top(4)
        popup_box.set_margin_bottom(4)
        popup_box.set_margin_start(4)
        popup_box.set_margin_end(4)

        rename_btn = Gtk.Button(label=t("sidebar.rename"))
        rename_btn.add_css_class("flat")
        rename_btn.connect("clicked", lambda _: self._do_rename(section, popup))
        popup_box.append(rename_btn)

        delete_btn = Gtk.Button(label=t("sidebar.delete"))
        delete_btn.add_css_class("flat")
        delete_btn.connect("clicked", lambda _: self._do_delete(section, popup))
        popup_box.append(delete_btn)

        popup.set_child(popup_box)
        widget = gesture.get_widget()
        popup.set_parent(widget)
        popup.popup()

    def _do_rename(self, section: Section, popup: Gtk.Popover) -> None:
        """Apre il dialog di rinomina sezione."""
        popup.popdown()
        parent = self.get_root()
        dialog = SectionRenameDialog(
            parent=parent,
            section=section,
            on_rename=self._on_section_renamed,
        )
        dialog.present()

    def _do_delete(self, section: Section, popup: Gtk.Popover) -> None:
        """Avvia la procedura di eliminazione sezione."""
        popup.popdown()
        parent = self.get_root()
        show_delete_section_dialog(
            parent=parent,
            section=section,
            on_confirm=self._on_section_deleted,
        )

    def _on_section_renamed(self, section_id: int, new_name: str) -> str | None:
        """Callback rinomina sezione. Restituisce messaggio errore o None."""
        try:
            self._section_repo.rename(section_id, new_name)
        except DuplicateSectionError:
            return t("section.error_name_duplicate", name=new_name)
        self.refresh()
        return None

    def _on_section_deleted(self, section_id: int) -> None:
        """Callback eliminazione sezione."""
        if self._current_section_id == section_id:
            self._current_section_id = None
        self._section_repo.delete(section_id)
        self.refresh()
        # Notifica il parent per aggiornare anche la lista voci
        self._on_section_changed(self._current_section_id)
