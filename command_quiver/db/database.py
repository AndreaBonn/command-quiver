"""Connessione SQLite, inizializzazione schema e seed dati di default."""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Schema SQL con vincoli e indici
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    icon        TEXT DEFAULT 'folder',
    position    INTEGER NOT NULL DEFAULT 0,
    is_default  INTEGER NOT NULL DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS entries (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    content       TEXT NOT NULL,
    section_id    INTEGER REFERENCES sections(id) ON DELETE SET NULL,
    type          TEXT DEFAULT 'prompt'
                  CHECK(type IN ('prompt', 'shell')),
    tags          TEXT DEFAULT '',
    personal_pos  INTEGER DEFAULT 0,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_entries_section_id ON entries(section_id);
CREATE INDEX IF NOT EXISTS idx_entries_name ON entries(name);
CREATE INDEX IF NOT EXISTS idx_entries_type ON entries(type);
CREATE INDEX IF NOT EXISTS idx_sections_position ON sections(position);
"""

# Sezioni di default inserite al primo avvio
_SEED_SQL = """
INSERT OR IGNORE INTO sections (name, icon, position, is_default) VALUES
    ('Shell Commands', 'utilities-terminal', 0, 0),
    ('AI Prompts',     'format-text-bold',   1, 0),
    ('Git',            'vcs-commit',          2, 0),
    ('Generale',       'folder',              3, 1);
"""

# Percorso predefinito del database
DEFAULT_DB_DIR = Path.home() / ".local" / "share" / "command-quiver"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "vault.db"


class Database:
    """Gestisce la connessione SQLite e l'inizializzazione dello schema.

    Tutte le operazioni avvengono sul thread principale GTK (single-threaded).
    Il database viene creato automaticamente se mancante o corrotto.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or DEFAULT_DB_PATH
        self._connection: sqlite3.Connection | None = None

    @property
    def connection(self) -> sqlite3.Connection:
        """Restituisce la connessione attiva, creandola se necessario."""
        if self._connection is None:
            self._connect()
        return self._connection

    def _connect(self, *, _allow_recreate: bool = True) -> None:
        """Apre la connessione e configura SQLite per integrità e performance."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._connection = sqlite3.connect(
                str(self._db_path),
                detect_types=sqlite3.PARSE_DECLTYPES,
            )
            self._connection.row_factory = sqlite3.Row
            # Abilita foreign key, WAL mode per performance, timeout ragionevole
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA busy_timeout = 5000")
            # Funzione per ricerca case-insensitive unicode (LIKE gestisce solo ASCII)
            self._connection.create_function("UNICODE_LOWER", 1, str.casefold)
            logger.info("Connessione database aperta: %s", self._db_path)
        except sqlite3.Error:
            if not _allow_recreate:
                raise
            logger.exception("Errore apertura database, tentativo di ricreare")
            self._recreate()

    def initialize(self) -> None:
        """Crea le tabelle e inserisce i dati di default se necessario."""
        try:
            self.connection.executescript(_SCHEMA_SQL)
            self._migrate()
            self.connection.executescript(_SEED_SQL)
            self.connection.commit()
            logger.info("Schema database inizializzato")
        except sqlite3.Error:
            logger.exception("Errore inizializzazione schema, tentativo di ricreare")
            self._recreate()

    def _migrate(self) -> None:
        """Applica migrazioni incrementali per DB pre-esistenti."""
        # Migrazione: aggiunge is_default se mancante
        columns = [
            row[1] for row in self.connection.execute("PRAGMA table_info(sections)").fetchall()
        ]
        if "is_default" not in columns:
            self.connection.execute(
                "ALTER TABLE sections ADD COLUMN is_default INTEGER NOT NULL DEFAULT 0"
            )
            self.connection.execute("UPDATE sections SET is_default = 1 WHERE name = 'Generale'")
            logger.info("Migrazione: aggiunta colonna is_default a sections")

    def _recreate(self) -> None:
        """Ricrea il database da zero in caso di corruzione."""
        logger.warning("Ricreazione database da zero: %s", self._db_path)
        self.close()
        if self._db_path.exists():
            timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
            backup = self._db_path.with_suffix(f".db.bak.{timestamp}")
            self._db_path.rename(backup)
            logger.info("Backup database corrotto salvato in: %s", backup)
        try:
            self._connect(_allow_recreate=False)
            self.connection.executescript(_SCHEMA_SQL)
            self.connection.executescript(_SEED_SQL)
            self.connection.commit()
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
