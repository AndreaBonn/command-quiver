"""Connessione SQLite e ciclo di vita del database."""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from command_quiver.db.backup import auto_backup
from command_quiver.db.schema import build_schema

logger = logging.getLogger(__name__)

DEFAULT_DB_DIR = Path.home() / ".local" / "share" / "command-quiver"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "vault.db"


class Database:
    """Gestisce la connessione SQLite e il ripristino dopo corruzione."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or DEFAULT_DB_PATH
        self._connection: sqlite3.Connection | None = None
        self._seed_language = "en"

    @property
    def connection(self) -> sqlite3.Connection:
        """Restituisce la connessione attiva, creandola se necessario."""
        if self._connection is None:
            self._connect()
        return self._connection

    def _connect(self, *, _allow_recreate: bool = True) -> None:
        """Apre la connessione principale (thread GTK) configurata."""
        try:
            self._connection = self.create_connection()
            logger.info("Connessione database aperta: %s", self._db_path)
        except sqlite3.Error as err:
            if not _allow_recreate or _is_lock_error(err):
                raise
            logger.exception("Errore apertura database, tentativo di ricreare")
            self._recreate()

    def create_connection(self) -> sqlite3.Connection:
        """Crea una connessione per il thread chiamante con WAL e ricerca Unicode.

        Ogni thread deve usare una connessione propria: SQLite vieta la
        condivisione tra thread. WAL permette alle connessioni del sync e
        della UI di leggere e scrivere sullo stesso file.
        """
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            str(self._db_path),
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        connection.row_factory = sqlite3.Row
        # Abilita foreign key, WAL mode per performance, timeout ragionevole
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 5000")
        # Funzione per ricerca case-insensitive unicode (LIKE gestisce solo ASCII)
        connection.create_function("UNICODE_LOWER", 1, str.casefold)
        return connection

    def initialize(self, language: str = "en") -> None:
        """Crea le tabelle e, solo su database vuoto, le sezioni iniziali nella lingua data."""
        self._seed_language = language
        try:
            build_schema(self.connection, self._seed_language)
            auto_backup(self.connection, self._db_path)
            logger.info("Schema database inizializzato")
        except sqlite3.Error as err:
            if _is_lock_error(err):
                # Un lock non è corruzione: ricreare nasconderebbe la libreria dell'utente
                raise
            logger.exception("Errore inizializzazione schema, tentativo di ricreare")
            self._recreate()

    def _recreate(self) -> None:
        """Ricrea il database da zero in caso di corruzione."""
        logger.warning("Ricreazione database da zero: %s", self._db_path)
        self.close()
        if self._db_path.exists():
            timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
            backup = self._db_path.with_suffix(f".db.bak.{timestamp}")
            _move_with_journal(source=self._db_path, target=backup)
            logger.info("Backup database corrotto salvato in: %s", backup)
        try:
            self._connect(_allow_recreate=False)
            build_schema(self.connection, self._seed_language)
        except sqlite3.Error:
            logger.critical("Impossibile ricreare il database: %s", self._db_path)
            raise

    def close(self) -> None:
        """Chiude la connessione al database."""
        if self._connection is not None:
            try:
                self._connection.close()
            except sqlite3.Error:
                logger.exception("Errore chiusura database")
            finally:
                self._connection = None
                logger.info("Connessione database chiusa")


def _is_lock_error(err: sqlite3.Error) -> bool:
    """Vero per un database occupato da un'altra connessione, che non va ricreato."""
    message = str(err).lower()
    return isinstance(err, sqlite3.OperationalError) and ("locked" in message or "busy" in message)


def _move_with_journal(source: Path, target: Path) -> None:
    """Sposta il database insieme ai file -wal e -shm, che contengono transazioni recenti."""
    source.rename(target)
    for suffix in ("-wal", "-shm"):
        journal = source.with_name(source.name + suffix)
        if journal.exists():
            journal.rename(target.with_name(target.name + suffix))
