"""Test per il modulo database: schema, inizializzazione, ricreazione."""

import functools
import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from uuid import UUID

import pytest

from command_quiver.db import backup
from command_quiver.db.backup import auto_backup
from command_quiver.db.database import Database
from command_quiver.db.schema import detect_schema_version, migrate


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Percorso temporaneo per il database di test."""
    return tmp_path / "test_vault.db"


@pytest.fixture
def db(db_path: Path) -> Database:
    """Database inizializzato per i test."""
    database = Database(db_path=db_path)
    database.initialize()
    yield database
    database.close()


class TestDatabaseInitialization:
    """Test di inizializzazione schema e seed."""

    def test_database_creates_file(self, db: Database, db_path: Path) -> None:
        assert db_path.exists()

    def test_schema_creates_sections_table(self, db: Database) -> None:
        cursor = db.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sections'"
        )
        assert cursor.fetchone() is not None

    def test_schema_creates_entries_table(self, db: Database) -> None:
        cursor = db.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='entries'"
        )
        assert cursor.fetchone() is not None

    def test_seed_creates_default_sections(self, db: Database) -> None:
        cursor = db.connection.execute("SELECT COUNT(*) FROM sections")
        count = cursor.fetchone()[0]
        assert count == 4

    def test_seed_default_section_names(self, db: Database) -> None:
        cursor = db.connection.execute("SELECT name FROM sections ORDER BY position")
        names = [row[0] for row in cursor.fetchall()]
        assert names == ["Shell Commands", "AI Prompts", "Git", "Generale"]

    def test_foreign_keys_enabled(self, db: Database) -> None:
        cursor = db.connection.execute("PRAGMA foreign_keys")
        assert cursor.fetchone()[0] == 1

    def test_wal_mode_enabled(self, db: Database) -> None:
        cursor = db.connection.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        assert mode.lower() == "wal"


class TestDatabaseRecreation:
    """Test di ricreazione database corrotto."""

    def test_recreate_on_corrupted_database(self, db_path: Path) -> None:
        # Crea un file corrotto
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.write_bytes(b"corrupted data that is not sqlite")

        db = Database(db_path=db_path)
        db.initialize()

        # Verifica che il database sia stato ricreato
        cursor = db.connection.execute("SELECT COUNT(*) FROM sections")
        assert cursor.fetchone()[0] == 4
        db.close()

    def test_backup_created_on_corruption(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.write_bytes(b"corrupted")

        db = Database(db_path=db_path)
        db.initialize()

        backups = list(db_path.parent.glob("*.db.bak.*"))
        assert len(backups) == 1
        assert backups[0].stat().st_size > 0
        db.close()

    def test_recreate_without_existing_file(self, tmp_path: Path) -> None:
        """_recreate funziona anche quando il file DB non esiste ancora."""
        db_path = tmp_path / "nonexistent" / "new.db"
        db = Database(db_path=db_path)
        # Forza _recreate direttamente
        db._recreate()

        cursor = db.connection.execute("SELECT COUNT(*) FROM sections")
        assert cursor.fetchone()[0] == 4
        db.close()

    def test_recreate_raises_on_critical_failure(self, tmp_path: Path) -> None:
        """_recreate propaga sqlite3.Error se anche la ricreazione fallisce."""
        from unittest.mock import MagicMock, patch

        db_path = tmp_path / "fail.db"
        db = Database(db_path=db_path)

        # Simula connessione che fallisce su executescript
        mock_conn = MagicMock()
        mock_conn.executescript.side_effect = sqlite3.Error("critical")

        with (
            patch.object(
                db, "_connect", side_effect=lambda **_: setattr(db, "_connection", mock_conn)
            ),
            pytest.raises(sqlite3.Error, match="critical"),
        ):
            db._recreate()


class TestDatabaseConnection:
    """Test gestione connessione."""

    def test_close_and_reconnect(self, db_path: Path) -> None:
        db = Database(db_path=db_path)
        db.initialize()
        db.close()

        # Deve riconnettersi automaticamente
        cursor = db.connection.execute("SELECT COUNT(*) FROM sections")
        assert cursor.fetchone()[0] == 4
        db.close()

    def test_row_factory_returns_dict_like(self, db: Database) -> None:
        cursor = db.connection.execute("SELECT id, name FROM sections LIMIT 1")
        row = cursor.fetchone()
        assert row["id"] is not None
        assert row["name"] is not None

    def test_double_close_no_error(self, db: Database) -> None:
        db.close()
        db.close()  # Non deve sollevare eccezioni

    def test_close_handles_sqlite_error(self, db: Database) -> None:
        """close() non propaga eccezioni SQLite."""
        from unittest.mock import MagicMock

        mock_conn = MagicMock()
        mock_conn.close.side_effect = sqlite3.Error("mock error")
        db._connection = mock_conn

        db.close()  # Non deve sollevare eccezioni
        assert db._connection is None

    def test_initialize_catches_executescript_error_and_recreates(self, db_path: Path) -> None:
        """initialize() chiama _recreate se executescript fallisce."""
        from unittest.mock import MagicMock, patch

        db = Database(db_path=db_path)
        # Usa MagicMock come connection che fallisce su executescript
        mock_conn = MagicMock()
        mock_conn.executescript.side_effect = sqlite3.Error("schema corrotto")
        db._connection = mock_conn

        with patch.object(db, "_recreate") as mock_recreate:
            db.initialize()
            mock_recreate.assert_called_once()
        db._connection = None

    def test_initialize_with_corrupted_schema_recreates(self, db_path: Path) -> None:
        """Test che initialize() ricrea il DB se executescript fallisce."""
        db = Database(db_path=db_path)
        db.initialize()  # Crea DB valido

        # Corrompi: drop tabella sections per causare errore nel seed
        db.connection.execute("DROP TABLE entries")
        db.connection.execute("DROP TABLE sections")
        db.connection.commit()
        db.close()

        # Re-inizializza: deve ricreare tutto
        db2 = Database(db_path=db_path)
        db2.initialize()
        cursor = db2.connection.execute("SELECT COUNT(*) FROM sections")
        assert cursor.fetchone()[0] == 4
        db2.close()


def test_connect_locked_database_propagates_error_and_preserves_library(
    db: Database, db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Senza attesa sul lock: col timeout predefinito di sqlite3 (5 s) il test durava 5 s
    monkeypatch.setattr(sqlite3, "connect", functools.partial(sqlite3.connect, timeout=0))
    db.connection.execute("INSERT INTO sections (name) VALUES ('Preserved library')")
    db.connection.commit()
    db.close()
    opening = Database(db_path=db_path)

    # Il lock esclusivo impedisce il PRAGMA WAL durante l'apertura, prima dello schema.
    with closing(sqlite3.connect(db_path)) as locker:
        locker.execute("PRAGMA journal_mode = DELETE")
        locker.execute("BEGIN EXCLUSIVE")
        try:
            with pytest.raises(sqlite3.OperationalError, match="database is locked"):
                opening.connection.execute("SELECT 1")
        finally:
            locker.rollback()
            opening.close()

    with closing(db.create_connection()) as reader:
        saved = reader.execute(
            "SELECT name FROM sections WHERE name = 'Preserved library'"
        ).fetchall()
    assert ([row[0] for row in saved], list(db_path.parent.glob("*.db.bak.*"))) == (
        ["Preserved library"],
        [],
    )


class TestMigrationSystem:
    """Test sistema di migrazioni incrementali."""

    def test_user_version_set_after_initialize(self, db: Database) -> None:
        version = db.connection.execute("PRAGMA user_version").fetchone()[0]
        assert version == 3

    def test_migrations_idempotent(self, db: Database) -> None:
        """Chiamare _migrate() più volte non causa errori."""
        migrate(db.connection)
        migrate(db.connection)
        version = db.connection.execute("PRAGMA user_version").fetchone()[0]
        assert version == 3

    def test_legacy_db_detected_and_migrated(self, tmp_path: Path) -> None:
        """DB con is_default ma user_version=0 viene rilevato come v1."""
        db_path = tmp_path / "legacy.db"
        conn = sqlite3.connect(str(db_path))
        # Crea schema con is_default (come il vecchio codice)
        conn.executescript("""
            CREATE TABLE sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                icon TEXT DEFAULT 'folder',
                position INTEGER NOT NULL DEFAULT 0,
                is_default INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                section_id INTEGER REFERENCES sections(id) ON DELETE SET NULL,
                type TEXT DEFAULT 'prompt' CHECK(type IN ('prompt', 'shell')),
                tags TEXT DEFAULT '',
                personal_pos INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.close()

        db = Database(db_path=db_path)
        db.initialize()

        version = db.connection.execute("PRAGMA user_version").fetchone()[0]
        assert version == 3
        db.close()

    def test_fresh_db_gets_latest_version(self, tmp_path: Path) -> None:
        """DB nuovo ottiene versione massima delle migrazioni."""
        db_path = tmp_path / "fresh.db"
        db = Database(db_path=db_path)
        db.initialize()

        version = db.connection.execute("PRAGMA user_version").fetchone()[0]
        assert version == 3
        db.close()


