"""Test per il modulo main: logging, entry point."""

import logging
import runpy
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from command_quiver.main import setup_logging


@pytest.fixture(autouse=True)
def _restore_root_logger():
    """setup_logging() modifica handler e livello del root logger: ripristina entrambi."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    for handler in root.handlers:
        if handler not in handlers:
            handler.close()
    root.handlers[:] = handlers
    root.setLevel(level)


class TestSetupLogging:
    """Test configurazione logging."""

    def test_creates_log_directory(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "logs"
        log_file = log_dir / "app.log"

        with (
            patch("command_quiver.main.LOG_DIR", log_dir),
            patch("command_quiver.main.LOG_FILE", log_file),
        ):
            root = logging.getLogger()
            root.handlers.clear()

            setup_logging()

            assert log_dir.exists()

    def test_configures_file_handler_at_debug_level(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "logs"
        log_file = log_dir / "app.log"

        with (
            patch("command_quiver.main.LOG_DIR", log_dir),
            patch("command_quiver.main.LOG_FILE", log_file),
        ):
            root = logging.getLogger()
            root.handlers.clear()

            setup_logging()

            # Deve avere almeno un file handler e uno stream handler
            handler_types = [type(h).__name__ for h in root.handlers]
            assert "RotatingFileHandler" in handler_types
            assert "StreamHandler" in handler_types

            # Root logger a DEBUG
            assert root.level == logging.DEBUG

    def test_log_file_receives_messages(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "logs"
        log_file = log_dir / "app.log"

        with (
            patch("command_quiver.main.LOG_DIR", log_dir),
            patch("command_quiver.main.LOG_FILE", log_file),
        ):
            root = logging.getLogger()
            root.handlers.clear()

            setup_logging()

            test_logger = logging.getLogger("test_main_logger")
            test_logger.info("Messaggio di test")

            # Flush handler
            for handler in root.handlers:
                handler.flush()

            content = log_file.read_text()
            assert "Messaggio di test" in content


class TestMainFunction:
    """Test funzione main()."""

    def test_main_creates_app_and_runs(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "logs"
        log_file = log_dir / "app.log"

        mock_app = MagicMock()
        mock_app.run.return_value = 3

        with (
            patch("command_quiver.main.LOG_DIR", log_dir),
            patch("command_quiver.main.LOG_FILE", log_file),
            patch(
                "command_quiver.app.CommandQuiverApp",
                return_value=mock_app,
            ),
        ):
            root = logging.getLogger()
            root.handlers.clear()

            from command_quiver.main import main

            exit_code = main()

            # Il codice d'uscita dell'app arriva intatto al processo
            assert exit_code == 3
            mock_app.run.assert_called_once()

    def test_version_flag_prints_version_and_exits(self) -> None:
        from command_quiver.main import main

        with patch("command_quiver.main.sys") as mock_sys:
            mock_sys.argv = ["command_quiver", "--version"]
            exit_code = main()

        assert exit_code == 0

    def test_version_short_flag(self) -> None:
        from command_quiver.main import main

        with patch("command_quiver.main.sys") as mock_sys:
            mock_sys.argv = ["command_quiver", "-V"]
            exit_code = main()

        assert exit_code == 0


def test_main_module_version_prints_version_and_exits_successfully(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from command_quiver import APP_NAME, __version__
    from command_quiver import main as main_module

    monkeypatch.setattr("sys.argv", ["command_quiver", "--version"])

    with pytest.raises(SystemExit) as result:
        runpy.run_path(path_name=main_module.__file__, run_name="__main__")

    assert result.value.code == 0
    assert capsys.readouterr().out == f"{APP_NAME} {__version__}\n"
