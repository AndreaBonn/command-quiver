"""Test per la conferma di esecuzione: richiesta, "non chiedere più" e annulla."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from command_quiver.core import i18n
from command_quiver.core import settings as settings_module
from command_quiver.core.settings import Settings, load_settings
from command_quiver.db.models import Entry
from tests.conftest import requires_display, wait_until

_EXECUTE = "command_quiver.ui.entry_list.execute_in_terminal"


@pytest.fixture(autouse=True)
def italian() -> None:
    i18n.init("it")


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


@pytest.fixture(autouse=True)
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """save_settings senza argomenti scrive nel path di default: va su tmp_path."""
    path = tmp_path / "settings.json"
    monkeypatch.setattr(settings_module, "DEFAULT_CONFIG_PATH", path)
    return path


def _entry(uuid: str = "uuid-1", content: str = "echo hello") -> Entry:
    return Entry(id=7, name="Saluto", content=content, type="shell", uuid=uuid)


def _descendants(widget):
    child = widget.get_first_child()
    while child is not None:
        yield child
        yield from _descendants(child)
        child = child.get_next_sibling()


def _button(dialog, label: str):
    from gi.repository import Gtk

    return next(
        w for w in _descendants(dialog) if isinstance(w, Gtk.Button) and w.get_label() == label
    )


def _labels(dialog) -> list[str]:
    from gi.repository import Gtk

    return [w.get_label() for w in _descendants(dialog) if isinstance(w, Gtk.Label)]


def _checkbox(dialog):
    from gi.repository import Gtk

    return next(w for w in _descendants(dialog) if isinstance(w, Gtk.CheckButton))


@requires_display
class TestRequestRun:
    def test_request_run_entry_in_skip_list_runs_without_dialog(self, gtk_init) -> None:
        from gi.repository import Gtk

        from command_quiver.ui.run_confirm import request_run

        on_use = MagicMock()
        settings = Settings(skip_run_confirm=["uuid-1"])
        with (
            patch(_EXECUTE) as execute,
            patch("command_quiver.ui.run_confirm.RunConfirmDialog") as dlg,
        ):
            request_run(Gtk.Window(), _entry(), settings, on_use)

        execute.assert_called_once_with("echo hello")
        on_use.assert_called_once_with(7)
        dlg.assert_not_called()

    def test_request_run_entry_not_in_skip_list_asks_and_does_not_run(self, gtk_init) -> None:
        from gi.repository import Gtk

        from command_quiver.ui.run_confirm import request_run

        on_use = MagicMock()
        with (
            patch(_EXECUTE) as execute,
            patch("command_quiver.ui.run_confirm.RunConfirmDialog") as dlg,
        ):
            request_run(Gtk.Window(), _entry(), Settings(skip_run_confirm=["altro"]), on_use)

        dlg.assert_called_once()
        dlg.return_value.present.assert_called_once()
        execute.assert_not_called()
        on_use.assert_not_called()

    def test_request_run_entry_without_uuid_always_asks(self, gtk_init) -> None:
        from gi.repository import Gtk

        from command_quiver.ui.run_confirm import request_run

        # Una voce senza uuid non può essere ricordata, nemmeno con "" in lista
        with (
            patch(_EXECUTE) as execute,
            patch("command_quiver.ui.run_confirm.RunConfirmDialog") as dlg,
        ):
            request_run(Gtk.Window(), _entry(uuid=""), Settings(skip_run_confirm=[""]), MagicMock())

        dlg.assert_called_once()
        execute.assert_not_called()

    def _confirm_from_dialog(self, remember: bool) -> None:
        """Apre il dialog via request_run e simula la conferma dell'utente."""
        from gi.repository import Gtk

        from command_quiver.ui import run_confirm

        captured = {}

        def fake_dialog(parent, entry, on_confirm):
            captured["on_confirm"] = on_confirm
            return MagicMock()

        with patch.object(run_confirm, "RunConfirmDialog", fake_dialog):
            run_confirm.request_run(Gtk.Window(), _entry(), Settings(), MagicMock())
            captured["on_confirm"](_entry(), remember)

    def test_request_run_dialog_confirm_runs_the_command(self, gtk_init) -> None:
        with patch(_EXECUTE) as execute:
            self._confirm_from_dialog(remember=False)

        execute.assert_called_once_with("echo hello")

    def test_request_run_dialog_confirm_with_remember_persists_uuid(
        self, gtk_init, isolated_config: Path
    ) -> None:
        with patch(_EXECUTE):
            self._confirm_from_dialog(remember=True)

        assert load_settings(isolated_config).skip_run_confirm == ["uuid-1"]