class TestAutoBackup:
    """Test backup automatico del database."""

    def test_no_backup_before_threshold(self, tmp_path: Path) -> None:
        """Nessun backup creato prima di N avvii."""
        db_path = tmp_path / "vault.db"
        db = Database(db_path=db_path)
        db.initialize()
        db.close()

        backups = list(tmp_path.glob("vault.auto.bak.*"))
        assert len(backups) == 0

    def test_backup_created_at_threshold(self, tmp_path: Path) -> None:
        """Backup creato ogni N avvii."""
        db_path = tmp_path / "vault.db"
        # Imposta contatore a N-1 per forzare backup al prossimo avvio
        counter_file = tmp_path / ".backup_counter"
        counter_file.write_text(str(backup._BACKUP_EVERY_N - 1))

        db = Database(db_path=db_path)
        db.initialize()
        db.close()

        backups = list(tmp_path.glob("vault.auto.bak.*"))
        assert len(backups) == 1

    def test_old_backups_cleaned_up(self, tmp_path: Path) -> None:
        """Mantiene solo MAX_BACKUPS backup."""
        db_path = tmp_path / "vault.db"

        # Crea backup finti vecchi
        for i in range(5):
            fake = tmp_path / f"vault.auto.bak.2024010{i}T000000"
            fake.write_text("fake")

        counter_file = tmp_path / ".backup_counter"
        counter_file.write_text(str(backup._BACKUP_EVERY_N - 1))

        db = Database(db_path=db_path)
        db.initialize()
        db.close()

        backups = list(tmp_path.glob("vault.auto.bak.*"))
        assert len(backups) == backup._MAX_BACKUPS

    def test_backup_is_valid_sqlite(self, tmp_path: Path) -> None:
        """Il backup deve essere un DB SQLite valido."""
        db_path = tmp_path / "vault.db"
        counter_file = tmp_path / ".backup_counter"
        counter_file.write_text(str(backup._BACKUP_EVERY_N - 1))

        db = Database(db_path=db_path)
        db.initialize()
        db.close()

        backups = list(tmp_path.glob("vault.auto.bak.*"))
        assert len(backups) == 1

        # Verifica che il backup sia leggibile
        conn = sqlite3.connect(str(backups[0]))
        count = conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
        assert count == 4
        conn.close()

    def test_auto_backup_skips_when_db_not_exists(self, tmp_path: Path) -> None:
        """_auto_backup non fa nulla se il file DB non esiste."""
        db_path = tmp_path / "nonexistent.db"
        db = Database(db_path=tmp_path / "source.db")
        auto_backup(db.connection, db_path)  # Non deve sollevare eccezioni
        backups = list(tmp_path.glob("*.auto.bak.*"))
        assert len(backups) == 0

    def test_auto_backup_handles_corrupted_counter(self, tmp_path: Path) -> None:
        """Counter file con contenuto non numerico viene gestito."""
        db_path = tmp_path / "vault.db"
        counter_file = tmp_path / ".backup_counter"
        counter_file.write_text("not_a_number")

        db = Database(db_path=db_path)
        db.initialize()
        db.close()

        # Counter resettato a 0 → incrementato a 1 → no backup (1 % 5 != 0)
        assert counter_file.read_text() == "1"

    def test_auto_backup_handles_counter_write_error(self, tmp_path: Path) -> None:
        """Se il counter file non è scrivibile, il backup viene saltato."""
        from unittest.mock import patch

        db_path = tmp_path / "vault.db"
        db = Database(db_path=db_path)
        db.initialize()

        with patch("command_quiver.db.backup.Path.write_text", side_effect=OSError("perm")):
            auto_backup(db.connection, db_path)  # Non deve sollevare eccezioni

        db.close()

    def test_auto_backup_handles_sqlite_backup_error(self, tmp_path: Path) -> None:
        """Errore SQLite durante backup non propaga eccezione."""
        from unittest.mock import patch

        db_path = tmp_path / "vault.db"
        db = Database(db_path=db_path)
        db.initialize()

        # Resetta counter per triggerare backup alla prossima chiamata
        counter_file = tmp_path / ".backup_counter"
        counter_file.write_text(str(backup._BACKUP_EVERY_N - 1))

        # Intercetta sqlite3.connect nel modulo database per far fallire il backup
        def failing_connect(path, *args, **kwargs):
            raise sqlite3.Error("backup connection fail")

        with patch("command_quiver.db.backup.sqlite3.connect", side_effect=failing_connect):
            auto_backup(db.connection, db_path)  # Non deve sollevare eccezioni

        db.close()


