"""Avvisi: un messaggio semplice non copre "Annulla", ma non va perso."""

from unittest.mock import MagicMock

from tests.conftest import requires_display


@requires_display
def test_plain_message_waits_for_action_toast_then_shows(gtk_init) -> None:
    from gi.repository import Gtk

    from command_quiver.ui.toast import ToastOverlay

    toast = ToastOverlay(Gtk.Box())
    toast.show_message("Eliminata: A", action_label="Annulla", on_action=MagicMock())
    toast.show_message("Impossibile scrivere il file")

    assert toast.message == "Eliminata: A"  # Annulla resta raggiungibile
    toast._hide()  # scade la finestra di annullamento
    assert toast.message == "Impossibile scrivere il file"
    toast.cancel()


@requires_display
def test_plain_message_after_undo_click_shows(gtk_init) -> None:
    from gi.repository import Gtk

    from command_quiver.ui.toast import ToastOverlay

    toast = ToastOverlay(Gtk.Box())
    undo = MagicMock()
    toast.show_message("Eliminata: A", action_label="Annulla", on_action=undo)
    toast.show_message("Copiato: B")
    toast._on_action_clicked(None)

    undo.assert_called_once()
    assert toast.message == "Copiato: B"
    toast.cancel()
