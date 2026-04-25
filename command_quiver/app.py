"""Ciclo di vita dell'applicazione, tray icon via helper AyatanaAppIndicator3.

L'app principale usa GTK4 per la UI. Il tray icon è gestito da un
processo separato (tray_helper.py) che usa GTK3 + AyatanaAppIndicator3,
perché GTK3 e GTK4 non possono coesistere nello stesso processo.

La comunicazione avviene via D-Bus:
- tray_helper → app: Toggle, NewEntry, ChangeLanguage, Quit
"""

import logging
import subprocess
import sys
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
        self._dbus_reg_id = 0

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
        """Inizializza database, impostazioni, i18n, D-Bus e tray."""
        self._db = Database()
        self._db.initialize()

        self._settings = load_settings()

        from command_quiver.core.i18n import init as i18n_init

        i18n_init(self._settings.language)

        self._register_dbus_interface()
        self._start_tray_helper()

    def _show_error_dialog(self, message: str) -> None:
        """Mostra un dialog di errore fatale all'utente."""
        dialog = Gtk.AlertDialog(message="Errore avvio", detail=message)
        dialog.set_buttons(["OK"])
        window = Gtk.Window(application=self)
        dialog.show(window)

    def do_activate(self) -> None:
        """Attivazione: mostra/crea la sidebar."""
        if self._sidebar is None:
            self._sidebar = SidebarPanel(db=self._db, settings=self._settings)
            self.add_window(self._sidebar)
        self._sidebar.present()

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
        helper_path = Path(__file__).resolve().parent / "tray_helper.py"
        if not helper_path.exists():
            logger.warning("Tray helper non trovato: %s", helper_path)
            return

        try:
            self._tray_process = subprocess.Popen(
                [sys.executable, str(helper_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Tray helper avviato (PID: %d)", self._tray_process.pid)
        except OSError:
            logger.exception("Errore avvio tray helper")

    def _stop_tray_helper(self) -> None:
        """Termina il processo tray helper."""
        if self._tray_process and self._tray_process.poll() is None:
            self._tray_process.terminate()
            try:
                self._tray_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._tray_process.kill()
            logger.info("Tray helper terminato")

    # --- Azioni sidebar ---

    def _toggle_sidebar(self) -> None:
        """Mostra o nasconde il pannello laterale."""
        if self._sidebar is None:
            self.do_activate()
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
            self._sidebar = SidebarPanel(db=self._db, settings=self._settings)
            self.add_window(self._sidebar)
            if was_visible:
                self._sidebar.present()

        logger.info("Lingua cambiata: %s", lang)

    def _quit_app(self) -> None:
        """Chiusura ordinata dell'applicazione."""
        logger.info("Chiusura Command Quiver")

        self._stop_tray_helper()

        if self._settings:
            save_settings(self._settings)

        if self._db:
            self._db.close()

        self.release()
        self.quit()