class TestDetectSchemaVersion:
    """Test rilevamento versione schema legacy."""

    def test_detect_returns_zero_without_is_default(self, tmp_path: Path) -> None:
        """DB senza colonna is_default viene rilevato come v0."""
        db_path = tmp_path / "old.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                icon TEXT DEFAULT 'folder',
                position INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                section_id INTEGER REFERENCES sections(id),
                type TEXT DEFAULT 'prompt',
                tags TEXT DEFAULT '',
                personal_pos INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.close()

        db = Database(db_path=db_path)
        db._connect()
        version = detect_schema_version(db.connection)
        assert version == 0
        db.close()


class TestLocalizedSeed:
    """Le sezioni iniziali seguono la lingua e nascono solo sul DB vuoto."""

    def test_seed_italian_names(self, tmp_path) -> None:
        db = Database(db_path=tmp_path / "it.db")
        db.initialize(language="it")
        names = [r[0] for r in db.connection.execute("SELECT name FROM sections ORDER BY position")]
        assert names == ["Comandi shell", "Prompt AI", "Git", "Generale"]
        db.close()

    def test_seed_not_repeated_on_restart_in_other_language(self, tmp_path) -> None:
        path = tmp_path / "v.db"
        db = Database(db_path=path)
        db.initialize(language="en")
        db.close()
        db = Database(db_path=path)
        db.initialize(language="it")
        count = db.connection.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
        assert count == 4
        db.close()

    def test_deleted_seed_section_does_not_come_back(self, tmp_path) -> None:
        path = tmp_path / "v.db"
        db = Database(db_path=path)
        db.initialize()
        db.connection.execute("DELETE FROM sections WHERE name = 'Git'")
        db.connection.commit()
        db.close()
        db = Database(db_path=path)
        db.initialize()
        names = [r[0] for r in db.connection.execute("SELECT name FROM sections")]
        assert "Git" not in names
        assert "Generale" in names
        db.close()


