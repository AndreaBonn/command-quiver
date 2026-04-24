"""Ciclo di vita dell'applicazione, tray icon via StatusNotifierItem D-Bus."""

import logging
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

from command_quiver import APP_ID, APP_NAME
from command_quiver.core.settings import Settings, load_settings, save_settings
from command_quiver.db.database import Database
from command_quiver.ui.sidebar import SidebarPanel

logger = logging.getLogger(__name__)

# XML di interfaccia D-Bus per il protocollo StatusNotifierItem
_SNI_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconThemePath" type="s" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <method name="Activate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="SecondaryActivate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="ContextMenu">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
  </interface>
</node>
"""

# XML di interfaccia D-Bus per il menu contestuale (com.canonical.dbusmenu)
_DBUSMENU_XML = """
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <method name="GetLayout">
      <arg name="parentId" type="i" direction="in"/>
      <arg name="recursionDepth" type="i" direction="in"/>
      <arg name="propertyNames" type="as" direction="in"/>
      <arg name="revision" type="u" direction="out"/>
      <arg name="layout" type="(ia{sv}av)" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg name="ids" type="ai" direction="in"/>
      <arg name="propertyNames" type="as" direction="in"/>
      <arg name="properties" type="a(ia{sv})" direction="out"/>
    </method>
    <method name="GetProperty">
      <arg name="id" type="i" direction="in"/>
      <arg name="name" type="s" direction="in"/>
      <arg name="value" type="v" direction="out"/>
    </method>
    <method name="Event">
      <arg name="id" type="i" direction="in"/>
      <arg name="eventId" type="s" direction="in"/>
      <arg name="data" type="v" direction="in"/>
      <arg name="timestamp" type="u" direction="in"/>
    </method>
    <method name="AboutToShow">
      <arg name="id" type="i" direction="in"/>
      <arg name="needUpdate" type="b" direction="out"/>
    </method>
    <signal name="ItemsPropertiesUpdated">
      <arg name="updatedProps" type="a(ia{sv})"/>
      <arg name="removedProps" type="a(ias)"/>
    </signal>
    <signal name="LayoutUpdated">
      <arg name="revision" type="u"/>
      <arg name="parent" type="i"/>
    </signal>
  </interface>
