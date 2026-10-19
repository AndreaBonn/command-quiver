"""Ciclo di vita dell'applicazione Command Quiver.

L'app usa GTK4 per la UI. La finestra principale (sidebar) coincide con
l'applicazione: chiudendola l'app termina, eseguendo prima il sync finale e
salvando lo stato. La singola istanza è garantita da GtkApplication + D-Bus.
"""

import logging
import threading
from collections.abc import Callable
from pathlib import Path

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")

from gi.repository import Gdk, Gio, GLib, Gtk

from command_quiver import APP_ID
from command_quiver.core.settings import load_settings, save_settings
from command_quiver.core.sync_coordinator import SyncCoordinator, SyncRuntime, ThreadHandle
from command_quiver.core.sync_engine import SyncEngine, SyncResult
from command_quiver.db.database import Database
from command_quiver.ui.sidebar import SidebarCallbacks, SidebarPanel

logger = logging.getLogger(__name__)

# Timeout massimo (secondi) per il sync finale alla chiusura
_FINAL_SYNC_TIMEOUT_SECONDS = 5


def _spawn_daemon_thread(target: Callable[[], object]) -> ThreadHandle:
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return thread


def _glib_runtime() -> SyncRuntime:
    return SyncRuntime(
        schedule=GLib.timeout_add_seconds,
        cancel=GLib.source_remove,
        call_on_main=GLib.idle_add,
        spawn=_spawn_daemon_thread,
    )


class CommandQuiverApp(Gtk.Application):
    """Applicazione principale Command Quiver.

    Gestisce il ciclo di vita e la finestra sidebar.
    Garantisce una singola istanza tramite GtkApplication + D-Bus.
    """

    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self._db: Database | None = None
        self._settings = None
        self._sidebar: SidebarPanel | None = None
        self._sync = SyncCoordinator(
            make_engine=self._make_sync_engine,
            runtime=_glib_runtime(),
            on_started=self._on_sync_started,
            on_finished=self._on_sync_finished,
        )

    def do_startup(self) -> None:
        """Inizializzazione al primo avvio (database, impostazioni, sync)."""
        Gtk.Application.do_startup(self)

        # Icona finestra per taskbar Ubuntu (GTK4 usa icon-name a livello app)
        icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        assets_dir = str(Path(__file__).resolve().parent / "assets")
        icon_theme.add_search_path(assets_dir)
        Gtk.Window.set_default_icon_name("icon")

        try:
            self._init_services()
        except Exception:
            logger.critical("Errore fatale durante l'avvio", exc_info=True)
            self._show_error_dialog(
                "Impossibile avviare Command Quiver.\n"
                "Controlla i log in ~/.local/share/command-quiver/logs/"
            )
            self.quit()
            return

        logger.info("Command Quiver avviato")

    def _init_services(self) -> None:
        """Inizializza database, impostazioni, i18n e sync."""
        # Settings e lingua prima del DB: al primo avvio le sezioni nascono nella lingua scelta
        self._settings = load_settings()

        from command_quiver.core.i18n import init as i18n_init

        i18n_init(self._settings.language)

        self._db = Database()
        self._db.initialize(language=self._settings.language)

        # Sync all'avvio in background (non blocca la UI)
        if self._settings.sync.enabled:
            self._sync.set_enabled(True)

    def _make_sync_engine(self) -> SyncEngine:
        return SyncEngine(db=self._db, settings=self._settings)

    def _on_sync_started(self) -> None:
        if self._sidebar is not None:
            self._sidebar.set_sync_pending()

    def _on_sync_finished(self, result: SyncResult) -> None:
        """Aggiorna la sidebar con l'esito (eseguita sul main thread GTK)."""
        if self._sidebar is None:
            return
        # Refresh solo se dal remoto è arrivato qualcosa
        if result.success and (result.entries_pulled > 0 or result.sections_pulled > 0):
            self._sidebar.refresh_all()
        self._sidebar.update_sync_status(result)

    def _on_sync_toggled(self) -> None:
        """Riallinea il sync quando viene attivato/disattivato dal dialog."""
        self._sync.set_enabled(self._settings.sync.enabled)

    def _show_error_dialog(self, message: str) -> None:
        """Mostra un dialog di errore fatale all'utente."""
        dialog = Gtk.AlertDialog(message="Errore avvio", detail=message)
        dialog.set_buttons(["OK"])
        window = Gtk.Window(application=self)
        dialog.show(window)

    def do_activate(self) -> None:
        """Attivazione: mostra/crea la sidebar."""
        logger.info("do_activate chiamato, sidebar=%s", self._sidebar)
        try:
            if self._sidebar is None:
                self._sidebar = self._create_sidebar()
                self.add_window(self._sidebar)
            self._sidebar.present()
            logger.info("Sidebar presentata")
        except Exception:
            logger.exception("Errore in do_activate")

    def _create_sidebar(self) -> SidebarPanel:
        """Crea la finestra principale collegata ai callback dell'app."""
        return SidebarPanel(
            db=self._db,
            settings=self._settings,
            callbacks=SidebarCallbacks(
                on_data_changed=self._sync.request_soon,
                on_sync_toggled=self._on_sync_toggled,
                on_language_changed=self._change_language,
                on_sync_now=self._sync.run_now,
            ),
        )

    def _change_language(self, lang: str) -> None:
        """Cambia la lingua dell'interfaccia e ricostruisce la sidebar."""
        from command_quiver.core.i18n import get_language
        from command_quiver.core.i18n import init as i18n_init

        if lang == get_language():
            return

        i18n_init(lang)
        self._settings.language = lang
        save_settings(self._settings)

        if self._sidebar is not None:
            self._replace_sidebar()

        logger.info("Lingua cambiata: %s", lang)

    def _replace_sidebar(self) -> None:
        """Ricostruisce la sidebar con le nuove traduzioni.

        La nuova finestra viene aggiunta prima di rimuovere la vecchia: senza
        hold() l'app uscirebbe se il numero di finestre toccasse zero.
        """
        old_sidebar = self._sidebar
        was_visible = old_sidebar.get_visible()
        # Prima rende definitiva un'eventuale cancellazione in attesa: la nuova
        # finestra rilegge il DB e non saprebbe di dover nascondere quella voce
        old_sidebar.cancel_pending_timers()
        # La nuova finestra nasce con la dimensione di quella che sostituisce
        width, height = old_sidebar.get_default_size()
        self._settings.window_width, self._settings.window_height = width, height
        new_sidebar = self._create_sidebar()
        self.add_window(new_sidebar)
        self._sidebar = new_sidebar
        self.remove_window(old_sidebar)
        old_sidebar.destroy()
        if was_visible:
            new_sidebar.present()

    def do_shutdown(self) -> None:
        """Chiusura ordinata: sync finale, salvataggio impostazioni, cleanup DB."""
        logger.info("Chiusura Command Quiver")

        # Cancellazione in attesa (Annulla non più possibile): definitiva prima della sync
        if self._sidebar is not None:
            self._sidebar.cancel_pending_timers()

        # Ferma il debounce e fa il sync finale con timeout (non blocca la chiusura)
        self._sync.final_sync(timeout=_FINAL_SYNC_TIMEOUT_SECONDS)

        if self._settings:
            save_settings(self._settings)

        if self._db:
            self._db.close()

        Gtk.Application.do_shutdown(self)
