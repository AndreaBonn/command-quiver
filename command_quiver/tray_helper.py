#!/usr/bin/env python3
"""Helper process per il tray icon con AyatanaAppIndicator3 (GTK3).

Processo separato dall'app principale GTK4 per evitare conflitti
tra GTK3 (richiesto da AppIndicator3) e GTK4 (usato dalla UI).

Comunica con l'app principale via D-Bus:
- Click sinistro / "Mostra" → invia segnale Activate all'app
- "Nuova voce" → invia segnale NewEntry all'app
- "Esci" → invia segnale Quit all'app
"""

import signal
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import AyatanaAppIndicator3, Gio, GLib, Gtk

APP_ID = "com.github.commandquiver"
DBUS_PATH = "/com/github/commandquiver"
DBUS_INTERFACE = "com.github.commandquiver.App"


def send_dbus_signal(action: str) -> None:
    """Invia un segnale D-Bus all'app principale."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync(
            APP_ID,
            DBUS_PATH,
            DBUS_INTERFACE,
            action,
            None,
            None,
            Gio.DBusCallFlags.NONE,
            -1,
            None,
        )
    except GLib.Error as e:
        print(f"Errore D-Bus: {e.message}", file=sys.stderr)


def on_show(_item) -> None:
    send_dbus_signal("Toggle")


def on_new_entry(_item) -> None:
    send_dbus_signal("NewEntry")


def on_quit(_item) -> None:
    send_dbus_signal("Quit")
    Gtk.main_quit()


def main() -> None:
    # Gestione segnale SIGTERM per chiusura ordinata
    signal.signal(signal.SIGTERM, lambda *_: Gtk.main_quit())

    # Trova l'icona
    icon_path = Path(__file__).resolve().parent / "assets" / "icon.png"
    if not icon_path.exists():
        # Fallback: cerca nell'installazione
        icon_path = (
            Path.home()
            / ".local"
            / "share"
            / "command-quiver"
            / "command_quiver"
            / "assets"
            / "icon.png"
        )

    # Crea l'indicatore
    indicator = AyatanaAppIndicator3.Indicator.new(
        "command-quiver",
        str(icon_path) if icon_path.exists() else "application-default-icon",
        AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS,
    )
    indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)
    indicator.set_title("Command Quiver")

    # Menu contestuale
    menu = Gtk.Menu()

    item_show = Gtk.MenuItem(label="Mostra/Nascondi")
    item_show.connect("activate", on_show)
    menu.append(item_show)

    item_new = Gtk.MenuItem(label="Nuova voce")
    item_new.connect("activate", on_new_entry)
    menu.append(item_new)

    menu.append(Gtk.SeparatorMenuItem())

    item_quit = Gtk.MenuItem(label="Esci")
    item_quit.connect("activate", on_quit)
    menu.append(item_quit)

    menu.show_all()
    indicator.set_menu(menu)

    # Click sinistro → apre/chiude sidebar
    indicator.set_secondary_activate_target(item_show)

    Gtk.main()


if __name__ == "__main__":
    main()
