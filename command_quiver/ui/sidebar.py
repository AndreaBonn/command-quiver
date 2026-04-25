"""Pannello laterale principale con ricerca, sezioni e lista voci."""

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
    SectionRepository,
)
from command_quiver.ui.entry_editor import EntryEditorDialog
from command_quiver.ui.entry_list import EntryListWidget
from command_quiver.ui.section_panel import SectionPanelWidget
from command_quiver.ui.styles import load_app_css

logger = logging.getLogger(__name__)


class SidebarPanel(Gtk.Window):
    """Pannello laterale principale dell'applicazione.

    Contiene: barra di ricerca, pannello sezioni, lista voci,
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
        self._search_text = ""

        load_app_css()
        self._build_ui()

        # Imposta sezione iniziale e carica dati
        self._section_panel.current_section_id = settings.last_section_id
        self._section_panel.refresh()
        self._refresh_entries()

        # Chiudi con Escape
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

        # Salva dimensioni alla chiusura
        self.connect("close-request", self._on_close_request)

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
        self._section_panel = SectionPanelWidget(
            section_repo=self._section_repo,
            entry_repo=self._entry_repo,
            on_section_changed=self._on_section_changed,
        )
        paned.set_start_child(self._section_panel)
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

    # --- Refresh dati ---

    def _refresh_entries(self) -> None:
        """Ricarica la lista voci con filtri attuali."""
        sort_order = self._SORT_VALUES[self._sort_dropdown.get_selected()]

        entries = self._entry_repo.get_all(
            section_id=self._section_panel.current_section_id,
            search=self._search_text,
            sort_order=sort_order,
        )
        self._entry_list.update_entries(entries)

    # --- Handler eventi ---

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        """Filtra le voci in tempo reale durante la ricerca."""
        self._search_text = entry.get_text().strip()
        self._refresh_entries()

    def _on_section_changed(self, _section_id: int | None) -> None:
        """Callback dal pannello sezioni: aggiorna la lista voci."""
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
        self._section_panel.refresh()
        self._refresh_entries()

    def _on_entry_deleted(self, entry_id: int) -> None:
        """Callback eliminazione voce."""
        self._entry_repo.delete(entry_id)
        self._section_panel.refresh()
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
        self._settings.last_section_id = self._section_panel.current_section_id
        self._settings.window_width = self.get_width()
        self._settings.window_height = self.get_height()
        save_settings(self._settings)

        # Nasconde invece di chiudere, per poterlo riaprire dal tray
        self.set_visible(False)
        return True  # Impedisce la distruzione
