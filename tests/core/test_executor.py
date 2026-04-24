"""Test per il modulo executor: esecuzione comandi in terminale."""

from unittest.mock import patch

import pytest

from command_quiver.core.executor import TerminalNotFoundError, execute_in_terminal


class TestExecuteInTerminal:
    """Test esecuzione comandi shell."""

    def test_raises_when_terminal_not_found(self) -> None:
        with (
            patch("command_quiver.core.executor.shutil.which", return_value=None),
            pytest.raises(TerminalNotFoundError),
        ):
            execute_in_terminal("echo hello")

    def test_returns_true_on_success(self) -> None:
        with (
            patch(
                "command_quiver.core.executor.shutil.which", return_value="/usr/bin/gnome-terminal"
            ),
            patch("command_quiver.core.executor.subprocess.Popen") as mock_popen,
        ):
            result = execute_in_terminal("echo hello")
            assert result is True
            mock_popen.assert_called_once()

    def test_returns_false_on_os_error(self) -> None:
        with (
            patch(
                "command_quiver.core.executor.shutil.which", return_value="/usr/bin/gnome-terminal"
            ),
            patch("command_quiver.core.executor.subprocess.Popen", side_effect=OSError("fail")),
        ):
            result = execute_in_terminal("echo hello")
            assert result is False

    def test_command_wrapping_includes_read(self) -> None:
        with (
            patch(
                "command_quiver.core.executor.shutil.which", return_value="/usr/bin/gnome-terminal"
            ),
            patch("command_quiver.core.executor.subprocess.Popen") as mock_popen,
        ):
            execute_in_terminal("ls -la")
            args = mock_popen.call_args[0][0]
            # args: ['gnome-terminal', '--', 'bash', '-c', '<wrapped>']
            wrapped_cmd = args[4]
            assert "ls -la" in wrapped_cmd
            assert "read" in wrapped_cmd


class TestTerminalNotFoundError:
    """Test eccezione personalizzata."""

    def test_message_contains_install_instruction(self) -> None:
        err = TerminalNotFoundError()
        assert "gnome-terminal" in str(err)
        assert "apt install" in str(err)
