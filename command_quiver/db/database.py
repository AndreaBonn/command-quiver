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

CREATE TABLE IF NOT EXISTS sync_tombstones (
    uuid        TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL CHECK(entity_type IN ('entry', 'section')),
    deleted_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

# Sezioni di default inserite al primo avvio
_SEED_SQL = """
INSERT OR IGNORE INTO sections (name, icon, position, is_default) VALUES
    ('Shell Commands', 'utilities-terminal', 0, 0),
    ('AI Prompts',     'format-text-bold',   1, 0),
    ('Git',            'vcs-commit',          2, 0),
    ('Generale',       'folder',              3, 1);
"""

# Migrazioni incrementali: (versione, descrizione, SQL)
# Le migrazioni vengono applicate in ordine, solo se user_version < versione.
# ATTENZIONE: MAI modificare migrazioni già rilasciate. Aggiungere sempre in coda.
_MIGRATIONS: list[tuple[int, str, str]] = [
    (
        1,
        "aggiunta colonna is_default a sections",
        """
        -- Verifica se la colonna esiste già (per DB pre-migration system)
        -- SQLite non ha IF NOT EXISTS per ALTER TABLE, usiamo try/catch via executescript
        ALTER TABLE sections ADD COLUMN is_default INTEGER NOT NULL DEFAULT 0;
        UPDATE sections SET is_default = 1 WHERE name = 'Generale';
        """,
    ),
    (
        2,
        "aggiunta uuid e sync support",
        # Placeholder: migrazione v2 gestita da _migrate_v2() con ALTER singoli
        "",
    ),
    (
        3,
        "contatori d'uso su entries per ranking locale",
        """
        ALTER TABLE entries ADD COLUMN use_count INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE entries ADD COLUMN last_used_at DATETIME;
        """,
    ),
]


# Migrazione v2 con ALTER TABLE singoli (SQLite non supporta IF NOT EXISTS su ALTER)
_V2_ALTER_STATEMENTS = [
    "ALTER TABLE entries ADD COLUMN uuid TEXT",
    "ALTER TABLE sections ADD COLUMN uuid TEXT",
    "ALTER TABLE sections ADD COLUMN updated_at DATETIME",
]

_V2_CREATE_STATEMENTS = """
CREATE TABLE IF NOT EXISTS sync_tombstones (
    uuid        TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL CHECK(entity_type IN ('entry', 'section')),
    deleted_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_entries_uuid ON entries(uuid);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sections_uuid ON sections(uuid);
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
        """Apre la connessione principale (thread GTK) configurata."""
        try:
            self._connection = self.create_connection()
            logger.info("Connessione database aperta: %s", self._db_path)
        except sqlite3.Error:
            if not _allow_recreate:
                raise
            logger.exception("Errore apertura database, tentativo di ricreare")
            self._recreate()

    def create_connection(self) -> sqlite3.Connection:
        """Crea una nuova connessione SQLite configurata al file del database.

        Ogni thread deve usare la propria connessione: SQLite vieta di
        condividere una connessione tra thread diversi. La modalità WAL
        (attivata qui) permette a letture e scritture su connessioni distinte
        di coesistere sullo stesso file, così il sync in background può usare
        una connessione dedicata senza interferire con il thread GTK.

        Returns
        -------
        sqlite3.Connection
            Connessione pronta all'uso (foreign key ON, WAL, row factory,
            funzione UNICODE_LOWER registrata).
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

    def initialize(self) -> None:
        """Crea le tabelle e inserisce i dati di default se necessario."""
        try:
            self.connection.executescript(_SCHEMA_SQL)
            self._migrate()
            self._populate_uuids()
            self.connection.executescript(_SEED_SQL)
            self.connection.commit()
            self._auto_backup()
            logger.info("Schema database inizializzato")
        except sqlite3.Error:
            logger.exception("Errore inizializzazione schema, tentativo di ricreare")
            self._recreate()

    def _migrate(self) -> None:
        """Applica migrazioni incrementali basate su PRAGMA user_version.

        Ogni migrazione ha un numero versione. Il DB traccia la versione
        corrente in user_version. Solo le migrazioni con versione superiore
        vengono eseguite.
        """
        current = self.connection.execute("PRAGMA user_version").fetchone()[0]

        # DB pre-migration system: rileva versione reale dalla struttura
        if current == 0:
            current = self._detect_schema_version()

        for version, description, sql in _MIGRATIONS:
            if current < version:
                logger.info("Migrazione v%d: %s", version, description)

                if version == 2:
                    # v2: ALTER singoli per evitare che un fallimento blocchi i successivi
                    self._migrate_v2()
                elif sql:
                    try:
                        self.connection.executescript(sql)
                    except sqlite3.OperationalError as err:
                        if "duplicate column" in str(err).lower():
                            logger.info(
                                "Migrazione v%d già applicata (colonna esistente)",
                                version,
                            )
                        else:
                            raise

                # PRAGMA non supporta parametri bindati — version è sempre int da _MIGRATIONS
                self.connection.execute(f"PRAGMA user_version = {version}")
                self.connection.commit()

        final = self.connection.execute("PRAGMA user_version").fetchone()[0]
        if final > current:
            logger.info("Schema migrato da v%d a v%d", current, final)

    def _migrate_v2(self) -> None:
        """Migrazione v2: ogni ALTER TABLE isolato per non bloccare i successivi."""
        for stmt in _V2_ALTER_STATEMENTS:
            try:
                self.connection.execute(stmt)
            except sqlite3.OperationalError as err:
                if "duplicate column" in str(err).lower():
                    logger.info("v2: colonna già esistente, skip: %s", stmt)
                else:
                    raise
        self.connection.executescript(_V2_CREATE_STATEMENTS)
        self.connection.commit()
        logger.info("Migrazione v2 completata")

    def _populate_uuids(self) -> None:
        """Genera UUID per righe esistenti prive di uuid (post-migrazione v2).

        Operazione idempotente: se tutte le righe hanno uuid, non fa nulla.
        """
        import uuid as uuid_mod

        # Verifica che la colonna uuid esista prima di operare
        columns = [
            row[1] for row in self.connection.execute("PRAGMA table_info(entries)").fetchall()
        ]
        if "uuid" not in columns:
            return

        updated = 0
        for table in ("entries", "sections"):
            cursor = self.connection.execute(f"SELECT id FROM {table} WHERE uuid IS NULL")
            for row in cursor.fetchall():
                self.connection.execute(
                    f"UPDATE {table} SET uuid = ? WHERE id = ?",
                    (str(uuid_mod.uuid4()), row["id"]),
                )
                updated += 1

        if updated:
            self.connection.commit()
            logger.info("UUID generati per %d righe esistenti", updated)

    def _detect_schema_version(self) -> int:
        """Rileva la versione dello schema per DB senza user_version (legacy)."""
        columns = [
            row[1] for row in self.connection.execute("PRAGMA table_info(sections)").fetchall()
        ]
        if "is_default" in columns:
            # Ha già la migrazione v1 applicata manualmente
            self.connection.execute("PRAGMA user_version = 1")
            self.connection.commit()
            logger.info("DB legacy rilevato con schema v1, user_version aggiornato")
            return 1
        return 0

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

    # Backup ogni N avvii (evita accumulazione backup)
    _BACKUP_EVERY_N = 5
    _BACKUP_SUFFIX = ".auto.bak"
    _MAX_BACKUPS = 3

    def _auto_backup(self) -> None:
        """Crea un backup automatico del DB ogni N avvii, mantenendo max 3 copie."""
        if not self._db_path.exists():
            return

        backup_dir = self._db_path.parent
        counter_file = backup_dir / ".backup_counter"

        # Leggi e incrementa contatore
        count = 0
        if counter_file.exists():
            try:
                count = int(counter_file.read_text().strip())
            except (ValueError, OSError):
                count = 0

        count += 1
        try:
            counter_file.write_text(str(count))
        except OSError:
            logger.warning("Impossibile aggiornare contatore backup")
            return

        if count % self._BACKUP_EVERY_N != 0:
            return

        # Crea backup via SQLite online backup API
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        backup_path = backup_dir / f"vault{self._BACKUP_SUFFIX}.{timestamp}"

        try:
            backup_conn = sqlite3.connect(str(backup_path))
            self.connection.backup(backup_conn)
            backup_conn.close()
            logger.info("Backup automatico creato: %s", backup_path.name)
        except sqlite3.Error:
            logger.exception("Errore durante backup automatico")
            return

        # Pulizia vecchi backup (mantieni solo gli ultimi N)
        backups = sorted(backup_dir.glob(f"vault{self._BACKUP_SUFFIX}.*"), reverse=True)
        for old_backup in backups[self._MAX_BACKUPS :]:
            try:
                old_backup.unlink()
                logger.debug("Backup obsoleto rimosso: %s", old_backup.name)
            except OSError:
                pass

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
