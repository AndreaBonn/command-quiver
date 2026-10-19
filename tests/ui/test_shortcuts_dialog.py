"""Test per la finestra delle scorciatoie da tastiera."""

import pytest

from command_quiver.core import i18n
from tests.conftest import requires_display


@pytest.fixture(autouse=True)
def italian() -> None:
    i18n.init("it")


def _labels(widget) -> list[str]:
    from gi.repository import Gtk

    found = []
    child = widget.get_first_child()
    while child is not None:
        if isinstance(child, Gtk.Label):
            found.append(child.get_label())
        found.extend(_labels(child))
        child = child.get_next_sibling()
    return found


def _dialog():
    from gi.repository import Gtk

    from command_quiver.ui.shortcuts_dialog import ShortcutsDialog

    return ShortcutsDialog(parent=Gtk.Window())


def _press_key(dialog, keyval: int) -> bool:
    """Emette key-pressed sul controller di tastiera della finestra, come farebbe GTK."""
    from gi.repository import Gtk

    controllers = dialog.observe_controllers()
    keys = next(
        c
        for c in (controllers.get_item(i) for i in range(controllers.get_n_items()))
        if isinstance(c, Gtk.EventControllerKey)
    )
    return bool(keys.emit("key-pressed", keyval, 0, 0))


def _find_label(dialog, text: str):
    from gi.repository import Gtk

    stack = [dialog]
    while stack:
        widget = stack.pop()
        if isinstance(widget, Gtk.Label) and widget.get_label() == text:
            return widget
        child = widget.get_first_child()
        while child is not None:
            stack.append(child)
            child = child.get_next_sibling()
    raise AssertionError(f"label {text!r} non trovata")


@requires_display
def test_shortcuts_dialog_lists_search_shortcut_with_description(gtk_init) -> None:
    labels = _labels(_dialog())

    assert "Ctrl+F" in labels
    assert i18n.t("shortcuts.search") in labels


@requires_display
def test_shortcuts_dialog_shows_quit_shortcut_with_description(gtk_init) -> None:
    labels = _labels(_dialog())

    assert "Ctrl+Q" in labels
    assert i18n.t("shortcuts.quit") in labels


@requires_display
def test_shortcuts_dialog_combination_and_description_share_the_same_row(gtk_init) -> None:
    from gi.repository import Gtk

    dialog = _dialog()
    grid = dialog.get_child()
    assert isinstance(grid, Gtk.Grid)

    combo = _find_label(dialog, "Ctrl+N")
    description = _find_label(dialog, i18n.t("shortcuts.new"))
    other = _find_label(dialog, i18n.t("shortcuts.search"))

    def row_of(widget) -> int:
        return grid.query_child(widget)[1]

    assert row_of(combo) == row_of(description)
    assert row_of(combo) != row_of(other)


@requires_display
def test_shortcuts_dialog_follows_current_language(gtk_init) -> None:
    italian_text = i18n.t("shortcuts.search")
    i18n.init("en")
    try:
        labels = _labels(_dialog())
        english_text = i18n.t("shortcuts.search")
    finally:
        i18n.init("it")

    assert english_text in labels
    assert english_text != italian_text
    assert italian_text not in labels


@requires_display
def test_shortcuts_dialog_uses_localized_title(gtk_init) -> None:
    assert _dialog().get_title() == i18n.t("shortcuts.title")


@requires_display
def test_shortcuts_dialog_escape_closes_window(gtk_init) -> None:
    from gi.repository import Gdk

    dialog = _dialog()
    dialog.present()

    handled = _press_key(dialog, Gdk.KEY_Escape)

    assert handled is True
    assert not dialog.get_visible()


@requires_display
def test_shortcuts_dialog_other_key_keeps_window_open(gtk_init) -> None:
    from gi.repository import Gdk

    dialog = _dialog()
    dialog.present()

    handled = _press_key(dialog, Gdk.KEY_a)

    assert handled is False
    assert dialog.get_visible()
    dialog.close()
