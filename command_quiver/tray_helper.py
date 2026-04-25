#!/usr/bin/env python3
"""Helper process per il tray icon con AyatanaAppIndicator3 (GTK3).

Processo separato dall'app principale GTK4 per evitare conflitti
tra GTK3 (richiesto da AppIndicator3) e GTK4 (usato dalla UI).

Comunica con l'app principale via D-Bus:
- Click sinistro / "Mostra" -> invia segnale Activate all'app
- "Nuova voce" -> invia segnale NewEntry all'app
- "Esci" -> invia segnale Quit all'app
"""

import logging
import signal
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import AyatanaAppIndicator3, Gio, GLib, Gtk

from command_quiver.core.i18n import LANGUAGE_LABELS, SUPPORTED_LANGUAGES, Language, t
from command_quiver.core.i18n import init as i18n_init
from command_quiver.core.settings import load_settings

logger = logging.getLogger(__name__)

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
        logger.error("Errore D-Bus: %s", e.message)


def on_show(_item) -> None:
    send_dbus_signal("Toggle")


def on_new_entry(_item) -> None:
    send_dbus_signal("NewEntry")


def on_quit(_item) -> None:
    send_dbus_signal("Quit")
    Gtk.main_quit()


def _on_language_selected(item: Gtk.RadioMenuItem, lang: Language) -> None:
    """Invia il cambio lingua all'app principale via D-Bus."""
    if not item.get_active():
        return
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync(
            APP_ID,
            DBUS_PATH,
            DBUS_INTERFACE,
            "ChangeLanguage",
            GLib.Variant("(s)", (lang,)),
            None,
            Gio.DBusCallFlags.NONE,
            -1,
            None,
        )
    except GLib.Error as e:
        logger.error("Errore D-Bus ChangeLanguage: %s", e.message)


def main() -> None:
    # Gestione segnale SIGTERM per chiusura ordinata
    signal.signal(signal.SIGTERM, lambda *_: Gtk.main_quit())

    # Carica impostazioni e inizializza i18n
    settings = load_settings()
    i18n_init(settings.language)

    # Trova la directory assets per l'icona simbolica
    assets_dir = Path(__file__).resolve().parent / "assets"
    if not assets_dir.exists():
        # Fallback: cerca nell'installazione
        assets_dir = (
            Path.home() / ".local" / "share" / "command-quiver" / "command_quiver" / "assets"
        )

    # Crea l'indicatore con icona simbolica (scala come le altre icone GNOME)
    indicator = AyatanaAppIndicator3.Indicator.new(
        "command-quiver",
        "command-quiver-symbolic",
        AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS,
    )
    indicator.set_icon_theme_path(str(assets_dir))
    indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)
    indicator.set_title("Command Quiver")

    # Menu contestuale
    menu = Gtk.Menu()

    item_show = Gtk.MenuItem(label=t("tray.toggle"))
    item_show.connect("activate", on_show)
    menu.append(item_show)

    item_new = Gtk.MenuItem(label=t("tray.new_entry"))
    item_new.connect("activate", on_new_entry)
    menu.append(item_new)

    menu.append(Gtk.SeparatorMenuItem())

    # Sottomenu lingua
    lang_item = Gtk.MenuItem(label=t("tray.language"))
    lang_submenu = Gtk.Menu()

    group: Gtk.RadioMenuItem | None = None
    for lang in SUPPORTED_LANGUAGES:
        if group is None:
            radio = Gtk.RadioMenuItem(label=LANGUAGE_LABELS[lang])
            group = radio
        else:
            radio = Gtk.RadioMenuItem(label=LANGUAGE_LABELS[lang], group=group)
        radio.set_active(lang == settings.language)
        radio.connect("toggled", _on_language_selected, lang)
        lang_submenu.append(radio)

    lang_item.set_submenu(lang_submenu)
    menu.append(lang_item)

    menu.append(Gtk.SeparatorMenuItem())

    item_quit = Gtk.MenuItem(label=t("tray.quit"))
    item_quit.connect("activate", on_quit)
    menu.append(item_quit)

    menu.show_all()
    indicator.set_menu(menu)

    # Click sinistro -> apre/chiude sidebar
    indicator.set_secondary_activate_target(item_show)

    Gtk.main()


def _setup_logging() -> None:
    """Configura logging per il tray helper (processo separato)."""
    from logging.handlers import RotatingFileHandler

    log_dir = Path.home() / ".local" / "share" / "command-quiver" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = RotatingFileHandler(
        log_dir / "tray.log",
        maxBytes=524_288,
        backupCount=2,
        encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)


if __name__ == "__main__":
    _setup_logging()
    main()
