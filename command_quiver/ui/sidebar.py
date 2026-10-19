"""Finestra principale: ricerca, sezioni, lista voci e stato di sincronizzazione."""

import logging
from collections.abc import Callable
from dataclasses import dataclass

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

from command_quiver.core.i18n import get_language, t
from command_quiver.core.settings import Settings, save_settings
from command_quiver.core.sync_engine import SyncResult
from command_quiver.db.database import Database
from command_quiver.db.entry_repository import EntryRepository
from command_quiver.db.models import Entry
from command_quiver.db.section_repository import SectionRepository
from command_quiver.ui import run_confirm
from command_quiver.ui.empty_states import EmptyActions, EmptyContext, build_empty_state
from command_quiver.ui.entry_list import EntryListWidget, RowCallbacks
from command_quiver.ui.header import build_header_bar
from command_quiver.ui.library_controller import LibraryController, LibraryView
from command_quiver.ui.search_bar import SearchBar
from command_quiver.ui.section_panel import SectionPanelWidget
from command_quiver.ui.shortcuts_dialog import ShortcutsDialog
from command_quiver.ui.status_bar import SyncStatusBar
from command_quiver.ui.styles import load_app_css
from command_quiver.ui.toast import ToastOverlay
from command_quiver.ui.window_actions import install_window_actions, show_about

logger = logging.getLogger(__name__)

_SECTIONS_PANE_WIDTH = 224


@dataclass
class SidebarCallbacks:
    """Callback verso l'applicazione (sync e lingua vivono a livello app)."""

    on_data_changed: Callable[[], None] | None = None
    on_sync_toggled: Callable[[], None] | None = None
    on_language_changed: Callable[[str], None] | None = None
    on_sync_now: Callable[[], None] | None = None


