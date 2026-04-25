"""Test per CommandQuiverApp — logica applicazione, lifecycle e tray management."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from command_quiver import APP_ID


class TestCommandQuiverAppInit:
    """Test inizializzazione applicazione."""

    def test_app_has_correct_application_id(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            assert app.get_application_id() == APP_ID

    def test_app_initial_state(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            assert app._db is None
            assert app._settings is None
            assert app._sidebar is None
            assert app._tray_process is None
            assert app._tray_health_source == 0


class TestTrayHelperManagement:
    """Test gestione processo tray helper."""

    def test_stop_tray_helper_terminates_running_process(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_process = MagicMock(spec=subprocess.Popen)
            mock_process.poll.return_value = None  # Processo attivo
            app._tray_process = mock_process

            app._stop_tray_helper()

            mock_process.terminate.assert_called_once()
            mock_process.wait.assert_called_once_with(timeout=3)

    def test_stop_tray_helper_kills_after_timeout(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_process = MagicMock(spec=subprocess.Popen)
            mock_process.poll.return_value = None
            mock_process.wait.side_effect = subprocess.TimeoutExpired(cmd="tray", timeout=3)
            app._tray_process = mock_process

            app._stop_tray_helper()

            mock_process.kill.assert_called_once()

    def test_stop_tray_helper_noop_when_already_dead(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_process = MagicMock(spec=subprocess.Popen)
            mock_process.poll.return_value = 0  # Già terminato
            app._tray_process = mock_process

            app._stop_tray_helper()

            mock_process.terminate.assert_not_called()

    def test_stop_tray_helper_noop_when_no_process(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._tray_process = None

            # Non deve sollevare eccezione
            app._stop_tray_helper()

    def test_stop_tray_helper_closes_stderr_file(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_process = MagicMock(spec=subprocess.Popen)
            mock_process.poll.return_value = None
            app._tray_process = mock_process
            mock_stderr = MagicMock()
            app._tray_stderr_file = mock_stderr

            app._stop_tray_helper()

            mock_stderr.close.assert_called_once()
            assert app._tray_stderr_file is None

    def test_launch_tray_process_returns_true_on_success(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.subprocess.Popen") as mock_popen,
        ):
            from command_quiver.app import CommandQuiverApp

            mock_popen.return_value = MagicMock(pid=1234)
            app = CommandQuiverApp()
            app._tray_helper_path = Path("/fake/tray_helper.py")

            result = app._launch_tray_process()

            assert result is True
            assert app._tray_process is not None

    def test_launch_tray_process_returns_false_on_oserror(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.subprocess.Popen", side_effect=OSError("fail")),
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._tray_helper_path = Path("/fake/tray_helper.py")

            result = app._launch_tray_process()

            assert result is False

    def test_check_tray_health_restarts_crashed_process(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_process = MagicMock(spec=subprocess.Popen)
            mock_process.poll.return_value = 1  # Crashato
            mock_process.returncode = 1
            app._tray_process = mock_process
            app._tray_helper_path = Path("/fake/tray_helper.py")

            with patch.object(app, "_launch_tray_process") as mock_launch:
                result = app._check_tray_health()

            assert result is True  # Continua polling
            mock_launch.assert_called_once()

    def test_check_tray_health_noop_when_running(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_process = MagicMock(spec=subprocess.Popen)
            mock_process.poll.return_value = None  # Attivo
            app._tray_process = mock_process

            with patch.object(app, "_launch_tray_process") as mock_launch:
                result = app._check_tray_health()

            assert result is True
            mock_launch.assert_not_called()

    def test_check_tray_health_stops_polling_when_no_process(self) -> None:
        with patch("command_quiver.app.Gtk"), patch("command_quiver.app.Gdk"):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            app._tray_process = None

            result = app._check_tray_health()

            assert result is False  # Rimuovi timeout


class TestQuitApp:
    """Test chiusura ordinata."""

    def test_quit_saves_settings_and_closes_db(self) -> None:
        with (
            patch("command_quiver.app.Gtk"),
            patch("command_quiver.app.Gdk"),
            patch("command_quiver.app.save_settings") as mock_save,
        ):
            from command_quiver.app import CommandQuiverApp

            app = CommandQuiverApp()
            mock_db = MagicMock()
            mock_settings = MagicMock()
            app._db = mock_db
            app._settings = mock_settings
            app._tray_process = None

            # Mock metodi GTK che richiedono un'app registrata
            with (
                patch.object(app, "release"),
                patch.object(app, "quit"),
            ):
                app._quit_app()

            mock_save.assert_called_once_with(mock_settings)
            mock_db.close.assert_called_once()
