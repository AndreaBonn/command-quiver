"""Ciclo di vita dell'applicazione Command Quiver.

L'app usa GTK4 per la UI. La finestra principale (sidebar) coincide con
l'applicazione: chiudendola l'app termina, eseguendo prima il sync finale e
salvando lo stato. La singola istanza è garantita da GtkApplication + D-Bus.
"""

import logging
import threading
from pathlib import Path

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")

from gi.repository import Gdk, Gio, GLib, Gtk

from command_quiver import APP_ID
from command_quiver.core.settings import load_settings, save_settings
from command_quiver.db.database import Database
from command_quiver.ui.sidebar import SidebarPanel

logger = logging.getLogger(__name__)

# Debounce sync: secondi di attesa dopo l'ultima modifica prima di pushare
_SYNC_DEBOUNCE_SECONDS = 30

# Timeout massimo (secondi) per il sync finale alla chiusura
_FINAL_SYNC_TIMEOUT_SECONDS = 5


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
        self._sync_engine = None
        self._sync_debounce_id: int = 0

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
        self._db = Database()
        self._db.initialize()

        self._settings = load_settings()

        from command_quiver.core.i18n import init as i18n_init

        i18n_init(self._settings.language)

        self._init_sync()

    def _init_sync(self) -> None:
        """Inizializza il sync engine e avvia sync all'avvio se abilitato."""
        if not self._settings.sync.enabled:
            return

        from command_quiver.core.sync_engine import SyncEngine

        self._sync_engine = SyncEngine(db=self._db, settings=self._settings)

        # Sync all'avvio in background (non blocca la UI)
        self._run_sync_background()

    def _run_sync_background(self) -> None:
        """Esegue sync in un thread separato per non bloccare la UI GTK."""
        if self._sync_engine is None:
            return

        def _sync_thread() -> None:
            try:
                result = self._sync_engine.sync()
            except Exception:
                logger.exception("Eccezione non gestita nel thread sync")
                from command_quiver.core.sync_engine import SyncResult

                result = SyncResult(success=False, message="Errore interno sync")
            GLib.idle_add(self._on_sync_complete, result)

        thread = threading.Thread(target=_sync_thread, daemon=True)
        thread.start()

    def _on_sync_complete(self, result) -> bool:
        """Callback sync completato (eseguita sul main thread GTK)."""
        if result.success:
            logger.info("Sync completato: %s", result.message)
            # Refresh sidebar se visibile e se ci sono cambiamenti dal remoto
            if (
                result.entries_pulled > 0 or result.sections_pulled > 0
            ) and self._sidebar is not None:
                self._sidebar.refresh_all()
        else:
            logger.warning("Sync fallito: %s", result.message)

        # Aggiorna status nella sidebar
        if self._sidebar is not None:
            self._sidebar.update_sync_status(result)

        return False  # Rimuovi da idle

    def _on_sync_toggled(self) -> None:
        """Reinizializza SyncEngine quando sync viene attivato/disattivato dal dialog."""
        if self._settings.sync.enabled:
            from command_quiver.core.sync_engine import SyncEngine

            self._sync_engine = SyncEngine(db=self._db, settings=self._settings)
            self._run_sync_background()
            logger.info("Sync attivato, primo sync avviato")
        else:
            self._sync_engine = None
            logger.info("Sync disattivato")

    def on_data_changed(self) -> None:
        """Callback invocato dalla sidebar dopo ogni CRUD. Debounce sync push."""
        if self._sync_engine is None:
            return

        # Reset debounce timer
        if self._sync_debounce_id:
            GLib.source_remove(self._sync_debounce_id)

        self._sync_debounce_id = GLib.timeout_add_seconds(
            _SYNC_DEBOUNCE_SECONDS,
            self._on_sync_debounce_fire,
        )

    def _on_sync_debounce_fire(self) -> bool:
        """Timer debounce scaduto: esegui sync push."""
        self._sync_debounce_id = 0
        self._run_sync_background()
        return False  # Non ripetere

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
                self._sidebar = SidebarPanel(
                    db=self._db,
                    settings=self._settings,
                    on_data_changed=self.on_data_changed,
                    on_sync_toggled=self._on_sync_toggled,
                    on_language_changed=self._change_language,
                )
                self.add_window(self._sidebar)
            self._sidebar.present()
            logger.info("Sidebar presentata")
        except Exception:
            logger.exception("Errore in do_activate")

    def _change_language(self, lang: str) -> None:
        """Cambia la lingua dell'interfaccia e ricostruisce la sidebar."""
        from command_quiver.core.i18n import get_language
        from command_quiver.core.i18n import init as i18n_init

        if lang == get_language():
            return

        i18n_init(lang)
        self._settings.language = lang
        save_settings(self._settings)

        # Ricostruisce la sidebar con le nuove traduzioni.
        # La nuova finestra viene aggiunta prima di rimuovere la vecchia: senza
        # hold() l'app uscirebbe se il numero di finestre toccasse zero.
        if self._sidebar is not None:
            old_sidebar = self._sidebar
            was_visible = old_sidebar.get_visible()
            new_sidebar = SidebarPanel(
                db=self._db,
                settings=self._settings,
                on_data_changed=self.on_data_changed,
                on_sync_toggled=self._on_sync_toggled,
                on_language_changed=self._change_language,
            )
            self.add_window(new_sidebar)
            self._sidebar = new_sidebar
            self.remove_window(old_sidebar)
            old_sidebar.cancel_pending_timers()
            old_sidebar.destroy()
            if was_visible:
                new_sidebar.present()

        logger.info("Lingua cambiata: %s", lang)

    def do_shutdown(self) -> None:
        """Chiusura ordinata: sync finale, salvataggio impostazioni, cleanup DB."""
        logger.info("Chiusura Command Quiver")

        # Ferma debounce sync
        if self._sync_debounce_id:
            GLib.source_remove(self._sync_debounce_id)
            self._sync_debounce_id = 0

        # Sync finale con timeout (non blocca la chiusura se la rete è lenta)
        if self._sync_engine is not None:
            sync_thread = threading.Thread(
                target=self._sync_engine.sync,
                daemon=True,
            )
            sync_thread.start()
            sync_thread.join(timeout=_FINAL_SYNC_TIMEOUT_SECONDS)
            if sync_thread.is_alive():
                logger.warning("Sync finale timeout, chiusura senza attendere")

        if self._settings:
            save_settings(self._settings)

        if self._db:
            self._db.close()

        Gtk.Application.do_shutdown(self)
