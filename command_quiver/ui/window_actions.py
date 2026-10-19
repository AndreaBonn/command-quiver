"""Azioni "win.*" della finestra principale, scorciatoie globali e finestra Informazioni."""

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

from command_quiver import __version__
from command_quiver.core.i18n import get_language, t

SHORTCUTS: tuple[tuple[str, str], ...] = (
    ("<Control>f", "focus-search"),
    ("<Control>n", "new-entry"),
    ("<Control>q", "quit"),
    ("<Control>question", "shortcuts"),
)


def install_window_actions(
    window: Gtk.Window,
    handlers: dict[str, Callable[[], None]],
    on_language: Callable[[Gio.SimpleAction, GLib.Variant], None],
) -> None:
    """Registra le azioni usate da menu, pulsanti e scorciatoie da tastiera.

    Parameters
    ----------
    window : Gtk.Window
        Finestra su cui installare il gruppo "win" e le scorciatoie.
    handlers : dict[str, Callable[[], None]]
        Nome azione -> funzione senza argomenti.
    on_language : Callable[[Gio.SimpleAction, GLib.Variant], None]
        Gestore dell'azione con stato "language" (codice lingua come stringa).
    """
    group = Gio.SimpleActionGroup()
    for name, handler in handlers.items():
        action = Gio.SimpleAction(name=name)
        action.connect("activate", lambda _a, _p, fn=handler: fn())
        group.add_action(action)
    language = Gio.SimpleAction.new_stateful(
        "language", GLib.VariantType.new("s"), GLib.Variant("s", get_language())
    )
    language.connect("activate", on_language)
    group.add_action(language)
    window.insert_action_group("win", group)

    shortcuts = Gtk.ShortcutController(scope=Gtk.ShortcutScope.GLOBAL)
    for accel, name in SHORTCUTS:
        shortcuts.add_shortcut(
            Gtk.Shortcut(
                trigger=Gtk.ShortcutTrigger.parse_string(accel),
                action=Gtk.NamedAction.new(f"win.{name}"),
            )
        )
    window.add_controller(shortcuts)


def show_about(parent: Gtk.Window) -> None:
    """Finestra Informazioni con versione e licenza."""
    Gtk.AboutDialog(
        transient_for=parent,
        modal=True,
        program_name="Command Quiver",
        version=__version__,
        comments=t("about.comments"),
        logo_icon_name="icon",
        license_type=Gtk.License.APACHE_2_0,
    ).present()
