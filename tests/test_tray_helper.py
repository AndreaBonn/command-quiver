"""Test per tray_helper — comunicazione D-Bus e callback menu.

Il modulo tray_helper importa GTK3 a livello modulo, incompatibile con
GTK4 usato dagli altri test. Tutti i test usano subprocess per isolamento.
"""

import subprocess
import sys


class TestTrayHelperUnit:
    """Test funzioni tray_helper eseguiti in subprocess isolato."""

    def _run_test_code(self, code: str) -> subprocess.CompletedProcess:
        """Esegue codice Python in un processo separato per isolare GTK3."""
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result

    def test_send_dbus_signal_calls_bus(self) -> None:
        result = self._run_test_code("""
from unittest.mock import MagicMock, patch

with patch("command_quiver.tray_helper.Gio") as mock_gio:
    mock_bus = MagicMock()
    mock_gio.bus_get_sync.return_value = mock_bus
    from command_quiver.tray_helper import send_dbus_signal, APP_ID, DBUS_PATH, DBUS_INTERFACE
    send_dbus_signal("Toggle")
    assert mock_bus.call_sync.called, "D-Bus call_sync not called"
    args = mock_bus.call_sync.call_args[0]
    assert args[0] == APP_ID
    assert args[1] == DBUS_PATH
    assert args[2] == DBUS_INTERFACE
    assert args[3] == "Toggle"
print("OK")
""")
        assert result.returncode == 0, f"STDERR: {result.stderr}"
        assert "OK" in result.stdout

    def test_send_dbus_signal_handles_error(self) -> None:
        result = self._run_test_code("""
from unittest.mock import MagicMock, patch

with patch("command_quiver.tray_helper.Gio") as mock_gio, \
     patch("command_quiver.tray_helper.GLib") as mock_glib:
    mock_bus = MagicMock()
    mock_gio.bus_get_sync.return_value = mock_bus
    mock_bus.call_sync.side_effect = mock_glib.Error("fail")
    from command_quiver.tray_helper import send_dbus_signal
    send_dbus_signal("Toggle")  # Non deve sollevare eccezione
print("OK")
""")
        assert result.returncode == 0, f"STDERR: {result.stderr}"
        assert "OK" in result.stdout

    def test_on_show_sends_toggle(self) -> None:
        result = self._run_test_code("""
from unittest.mock import patch
with patch("command_quiver.tray_helper.send_dbus_signal") as mock_send:
    from command_quiver.tray_helper import on_show
    on_show(None)
    assert mock_send.call_args[0][0] == "Toggle"
print("OK")
""")
        assert result.returncode == 0, f"STDERR: {result.stderr}"

    def test_on_new_entry_sends_new_entry(self) -> None:
        result = self._run_test_code("""
from unittest.mock import patch
with patch("command_quiver.tray_helper.send_dbus_signal") as mock_send:
    from command_quiver.tray_helper import on_new_entry
    on_new_entry(None)
    assert mock_send.call_args[0][0] == "NewEntry"
print("OK")
""")
        assert result.returncode == 0, f"STDERR: {result.stderr}"

    def test_on_quit_sends_quit_and_exits(self) -> None:
        result = self._run_test_code("""
from unittest.mock import patch, MagicMock
with patch("command_quiver.tray_helper.send_dbus_signal") as mock_send, \
     patch("command_quiver.tray_helper.Gtk") as mock_gtk:
    from command_quiver.tray_helper import on_quit
    on_quit(None)
    assert mock_send.call_args[0][0] == "Quit"
    assert mock_gtk.main_quit.called
print("OK")
""")
        assert result.returncode == 0, f"STDERR: {result.stderr}"

    def test_language_selected_active_sends_dbus(self) -> None:
        result = self._run_test_code("""
from unittest.mock import patch, MagicMock
with patch("command_quiver.tray_helper.Gio") as mock_gio, \
     patch("command_quiver.tray_helper.GLib"):
    mock_bus = MagicMock()
    mock_gio.bus_get_sync.return_value = mock_bus
    from command_quiver.tray_helper import _on_language_selected
    mock_item = MagicMock()
    mock_item.get_active.return_value = True
    _on_language_selected(mock_item, "en")
    assert mock_bus.call_sync.called
    assert mock_bus.call_sync.call_args[0][3] == "ChangeLanguage"
print("OK")
""")
        assert result.returncode == 0, f"STDERR: {result.stderr}"

    def test_language_selected_inactive_noop(self) -> None:
        result = self._run_test_code("""
from unittest.mock import patch, MagicMock
with patch("command_quiver.tray_helper.Gio") as mock_gio:
    mock_bus = MagicMock()
    mock_gio.bus_get_sync.return_value = mock_bus
    from command_quiver.tray_helper import _on_language_selected
    mock_item = MagicMock()
    mock_item.get_active.return_value = False
    _on_language_selected(mock_item, "en")
    assert not mock_bus.call_sync.called
print("OK")
""")
        assert result.returncode == 0, f"STDERR: {result.stderr}"

    def test_setup_logging_creates_log_dir(self, tmp_path) -> None:
        result = self._run_test_code(f"""
from unittest.mock import patch
from pathlib import Path
with patch("command_quiver.tray_helper.Path.home", return_value=Path("{tmp_path}")):
    from command_quiver.tray_helper import _setup_logging
    _setup_logging()
log_dir = Path("{tmp_path}") / ".local" / "share" / "command-quiver" / "logs"
assert log_dir.exists(), f"Log dir not created: {{log_dir}}"
assert (log_dir / "tray.log").exists(), "tray.log not created"
print("OK")
""")
        assert result.returncode == 0, f"STDERR: {result.stderr}"
