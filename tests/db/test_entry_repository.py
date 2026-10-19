"""Test per i repository CRUD di sezioni e voci."""

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from command_quiver.db.database import Database
from command_quiver.db.entry_repository import EntryRepository
from command_quiver.db.models import EntryCreate, EntryUpdate
from command_quiver.db.section_repository import SectionRepository
from command_quiver.db.tombstone_repository import TombstoneRepository


def _is_recent_utc(value: str) -> bool:
    moment = datetime.fromisoformat(value)
    return moment.utcoffset() == timedelta(0) and (
        datetime.now(timezone.utc) - moment < timedelta(minutes=1)
    )


class TestEntryRepository:
    """Test CRUD voci."""

    @pytest.fixture
    def shell_section_id(self, sections: SectionRepository) -> int:
        return sections.get_all()[0].id

    def test_create_entry(self, entries: EntryRepository, shell_section_id: int) -> None:
        entry = entries.create(
            EntryCreate(
                name="Docker PS",
                content="docker ps -a",
                section_id=shell_section_id,
                type="shell",
                tags="docker,container",
            )
        )
        assert entry.id is not None
        assert entry.name == "Docker PS"
        assert entry.type == "shell"
        assert entry.tags == "docker,container"

    def test_get_by_id(self, entries: EntryRepository, shell_section_id: int) -> None:
        created = entries.create(
            EntryCreate(name="test", content="content", section_id=shell_section_id)
        )
        fetched = entries.get_by_id(created.id)
        assert fetched.name == "test"
        assert fetched.content == "content"

    def test_update_entry(self, entries: EntryRepository, shell_section_id: int) -> None:
        created = entries.create(
            EntryCreate(name="old name", content="old content", section_id=shell_section_id)
        )
        updated = entries.update(
            EntryUpdate(
                id=created.id,
                name="new name",
                content="new content",
                section_id=shell_section_id,
                type="shell",
            )
        )
        assert updated.name == "new name"
        assert updated.content == "new content"
        assert updated.type == "shell"

    def test_delete_entry(self, entries: EntryRepository, shell_section_id: int) -> None:
        created = entries.create(
            EntryCreate(name="to delete", content="content", section_id=shell_section_id)
        )
        assert entries.delete(created.id) is True
        assert entries.get_by_id(created.id) is None

    def test_delete_nonexistent_returns_false(self, entries: EntryRepository) -> None:
        assert entries.delete(9999) is False

    def test_count_all(self, entries: EntryRepository, shell_section_id: int) -> None:
        assert entries.count_all() == 0
        entries.create(EntryCreate(name="a", content="b", section_id=shell_section_id))
        entries.create(EntryCreate(name="c", content="d", section_id=shell_section_id))
        assert entries.count_all() == 2


class TestEntryFiltering:
    """Test ricerca e ordinamento."""

    @pytest.fixture(autouse=True)
    def _seed_entries(self, entries: EntryRepository, sections: SectionRepository) -> None:
        all_sections = sections.get_all()
        shell_id = all_sections[0].id
        ai_id = all_sections[1].id

        entries.create(
            EntryCreate(
                name="Docker Build", content="docker build .", section_id=shell_id, type="shell"
            )
        )
        entries.create(
            EntryCreate(name="Git Status", content="git status", section_id=shell_id, type="shell")
        )
        entries.create(
            EntryCreate(
                name="AI Summary", content="Summarize this text", section_id=ai_id, type="prompt"
            )
        )
        entries.create(
            EntryCreate(name="Alpha First", content="abc", section_id=ai_id, type="prompt")
        )

    def test_filter_by_section(self, entries: EntryRepository, sections: SectionRepository) -> None:
        shell_id = sections.get_all()[0].id
        result = entries.get_all(section_id=shell_id)
        assert len(result) == 2
        assert all(e.type == "shell" for e in result)

    def test_filter_by_search(self, entries: EntryRepository) -> None:
        result = entries.get_all(search="docker")
        assert len(result) == 1
        assert result[0].name == "Docker Build"

    def test_search_case_insensitive(self, entries: EntryRepository) -> None:
        result = entries.get_all(search="DOCKER")
        assert len(result) == 1

    def test_search_case_insensitive_unicode(
        self, entries: EntryRepository, sections: SectionRepository
    ) -> None:
        """Ricerca case-insensitive per caratteri accentati/unicode."""
        shell_id = sections.get_all()[0].id
        entries.create(
            EntryCreate(
                name="Résumé Generator",
                content="generate résumé",
                section_id=shell_id,
            )
        )
        # Cerca con case diverso
        result = entries.get_all(search="résumé")
        assert len(result) == 1
        result = entries.get_all(search="RÉSUMÉ")
        assert len(result) == 1

    def test_sort_alpha_asc(self, entries: EntryRepository) -> None:
        result = entries.get_all(sort_order="alpha_asc")
        names = [e.name for e in result]
        assert names == sorted(names)

    def test_sort_alpha_desc(self, entries: EntryRepository) -> None:
        result = entries.get_all(sort_order="alpha_desc")
        names = [e.name for e in result]
        assert names == sorted(names, reverse=True)

    def test_get_all_no_filters(self, entries: EntryRepository) -> None:
        result = entries.get_all()
        assert len(result) == 4

    def test_search_with_section_filter(
        self, entries: EntryRepository, sections: SectionRepository
    ) -> None:
        ai_id = sections.get_all()[1].id
        result = entries.get_all(section_id=ai_id, search="alpha")
        assert len(result) == 1
        assert result[0].name == "Alpha First"


