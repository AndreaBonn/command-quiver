"""Ciclo di vita dell'applicazione, tray icon via helper AyatanaAppIndicator3.

L'app principale usa GTK4 per la UI. Il tray icon è gestito da un
processo separato (tray_helper.py) che usa GTK3 + AyatanaAppIndicator3,
perché GTK3 e GTK4 non possono coesistere nello stesso processo.

La comunicazione avviene via D-Bus:
- tray_helper -> app: Toggle, NewEntry, ChangeLanguage, Quit
"""

import logging
import subprocess
import sys
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

# Interfaccia D-Bus esposta dall'app per ricevere comandi dal tray helper
_APP_DBUS_XML = """
<node>
  <interface name="com.github.commandquiver.App">
    <method name="Toggle"/>
    <method name="NewEntry"/>
    <method name="ChangeLanguage">
      <arg type="s" name="lang" direction="in"/>
    </method>
    <method name="Quit"/>
  </interface>
</node>
"""

# Debounce sync: secondi di attesa dopo l'ultima modifica prima di pushare
_SYNC_DEBOUNCE_SECONDS = 30


class CommandQuiverApp(Gtk.Application):
    """Applicazione principale Command Quiver.

    Gestisce il ciclo di vita, la finestra sidebar e l'icona tray.
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
        self._tray_process: subprocess.Popen | None = None
        self._tray_helper_path: Path | None = None
        self._tray_health_source: int = 0
        self._tray_stderr_file = None
        self._dbus_reg_id = 0
        self._sync_engine = None
        self._sync_debounce_id: int = 0

    def do_startup(self) -> None:
        """Inizializzazione al primo avvio (database, impostazioni, tray)."""
        Gtk.Application.do_startup(self)

        # Icona finestra per taskbar Ubuntu (GTK4 usa icon-name a livello app)
        icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        assets_dir = str(Path(__file__).resolve().parent / "assets")
        icon_theme.add_search_path(assets_dir)
        Gtk.Window.set_default_icon_name("icon")

        # Mantiene l'app in vita anche senza finestre visibili (tray app)
        self.hold()

        try:
            self._init_services()
        except Exception:
            logger.critical("Errore fatale durante l'avvio", exc_info=True)
            self._show_error_dialog(
                "Impossibile avviare Command Quiver.\n"
                "Controlla i log in ~/.local/share/command-quiver/logs/"
            )
            self.release()
            return

        logger.info("Command Quiver avviato")

    def _init_services(self) -> None:
        """Inizializza database, impostazioni, i18n, D-Bus, tray e sync."""
        self._db = Database()
        self._db.initialize()

        self._settings = load_settings()

        from command_quiver.core.i18n import init as i18n_init

        i18n_init(self._settings.language)

        self._register_dbus_interface()
        self._start_tray_helper()
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
            result = self._sync_engine.sync()
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
                )
                self.add_window(self._sidebar)
            self._sidebar.present()
            logger.info("Sidebar presentata")
        except Exception:
            logger.exception("Errore in do_activate")

    # --- D-Bus interface per il tray helper ---

    def _register_dbus_interface(self) -> None:
        """Registra l'interfaccia D-Bus per ricevere comandi dal tray."""
        bus = self.get_dbus_connection()
        if bus is None:
            logger.warning("Nessuna connessione D-Bus disponibile")
            return

        node_info = Gio.DBusNodeInfo.new_for_xml(_APP_DBUS_XML)
        self._dbus_reg_id = bus.register_object(
            "/com/github/commandquiver",
            node_info.interfaces[0],
            self._on_dbus_method_call,
            None,
            None,
        )
        logger.info("Interfaccia D-Bus registrata: com.github.commandquiver.App")

    def _on_dbus_method_call(
        self,
        _connection: Gio.DBusConnection,
        _sender: str,
        _path: str,
        _interface: str,
        method: str,
        _params: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        """Gestisce i comandi ricevuti dal tray helper via D-Bus."""
        logger.info("Comando D-Bus ricevuto: %s", method)

        if method == "Toggle":
            self._toggle_sidebar()
        elif method == "NewEntry":
            self._open_new_entry()
        elif method == "ChangeLanguage":
            lang = _params.unpack()[0] if _params else "it"
            self._change_language(lang)
        elif method == "Quit":
            self._quit_app()

        invocation.return_value(None)

    # --- Tray helper process ---

    def _start_tray_helper(self) -> None:
        """Avvia il processo tray helper (GTK3 + AyatanaAppIndicator3)."""
        self._tray_helper_path = Path(__file__).resolve().parent / "tray_helper.py"
        if not self._tray_helper_path.exists():
            logger.warning("Tray helper non trovato: %s", self._tray_helper_path)
            return

        self._launch_tray_process()
        # Health check periodico ogni 10 secondi
        self._tray_health_source = GLib.timeout_add_seconds(10, self._check_tray_health)

    def _launch_tray_process(self) -> bool:
        """Lancia il processo tray helper. Restituisce True se avviato."""
        try:
            log_dir = Path.home() / ".local" / "share" / "command-quiver" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            self._tray_stderr_file = (log_dir / "tray_stderr.log").open("a", encoding="utf-8")

            self._tray_process = subprocess.Popen(
                [sys.executable, str(self._tray_helper_path)],
                stdout=subprocess.DEVNULL,
                stderr=self._tray_stderr_file,
            )
            logger.info("Tray helper avviato (PID: %d)", self._tray_process.pid)
            return True
        except OSError:
            logger.exception("Errore avvio tray helper")
            return False

    def _check_tray_health(self) -> bool:
        """Verifica che il tray helper sia attivo; riavvia se crashato."""
        if self._tray_process is None:
            return False  # Rimuovi il timeout
        if self._tray_process.poll() is not None:
            exit_code = self._tray_process.returncode
            logger.warning("Tray helper terminato inatteso (exit code: %d), riavvio", exit_code)
            self._launch_tray_process()
        return True  # Continua il polling

    def _stop_tray_helper(self) -> None:
        """Termina il processo tray helper."""
        if self._tray_process and self._tray_process.poll() is None:
            self._tray_process.terminate()
            try:
                self._tray_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._tray_process.kill()
            logger.info("Tray helper terminato")
        if self._tray_stderr_file is not None:
            self._tray_stderr_file.close()
            self._tray_stderr_file = None

    # --- Azioni sidebar ---

    def _toggle_sidebar(self) -> None:
        """Mostra o nasconde il pannello laterale."""
        if self._sidebar is None:
            logger.info("Toggle: sidebar non esiste, creo via do_activate")
            try:
                self.do_activate()
            except Exception:
                logger.exception("Errore creazione sidebar in toggle")
            return

        if self._sidebar.get_visible():
            self._sidebar.set_visible(False)
        else:
            self._sidebar.present()

    def _open_new_entry(self) -> None:
        """Apre la sidebar e mostra il dialog di nuova voce."""
        if self._sidebar is None:
            self.do_activate()
        elif not self._sidebar.get_visible():
            self._sidebar.present()

        GLib.idle_add(self._sidebar.open_new_entry_dialog)

    def _change_language(self, lang: str) -> None:
        """Cambia la lingua dell'interfaccia e ricostruisce la sidebar."""
        from command_quiver.core.i18n import get_language
        from command_quiver.core.i18n import init as i18n_init

        if lang == get_language():
            return

        i18n_init(lang)
        self._settings.language = lang
        save_settings(self._settings)

        # Ricostruisce la sidebar con le nuove traduzioni
        if self._sidebar is not None:
            was_visible = self._sidebar.get_visible()
            self.remove_window(self._sidebar)
            self._sidebar.destroy()
            self._sidebar = SidebarPanel(
                db=self._db,
                settings=self._settings,
                on_data_changed=self.on_data_changed,
                on_sync_toggled=self._on_sync_toggled,
            )
            self.add_window(self._sidebar)
            if was_visible:
                self._sidebar.present()

        logger.info("Lingua cambiata: %s", lang)

    def _quit_app(self) -> None:
        """Chiusura ordinata dell'applicazione."""
        logger.info("Chiusura Command Quiver")

        # Ferma health check prima di terminare il tray
        if self._tray_health_source:
            GLib.source_remove(self._tray_health_source)
            self._tray_health_source = 0

        # Ferma debounce sync
        if self._sync_debounce_id:
            GLib.source_remove(self._sync_debounce_id)
            self._sync_debounce_id = 0

        self._stop_tray_helper()

        # Sync finale con timeout 5s (non blocca la chiusura se rete lenta)
        if self._sync_engine is not None:
            sync_thread = threading.Thread(
                target=self._sync_engine.sync,
                daemon=True,
            )
            sync_thread.start()
            sync_thread.join(timeout=5)
            if sync_thread.is_alive():
                logger.warning("Sync finale timeout, chiusura senza attendere")

        if self._settings:
            save_settings(self._settings)

        if self._db:
            self._db.close()

        self.release()
        self.quit()
