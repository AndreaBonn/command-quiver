"""Test per il modulo main: logging, entry point."""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

from command_quiver.main import setup_logging


class TestSetupLogging:
    """Test configurazione logging."""

    def test_creates_log_directory(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "logs"
        log_file = log_dir / "app.log"

        with (
            patch("command_quiver.main.LOG_DIR", log_dir),
            patch("command_quiver.main.LOG_FILE", log_file),
        ):
            # Rimuovi handler esistenti per evitare interferenze
            root = logging.getLogger()
            original_handlers = root.handlers[:]
            root.handlers.clear()

            setup_logging()

            assert log_dir.exists()

            # Cleanup: ripristina handler originali
            root.handlers.clear()
            root.handlers.extend(original_handlers)

    def test_configures_file_handler_at_debug_level(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "logs"
        log_file = log_dir / "app.log"

        with (
            patch("command_quiver.main.LOG_DIR", log_dir),
            patch("command_quiver.main.LOG_FILE", log_file),
        ):
            root = logging.getLogger()
            original_handlers = root.handlers[:]
            root.handlers.clear()

            setup_logging()

            # Deve avere almeno un file handler e uno stream handler
            handler_types = [type(h).__name__ for h in root.handlers]
            assert "RotatingFileHandler" in handler_types
            assert "StreamHandler" in handler_types

            # Root logger a DEBUG
            assert root.level == logging.DEBUG

            root.handlers.clear()
            root.handlers.extend(original_handlers)

    def test_log_file_receives_messages(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "logs"
        log_file = log_dir / "app.log"

        with (
            patch("command_quiver.main.LOG_DIR", log_dir),
            patch("command_quiver.main.LOG_FILE", log_file),
        ):
            root = logging.getLogger()
            original_handlers = root.handlers[:]
            root.handlers.clear()

            setup_logging()

            test_logger = logging.getLogger("test_main_logger")
            test_logger.info("Messaggio di test")

            # Flush handler
            for handler in root.handlers:
                handler.flush()

            content = log_file.read_text()
            assert "Messaggio di test" in content

            root.handlers.clear()
            root.handlers.extend(original_handlers)


class TestMainFunction:
    """Test funzione main()."""

    def test_main_creates_app_and_runs(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "logs"
        log_file = log_dir / "app.log"

        mock_app = MagicMock()
        mock_app.run.return_value = 0

        with (
            patch("command_quiver.main.LOG_DIR", log_dir),
            patch("command_quiver.main.LOG_FILE", log_file),
            patch(
                "command_quiver.app.CommandQuiverApp",
                return_value=mock_app,
            ),
        ):
            root = logging.getLogger()
            original_handlers = root.handlers[:]
            root.handlers.clear()

            from command_quiver.main import main

            exit_code = main()

            assert exit_code == 0
            mock_app.run.assert_called_once()

            root.handlers.clear()
            root.handlers.extend(original_handlers)

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