</node>
"""

# ID per le voci del menu contestuale
_MENU_ID_TOGGLE = 1
_MENU_ID_NEW_ENTRY = 2
_MENU_ID_QUIT = 3


class StatusNotifierItem:
    """Tray icon tramite protocollo D-Bus StatusNotifierItem.

    Compatibile con GNOME Shell (tramite estensione AppIndicator preinstallata
    su Ubuntu), KDE Plasma e altri DE che supportano il protocollo SNI.
    """

    def __init__(
        self,
        app_id: str,
        icon_path: Path,
        on_activate: callable,
        on_new_entry: callable,
        on_quit: callable,
    ) -> None:
        self._app_id = app_id
        self._icon_dir = str(icon_path.parent)
        self._icon_name = icon_path.stem
        self._on_activate = on_activate
        self._on_new_entry = on_new_entry
        self._on_quit = on_quit
        self._bus: Gio.DBusConnection | None = None
        self._sni_reg_id = 0
        self._menu_reg_id = 0
        self._menu_revision = 1

    def register(self) -> bool:
        """Registra l'icona tray sul bus di sessione D-Bus."""
        try:
            self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except GLib.Error:
            logger.exception("Impossibile connettersi al bus D-Bus di sessione")
            return False

        # Registra l'oggetto StatusNotifierItem
        node_info = Gio.DBusNodeInfo.new_for_xml(_SNI_XML)
        self._sni_reg_id = self._bus.register_object(
            "/StatusNotifierItem",
            node_info.interfaces[0],
            self._on_sni_method_call,
            self._on_sni_get_property,
            None,
        )

        # Registra l'oggetto menu D-Bus
        menu_node = Gio.DBusNodeInfo.new_for_xml(_DBUSMENU_XML)
        self._menu_reg_id = self._bus.register_object(
            "/MenuBar",
            menu_node.interfaces[0],
            self._on_menu_method_call,
            self._on_menu_get_property,
            None,
        )

        # Registra con il StatusNotifierWatcher
        try:
            self._bus.call_sync(
                "org.kde.StatusNotifierWatcher",
                "/StatusNotifierWatcher",
                "org.kde.StatusNotifierWatcher",
                "RegisterStatusNotifierItem",
                GLib.Variant("(s)", (self._bus.get_unique_name(),)),
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            )
            logger.info("StatusNotifierItem registrato con successo")
            return True
        except GLib.Error:
            logger.warning(
                "StatusNotifierWatcher non disponibile. "
                "Assicurarsi che l'estensione 'AppIndicator' di GNOME Shell sia attiva."
            )
            return False

    def unregister(self) -> None:
        """Rimuove la registrazione D-Bus."""
        if self._bus and self._sni_reg_id:
            self._bus.unregister_object(self._sni_reg_id)
        if self._bus and self._menu_reg_id:
            self._bus.unregister_object(self._menu_reg_id)

    # --- Handler SNI ---

    def _on_sni_method_call(
        self,
        _connection: Gio.DBusConnection,
        _sender: str,
        _path: str,
        _interface: str,
        method: str,
        _params: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        """Gestisce le chiamate ai metodi SNI (click sull'icona)."""
        if method == "Activate" or method == "SecondaryActivate":
            GLib.idle_add(self._on_activate)
        elif method == "ContextMenu":
            # Il menu contestuale viene gestito dal protocollo dbusmenu
            pass

        invocation.return_value(None)

    def _on_sni_get_property(
        self,
        _connection: Gio.DBusConnection,
        _sender: str,
        _path: str,
        _interface: str,
        prop: str,
    ) -> GLib.Variant | None:
        """Restituisce le proprietà dell'icona tray."""
        props = {
            "Category": GLib.Variant("s", "ApplicationStatus"),
            "Id": GLib.Variant("s", self._app_id),
            "Title": GLib.Variant("s", APP_NAME),
            "Status": GLib.Variant("s", "Active"),
            "IconName": GLib.Variant("s", self._icon_name),
            "IconThemePath": GLib.Variant("s", self._icon_dir),
            "Menu": GLib.Variant("o", "/MenuBar"),
        }
        return props.get(prop)

    # --- Handler Menu D-Bus ---

    def _on_menu_method_call(
        self,
        _connection: Gio.DBusConnection,
        _sender: str,
        _path: str,
        _interface: str,
        method: str,
        params: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        """Gestisce le chiamate ai metodi del menu contestuale."""
        if method == "GetLayout":
            layout = self._build_menu_layout()
            invocation.return_value(GLib.Variant("(u(ia{sv}av))", (self._menu_revision, layout)))
        elif method == "GetGroupProperties":
            invocation.return_value(GLib.Variant("(a(ia{sv}),)", ([],)))
        elif method == "GetProperty":
            invocation.return_value(GLib.Variant("(v,)", (GLib.Variant("s", ""),)))
        elif method == "Event":
            item_id = params[0]
            event_id = params[1]
            if event_id == "clicked":
                self._handle_menu_click(item_id)
            invocation.return_value(None)
        elif method == "AboutToShow":
            invocation.return_value(GLib.Variant("(b,)", (False,)))
        else:
            invocation.return_value(None)

    def _on_menu_get_property(
        self,
        _connection: Gio.DBusConnection,
        _sender: str,
        _path: str,
        _interface: str,
        prop: str,
    ) -> GLib.Variant | None:
        """Restituisce le proprietà del menu."""
        props = {
            "Version": GLib.Variant("u", 3),
            "TextDirection": GLib.Variant("s", "ltr"),
            "Status": GLib.Variant("s", "normal"),
            "IconThemePath": GLib.Variant("as", []),
        }
        return props.get(prop)

    def _build_menu_layout(self) -> tuple:
        """Costruisce la struttura del menu contestuale D-Bus."""
        # Ogni voce: (id, {proprietà}, [figli])
        items = [
            self._menu_item(_MENU_ID_TOGGLE, "Mostra/Nascondi"),
            self._menu_item(_MENU_ID_NEW_ENTRY, "Nuova voce"),
            self._menu_separator(),
            self._menu_item(_MENU_ID_QUIT, "Esci"),
        ]

        # Root del menu
        root_props = {"children-display": GLib.Variant("s", "submenu")}
        return (0, root_props, items)

    @staticmethod
    def _menu_item(item_id: int, label: str) -> GLib.Variant:
        """Crea una voce di menu."""
        props = {"label": GLib.Variant("s", label)}
        return GLib.Variant("v", GLib.Variant("(ia{sv}av)", (item_id, props, [])))

    @staticmethod
    def _menu_separator() -> GLib.Variant:
        """Crea un separatore nel menu."""
        props = {"type": GLib.Variant("s", "separator")}
        return GLib.Variant("v", GLib.Variant("(ia{sv}av)", (0, props, [])))

    def _handle_menu_click(self, item_id: int) -> None:
        """Gestisce il click su una voce del menu contestuale."""
        if item_id == _MENU_ID_TOGGLE:
            GLib.idle_add(self._on_activate)
        elif item_id == _MENU_ID_NEW_ENTRY:
            GLib.idle_add(self._on_new_entry)
        elif item_id == _MENU_ID_QUIT:
            GLib.idle_add(self._on_quit)


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
        self._settings: Settings | None = None
        self._sidebar: SidebarPanel | None = None
        self._tray: StatusNotifierItem | None = None

    def do_startup(self) -> None:
        """Inizializzazione al primo avvio (database, impostazioni, tray)."""
        Gtk.Application.do_startup(self)

        # Database
        self._db = Database()
        self._db.initialize()

        # Impostazioni
        self._settings = load_settings()

        # Icona tray
        icon_path = self._resolve_icon_path()
        self._tray = StatusNotifierItem(
            app_id=APP_ID,
            icon_path=icon_path,
            on_activate=self._toggle_sidebar,
            on_new_entry=self._open_new_entry,
            on_quit=self._quit_app,
        )
        self._tray.register()

        logger.info("Command Quiver avviato")

    def do_activate(self) -> None:
        """Attivazione: mostra/crea la sidebar."""
        if self._sidebar is None:
            self._sidebar = SidebarPanel(db=self._db, settings=self._settings)
            self.add_window(self._sidebar)
        self._sidebar.present()

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

        if self._tray:
            self._tray.unregister()

        if self._settings:
            save_settings(self._settings)

        if self._db:
            self._db.close()

        self.quit()

    def _resolve_icon_path(self) -> Path:
        """Trova il percorso dell'icona, generandola se necessario."""
        # Cerca nella directory dell'app
        app_dir = Path(__file__).resolve().parent
        icon_path = app_dir / "assets" / "icon.png"

        if not icon_path.exists():
            logger.info("Icona non trovata, generazione automatica")
            self._generate_icon(icon_path)

        return icon_path

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
