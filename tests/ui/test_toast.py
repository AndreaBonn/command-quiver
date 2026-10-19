"""Avvisi: un messaggio semplice non copre "Annulla", ma non va perso."""

from unittest.mock import MagicMock

import pytest

from tests.conftest import button_labelled, requires_display, wait_until


@pytest.fixture
def toast(gtk_init):
    from gi.repository import Gtk

    from command_quiver.ui.toast import ToastOverlay

    overlay = ToastOverlay(Gtk.Box())
    yield overlay
    overlay.cancel()


@requires_display
def test_plain_message_waits_for_action_toast_then_shows(toast) -> None:
    toast.show_message("Eliminata: A", action_label="Annulla", on_action=MagicMock(), timeout_ms=30)
    toast.show_message("Impossibile scrivere il file")

    assert toast.message == "Eliminata: A"  # Annulla resta raggiungibile
    # La finestra di annullamento scade da sola: il messaggio in coda compare
    assert wait_until(lambda: toast.message == "Impossibile scrivere il file")


@requires_display
def test_plain_message_after_undo_click_shows(toast) -> None:
    undo = MagicMock()
    toast.show_message("Eliminata: A", action_label="Annulla", on_action=undo)
    toast.show_message("Copiato: B")

    button_labelled(toast, "Annulla").emit("clicked")

    undo.assert_called_once()
    assert toast.message == "Copiato: B"


@requires_display
def test_message_hides_itself_after_its_timeout(toast) -> None:
    toast.show_message("Copiato: Log", timeout_ms=30)
    assert toast.message == "Copiato: Log"

    assert wait_until(lambda: toast.message == "")


@requires_display
def test_undo_clicked_after_its_window_expired_does_nothing(toast, monkeypatch) -> None:
    """Scaduto l'avviso, "Annulla" (ancora visibile mentre si chiude) non annulla più."""
    import sys

    # Un errore in un handler GTK non risale a emit(): PyGObject lo passa a excepthook
    handler_errors: list[BaseException] = []
    monkeypatch.setattr(sys, "excepthook", lambda _t, err, _tb: handler_errors.append(err))
    undo = MagicMock()
    toast.show_message("Eliminata: A", action_label="Annulla", on_action=undo, timeout_ms=30)
    assert wait_until(lambda: toast.message == "")

    button_labelled(toast, "Annulla").emit("clicked")

    undo.assert_not_called()
    assert (toast.message, handler_errors) == ("", [])


@requires_display
def test_undo_clicked_within_its_window_undoes(toast) -> None:
    """Positivo appaiato: prima della scadenza lo stesso clic annulla."""
    undo = MagicMock()
    toast.show_message("Eliminata: A", action_label="Annulla", on_action=undo, timeout_ms=5000)

    button_labelled(toast, "Annulla").emit("clicked")

    undo.assert_called_once_with()
