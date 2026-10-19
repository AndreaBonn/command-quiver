"""Test della finestra di sincronizzazione: campo repository unico ed errori azionabili."""

import json
import threading
from unittest.mock import MagicMock, patch

import pytest

from command_quiver.core.github_client import ConnectionStatus
from command_quiver.core.i18n import init as i18n_init
from command_quiver.core.settings import Settings
from tests.conftest import button_labelled, key_press, requires_display, wait_until


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


def _real_dialog(settings: Settings, on_sync_toggled=None, on_sync_now=None):
    """Dialog con token e impostazioni veri (su tmp via ``isolated_config``)."""
    from gi.repository import Gtk

    from command_quiver.ui.sync_dialog import SyncSetupDialog

    return SyncSetupDialog(
        parent=Gtk.Window(),
        settings=settings,
        on_sync_toggled=on_sync_toggled,
        on_sync_now=on_sync_now,
    )


def _fill(dialog, repo: str = "mrossi/vault", token: str = "tok") -> None:
    dialog._repo_entry.set_text(repo)
    dialog._token_entry.set_text(token)


def _enabled_settings() -> Settings:
    settings = Settings()
    settings.sync.enabled = True
    settings.sync.repo_owner = "mrossi"
    settings.sync.repo_name = "vault"
    return settings


@requires_display
class TestSyncDialogFlows:
    """Salvataggio, attivazione e test di connessione con file veri su tmp e GitHub finto."""

    def test_saved_token_is_prefilled(self, gtk_init, isolated_config) -> None:
        (isolated_config / ".sync_token").write_text("ghp_saved\n", encoding="utf-8")

        assert _real_dialog(Settings())._token_entry.get_text() == "ghp_saved"

    def test_enable_persists_settings_and_token_and_notifies(
        self, gtk_init, isolated_config
    ) -> None:
        settings = Settings()
        toggled = MagicMock()
        dialog = _real_dialog(settings, on_sync_toggled=toggled)
        _fill(dialog, repo="mrossi/vault", token="ghp_new")

        button_labelled(dialog, "Attiva sincronizzazione").emit("clicked")

        saved = json.loads((isolated_config / "settings.json").read_text(encoding="utf-8"))
        assert saved["sync"]["enabled"] is True
        assert (saved["sync"]["repo_owner"], saved["sync"]["repo_name"]) == ("mrossi", "vault")
        token_file = isolated_config / ".sync_token"
        assert token_file.read_text(encoding="utf-8").strip() == "ghp_new"
        assert token_file.stat().st_mode & 0o777 == 0o600
        toggled.assert_called_once_with()
        assert dialog._status_label.get_label() == "Sincronizzazione attiva: la prima parte adesso."
        button_labelled(dialog, "Disattiva sincronizzazione")  # asserisce da sé che esiste

    def test_enable_with_missing_token_saves_nothing(self, gtk_init, isolated_config) -> None:
        toggled = MagicMock()
        dialog = _real_dialog(Settings(), on_sync_toggled=toggled)
        _fill(dialog, token="")

        button_labelled(dialog, "Attiva sincronizzazione").emit("clicked")

        assert not (isolated_config / "settings.json").exists()
        assert not (isolated_config / ".sync_token").exists()
        toggled.assert_not_called()
        assert dialog._status_label.get_label() == "Compila repository e token."

    def test_disable_removes_token_and_persists_off(self, gtk_init, isolated_config) -> None:
        (isolated_config / ".sync_token").write_text("ghp_saved\n", encoding="utf-8")
        toggled = MagicMock()
        dialog = _real_dialog(_enabled_settings(), on_sync_toggled=toggled)

        button_labelled(dialog, "Disattiva sincronizzazione").emit("clicked")

        saved = json.loads((isolated_config / "settings.json").read_text(encoding="utf-8"))
        assert saved["sync"]["enabled"] is False
        assert not (isolated_config / ".sync_token").exists()
        toggled.assert_called_once_with()
        assert "restano su questo computer" in dialog._status_label.get_label()
        button_labelled(dialog, "Attiva sincronizzazione")  # asserisce da sé che esiste

    def test_sync_now_runs_callback_and_closes_dialog(self, gtk_init, isolated_config) -> None:
        sync_now = MagicMock()
        dialog = _real_dialog(_enabled_settings(), on_sync_now=sync_now)
        # Window.close() su una finestra non realizzata non emette nulla
        dialog.realize()
        close_requests: list[bool] = []
        dialog.connect("close-request", lambda _w: close_requests.append(True) or False)

        button_labelled(dialog, "Sincronizza ora").emit("clicked")

        sync_now.assert_called_once_with()
        assert close_requests == [True]

    def test_sync_now_button_visible_only_with_callback_when_enabled(
        self, gtk_init, isolated_config
    ) -> None:
        with_callback = _real_dialog(_enabled_settings(), on_sync_now=MagicMock())
        without_callback = _real_dialog(_enabled_settings())

        assert with_callback._sync_now_btn.get_visible() is True
        assert without_callback._sync_now_btn.get_visible() is False

    def test_escape_closes_dialog_other_keys_do_not(self, gtk_init, isolated_config) -> None:
        from gi.repository import Gdk

        dialog = _real_dialog(Settings())
        # Window.close() su una finestra non realizzata non emette nulla
        dialog.realize()
        close_requests: list[bool] = []
        dialog.connect("close-request", lambda _w: close_requests.append(True) or False)

        assert key_press(dialog, Gdk.KEY_a) is False
        assert close_requests == []
        assert key_press(dialog, Gdk.KEY_Escape) is True
        assert close_requests == [True]