def _create_legacy_database(db_path: Path, *, has_default: bool) -> None:
    default_column = ", is_default INTEGER NOT NULL DEFAULT 0" if has_default else ""
    with sqlite3.connect(str(db_path)) as connection:
        connection.executescript(f"""
            CREATE TABLE sections (
                id INTEGER PRIMARY KEY, name TEXT UNIQUE, icon TEXT,
                position INTEGER DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                {default_column}
            );
            CREATE TABLE entries (
                id INTEGER PRIMARY KEY, name TEXT, content TEXT, section_id INTEGER,
                type TEXT, tags TEXT, personal_pos INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO sections (id, name) VALUES (1, 'Generale');
            INSERT INTO entries (id, name, content, section_id, type, tags)
                VALUES (1, 'Saved command', 'echo saved', 1, 'shell', 'legacy');
        """)


@pytest.fixture(params=[False, True], ids=["v0", "v1"])
def migrated_legacy_database(db_path: Path, request: pytest.FixtureRequest) -> Database:
    """Database legacy (senza o con is_default) dopo la prima initialize."""
    _create_legacy_database(db_path=db_path, has_default=request.param)
    database = Database(db_path=db_path)
    database.initialize(language="it")
    yield database
    database.close()


def test_initialize_legacy_database_reaches_current_schema_version(
    migrated_legacy_database: Database,
) -> None:
    version = migrated_legacy_database.connection.execute("PRAGMA user_version").fetchone()[0]

    assert version == 3


