"""Widget pannello sezioni con lista, creazione, rinomina ed eliminazione."""

import logging
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from command_quiver.core.i18n import t
from command_quiver.db.queries import (
    DuplicateSectionError,
    Entry,
    EntryRepository,
    Section,
    SectionRepository,
)
from command_quiver.ui.section_manager import (
    SectionCreateDialog,
    SectionRenameDialog,
    show_delete_section_dialog,
)
from command_quiver.ui.section_row import (
    ALL_ENTRIES_ICON,
    FALLBACK_ICON,
    SectionRow,
    resolve_section_icon,
    theme_has_icon,
)

logger = logging.getLogger(__name__)


class SectionPanelWidget(Gtk.Box):
    """Pannello sezioni: lista sezioni con selezione, menu azioni e CRUD.

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
        hidden_entry: Callable[[], Entry | None] = lambda: None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._section_repo = section_repo
        self._entry_repo = entry_repo
        self._on_section_changed = on_section_changed
        self._hidden_entry = hidden_entry
        self._current_section_id: int | None = None
        self._sections: list[Section] = []

        self._build_ui()

    @property
    def current_section_id(self) -> int | None:
        return self._current_section_id

    @current_section_id.setter
    def current_section_id(self, value: int | None) -> None:
        self._current_section_id = value

    @property
    def current_section_name(self) -> str | None:
        """Nome della sezione selezionata, None per "Tutti"."""
        section = next((s for s in self._sections if s.id == self._current_section_id), None)
        return section.name if section else None

    def select_section(self, section_id: int | None) -> None:
        """Seleziona una sezione dal codice (es. "Cerca in tutte le sezioni")."""
        self._current_section_id = section_id
        self._select_current()

    def _build_ui(self) -> None:
        """Costruisce il pannello sezioni."""
        section_header = Gtk.Label(label=t("sidebar.sections_header"), xalign=0)
        section_header.add_css_class("caption")
        section_header.set_margin_start(12)
        section_header.set_margin_top(8)
        section_header.set_margin_bottom(4)
        self.append(section_header)

        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._section_list = Gtk.ListBox()
        self._section_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._section_list.add_css_class("section-list")
        self._section_list.connect("row-selected", self._on_section_selected)
        scrolled.set_child(self._section_list)
        self.append(scrolled)

        add_section_btn = Gtk.Button(label=t("sidebar.new_section"))
        add_section_btn.add_css_class("flat")
        add_section_btn.set_margin_start(8)
        add_section_btn.set_margin_end(8)
        add_section_btn.set_margin_bottom(4)
        add_section_btn.connect("clicked", self._on_new_section)
        self.append(add_section_btn)

    def refresh(self) -> None:
        """Ricarica la lista sezioni dal database.

        La voce in attesa di cancellazione (``hidden_entry``) non conta più nei
        totali, anche se è ancora nel database finché l'utente può annullare.
        """
        hidden = self._hidden_entry()
        self._sections = self._section_repo.get_all()
        self._section_list.remove_all()
        self._section_list.append(
            SectionRow(
                label=t("sidebar.all_entries"),
                section_id=None,
                count=self._entry_repo.count_all() - (1 if hidden else 0),
                icon_name=ALL_ENTRIES_ICON if theme_has_icon(ALL_ENTRIES_ICON) else FALLBACK_ICON,
            )
        )
        for section in self._sections:
            row = self._create_row(section)
            if hidden is not None and hidden.section_id == section.id:
                row.count_label.set_label(str(max(section.entry_count - 1, 0)))
            self._section_list.append(row)
        self._select_current()

    def _create_row(self, section: Section) -> SectionRow:
        """Crea la riga di una sezione con menu ⋯ e tasto destro."""
        row = SectionRow(
            label=section.name,
            section_id=section.id,
            section=section,
            count=section.entry_count,
            icon_name=resolve_section_icon(section.icon, theme_has_icon),
        )
        row.add_menu(self._build_menu(section))

        gesture = Gtk.GestureClick(button=3)
        gesture.connect("pressed", self._on_right_click, row)
        row.add_controller(gesture)
        return row

    def _build_menu(self, section: Section) -> Gtk.Popover:
        """Menu della sezione. La sezione predefinita non si elimina: lo dice invece di fingere."""
        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(4)

        rename_btn = Gtk.Button(label=t("sidebar.rename"))
        rename_btn.add_css_class("flat")
        rename_btn.connect("clicked", lambda _: self._do_rename(section, popover))
        box.append(rename_btn)

        if section.is_default:
            note = Gtk.Label(label=t("sidebar.default_not_deletable"), wrap=True, xalign=0)
            note.set_max_width_chars(28)
            note.add_css_class("dim-label")
            note.add_css_class("caption")
            box.append(note)
        else:
            delete_btn = Gtk.Button(label=t("sidebar.delete"))
            delete_btn.add_css_class("flat")
            delete_btn.connect("clicked", lambda _: self._do_delete(section, popover))
            box.append(delete_btn)

        popover.set_child(box)
        return popover

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
        dialog = SectionCreateDialog(parent=self.get_root(), on_create=self._on_section_created)
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
        _gesture: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
        row: SectionRow,
    ) -> None:
        """Il tasto destro apre lo stesso menu del pulsante ⋯."""
        if row.menu_button is not None:
            row.menu_button.popup()

    def _do_rename(self, section: Section, popup: Gtk.Popover) -> None:
        """Apre il dialog di rinomina sezione."""
        popup.popdown()
        dialog = SectionRenameDialog(
            parent=self.get_root(),
            section=section,
            on_rename=self._on_section_renamed,
        )
        dialog.present()

    def _do_delete(self, section: Section, popup: Gtk.Popover) -> None:
        """Avvia la procedura di eliminazione sezione."""
        popup.popdown()
        show_delete_section_dialog(
            parent=self.get_root(),
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
        self._on_section_changed(self._current_section_id)
