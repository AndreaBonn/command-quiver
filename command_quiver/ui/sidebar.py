"""Pannello laterale principale con ricerca, sezioni e lista voci."""

import logging
from collections.abc import Callable

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
    barra inferiore con azioni e stato sync.
    """

    _SORT_VALUES = [
        "chronological_desc",
        "chronological_asc",
        "alpha_asc",
        "alpha_desc",
        "personal",
        "usage",
    ]

    # Selettore lingua: codici e autonimi (mostrati uguali in ogni lingua)
    _LANG_VALUES = ["it", "en"]
    _LANG_LABELS = ["Italiano", "English"]

    def __init__(
        self,
        db: Database,
        settings: Settings,
        on_data_changed: Callable[[], None] | None = None,
        on_sync_toggled: Callable[[], None] | None = None,
        on_language_changed: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(
            title="Command Quiver by Bonn",
            default_width=settings.window_width,
            default_height=settings.window_height,
            decorated=True,
        )

        self._db = db
        self._settings = settings
        self._section_repo = SectionRepository(db.connection)
        self._entry_repo = EntryRepository(db.connection)
        self._search_text = ""
        self._search_debounce_id: int = 0
        self._on_data_changed = on_data_changed
        self._on_sync_toggled_cb = on_sync_toggled
        self._on_language_changed_cb = on_language_changed

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

        self._entry_list = EntryListWidget(
            on_entry_edit=self._on_entry_click,
            on_move=self._on_entry_move,
            on_use=self._on_entry_used,
        )
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
            t("sidebar.sort_usage"),
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
            "usage": 5,
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

        # Selettore lingua interfaccia (it/en)
        self._lang_dropdown = Gtk.DropDown()
        self._lang_dropdown.set_model(Gtk.StringList.new(self._LANG_LABELS))
        self._lang_dropdown.set_tooltip_text(t("sidebar.language"))
        from command_quiver.core.i18n import get_language

        current_lang = get_language()
        if current_lang in self._LANG_VALUES:
            self._lang_dropdown.set_selected(self._LANG_VALUES.index(current_lang))
        self._lang_dropdown.connect("notify::selected", self._on_language_selected)
        bottom_bar.append(self._lang_dropdown)

        # Bottone sync (icona ingranaggio)
        sync_btn = Gtk.Button(icon_name="emblem-synchronizing-symbolic")
        sync_btn.set_tooltip_text(t("sync.title"))
        sync_btn.connect("clicked", self._on_sync_clicked)
        bottom_bar.append(sync_btn)

        main_box.append(bottom_bar)

        # --- Status bar sync ---
        self._sync_status_label = Gtk.Label(xalign=0)
        self._sync_status_label.add_css_class("dim-label")
        self._sync_status_label.set_margin_start(8)
        self._sync_status_label.set_margin_bottom(4)

        if self._settings.sync.enabled:
            self._sync_status_label.set_label(t("sync.status_ok"))
        else:
            self._sync_status_label.set_label(t("sync.status_disabled"))

        main_box.append(self._sync_status_label)

    def _on_entry_used(self, entry_id: int) -> None:
        """Registra l'uso di una voce (copia/esecuzione) per il ranking locale.

        Non forza il refresh: in modalità "Più usati" il nuovo ordine si applica
        al prossimo ricaricamento, così la lista non si riordina sotto il cursore
        mentre l'utente copia.
        """
        self._entry_repo.bump_usage(entry_id)

    # --- Refresh dati ---

    def _refresh_entries(self) -> None:
        """Ricarica la lista voci con filtri attuali."""
        sort_order = self._SORT_VALUES[self._sort_dropdown.get_selected()]

        entries = self._entry_repo.get_all(
            section_id=self._section_panel.current_section_id,
            search=self._search_text,
            sort_order=sort_order,
        )
        self._entry_list.update_entries(entries, show_move=(sort_order == "personal"))

    def cancel_pending_timers(self) -> None:
        """Annulla i timer GLib pendenti (API pubblica per app.py).

        Va invocato prima di distruggere la finestra, ad esempio quando l'app
        ricostruisce la sidebar per il cambio lingua, per evitare che un timer
        di debounce spari su widget ormai distrutti.
        """
        if self._search_debounce_id:
            from gi.repository import GLib

            GLib.source_remove(self._search_debounce_id)
            self._search_debounce_id = 0

    def refresh_all(self) -> None:
        """Refresh completo dopo sync (API pubblica per app.py)."""
        self._section_panel.refresh()
        self._refresh_entries()

    def update_sync_status(self, result) -> None:
        """Aggiorna la label di stato sync (API pubblica per app.py)."""
        if result.success:
            if result.entries_pulled > 0 or result.sections_pulled > 0:
                self._sync_status_label.set_label(
                    t("sync.result", pulled=result.entries_pulled, pushed=0),
                )
            else:
                self._sync_status_label.set_label(t("sync.status_ok"))
            self._sync_status_label.remove_css_class("error")
        else:
            self._sync_status_label.set_label(t("sync.status_error"))
            self._sync_status_label.add_css_class("error")

    def _notify_data_changed(self) -> None:
        """Notifica l'app che i dati sono cambiati (per trigger sync debounced)."""
        if self._on_data_changed:
            self._on_data_changed()

    # --- Handler eventi ---

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        """Filtra le voci con debounce 250ms per evitare query a ogni keystroke."""
        from gi.repository import GLib

        if self._search_debounce_id:
            GLib.source_remove(self._search_debounce_id)

        self._search_debounce_id = GLib.timeout_add(250, self._apply_search, entry)

    def _apply_search(self, entry: Gtk.SearchEntry) -> bool:
        """Applica il filtro di ricerca (callback debounce)."""
        self._search_debounce_id = 0
        self._search_text = entry.get_text().strip()
        self._refresh_entries()
        return False  # Rimuovi il timeout

    def _on_section_changed(self, _section_id: int | None) -> None:
        """Callback dal pannello sezioni: aggiorna la lista voci."""
        self._refresh_entries()

    def _on_sort_changed(self, dropdown: Gtk.DropDown, _pspec) -> None:
        """Cambia l'ordinamento delle voci."""
        self._settings.sort_order = self._SORT_VALUES[dropdown.get_selected()]
        save_settings(self._settings)
        self._refresh_entries()

    def _on_language_selected(self, dropdown: Gtk.DropDown, _pspec) -> None:
        """Cambia la lingua dell'interfaccia tramite il callback dell'app."""
        lang = self._LANG_VALUES[dropdown.get_selected()]
        from command_quiver.core.i18n import get_language

        if lang == get_language() or self._on_language_changed_cb is None:
            return

        # Deferito: il callback ricostruisce questa finestra e non si può
        # distruggere un widget durante il proprio handler di segnale.
        from gi.repository import GLib

        GLib.idle_add(self._on_language_changed_cb, lang)

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
        self._notify_data_changed()

    def _on_entry_deleted(self, entry_id: int) -> None:
        """Callback eliminazione voce."""
        self._entry_repo.delete(entry_id)
        self._section_panel.refresh()
        self._refresh_entries()
        self._notify_data_changed()

    def _on_entry_move(self, entry_id: int, direction: int) -> None:
        """Sposta una voce su (-1) o giù (+1) nell'ordinamento personale."""
        entries = self._entry_list.entries
        idx = next((i for i, e in enumerate(entries) if e.id == entry_id), None)
        if idx is None:
            return

        swap_idx = idx + direction
        if swap_idx < 0 or swap_idx >= len(entries):
            return

        # Scambia le posizioni personali
        self._entry_repo.update_position(
            entry_id=entries[idx].id, new_position=entries[swap_idx].personal_pos
        )
        self._entry_repo.update_position(
            entry_id=entries[swap_idx].id, new_position=entries[idx].personal_pos
        )
        self._refresh_entries()

    def _on_sync_clicked(self, _button: Gtk.Button) -> None:
        """Apre il dialog di configurazione sync."""
        from command_quiver.ui.sync_dialog import SyncSetupDialog

        dialog = SyncSetupDialog(
            parent=self,
            settings=self._settings,
            on_sync_toggled=self._on_sync_toggled,
        )
        dialog.present()

    def _on_sync_toggled(self) -> None:
        """Callback quando sync viene attivato/disattivato."""
        if self._settings.sync.enabled:
            self._sync_status_label.set_label(t("sync.status_ok"))
        else:
            self._sync_status_label.set_label(t("sync.status_disabled"))
        # Notifica app.py per reinizializzare SyncEngine
        if self._on_sync_toggled_cb:
            self._on_sync_toggled_cb()

    def _on_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        """Chiude la finestra (e quindi l'app) con Escape."""
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def _on_close_request(self, _window: Gtk.Window) -> bool:
        """Salva lo stato e lascia chiudere la finestra (l'app termina)."""
        self._settings.last_section_id = self._section_panel.current_section_id
        self._settings.window_width = self.get_width()
        self._settings.window_height = self.get_height()
        save_settings(self._settings)

        return False  # Consente la distruzione della finestra
