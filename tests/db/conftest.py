"""Test per i repository CRUD di sezioni e voci."""

from pathlib import Path

import pytest

from command_quiver.db.database import Database
from command_quiver.db.entry_repository import EntryRepository
from command_quiver.db.section_repository import SectionRepository
from command_quiver.db.sync_repository import SyncRepository


@pytest.fixture
def db(tmp_path: Path) -> Database:
    """Database inizializzato per i test."""
    database = Database(db_path=tmp_path / "test.db")
    database.initialize()
    yield database
    database.close()


@pytest.fixture
def sections(db: Database) -> SectionRepository:
    return SectionRepository(db.connection)


@pytest.fixture
def entries(db: Database) -> EntryRepository:
    return EntryRepository(db.connection)


@pytest.fixture
def legacy_sections(db: Database, sections: SectionRepository) -> SectionRepository:
    """Libreria legacy: nessuna sezione ha il flag di default, "Generale" esiste."""
    db.connection.execute("UPDATE sections SET is_default = 0")
    db.connection.commit()
    return sections


@pytest.fixture
def sections_without_default(db: Database, sections: SectionRepository) -> SectionRepository:
    """Libreria senza flag di default e senza la sezione "Generale"."""
    db.connection.execute("UPDATE sections SET is_default = 0")
    db.connection.execute("DELETE FROM sections WHERE name = 'Generale'")
    db.connection.commit()
    return sections


@pytest.fixture
def failing_tombstones(db: Database) -> None:
    """La scrittura della tombstone fallisce, come per un errore di disco a metà."""
    db.connection.execute(
        "CREATE TRIGGER fail_tombstone BEFORE INSERT ON sync_tombstones "
        "BEGIN SELECT RAISE(ABORT, 'disco pieno'); END"
    )
    db.connection.commit()


@pytest.fixture
def sync_repo(db: Database) -> SyncRepository:
    return SyncRepository(connection=db.connection)