def test_initialize_legacy_database_preserves_entry_data(
    migrated_legacy_database: Database,
) -> None:
    connection = migrated_legacy_database.connection

    entry = connection.execute("SELECT * FROM entries").fetchone()
    section = connection.execute("SELECT * FROM sections").fetchone()

    assert (entry["name"], entry["content"], entry["section_id"]) == (
        "Saved command",
        "echo saved",
        section["id"],
    )


def test_initialize_legacy_database_gives_new_columns_their_defaults(
    migrated_legacy_database: Database,
) -> None:
    entry = migrated_legacy_database.connection.execute("SELECT * FROM entries").fetchone()

    assert (entry["use_count"], entry["last_used_at"]) == (0, None)


def test_initialize_legacy_database_populates_entry_uuid(
    migrated_legacy_database: Database,
) -> None:
    entry = migrated_legacy_database.connection.execute("SELECT * FROM entries").fetchone()

    assert str(UUID(entry["uuid"])) == entry["uuid"]


def test_initialize_legacy_database_populates_section_uuid(
    migrated_legacy_database: Database,
) -> None:
    section = migrated_legacy_database.connection.execute("SELECT * FROM sections").fetchone()

    assert str(UUID(section["uuid"])) == section["uuid"]


def test_initialize_legacy_database_with_sections_does_not_seed_more(
    migrated_legacy_database: Database,
) -> None:
    count = migrated_legacy_database.connection.execute("SELECT COUNT(*) FROM sections")

    assert count.fetchone()[0] == 1


@pytest.fixture(params=[1, 2])
def partially_migrated_database(db_path: Path, request: pytest.FixtureRequest) -> Database:
    """Database con le colonne delle migrazioni già presenti ma user_version indietro."""
    database = Database(db_path=db_path)
    database.initialize()
    connection = database.connection
    connection.execute("UPDATE sections SET uuid = 'stable-id' WHERE name = 'Generale'")
    connection.execute(f"PRAGMA user_version = {request.param}")
    connection.commit()
    database.close()
    database.initialize()
    yield database
    database.close()


def test_initialize_existing_migration_columns_finishes_migration(
    partially_migrated_database: Database,
) -> None:
    version = partially_migrated_database.connection.execute("PRAGMA user_version").fetchone()[0]

    assert version == 3


def test_initialize_existing_migration_columns_preserves_existing_uuid(
    partially_migrated_database: Database,
) -> None:
    row = partially_migrated_database.connection.execute(
        "SELECT uuid FROM sections WHERE name = 'Generale'"
    ).fetchone()

    assert row[0] == "stable-id"


def test_initialize_existing_migration_columns_does_not_duplicate_sections(
    partially_migrated_database: Database,
) -> None:
    count = partially_migrated_database.connection.execute("SELECT COUNT(*) FROM sections")

    assert count.fetchone()[0] == 4


def test_initialize_corrupt_file_preserves_original_bytes_in_backup(db_path: Path) -> None:
    original = b"not a sqlite database\x00"
    db_path.write_bytes(original)
    database = Database(db_path=db_path)

    database.initialize(language="it")

    database.close()
    backups = list(db_path.parent.glob("*.db.bak.*"))
    assert [backup.read_bytes() for backup in backups] == [original]


_BACKUP_GLOB = "vault.auto.bak.*"


def _start_database_with_counter(tmp_path: Path, counter: str) -> Database:
    """Inizializza un database il cui contatore avvii vale `counter` prima dell'avvio."""
    database = Database(db_path=tmp_path / "vault.db")
    (tmp_path / ".backup_counter").write_text(counter)
    database.initialize()
    return database


def test_initialize_counts_each_start(tmp_path: Path) -> None:
    database = _start_database_with_counter(tmp_path, counter="2")
    database.close()

    assert (tmp_path / ".backup_counter").read_text() == "3"


def test_initialize_fifth_start_creates_backup(tmp_path: Path) -> None:
    database = _start_database_with_counter(tmp_path, counter="4")
    database.close()

    assert len(list(tmp_path.glob(_BACKUP_GLOB))) == 1