class TestEntryPosition:
    """Test ordinamento personale."""

    def test_update_position(self, entries: EntryRepository, sections: SectionRepository) -> None:
        shell_id = sections.get_all()[0].id
        entry = entries.create(EntryCreate(name="test", content="c", section_id=shell_id))

        entries.update_position(entry_id=entry.id, new_position=42)

        updated = entries.get_by_id(entry.id)
        assert updated.personal_pos == 42


class TestEntryEdgeCases:
    """Test edge case voci."""

    def test_update_nonexistent_returns_none(self, entries: EntryRepository) -> None:
        result = entries.update(
            EntryUpdate(
                id=9999,
                name="ghost",
                content="nope",
                section_id=1,
                type="prompt",
            )
        )
        assert result is None

    def test_get_all_with_invalid_sort_falls_back(
        self,
        entries: EntryRepository,
        sections: SectionRepository,
    ) -> None:
        """Sort order sconosciuto usa il default."""
        shell_id = sections.get_all()[0].id
        entries.create(
            EntryCreate(
                name="a",
                content="b",
                section_id=shell_id,
            )
        )
        result = entries.get_all(sort_order="nonexistent_sort")
        assert len(result) == 1  # Funziona comunque con fallback

    def test_get_by_id_returns_none_for_nonexistent(self, entries: EntryRepository) -> None:
        assert entries.get_by_id(9999) is None

    def test_update_position_nonexistent_returns_false(self, entries: EntryRepository) -> None:
        assert entries.update_position(entry_id=9999, new_position=0) is False


class TestGetAllPagination:
    """Test paginazione di get_all."""

    @pytest.fixture
    def sections(self, db: Database) -> SectionRepository:
        return SectionRepository(db.connection)

    @pytest.fixture
    def entries(self, db: Database) -> EntryRepository:
        return EntryRepository(db.connection)

    def test_get_all_with_limit(
        self, entries: EntryRepository, sections: SectionRepository
    ) -> None:
        shell_id = sections.get_all()[0].id
        for i in range(5):
            entries.create(EntryCreate(name=f"e{i}", content=f"c{i}", section_id=shell_id))

        result = entries.get_all(limit=2)
        assert len(result) == 2

    def test_get_all_with_offset(
        self, entries: EntryRepository, sections: SectionRepository
    ) -> None:
        shell_id = sections.get_all()[0].id
        for i in range(5):
            entries.create(EntryCreate(name=f"e{i}", content=f"c{i}", section_id=shell_id))

        all_entries = entries.get_all(sort_order="alpha_asc")
        offset_entries = entries.get_all(sort_order="alpha_asc", offset=2)
        assert len(offset_entries) == 3
        assert offset_entries[0].name == all_entries[2].name


def test_create_entry_writes_utc_timestamps(entries: EntryRepository) -> None:
    """Regressione B2: la voce nuova non usa più il formato di CURRENT_TIMESTAMP."""
    created = entries.create(EntryCreate(name="e", content="c"))

    stored = entries.get_by_id(created.id)

    assert _is_recent_utc(stored.created_at)
    assert _is_recent_utc(stored.updated_at)


def test_update_entry_writes_utc_timestamp(entries: EntryRepository) -> None:
    created = entries.create(EntryCreate(name="e", content="c"))

    updated = entries.update(EntryUpdate(id=created.id, name="e2", content="c2"))

    assert _is_recent_utc(updated.updated_at)


def test_delete_entry_writes_utc_tombstone(entries: EntryRepository, db: Database) -> None:
    created = entries.create(EntryCreate(name="e", content="c"))

    entries.delete(created.id)

    tombstone = TombstoneRepository(db.connection).get_all()[0]
    assert _is_recent_utc(tombstone["deleted_at"])


@pytest.mark.usefixtures("failing_tombstones")
def test_delete_entry_tombstone_failure_keeps_entry(entries: EntryRepository, db: Database) -> None:
    """Regressione B8: senza tombstone la voce non sparisce, altrimenti il sync la ricrea."""
    created = entries.create(EntryCreate(name="e", content="c"))

    with pytest.raises(sqlite3.IntegrityError):
        entries.delete(created.id)

    db.connection.rollback()
    assert entries.get_by_id(created.id) is not None


def test_delete_entry_without_failure_removes_entry_and_records_tombstone(
    entries: EntryRepository, db: Database
) -> None:
    """Positivo appaiato di B8: senza errori voce rimossa e tombstone presente."""
    created = entries.create(EntryCreate(name="e", content="c"))

    entries.delete(created.id)

    assert entries.get_by_id(created.id) is None
    assert [t["uuid"] for t in TombstoneRepository(db.connection).get_all()] == [created.uuid]


class TestExportImport:
    def test_export_returns_all_entries(
        self, entries: EntryRepository, sections: SectionRepository
    ) -> None:
        shell_id = sections.get_all()[0].id
        entries.create(
            EntryCreate(name="cmd1", content="echo 1", section_id=shell_id, type="shell")
        )
        entries.create(
            EntryCreate(name="cmd2", content="echo 2", section_id=shell_id, type="shell")
        )

        exported = entries.export_all()
        assert len(exported) == 2
        assert exported[0]["name"] == "cmd1"
        assert exported[0]["section_name"] == "Shell Commands"
