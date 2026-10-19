"""Test per il modulo executor: esecuzione comandi in terminale."""

import subprocess
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


def _script_for(command: str) -> str:
    """Lo script bash che gnome-terminal riceverebbe per ``command``."""
    with (
        patch("command_quiver.core.executor.shutil.which", return_value="/usr/bin/gnome-terminal"),
        patch("command_quiver.core.executor.subprocess.Popen") as popen,
    ):
        execute_in_terminal(command)
    argv = popen.call_args.args[0]
    assert argv[:4] == ["gnome-terminal", "--", "bash", "-c"]
    return argv[4]


def _run_in_bash(script: str) -> str:
    # stdin chiuso: la read finale torna subito invece di attendere INVIO
    result = subprocess.run(
        ["bash", "-c", script], stdin=subprocess.DEVNULL, capture_output=True, text=True
    )
    return result.stdout


@pytest.mark.parametrize(
    "command",
    ["echo prima", "echo prima # elenco", "false"],
    ids=["plain", "trailing-comment", "failing-command"],
)
def test_terminal_script_always_shows_press_enter_after_the_command(command: str) -> None:
    """Regressione B15: il terminale resta aperto anche con un commento finale o un errore.

    Con ";" un "# commento" in coda al comando commentava via anche il messaggio
    e la read: il terminale si chiudeva subito, contro la docstring.
    """
    from command_quiver.core.i18n import t

    output = _run_in_bash(_script_for(command))

    assert output.rstrip("\n").endswith(t("executor.press_enter").strip())


def test_terminal_script_runs_the_command_literally() -> None:
    """Positivo appaiato: il comando dell'utente viene eseguito, prima del messaggio."""
    output = _run_in_bash(_script_for("echo prima"))

    assert output.startswith("prima\n")
