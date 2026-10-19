"""Test della finestra di sincronizzazione: campo repository unico ed errori azionabili."""

from unittest.mock import patch

import pytest

from command_quiver.core.github_client import ConnectionStatus
from command_quiver.core.i18n import init as i18n_init
from command_quiver.core.settings import Settings
from tests.conftest import requires_display


@pytest.fixture(autouse=True)
def _italian() -> None:
    i18n_init("it")


@pytest.mark.parametrize("status", list(ConnectionStatus))
def test_every_connection_status_has_a_message(status: ConnectionStatus) -> None:
    from command_quiver.ui.sync_dialog import connection_message

    message = connection_message(status)
    assert message and not message.startswith("sync.conn_")


@requires_display
class TestSyncDialog:
    def _dialog(self, settings: Settings):
        from gi.repository import Gtk

        from command_quiver.ui.sync_dialog import SyncSetupDialog

        with patch("command_quiver.ui.sync_dialog.load_sync_token", return_value=""):
            return SyncSetupDialog(parent=Gtk.Window(), settings=settings)

    def test_existing_config_shown_as_single_field(self, gtk_init) -> None:
        settings = Settings()
        settings.sync.repo_owner = "mrossi"
        settings.sync.repo_name = "vault"
        assert self._dialog(settings)._repo_entry.get_text() == "mrossi/vault"

    def test_enable_with_pasted_url_saves_owner_and_repo(self, gtk_init) -> None:
        settings = Settings()
        dialog = self._dialog(settings)
        dialog._repo_entry.set_text("https://github.com/mrossi/vault.git")
        dialog._token_entry.set_text("tok")
        with (
            patch("command_quiver.ui.sync_dialog.save_sync_token") as mock_token,
            patch("command_quiver.ui.sync_dialog.save_settings"),
        ):
            dialog._on_toggle_clicked(None)
        assert settings.sync.enabled is True
        assert (settings.sync.repo_owner, settings.sync.repo_name) == ("mrossi", "vault")
        mock_token.assert_called_once_with("tok")

    def test_enable_with_unreadable_repo_explains_format(self, gtk_init) -> None:
        settings = Settings()
        dialog = self._dialog(settings)
        dialog._repo_entry.set_text("solo-utente")
        dialog._token_entry.set_text("tok")
        dialog._on_toggle_clicked(None)
        assert settings.sync.enabled is False
        assert "utente/nome" in dialog._status_label.get_label()

    def test_missing_token_says_what_to_fill(self, gtk_init) -> None:
        dialog = self._dialog(Settings())
        dialog._repo_entry.set_text("mrossi/vault")
        dialog._on_test_clicked(None)
        assert dialog._status_label.get_label() == "Compila repository e token."

    def test_test_result_shows_specific_cause(self, gtk_init) -> None:
        dialog = self._dialog(Settings())
        dialog._on_test_result(ConnectionStatus.BAD_TOKEN)
        assert "scaduto" in dialog._status_label.get_label()

    def test_sync_now_hidden_when_disabled(self, gtk_init) -> None:
        dialog = self._dialog(Settings())
        assert dialog._sync_now_btn.get_visible() is False
