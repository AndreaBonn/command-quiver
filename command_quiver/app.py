"""Ciclo di vita dell'applicazione, tray icon via helper AyatanaAppIndicator3.

L'app principale usa GTK4 per la UI. Il tray icon è gestito da un
processo separato (tray_helper.py) che usa GTK3 + AyatanaAppIndicator3,
perché GTK3 e GTK4 non possono coesistere nello stesso processo.

La comunicazione avviene via D-Bus:
- tray_helper → app: Toggle, NewEntry, Quit
"""

import logging
import subprocess
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

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

        # Mantiene l'app in vita anche senza finestre visibili (tray app)
        self.hold()

        # Database
        self._db = Database()
        self._db.initialize()

        # Impostazioni
        self._settings = load_settings()

        # Registra interfaccia D-Bus per ricevere comandi dal tray helper
        self._register_dbus_interface()

        # Avvia il tray helper (processo separato GTK3)
        self._start_tray_helper()

        logger.info("Command Quiver avviato")

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

    # --- Icona ---

    @staticmethod
    def _generate_icon(path: Path) -> None:
        """Genera programmaticamente l'icona dell'app (lettera Q stilizzata)."""
        import cairo

        path.parent.mkdir(parents=True, exist_ok=True)

        size = 32
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        ctx = cairo.Context(surface)

        # Sfondo arrotondato scuro
        radius = 6
        ctx.new_sub_path()
        ctx.arc(size - radius, radius, radius, -0.5 * 3.14159, 0)
        ctx.arc(size - radius, size - radius, radius, 0, 0.5 * 3.14159)
        ctx.arc(radius, size - radius, radius, 0.5 * 3.14159, 3.14159)
        ctx.arc(radius, radius, radius, 3.14159, 1.5 * 3.14159)
        ctx.close_path()
        ctx.set_source_rgb(0.18, 0.20, 0.25)
        ctx.fill()

        # Lettera "Q" stilizzata in bianco
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(20)
        ctx.set_source_rgb(0.95, 0.95, 0.95)
        extents = ctx.text_extents("Q")
        x = (size - extents.width) / 2 - extents.x_bearing
        y = (size - extents.height) / 2 - extents.y_bearing
        ctx.move_to(x, y)
        ctx.show_text("Q")

        # Freccia piccola (quiver = faretra) in colore accento
        ctx.set_source_rgb(0.35, 0.65, 0.95)
        ctx.set_line_width(1.5)
        ctx.move_to(20, 22)
        ctx.line_to(27, 22)
        ctx.stroke()
        ctx.move_to(24, 19)
        ctx.line_to(27, 22)
        ctx.line_to(24, 25)
        ctx.stroke()

        surface.write_to_png(str(path))
        logger.info("Icona generata: %s", path)
