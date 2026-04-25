"""Esecuzione comandi shell in una nuova finestra gnome-terminal."""

import logging
import shlex
import shutil
import subprocess

from command_quiver.core.i18n import t

logger = logging.getLogger(__name__)


class TerminalNotFoundError(Exception):
    """Eccezione sollevata quando gnome-terminal non è installato."""

    def __init__(self) -> None:
        super().__init__(t("executor.terminal_not_found"))


def execute_in_terminal(command: str) -> bool:
    """Apre una nuova finestra gnome-terminal ed esegue il comando.

    Il terminale resta aperto dopo l'esecuzione per permettere
    all'utente di leggere l'output.

    Parameters
    ----------
    command : str
        Comando shell da eseguire.

    Returns
    -------
    bool
        True se il terminale è stato lanciato con successo.

    Raises
    ------
    TerminalNotFoundError
        Se gnome-terminal non è installato nel sistema.
    """
    if not shutil.which("gnome-terminal"):
        raise TerminalNotFoundError()

    # Il comando utente viene quotato per evitare che caratteri speciali
    # nel prompt di "premi INVIO" rompano la concatenazione bash.
    # Il comando stesso viene eseguito letteralmente (è ciò che l'utente vuole).
    press_enter_msg = t("executor.press_enter")
    wrapped = f"{command}; echo {shlex.quote(press_enter_msg)}; read"

    try:
        subprocess.Popen(
            ["gnome-terminal", "--", "bash", "-c", wrapped],
        )
        logger.info("Comando eseguito in terminale: %s", command[:80])
        return True
    except OSError:
        logger.exception("Errore avvio gnome-terminal")
        return False
