"""Widget pannello sezioni con lista, creazione, rinomina ed eliminazione."""

import logging
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from command_quiver.core.i18n import t
from command_quiver.db.entry_repository import EntryRepository
from command_quiver.db.models import DuplicateSectionError, Entry, Section
from command_quiver.db.section_repository import SectionRepository
from command_quiver.ui.section_manager import (
    create_section_dialog,
    rename_section_dialog,
    show_delete_section_dialog,
)
from command_quiver.ui.section_row import (
    ALL_ENTRIES_ICON,
    FALLBACK_ICON,
    SectionRow,
    build_section_menu,
    resolve_section_icon,
    theme_has_icon,
)

logger = logging.getLogger(__name__)


def visible_counts(
    total: int, sections: list[Section], hidden: Entry | None
) -> tuple[int, dict[int, int]]:
    """Conteggi da mostrare, al netto della voce in attesa di cancellazione.

    Returns
    -------
    tuple[int, dict[int, int]]
        Totale per "Tutti" e conteggio per id di sezione.
    """
    all_count = total - (1 if hidden else 0)
    per_section = {
        s.id: max(s.entry_count - 1, 0)
        if hidden is not None and hidden.section_id == s.id
        else s.entry_count
        for s in sections
    }
    return all_count, per_section


def row_index_for(ids: list[int | None], current_id: int | None) -> int:
    """Indice della riga della sezione corrente; 0 ("Tutti") se non c'è."""
    return ids.index(current_id) if current_id in ids else 0


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
        self._sections = self._section_repo.get_all()
        all_count, counts = visible_counts(
            total=self._entry_repo.count_all(),
            sections=self._sections,
            hidden=self._hidden_entry(),
        )
        self._section_list.remove_all()
        self._section_list.append(
            SectionRow(
                label=t("sidebar.all_entries"),
                count=all_count,
                icon_name=ALL_ENTRIES_ICON if theme_has_icon(ALL_ENTRIES_ICON) else FALLBACK_ICON,
            )
        )
        for section in self._sections:
            self._section_list.append(self._create_row(section, counts[section.id]))
        self._select_current()

    def _create_row(self, section: Section, count: int) -> SectionRow:
        """Crea la riga di una sezione con menu ⋯ e tasto destro."""
        row = SectionRow(
            label=section.name,
            section=section,
            count=count,
            icon_name=resolve_section_icon(section.icon, theme_has_icon),
        )
        row.add_menu(
            build_section_menu(section, on_rename=self._do_rename, on_delete=self._do_delete)
        )

        gesture = Gtk.GestureClick(button=3)
        gesture.connect("pressed", self._on_right_click, row)
        row.add_controller(gesture)
        return row

    def _select_current(self) -> None:
        """Seleziona la riga della sezione attualmente attiva."""
        rows = []
        while (row := self._section_list.get_row_at_index(len(rows))) is not None:
            rows.append(getattr(row.get_child(), "section_id", None))
        target_row = self._section_list.get_row_at_index(
            row_index_for(rows, self._current_section_id)
        )
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
        dialog = create_section_dialog(parent=self.get_root(), on_create=self._on_section_created)
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

    def _do_rename(self, section: Section) -> None:
        """Apre il dialog di rinomina sezione."""
        dialog = rename_section_dialog(
            parent=self.get_root(),
            section=section,
            on_rename=self._on_section_renamed,
        )
        dialog.present()

    def _do_delete(self, section: Section) -> None:
        """Avvia la procedura di eliminazione sezione."""
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
