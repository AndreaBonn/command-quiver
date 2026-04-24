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

        backup = db_path.with_suffix(".db.bak")
        assert backup.exists()
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
            patch.object(db, "_connect", side_effect=lambda: setattr(db, "_connection", mock_conn)),
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
