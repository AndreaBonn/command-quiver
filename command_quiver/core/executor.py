"""Esecuzione comandi shell in una nuova finestra gnome-terminal."""

import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)


class TerminalNotFoundError(Exception):
    """Eccezione sollevata quando gnome-terminal non è installato."""

    def __init__(self) -> None:
        super().__init__(
            "gnome-terminal non trovato. "
            "Installalo con: sudo apt install gnome-terminal"
        )


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

    # Il comando viene wrappato in bash -c con prompt finale
    # per mantenere il terminale aperto dopo l'esecuzione
    wrapped = f'{command}; echo "\\n--- Premere INVIO per chiudere ---"; read'

    try:
        subprocess.Popen(
            ["gnome-terminal", "--", "bash", "-c", wrapped],
        )
        logger.info("Comando eseguito in terminale: %s", command[:80])
        return True
    except OSError:
        logger.exception("Errore avvio gnome-terminal")
        return False
