"""Gestione copia negli appunti tramite GDK4 Clipboard."""

import logging

import gi

gi.require_version("Gdk", "4.0")
from gi.repository import Gdk

logger = logging.getLogger(__name__)


def copy_to_clipboard(content: str) -> bool:
    """Copia il testo negli appunti di sistema.

    Parameters
    ----------
    content : str
        Testo da copiare negli appunti.

    Returns
    -------
    bool
        True se la copia è riuscita, False altrimenti.
    """
    display = Gdk.Display.get_default()
    if display is None:
        logger.error("Nessun display disponibile per la clipboard")
        return False

    clipboard = display.get_clipboard()
    clipboard.set(content)
    logger.info("Contenuto copiato negli appunti (%d caratteri)", len(content))
    return True
