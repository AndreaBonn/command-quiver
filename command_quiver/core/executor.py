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

    # Il comando gira letteralmente in una bash annidata: un errore di sintassi
    # (virgolette o blocco non chiusi) o un "exit" fermano solo quella, e il
    # messaggio con la read che tiene aperto il terminale arriva comunque.
    # Concatenato allo script, un errore di sintassi impediva il parsing di tutto.
    # A capo e non ";" fra i comandi, come per il "# commento" finale della regressione B15.
    press_enter_msg = t("executor.press_enter")
    wrapped = f"bash -c {shlex.quote(command)}\necho {shlex.quote(press_enter_msg)}\nread"

    try:
        subprocess.Popen(
            ["gnome-terminal", "--", "bash", "-c", wrapped],
        )
        logger.info("Comando eseguito in terminale: %s", command[:80])
        return True
    except OSError:
        logger.exception("Errore avvio gnome-terminal")
        return False
