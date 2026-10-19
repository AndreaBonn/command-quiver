"""Finestra Informazioni e azioni della finestra principale."""

from tests.conftest import requires_display


@requires_display
def test_about_dialog_shows_the_app_version(gtk_init) -> None:
    from gi.repository import Gtk

    from command_quiver import __version__
    from command_quiver.core.i18n import init as i18n_init
    from command_quiver.ui.window_actions import show_about

    i18n_init("it")
    parent = Gtk.Window()
    before = set(Gtk.Window.list_toplevels())

    show_about(parent)

    about = [w for w in Gtk.Window.list_toplevels() if w not in before]
    try:
        assert len(about) == 1
        assert isinstance(about[0], Gtk.AboutDialog)
        assert about[0].get_version() == __version__
        assert about[0].get_program_name() == "Command Quiver"
    finally:
        for window in about:
            window.destroy()
        parent.destroy()