def test_initialize_start_between_multiples_of_five_creates_no_backup(tmp_path: Path) -> None:
    database = _start_database_with_counter(tmp_path, counter="3")
    database.close()

    assert list(tmp_path.glob(_BACKUP_GLOB)) == []


def test_initialize_backup_is_a_consistent_copy_of_the_database(tmp_path: Path) -> None:
    database = Database(db_path=tmp_path / "vault.db")
    database.initialize()
    database.connection.execute("INSERT INTO entries (name, content) VALUES ('kept', 'saved')")
    database.connection.commit()
    (tmp_path / ".backup_counter").write_text("4")

    database.initialize()

    database.close()
    backup = next(tmp_path.glob(_BACKUP_GLOB))
    with sqlite3.connect(str(backup)) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_initialize_backup_contains_the_stored_entries(tmp_path: Path) -> None:
    database = Database(db_path=tmp_path / "vault.db")
    database.initialize()
    database.connection.execute("INSERT INTO entries (name, content) VALUES ('kept', 'saved')")
    database.connection.commit()
    (tmp_path / ".backup_counter").write_text("4")

    database.initialize()

    database.close()
    backup = next(tmp_path.glob(_BACKUP_GLOB))
    with sqlite3.connect(str(backup)) as connection:
        assert connection.execute("SELECT name FROM entries").fetchall() == [("kept",)]


def _seed_old_backups(database: Database, directory: Path, days: range) -> None:
    for day in days:
        backup = directory / f"vault.auto.bak.200001{day:02d}T000000"
        with sqlite3.connect(str(backup)) as connection:
            database.connection.backup(connection)
    (directory / ".backup_counter").write_text("4")


def test_initialize_backup_keeps_only_the_three_newest_copies(tmp_path: Path) -> None:
    database = Database(db_path=tmp_path / "vault.db")
    database.initialize()
    _seed_old_backups(database, directory=tmp_path, days=range(1, 5))

    database.initialize()

    database.close()
    names = sorted(path.name for path in tmp_path.glob(_BACKUP_GLOB))
    assert len(names) == 3
    assert names[:2] == ["vault.auto.bak.20000103T000000", "vault.auto.bak.20000104T000000"]


def test_initialize_invalid_counter_restarts_count_from_one(tmp_path: Path) -> None:
    database = _start_database_with_counter(tmp_path, counter="invalid counter")
    database.close()

    assert (tmp_path / ".backup_counter").read_text() == "1"


def test_initialize_invalid_counter_creates_backup_on_fifth_start(tmp_path: Path) -> None:
    counter = tmp_path / ".backup_counter"
    counter.write_text("invalid counter")
    database = Database(db_path=tmp_path / "vault.db")

    for _ in range(5):
        database.initialize()
        database.close()

    assert len(list(tmp_path.glob(_BACKUP_GLOB))) == 1


@pytest.fixture
def database_closed_from_other_thread(
    db_path: Path,
) -> tuple[Database, sqlite3.Connection]:
    """Database la cui connessione è stata chiusa da un thread diverso da quello creatore."""
    database = Database(db_path=db_path)
    database.initialize()
    original = database.connection
    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(database.close).result()
    yield database, original
    original.close()
    database.close()


def test_close_wrong_thread_logs_error(db: Database, caplog: pytest.LogCaptureFixture) -> None:
    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(db.close).result()

    assert logging.ERROR in {record.levelno for record in caplog.records}


def test_close_wrong_thread_allows_reconnection_with_working_connection(
    database_closed_from_other_thread: tuple[Database, sqlite3.Connection],
) -> None:
    database, original = database_closed_from_other_thread

    connection = database.connection

    assert connection is not original
    assert connection.execute("SELECT COUNT(*) FROM sections").fetchone()[0] == 4


