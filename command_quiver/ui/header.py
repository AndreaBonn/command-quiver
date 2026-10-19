"""Barra del titolo GNOME: "+ Nuova" a sinistra, menu principale a destra."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk

from command_quiver.core.i18n import LANGUAGE_LABELS, t


def build_main_menu() -> Gio.Menu:
    """Menu ☰: impostazioni usate di rado, fuori dalla vista principale.

    Le voci puntano ad azioni "win.*" registrate dalla finestra.
    """
    menu = Gio.Menu()

    language = Gio.Menu()
    for code, label in LANGUAGE_LABELS.items():
        language.append(label, f"win.language::{code}")
    menu.append_submenu(t("menu.language"), language)
    menu.append(t("menu.sync"), "win.sync")

    files = Gio.Menu()
    files.append(t("menu.import"), "win.import")
    files.append(t("menu.export"), "win.export")
    menu.append_section(None, files)

    help_section = Gio.Menu()
    help_section.append(t("menu.shortcuts"), "win.shortcuts")
    help_section.append(t("menu.about"), "win.about")
    help_section.append(t("menu.quit"), "win.quit")
    menu.append_section(None, help_section)
    return menu


def build_header_bar() -> Gtk.HeaderBar:
    """HeaderBar con il pulsante di creazione e il menu principale."""
    header = Gtk.HeaderBar()

    new_btn = Gtk.Button(tooltip_text=t("header.new_entry_tooltip"), action_name="win.new-entry")
    content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    content.append(Gtk.Image(icon_name="list-add-symbolic"))
    content.append(Gtk.Label(label=t("header.new_entry")))
    new_btn.set_child(content)
    new_btn.add_css_class("suggested-action")
    header.pack_start(new_btn)

    menu_btn = Gtk.MenuButton(
        icon_name="open-menu-symbolic",
        menu_model=build_main_menu(),
        tooltip_text=t("header.menu_tooltip"),
        primary=True,
    )
    header.pack_end(menu_btn)
    return header