class SidebarPanel(Gtk.Window):
    """Finestra principale dell'applicazione."""

    def __init__(
        self,
        db: Database,
        settings: Settings,
        callbacks: SidebarCallbacks | None = None,
    ) -> None:
        super().__init__(
            title="Command Quiver by Bonn",
            default_width=settings.window_width,
            default_height=settings.window_height,
        )
        self._settings = settings
        self._callbacks = callbacks or SidebarCallbacks()
        self._section_repo = SectionRepository(db.connection)
        self._entry_repo = EntryRepository(db.connection)
        self._search_text = ""

        load_app_css()
        self.set_titlebar(build_header_bar())
        self._build_ui()
        self._library = self._build_library()
        self._pending_delete = self._library.pending_delete
        self._install_actions()

        self._section_panel.current_section_id = settings.last_section_id
        self._section_panel.refresh()
        self._refresh_entries()
        self._connect_window_events()

    # --- Costruzione ---

    def _build_library(self) -> LibraryController:
        return LibraryController(
            self._entry_repo,
            self._section_repo,
            LibraryView(
                window=self,
                toast=self._toast,
                refresh_all=self.refresh_all,
                refresh_entries=self._refresh_entries,
                visible_entries=lambda: self._entry_list.entries,
                notify_changed=self._notify_data_changed,
            ),
        )

    def _connect_window_events(self) -> None:
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)
        self.connect("close-request", self._on_close_request)

    def _install_actions(self) -> None:
        install_window_actions(
            self,
            handlers={
                "new-entry": self.open_new_entry_dialog,
                "focus-search": self._search_entry.grab_focus,
                "sync": self._open_sync_dialog,
                "import": lambda: self._library.import_file(),
                "export": lambda: self._library.export_file(),
                "shortcuts": lambda: ShortcutsDialog(parent=self).present(),
                "about": lambda: show_about(self),
                "quit": self.close,
            },
            on_language=self._on_language_action,
        )

    def _build_entry_list(self) -> EntryListWidget:
        return EntryListWidget(
            callbacks=RowCallbacks(
                on_edit=self._on_entry_click,
                on_move=lambda eid, d: self._library.move(eid, d),
                on_reorder=lambda m, t_: self._library.reorder(m, t_),
                on_use=self._on_entry_used,
                on_copied=lambda e: self._toast.show_message(t("toast.copied", name=e.name)),
                on_run=self._on_run_requested,
                on_tag=self._search_entry.set_text,
            ),
        )

    def _build_ui(self) -> None:
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main_box.add_css_class("sidebar-panel")
        main_box.append(self._build_search_row())

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, vexpand=True)
        paned.set_position(_SECTIONS_PANE_WIDTH)
        self._section_panel = SectionPanelWidget(
            section_repo=self._section_repo,
            entry_repo=self._entry_repo,
            on_section_changed=lambda _id: self._refresh_entries(),
            hidden_entry=lambda: self._library.pending_entry,
        )
        # Larghezza minima: nome, conteggio e pulsante ⋯ devono stare insieme senza "…"
        self._section_panel.set_size_request(_SECTIONS_PANE_WIDTH, -1)
        paned.set_start_child(self._section_panel)
        paned.set_shrink_start_child(False)
        self._entry_list = self._build_entry_list()
        # Avvisi sopra la sola lista: non coprono il pannello sezioni né la riga di stato
        self._toast = ToastOverlay(self._entry_list)
        paned.set_end_child(self._toast)
        paned.set_shrink_end_child(False)
        main_box.append(paned)
        self._status_bar = SyncStatusBar(self._settings, on_open_sync=self._open_sync_dialog)
        main_box.append(self._status_bar)
        self.set_child(main_box)

    def _build_search_row(self) -> Gtk.Box:
        bar = SearchBar(sort_order=self._settings.sort_order, on_search=self._apply_search)
        self._search_entry = bar.entry
        self._search_entry.connect("activate", lambda _: self._entry_list.copy_first())
        self._sort_bar = bar
        self._sort_dropdown = bar.sort_dropdown
        self._sort_dropdown.connect("notify::selected", self._on_sort_changed)
        return bar

    # --- Refresh dati ---

    def _refresh_entries(self) -> None:
        """Ricarica la lista voci con filtri attuali e lo stato vuoto adatto."""
        sort_order = self._sort_bar.sort_order
        entries = self._entry_repo.get_all(
            section_id=self._section_panel.current_section_id,
            search=self._search_text,
            sort_order=sort_order,
        )
        entries = [e for e in entries if e.id != self._library.pending_delete.entry_id]
        empty_state = None if entries else self._build_empty_state()
        self._entry_list.update_entries(
            entries, show_move=(sort_order == "personal"), empty_state=empty_state
        )

    def _build_empty_state(self) -> Gtk.Widget:
        return build_empty_state(
            EmptyContext(
                library_empty=self._entry_repo.count_all() == 0,
                query=self._search_text,
                section_name=self._section_panel.current_section_name,
            ),
            EmptyActions(
                on_create=self.open_new_entry_dialog,
                on_add_samples=self._library.add_samples,
                on_search_all=lambda: self._section_panel.select_section(None),
                on_clear_search=lambda: self._search_entry.set_text(""),
            ),
        )

    def refresh_all(self) -> None:
        """Refresh completo dopo sync (API pubblica per app.py)."""
        self._section_panel.refresh()
        self._refresh_entries()

    def cancel_pending_timers(self) -> None:
        """Annulla i timer GLib pendenti prima di distruggere la finestra (cambio lingua)."""
        self._sort_bar.cancel()
        self._toast.cancel()
        self._pending_delete.flush()

    # --- Stato sincronizzazione (API pubblica per app.py) ---

    def set_sync_pending(self) -> None:
        """Una sincronizzazione è partita."""
        self._status_bar.set_pending()

    def update_sync_status(self, result: SyncResult) -> None:
        """Esito reale di una sincronizzazione."""
        self._status_bar.set_result(result)

    def _notify_data_changed(self) -> None:
        if self._callbacks.on_data_changed:
            self._callbacks.on_data_changed()

    # --- Handler ricerca, ordinamento, lingua ---

    def _apply_search(self, text: str) -> None:
        self._search_text = text
        self._refresh_entries()

    def _on_sort_changed(self, dropdown: Gtk.DropDown, _pspec) -> None:
        self._settings.sort_order = self._sort_bar.sort_order
        save_settings(self._settings)
        self._refresh_entries()

    def _on_language_action(self, action: Gio.SimpleAction, value: GLib.Variant) -> None:
        lang = value.get_string()
        if lang == get_language() or self._callbacks.on_language_changed is None:
            return
        action.set_state(value)
        # Deferito: il callback ricostruisce questa finestra, non distruggibile nel proprio handler
        GLib.idle_add(self._callbacks.on_language_changed, lang)

    # --- Handler voci ---

    def _on_entry_used(self, entry_id: int) -> None:
        """Registra l'uso per il ranking, senza riordinare la lista sotto il cursore."""
        self._entry_repo.bump_usage(entry_id)

    def _on_run_requested(self, entry: Entry) -> None:
        run_confirm.request_run(self, entry, self._settings, on_use=self._on_entry_used)

    def _on_entry_click(self, entry: Entry) -> None:
        self._library.open_editor(entry, self._section_panel.current_section_id)

    def open_new_entry_dialog(self) -> None:
        """Apre il dialog di creazione voce (API pubblica)."""
        self._library.open_editor(None, self._section_panel.current_section_id)

    def _open_sync_dialog(self) -> None:
        from command_quiver.ui.sync_dialog import SyncSetupDialog

        SyncSetupDialog(
            parent=self,
            settings=self._settings,
            on_sync_toggled=self._on_sync_toggled,
            on_sync_now=self._callbacks.on_sync_now,
        ).present()

    def _on_sync_toggled(self) -> None:
        self._status_bar.reset()
        if self._callbacks.on_sync_toggled:
            self._callbacks.on_sync_toggled()

    # --- Tastiera e chiusura ---

    def _on_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        """Esc svuota la ricerca. Non chiude più l'app: per uscire, X o Ctrl+Q."""
        if keyval == Gdk.KEY_Escape and self._search_entry.get_text():
            self._search_entry.set_text("")
            return True
        return False

    def _on_close_request(self, _window: Gtk.Window) -> bool:
        """Salva lo stato e lascia chiudere la finestra (l'app termina)."""
        # Una cancellazione in attesa diventa definitiva prima della sync finale
        self._pending_delete.flush()
        self._settings.last_section_id = self._section_panel.current_section_id
        # get_default_size segue i ridimensionamenti ed è il valore che GTK riapplica;
        # get_width esclude i margini della finestra e la faceva stringere a ogni avvio
        self._settings.window_width, self._settings.window_height = self.get_default_size()
        save_settings(self._settings)
        return False
