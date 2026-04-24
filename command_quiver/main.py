"""Entry point dell'applicazione Command Quiver.

Configura il logging, verifica la single instance e avvia l'app GTK4.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from command_quiver import APP_NAME

# Directory per log e dati
LOG_DIR = Path.home() / ".local" / "share" / "command-quiver" / "logs"
LOG_FILE = LOG_DIR / "app.log"


def setup_logging() -> None:
    """Configura il logging con rotazione su file e output su stderr."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler file con rotazione (max 1 MB, 3 backup)
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=1_048_576,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Handler stderr (solo WARNING+)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stderr_handler)


def main() -> int:
    """Avvia l'applicazione Command Quiver."""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Avvio %s", APP_NAME)

    # Import posticipato per evitare che GTK venga inizializzato
    # prima della configurazione del logging
    from command_quiver.app import CommandQuiverApp

    app = CommandQuiverApp()
    exit_code = app.run(sys.argv)

    logger.info("Chiusura %s (exit code: %d)", APP_NAME, exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