class _BlockingClient:
    """GitHubClient finto: resta in attesa finché il test non lo sblocca."""

    release = threading.Event()
    status = ConnectionStatus.OK
    created_with: dict[str, str] = {}

    def __init__(self, token: str, owner: str, repo: str) -> None:
        type(self).created_with = {"token": token, "owner": owner, "repo": repo}

    def check_connection(self) -> ConnectionStatus:
        type(self).release.wait(timeout=5)
        return type(self).status


@requires_display
class TestConnectionTest:
    @pytest.fixture(autouse=True)
    def _reset_client(self) -> None:
        _BlockingClient.release = threading.Event()
        _BlockingClient.status = ConnectionStatus.OK
        _BlockingClient.created_with = {}

    def test_button_is_locked_while_testing_and_unlocked_after(
        self, gtk_init, isolated_config
    ) -> None:
        dialog = _real_dialog(Settings())
        _fill(dialog)
        with patch("command_quiver.ui.sync_dialog.GitHubClient", _BlockingClient):
            button = button_labelled(dialog, "Testa connessione")
            button.emit("clicked")

            assert button.get_sensitive() is False
            assert dialog._status_label.get_label() == "Verifico…"

            _BlockingClient.release.set()
            assert wait_until(lambda: button.get_sensitive())

    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (ConnectionStatus.OK, "Connessione riuscita"),
            (ConnectionStatus.NETWORK, "GitHub non risponde"),
        ],
    )
    def test_result_message_matches_outcome(
        self, gtk_init, isolated_config, status: ConnectionStatus, expected: str
    ) -> None:
        dialog = _real_dialog(Settings())
        _fill(dialog, repo="https://github.com/mrossi/vault.git", token=" ghp_x ")
        _BlockingClient.status = status
        _BlockingClient.release.set()
        with patch("command_quiver.ui.sync_dialog.GitHubClient", _BlockingClient):
            button_labelled(dialog, "Testa connessione").emit("clicked")

            assert wait_until(lambda: expected in dialog._status_label.get_label())

        assert _BlockingClient.created_with == {
            "token": "ghp_x",
            "owner": "mrossi",
            "repo": "vault",
        }
        assert dialog._status_label.has_css_class("success-label") is (
            status is ConnectionStatus.OK
        )
        assert dialog._status_label.has_css_class("error-label") is (
            status is not ConnectionStatus.OK
        )

    def test_test_with_missing_fields_never_calls_github(self, gtk_init, isolated_config) -> None:
        dialog = _real_dialog(Settings())
        _fill(dialog, token="")
        client = MagicMock()
        with patch("command_quiver.ui.sync_dialog.GitHubClient", client):
            button_labelled(dialog, "Testa connessione").emit("clicked")

        client.assert_not_called()
        assert dialog._status_label.get_label() == "Compila repository e token."
