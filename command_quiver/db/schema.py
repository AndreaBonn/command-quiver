"""Schema SQLite, migrazioni e sezioni iniziali."""

import logging
import sqlite3

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

# Sezioni di default inserite al primo avvio, nella lingua dell'interfaccia.
# "Generale" resta invariata in ogni lingua: il codice la usa come fallback per nome.
_SEED_NAMES: dict[str, tuple[str, str]] = {
    "it": ("Comandi shell", "Prompt AI"),
    "en": ("Shell Commands", "AI Prompts"),
}
_SEED_SQL = """
INSERT OR IGNORE INTO sections (name, icon, position, is_default) VALUES
    (?, 'utilities-terminal', 0, 0),
    (?, 'format-text-bold',   1, 0),
    ('Git', 'vcs-commit',     2, 0),
    ('Generale', 'folder',    3, 1);
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
        # Placeholder: migrazione v2 gestita da migrate_v2(connection) con ALTER singoli
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


def build_schema(connection: sqlite3.Connection, language: str) -> None:
    """Porta il database allo schema corrente: DDL, migrazioni, seed e uuid.

    Unico percorso sia per l'avvio sia per la ricreazione dopo corruzione,
    così un database ricreato è già migrato. Il seed precede l'assegnazione
    degli uuid: le sezioni iniziali li ricevono subito, non al riavvio.
    """
    connection.executescript(_SCHEMA_SQL)
    migrate(connection)
    seed_if_empty(connection, language)
    populate_uuids(connection)
    connection.commit()


def migrate_v2(connection: sqlite3.Connection) -> None:
    """Migrazione v2: ogni ALTER TABLE isolato per non bloccare i successivi."""
    for stmt in _V2_ALTER_STATEMENTS:
        try:
            connection.execute(stmt)
        except sqlite3.OperationalError as err:
            if "duplicate column" in str(err).lower():
                logger.info("v2: colonna già esistente, skip: %s", stmt)
            else:
                raise
    connection.executescript(_V2_CREATE_STATEMENTS)
    connection.commit()
    logger.info("Migrazione v2 completata")


def populate_uuids(connection: sqlite3.Connection) -> None:
    """Genera UUID per righe esistenti prive di uuid (post-migrazione v2).

    Operazione idempotente: se tutte le righe hanno uuid, non fa nulla.
    La connessione deve usare ``sqlite3.Row`` come row factory.
    """
    import uuid as uuid_mod

    # Verifica che la colonna uuid esista prima di operare
    columns = [row[1] for row in connection.execute("PRAGMA table_info(entries)").fetchall()]
    if "uuid" not in columns:
        return

    updated = 0
    for table in ("entries", "sections"):
        cursor = connection.execute(f"SELECT id FROM {table} WHERE uuid IS NULL")
        for row in cursor.fetchall():
            connection.execute(
                f"UPDATE {table} SET uuid = ? WHERE id = ?",
                (str(uuid_mod.uuid4()), row["id"]),
            )
            updated += 1

    if updated:
        connection.commit()
        logger.info("UUID generati per %d righe esistenti", updated)


def detect_schema_version(connection: sqlite3.Connection) -> int:
    """Rileva lo schema legacy; se trova is_default scrive e committa PRAGMA user_version=1."""
    columns = [row[1] for row in connection.execute("PRAGMA table_info(sections)").fetchall()]
    if "is_default" in columns:
        # Ha già la migrazione v1 applicata manualmente
        connection.execute("PRAGMA user_version = 1")
        connection.commit()
        logger.info("DB legacy rilevato con schema v1, user_version aggiornato")
        return 1
    return 0


def seed_if_empty(connection: sqlite3.Connection, language: str) -> None:
    """Inserisce le sezioni iniziali solo al primo avvio.

    Prima il seed girava a ogni avvio con INSERT OR IGNORE: una sezione
    iniziale eliminata dall'utente ricompariva al riavvio, e con nomi
    localizzati avrebbe duplicato le sezioni a ogni cambio di lingua.
    """
    count = connection.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
    if count:
        return
    names = _SEED_NAMES.get(language, _SEED_NAMES["en"])
    connection.execute(_SEED_SQL, names)


def migrate(connection: sqlite3.Connection) -> None:
    """Applica e committa le migrazioni successive alla versione corrente."""
    current = connection.execute("PRAGMA user_version").fetchone()[0]
    if current == 0:
        current = detect_schema_version(connection)
    for version, description, sql in _MIGRATIONS:
        if current < version:
            logger.info("Migrazione v%d: %s", version, description)
            _apply_migration(connection, version, sql)
            # PRAGMA non supporta parametri bindati: version è sempre int da _MIGRATIONS
            connection.execute(f"PRAGMA user_version = {version}")
            connection.commit()
    final = connection.execute("PRAGMA user_version").fetchone()[0]
    if final > current:
        logger.info("Schema migrato da v%d a v%d", current, final)


def _apply_migration(connection: sqlite3.Connection, version: int, sql: str) -> None:
    """Applica una migrazione tollerando le colonne già presenti."""
    if version == 2:
        migrate_v2(connection)
    elif sql:
        try:
            connection.executescript(sql)
        except sqlite3.OperationalError as err:
            if "duplicate column" in str(err).lower():
                logger.info("Migrazione v%d già applicata (colonna esistente)", version)
            else:
                raise
