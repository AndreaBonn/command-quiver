"""Test del ranking per uso: contatore locale e ordinamento "più usati"."""

from pathlib import Path

import pytest

from command_quiver.db.database import Database
from command_quiver.db.queries import EntryCreate, EntryRepository, SectionRepository


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(db_path=tmp_path / "test.db")
    database.initialize()
    yield database
    database.close()


@pytest.fixture
def entries(db: Database) -> EntryRepository:
    return EntryRepository(db.connection)


@pytest.fixture
def sections(db: Database) -> SectionRepository:
    return SectionRepository(db.connection)


@pytest.fixture
def section_id(sections: SectionRepository) -> int:
    return sections.get_all()[0].id


def test_new_entry_starts_with_zero_uses(entries: EntryRepository, section_id: int) -> None:
    entry = entries.create(EntryCreate(name="A", content="x", section_id=section_id))
    assert entry.use_count == 0
    assert entry.last_used_at == ""


def test_bump_usage_increments_count(entries: EntryRepository, section_id: int) -> None:
    entry = entries.create(EntryCreate(name="A", content="x", section_id=section_id))

    entries.bump_usage(entry.id)
    entries.bump_usage(entry.id)

    assert entries.get_by_id(entry.id).use_count == 2


def test_bump_usage_sets_last_used_at(entries: EntryRepository, section_id: int) -> None:
    entry = entries.create(EntryCreate(name="A", content="x", section_id=section_id))

    entries.bump_usage(entry.id)

    assert entries.get_by_id(entry.id).last_used_at != ""


def test_bump_usage_does_not_touch_updated_at(
    db: Database, entries: EntryRepository, section_id: int
) -> None:
    """Il bump è locale: NON deve modificare updated_at, altrimenti il merge
    sync (last-write-wins) propagherebbe l'uso come una modifica del contenuto."""
    entry = entries.create(EntryCreate(name="A", content="x", section_id=section_id))
    # Ancora updated_at a un valore noto e passato.
    db.connection.execute(
        "UPDATE entries SET updated_at = ? WHERE id = ?",
        ("2020-01-01T00:00:00", entry.id),
    )
    db.connection.commit()

    entries.bump_usage(entry.id)

    assert entries.get_by_id(entry.id).updated_at == "2020-01-01T00:00:00"


def test_get_all_usage_sort_orders_by_count_desc(entries: EntryRepository, section_id: int) -> None:
    a = entries.create(EntryCreate(name="A", content="x", section_id=section_id))
    # B resta a 0 usi: deve finire ultima.
    entries.create(EntryCreate(name="B", content="x", section_id=section_id))
    c = entries.create(EntryCreate(name="C", content="x", section_id=section_id))

    for _ in range(3):
        entries.bump_usage(c.id)
    entries.bump_usage(a.id)

    result = entries.get_all(section_id=section_id, sort_order="usage")

    assert [e.name for e in result] == ["C", "A", "B"]


def test_usage_count_is_not_exported_for_sync(entries: EntryRepository, section_id: int) -> None:
    """Il contatore è locale per device: non deve finire nel payload di sync."""
    entry = entries.create(EntryCreate(name="A", content="x", section_id=section_id))
    entries.bump_usage(entry.id)

    exported = entries.export_for_sync()

    assert exported, "atteso almeno un record esportato"
    assert "use_count" not in exported[0]
    assert "last_used_at" not in exported[0]
