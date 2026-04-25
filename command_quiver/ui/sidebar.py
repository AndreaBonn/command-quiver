"""Pannello laterale principale con sezioni, ricerca e lista voci."""

import logging

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk

from command_quiver.core.i18n import t
from command_quiver.core.settings import Settings, save_settings
from command_quiver.db.database import Database
from command_quiver.db.queries import (
    Entry,
    EntryCreate,
    EntryRepository,
    EntryUpdate,
    Section,
    SectionRepository,
)
from command_quiver.ui.entry_editor import EntryEditorDialog
from command_quiver.ui.entry_list import EntryListWidget
from command_quiver.ui.section_manager import (
    SectionCreateDialog,
    SectionRenameDialog,
    show_delete_section_dialog,
)

logger = logging.getLogger(__name__)

# CSS dell'applicazione
_APP_CSS = """
.sidebar-panel {
    background-color: @theme_bg_color;
}
.section-list {
    background-color: transparent;
}
.section-row {
    padding: 6px 12px;
    border-radius: 6px;
}
.section-row:selected, .section-row.active {
    background-color: alpha(@theme_selected_bg_color, 0.3);
}
.section-count {
    font-size: 0.85em;
    opacity: 0.6;
}
.entry-list row {
    border-bottom: 1px solid alpha(@theme_fg_color, 0.08);
}
.entry-list row:hover {
    background-color: alpha(@theme_selected_bg_color, 0.1);
}
.entry-name {
    font-weight: 500;
}
.entry-badge {
    font-size: 0.75em;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
}
.badge-shell {
    background-color: alpha(#2ecc71, 0.2);
    color: #27ae60;
}
.badge-prompt {
    background-color: alpha(#3498db, 0.2);
    color: #2980b9;
}
.copy-success {
    color: #27ae60;
}
.error-label {
    color: #e74c3c;
    font-size: 0.85em;
}
.content-editor {
    font-family: monospace;
    font-size: 0.95em;
}
.content-scroll {
    border: 1px solid alpha(@theme_fg_color, 0.15);
    border-radius: 6px;
}
.search-entry {
    margin: 8px;
}
.bottom-bar {
    padding: 8px 12px;
    border-top: 1px solid alpha(@theme_fg_color, 0.1);
}
"""


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