def test_close_twice_in_creating_thread_logs_nothing(
    db_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    database = Database(db_path=db_path)
    database.initialize()
    database.close()

    database.close()

    assert caplog.records == []


def test_initialize_backup_unlink_error_does_not_stop_pruning_older_copies(
    tmp_path: Path,
) -> None:
    database = Database(db_path=tmp_path / "vault.db")
    database.initialize()
    (tmp_path / "vault.auto.bak.20000101T000000").mkdir()
    _seed_old_backups(database, directory=tmp_path, days=range(2, 6))

    database.initialize()

    database.close()
    remaining = {path.name for path in tmp_path.glob("vault.auto.bak.2000*")}
    assert remaining.isdisjoint(
        {"vault.auto.bak.20000102T000000", "vault.auto.bak.20000103T000000"}
    )


def test_initialize_backup_unlink_error_preserves_recent_copies(tmp_path: Path) -> None:
    database = Database(db_path=tmp_path / "vault.db")
    database.initialize()
    (tmp_path / "vault.auto.bak.20000101T000000").mkdir()
    _seed_old_backups(database, directory=tmp_path, days=range(2, 6))

    database.initialize()

    database.close()
    remaining = {path.name for path in tmp_path.glob("vault.auto.bak.2000*")}
    assert {"vault.auto.bak.20000104T000000", "vault.auto.bak.20000105T000000"} <= remaining


def test_initialize_fresh_database_assigns_uuid_to_seed_sections(db_path: Path) -> None:
    """Regressione B6: le sezioni iniziali nascono con uuid già al primo avvio.

    Il seed girava dopo l'assegnazione degli uuid: fino al riavvio le sezioni
    restavano senza uuid e un sync nella stessa sessione esportava uuid nulli.
    """
    database = Database(db_path=db_path)

    database.initialize(language="it")

    try:
        uuids = [row[0] for row in database.connection.execute("SELECT uuid FROM sections")]
        assert len(uuids) == 4
        assert all(UUID(value) for value in uuids)
    finally:
        database.close()


def test_initialize_schema_error_recreates_fully_migrated_database(db_path: Path) -> None:
    """Regressione B9: il database ricreato dopo un errore di schema è già migrato.

    La ricreazione eseguiva solo DDL di base e seed: user_version restava 0 e
    mancavano le colonne uuid, quindi le query del sync fallivano fino al riavvio.
    """
    legacy = sqlite3.connect(db_path)
    # Una vista al posto della tabella entries fa fallire la creazione degli indici
    legacy.executescript(
        "CREATE TABLE sections (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);"
        "CREATE VIEW entries AS SELECT 1 AS id;"
    )
    legacy.close()
    database = Database(db_path=db_path)

    database.initialize(language="it")

    try:
        version = database.connection.execute("PRAGMA user_version").fetchone()[0]
        uuids = [row[0] for row in database.connection.execute("SELECT uuid FROM sections")]
        assert version == 3
        assert len(uuids) == 4
        assert all(UUID(value) for value in uuids)
    finally:
        database.close()


def test_connect_without_recreation_propagates_open_error(db_path: Path) -> None:
    # Ramo usato dalla ricreazione: se anche il nuovo file non si apre, l'errore sale
    db_path.write_bytes(b"corrupt sqlite file")
    database = Database(db_path=db_path)

    with pytest.raises(sqlite3.DatabaseError, match="not a database"):
        database._connect(_allow_recreate=False)


def test_initialize_locked_database_raises_and_keeps_the_file(
    db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un lock non è corruzione: niente ricreazione, la libreria dell'utente resta al suo posto."""
    database = Database(db_path=db_path)
    database.initialize(language="it")
    database.close()
    original = db_path.read_bytes()

    def locked(*args: object, **kwargs: object) -> None:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr("command_quiver.db.database.build_schema", locked)
    reopened = Database(db_path=db_path)

    with pytest.raises(sqlite3.OperationalError, match="locked"):
        reopened.initialize(language="it")

    reopened.close()
    assert list(db_path.parent.glob("*.db.bak.*")) == []
    assert db_path.read_bytes() == original


def test_initialize_corrupt_database_moves_its_wal_with_the_backup(db_path: Path) -> None:
    """Le transazioni non ancora consolidate seguono il file corrotto nel backup."""
    db_path.write_bytes(b"not a sqlite database\x00")
    wal = db_path.with_name(db_path.name + "-wal")
    wal.write_bytes(b"pending transactions")
    database = Database(db_path=db_path)

    database.initialize(language="it")

    try:
        backups = [
            p for p in db_path.parent.glob("*.db.bak.*") if not p.name.endswith(("-wal", "-shm"))
        ]
        assert len(backups) == 1
        moved_wal = backups[0].with_name(backups[0].name + "-wal")
        assert moved_wal.read_bytes() == b"pending transactions"
    finally:
        database.close()
