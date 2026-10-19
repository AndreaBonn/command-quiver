"""Riga di stato: reagisce solo a esiti reali di sincronizzazione."""

from unittest.mock import MagicMock

import pytest

from command_quiver.core.i18n import init as i18n_init
from command_quiver.core.settings import Settings
from tests.conftest import requires_display


@pytest.fixture(autouse=True)
def _italian() -> None:
    i18n_init("it")


def _enabled() -> Settings:
    settings = Settings()
    settings.sync.enabled = True
    return settings


@requires_display
class TestSyncStatusBar:
    def test_reset_forgets_the_previous_outcome(self, gtk_init) -> None:
        from command_quiver.ui.status_bar import SyncStatusBar

        bar = SyncStatusBar(_enabled(), on_open_sync=MagicMock())
        bar.set_result(success=False, pulled=0, pushed=0, message="Token scaduto")
        assert bar.text == "Sincronizzazione non riuscita"
        assert bar.get_tooltip_text() == "Token scaduto"

        bar.reset()

        assert bar.text == "Non ancora sincronizzato"
        assert bar.get_tooltip_text() is None

    def test_error_state_offers_the_action_that_opens_sync(self, gtk_init) -> None:
        from command_quiver.ui.status_bar import SyncStatusBar

        opened = MagicMock()
        bar = SyncStatusBar(_enabled(), on_open_sync=opened)
        bar.set_result(success=False, pulled=0, pushed=0, message="x")
        action = [b for b in _buttons(bar) if b.get_visible()]
        assert len(action) == 1

        action[0].emit("clicked")

        opened.assert_called_once_with()

    def test_pending_state_hides_the_action_that_local_state_shows(self, gtk_init) -> None:
        from command_quiver.ui.status_bar import SyncStatusBar

        bar = SyncStatusBar(Settings(), on_open_sync=MagicMock())
        assert [b for b in _buttons(bar) if b.get_visible()] != []  # locale: invita ad attivare

        enabled = SyncStatusBar(_enabled(), on_open_sync=MagicMock())
        enabled.set_pending()

        assert enabled.text == "Sincronizzazione in corso…"
        assert [b for b in _buttons(enabled) if b.get_visible()] == []


def _buttons(widget):
    from gi.repository import Gtk

    from tests.conftest import descendants

    return [w for w in descendants(widget) if isinstance(w, Gtk.Button)]