class SidebarPanel(Gtk.Window):
    """Pannello laterale principale dell'applicazione.

    Contiene: barra di ricerca, lista sezioni, lista voci,
    barra inferiore con azioni.
    """

    _SORT_VALUES = [
        "chronological_desc",
        "chronological_asc",
        "alpha_asc",
        "alpha_desc",
        "personal",
    ]

    def __init__(
        self,
        db: Database,
        settings: Settings,
    ) -> None:
        super().__init__(
            title="Command Quiver",
            default_width=settings.window_width,
            default_height=settings.window_height,
            decorated=True,
        )
        self._db = db
        self._settings = settings
        self._section_repo = SectionRepository(db.connection)
        self._entry_repo = EntryRepository(db.connection)
        self._current_section_id: int | None = settings.last_section_id
        self._search_text = ""

        self._load_css()
        self._build_ui()
        self._refresh_sections()
        self._refresh_entries()

        # Chiudi con Escape
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

        # Salva dimensioni alla chiusura
        self.connect("close-request", self._on_close_request)

    def _load_css(self) -> None:
        """Carica il CSS dell'applicazione."""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_string(_APP_CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _build_ui(self) -> None:
        """Costruisce il layout del pannello."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main_box.add_css_class("sidebar-panel")
        self.set_child(main_box)

        # --- Barra di ricerca ---
        self._search_entry = Gtk.SearchEntry(placeholder_text=t("sidebar.search_placeholder"))
        self._search_entry.add_css_class("search-entry")
        self._search_entry.connect("search-changed", self._on_search_changed)
        main_box.append(self._search_entry)

        # --- Area centrale: sezioni + lista ---
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(160)
        paned.set_vexpand(True)

        # Colonna sezioni (sinistra)
        paned.set_start_child(self._build_section_panel())
        paned.set_shrink_start_child(False)

        # Colonna voci (destra)
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self._entry_list = EntryListWidget(on_entry_click=self._on_entry_click)
        right_box.append(self._entry_list)

        # Menu ordinamento
        sort_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        sort_box.set_margin_start(8)
        sort_box.set_margin_end(8)
        sort_box.set_margin_top(4)
        sort_box.set_margin_bottom(4)

        sort_label = Gtk.Label(label=t("sidebar.sort_label"), xalign=0)
        sort_box.append(sort_label)

        sort_options = [
            t("sidebar.sort_recent_desc"),
            t("sidebar.sort_oldest_asc"),
            t("sidebar.sort_alpha_asc"),
            t("sidebar.sort_alpha_desc"),
            t("sidebar.sort_personal"),
        ]
        self._sort_dropdown = Gtk.DropDown()
        self._sort_dropdown.set_model(Gtk.StringList.new(sort_options))
        self._sort_dropdown.set_hexpand(True)

        # Imposta ordinamento corrente
        sort_map = {
            "chronological_desc": 0,
            "chronological_asc": 1,
            "alpha_asc": 2,
            "alpha_desc": 3,
            "personal": 4,
        }
        self._sort_dropdown.set_selected(sort_map.get(self._settings.sort_order, 0))
        self._sort_dropdown.connect("notify::selected", self._on_sort_changed)
        sort_box.append(self._sort_dropdown)

        right_box.append(sort_box)
        paned.set_end_child(right_box)
        paned.set_shrink_end_child(False)

        main_box.append(paned)

        # --- Barra inferiore ---
        bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bottom_bar.add_css_class("bottom-bar")

        new_btn = Gtk.Button(label=t("sidebar.new_entry"))
        new_btn.add_css_class("suggested-action")
        new_btn.connect("clicked", self._on_new_entry)
        new_btn.set_hexpand(True)
        bottom_bar.append(new_btn)

        main_box.append(bottom_bar)

    def _build_section_panel(self) -> Gtk.Box:
        """Costruisce il pannello sezioni (colonna sinistra)."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        section_header = Gtk.Label(label=t("sidebar.sections_header"), xalign=0)
        section_header.add_css_class("caption")
        section_header.set_margin_start(12)
        section_header.set_margin_top(8)
        section_header.set_margin_bottom(4)
        box.append(section_header)

        # Lista sezioni scrollabile
        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._section_list = Gtk.ListBox()
        self._section_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._section_list.add_css_class("section-list")
        self._section_list.connect("row-selected", self._on_section_selected)
        scrolled.set_child(self._section_list)
        box.append(scrolled)

        # Bottone nuova sezione
        add_section_btn = Gtk.Button(label=t("sidebar.new_section"))
        add_section_btn.add_css_class("flat")
        add_section_btn.set_margin_start(8)
        add_section_btn.set_margin_end(8)
        add_section_btn.set_margin_bottom(4)
        add_section_btn.connect("clicked", self._on_new_section)
        box.append(add_section_btn)

        return box

    # --- Refresh dati ---

    def _refresh_sections(self) -> None:
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
        all_row = self._create_section_row(
            label=t("sidebar.all_entries", count=total_count),
            section_id=None,
        )
        self._section_list.append(all_row)

        # Sezioni dal database
        for section in sections:
            row = self._create_section_row(
                label=t("sidebar.section_row", name=section.name, count=section.entry_count),
                section_id=section.id,
                section=section,
            )
            self._section_list.append(row)

        # Seleziona la sezione attiva
        self._select_current_section()

    def _create_section_row(
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
            gesture.connect("pressed", self._on_section_right_click, section)
            row.add_controller(gesture)

        return row

    def _select_current_section(self) -> None:
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

    def _refresh_entries(self) -> None:
        """Ricarica la lista voci con filtri attuali."""
        sort_order = self._SORT_VALUES[self._sort_dropdown.get_selected()]

        entries = self._entry_repo.get_all(
            section_id=self._current_section_id,
            search=self._search_text,
            sort_order=sort_order,
        )
        self._entry_list.update_entries(entries)

    # --- Handler eventi ---

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        """Filtra le voci in tempo reale durante la ricerca."""
        self._search_text = entry.get_text().strip()
        self._refresh_entries()

    def _on_section_selected(self, _list_box: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        """Aggiorna la lista voci quando si seleziona una sezione."""
        if row is None:
            return
        child = row.get_child()
        if isinstance(child, SectionRow):
            self._current_section_id = child.section_id
            self._refresh_entries()

    def _on_sort_changed(self, dropdown: Gtk.DropDown, _pspec) -> None:
        """Cambia l'ordinamento delle voci."""
        self._settings.sort_order = self._SORT_VALUES[dropdown.get_selected()]
        save_settings(self._settings)
        self._refresh_entries()

    def _on_entry_click(self, entry: Entry) -> None:
        """Apre l'editor per modificare una voce."""
        sections = self._section_repo.get_all()
        dialog = EntryEditorDialog(
            parent=self,
            sections=sections,
            entry=entry,
            on_save=self._on_entry_saved,
            on_delete=self._on_entry_deleted,
        )
        dialog.present()

    def open_new_entry_dialog(self) -> None:
        """Apre il dialog di creazione voce (API pubblica per uso da app.py)."""
        self._on_new_entry(None)

    def _on_new_entry(self, _button: Gtk.Button | None) -> None:
        """Apre l'editor per creare una nuova voce."""
        sections = self._section_repo.get_all()
        dialog = EntryEditorDialog(
            parent=self,
            sections=sections,
            on_save=self._on_entry_saved,
        )
        dialog.present()

    def _on_entry_saved(self, data: EntryCreate | EntryUpdate) -> None:
        """Callback salvataggio voce (creazione o modifica)."""
        if isinstance(data, EntryUpdate):
            self._entry_repo.update(data)
        else:
            self._entry_repo.create(data)
        self._refresh_sections()
        self._refresh_entries()

    def _on_entry_deleted(self, entry_id: int) -> None:
        """Callback eliminazione voce."""
        self._entry_repo.delete(entry_id)
        self._refresh_sections()
        self._refresh_entries()

    def _on_new_section(self, _button: Gtk.Button) -> None:
        """Apre il dialog per creare una nuova sezione."""
        dialog = SectionCreateDialog(
            parent=self,
            on_create=self._on_section_created,
        )
        dialog.present()

    def _on_section_created(self, name: str) -> None:
        """Callback creazione sezione."""
        self._section_repo.create(name)
        self._refresh_sections()

    def _on_section_right_click(
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
        rename_btn.connect("clicked", lambda _: self._do_rename_section(section, popup))
        popup_box.append(rename_btn)

        delete_btn = Gtk.Button(label=t("sidebar.delete"))
        delete_btn.add_css_class("flat")
        delete_btn.connect("clicked", lambda _: self._do_delete_section(section, popup))
        popup_box.append(delete_btn)

        popup.set_child(popup_box)
        widget = gesture.get_widget()
        popup.set_parent(widget)
        popup.popup()

    def _do_rename_section(self, section, popup: Gtk.Popover) -> None:
        """Apre il dialog di rinomina sezione."""
        popup.popdown()
        dialog = SectionRenameDialog(
            parent=self,
            section=section,
            on_rename=self._on_section_renamed,
        )
        dialog.present()

    def _do_delete_section(self, section, popup: Gtk.Popover) -> None:
        """Avvia la procedura di eliminazione sezione."""
        popup.popdown()
        show_delete_section_dialog(
            parent=self,
            section=section,
            on_confirm=self._on_section_deleted,
        )

    def _on_section_renamed(self, section_id: int, new_name: str) -> None:
        """Callback rinomina sezione."""
        self._section_repo.rename(section_id, new_name)
        self._refresh_sections()

    def _on_section_deleted(self, section_id: int) -> None:
        """Callback eliminazione sezione."""
        if self._current_section_id == section_id:
            self._current_section_id = None
        self._section_repo.delete(section_id)
        self._refresh_sections()
        self._refresh_entries()

    def _on_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        """Chiude il pannello con Escape."""
        if keyval == Gdk.KEY_Escape:
            self.set_visible(False)
            return True
        return False

    def _on_close_request(self, _window: Gtk.Window) -> bool:
        """Salva stato e nasconde il pannello (non lo distrugge)."""
        self._settings.last_section_id = self._current_section_id
        self._settings.window_width = self.get_width()
        self._settings.window_height = self.get_height()
        save_settings(self._settings)

        # Nasconde invece di chiudere, per poterlo riaprire dal tray
        self.set_visible(False)
        return True  # Impedisce la distruzione
