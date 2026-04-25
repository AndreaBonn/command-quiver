"""Test per il modulo database: schema, inizializzazione, ricreazione."""

import sqlite3
from pathlib import Path

import pytest

from command_quiver.db.database import Database


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


class TestMigrationSystem:
    """Test sistema di migrazioni incrementali."""

    def test_user_version_set_after_initialize(self, db: Database) -> None:
        version = db.connection.execute("PRAGMA user_version").fetchone()[0]
        assert version >= 1

    def test_migrations_idempotent(self, db: Database) -> None:
        """Chiamare _migrate() più volte non causa errori."""
        db._migrate()
        db._migrate()
        version = db.connection.execute("PRAGMA user_version").fetchone()[0]
        assert version >= 1

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
        assert version == 1
        db.close()

    def test_fresh_db_gets_latest_version(self, tmp_path: Path) -> None:
        """DB nuovo ottiene versione massima delle migrazioni."""
        db_path = tmp_path / "fresh.db"
        db = Database(db_path=db_path)
        db.initialize()

        version = db.connection.execute("PRAGMA user_version").fetchone()[0]
        assert version >= 1
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
        counter_file.write_text(str(Database._BACKUP_EVERY_N - 1))

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
        counter_file.write_text(str(Database._BACKUP_EVERY_N - 1))

        db = Database(db_path=db_path)
        db.initialize()
        db.close()

        backups = list(tmp_path.glob("vault.auto.bak.*"))
        assert len(backups) == Database._MAX_BACKUPS

    def test_backup_is_valid_sqlite(self, tmp_path: Path) -> None:
        """Il backup deve essere un DB SQLite valido."""
        db_path = tmp_path / "vault.db"
        counter_file = tmp_path / ".backup_counter"
        counter_file.write_text(str(Database._BACKUP_EVERY_N - 1))

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
        db = Database(db_path=db_path)
        db._auto_backup()  # Non deve sollevare eccezioni
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

        with patch("command_quiver.db.database.Path.write_text", side_effect=OSError("perm")):
            db._auto_backup()  # Non deve sollevare eccezioni

        db.close()

    def test_auto_backup_handles_sqlite_backup_error(self, tmp_path: Path) -> None:
        """Errore SQLite durante backup non propaga eccezione."""
        from unittest.mock import patch

        db_path = tmp_path / "vault.db"
        db = Database(db_path=db_path)
        db.initialize()

        # Resetta counter per triggerare backup alla prossima chiamata
        counter_file = tmp_path / ".backup_counter"
        counter_file.write_text(str(Database._BACKUP_EVERY_N - 1))

        # Intercetta sqlite3.connect nel modulo database per far fallire il backup
        def failing_connect(path, *args, **kwargs):
            raise sqlite3.Error("backup connection fail")

        with patch("command_quiver.db.database.sqlite3.connect", side_effect=failing_connect):
            db._auto_backup()  # Non deve sollevare eccezioni

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
        version = db._detect_schema_version()
        assert version == 0
        db.close()