@requires_display
class TestConfirmAndRun:
    def test_confirm_and_run_remember_saves_uuid_and_runs(
        self, gtk_init, isolated_config: Path
    ) -> None:
        from gi.repository import Gtk

        from command_quiver.ui.run_confirm import confirm_and_run

        settings = Settings()
        on_use = MagicMock()
        with patch(_EXECUTE) as execute:
            confirm_and_run(Gtk.Window(), _entry(), settings, on_use, remember=True)

        assert settings.skip_run_confirm == ["uuid-1"]
        assert load_settings(isolated_config).skip_run_confirm == ["uuid-1"]
        execute.assert_called_once_with("echo hello")
        on_use.assert_called_once_with(7)

    def test_confirm_and_run_without_remember_runs_but_does_not_persist(
        self, gtk_init, isolated_config: Path
    ) -> None:
        from gi.repository import Gtk

        from command_quiver.ui.run_confirm import confirm_and_run

        settings = Settings()
        with patch(_EXECUTE) as execute:
            confirm_and_run(Gtk.Window(), _entry(), settings, MagicMock(), remember=False)

        assert settings.skip_run_confirm == []
        assert not isolated_config.exists()
        execute.assert_called_once()

    def test_confirm_and_run_remember_twice_keeps_single_uuid(
        self, gtk_init, isolated_config: Path
    ) -> None:
        from gi.repository import Gtk

        from command_quiver.ui.run_confirm import confirm_and_run

        settings = Settings(skip_run_confirm=["uuid-1"])
        with patch(_EXECUTE):
            confirm_and_run(Gtk.Window(), _entry(), settings, MagicMock(), remember=True)

        assert settings.skip_run_confirm == ["uuid-1"]
        assert not isolated_config.exists()  # già presente: niente scrittura inutile

    def test_confirm_and_run_remember_without_uuid_is_not_persisted(
        self, gtk_init, isolated_config: Path
    ) -> None:
        from gi.repository import Gtk

        from command_quiver.ui.run_confirm import confirm_and_run

        settings = Settings()
        with patch(_EXECUTE) as execute:
            confirm_and_run(Gtk.Window(), _entry(uuid=""), settings, MagicMock(), remember=True)

        assert settings.skip_run_confirm == []
        assert not isolated_config.exists()
        execute.assert_called_once()  # il comando parte comunque

    def test_confirm_and_run_terminal_missing_skips_on_use(self, gtk_init) -> None:
        from command_quiver.core.executor import TerminalNotFoundError
        from command_quiver.ui.run_confirm import confirm_and_run

        on_use = MagicMock()
        with patch(_EXECUTE, side_effect=TerminalNotFoundError()):
            confirm_and_run(None, _entry(), Settings(), on_use, remember=False)

        on_use.assert_not_called()


@requires_display
class TestRunConfirmDialog:
    def _dialog(self, content: str = "echo hello"):
        from gi.repository import Gtk

        from command_quiver.ui.run_confirm import RunConfirmDialog

        on_confirm = MagicMock()
        dialog = RunConfirmDialog(
            parent=Gtk.Window(), entry=_entry(content=content), on_confirm=on_confirm
        )
        return dialog, on_confirm

    def test_dialog_shows_entry_name_and_exact_command(self, gtk_init) -> None:
        dialog, _ = self._dialog(content="rm -rf /tmp/demo")

        labels = _labels(dialog)

        assert "Saluto" in labels
        assert "rm -rf /tmp/demo" in labels

    def test_dialog_truncates_very_long_command_preview(self, gtk_init) -> None:
        dialog, _ = self._dialog(content="x" * 2000)

        previews = [text for text in _labels(dialog) if text.startswith("xxx")]

        assert len(previews) == 1
        assert 0 < len(previews[0]) < 2000
        assert set(previews[0]) == {"x"}  # prefisso del comando, non altro testo

    def test_dialog_confirm_without_checkbox_reports_remember_false(self, gtk_init) -> None:
        dialog, on_confirm = self._dialog()

        _button(dialog, i18n.t("run.run")).emit("clicked")

        on_confirm.assert_called_once()
        entry, remember = on_confirm.call_args.args
        assert entry.uuid == "uuid-1"
        assert remember is False

    def test_dialog_confirm_with_checkbox_reports_remember_true(self, gtk_init) -> None:
        dialog, on_confirm = self._dialog()
        _checkbox(dialog).set_active(True)

        _button(dialog, i18n.t("run.run")).emit("clicked")

        assert on_confirm.call_args.args[1] is True

    def test_dialog_cancel_button_closes_without_confirming(self, gtk_init) -> None:
        dialog, on_confirm = self._dialog()
        dialog.present()

        _button(dialog, i18n.t("common.cancel")).emit("clicked")

        assert not dialog.get_visible()
        on_confirm.assert_not_called()

    def test_dialog_escape_closes_without_confirming(self, gtk_init) -> None:
        from gi.repository import Gdk

        dialog, on_confirm = self._dialog()
        dialog.present()

        handled = _press_key(dialog, Gdk.KEY_Escape)

        assert handled is True
        assert not dialog.get_visible()
        on_confirm.assert_not_called()

    def test_dialog_enter_runs_through_the_default_button(self, gtk_init) -> None:
        """Docstring: "Invio esegue". Invio attiva il pulsante di default, cioè Esegui."""
        dialog, on_confirm = self._dialog()
        dialog.present()
        # Caso reale: l'utente ha appena spuntato "non chiedere più", il focus è lì
        _checkbox(dialog).set_active(True)
        _checkbox(dialog).grab_focus()

        # L'azione che GTK lega a Invio; il clic arriva dopo l'animazione del pulsante
        dialog.activate_action("default.activate", None)

        assert wait_until(lambda: on_confirm.call_count == 1)
        assert on_confirm.call_args.args[1] is True

    def test_dialog_focus_starts_on_run_not_on_the_selectable_command(self, gtk_init) -> None:
        dialog, _ = self._dialog()

        assert dialog.get_focus() is _button(dialog, i18n.t("run.run"))

    def test_dialog_other_key_is_not_handled_and_keeps_dialog_open(self, gtk_init) -> None:
        from gi.repository import Gdk

        dialog, on_confirm = self._dialog()
        dialog.present()

        handled = _press_key(dialog, Gdk.KEY_a)

        assert handled is False
        assert dialog.get_visible()
        on_confirm.assert_not_called()
        dialog.close()

    def test_dialog_confirm_closes_window(self, gtk_init) -> None:
        dialog, _ = self._dialog()
        dialog.present()

        dialog.confirm()

        assert not dialog.get_visible()
