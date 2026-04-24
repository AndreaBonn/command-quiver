"""Test per i repository CRUD di sezioni e voci."""

from pathlib import Path

import pytest

from command_quiver.db.database import Database
from command_quiver.db.queries import (
    EntryCreate,
    EntryRepository,
    EntryUpdate,
    SectionRepository,
)


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


# --- Test SectionRepository ---


class TestSectionRepository:
    """Test CRUD sezioni."""

    def test_get_all_returns_default_sections(self, sections: SectionRepository) -> None:
        result = sections.get_all()
        assert len(result) == 4
        assert result[0].name == "Shell Commands"

    def test_get_all_includes_entry_count(
        self,
        sections: SectionRepository,
        entries: EntryRepository,
    ) -> None:
        # Crea una voce nella prima sezione
        all_sections = sections.get_all()
        entries.create(
            EntryCreate(
                name="test", content="echo hello", section_id=all_sections[0].id, type="shell"
            )
        )

        result = sections.get_all()
        shell_section = next(s for s in result if s.name == "Shell Commands")
        assert shell_section.entry_count == 1

    def test_create_section(self, sections: SectionRepository) -> None:
        section = sections.create(name="Docker")
        assert section.id is not None
        assert section.name == "Docker"
        assert section.position == 4  # Dopo le 4 di default

    def test_rename_section(self, sections: SectionRepository) -> None:
        all_sections = sections.get_all()
        result = sections.rename(section_id=all_sections[0].id, new_name="Comandi Shell")
        assert result is True

        updated = sections.get_by_id(all_sections[0].id)
        assert updated.name == "Comandi Shell"

    def test_delete_section_moves_entries_to_generale(
        self, sections: SectionRepository, entries: EntryRepository
    ) -> None:
        all_sections = sections.get_all()
        shell_id = all_sections[0].id  # Shell Commands
        generale_id = sections.get_generale_id()

        # Crea voce nella sezione Shell
        entries.create(EntryCreate(name="ls", content="ls -la", section_id=shell_id, type="shell"))

        # Elimina la sezione
        sections.delete(shell_id)

        # La voce deve essere in Generale
        all_entries = entries.get_all(section_id=generale_id)
        assert any(e.name == "ls" for e in all_entries)

    def test_cannot_delete_generale(self, sections: SectionRepository) -> None:
        generale_id = sections.get_generale_id()
        result = sections.delete(generale_id)
        assert result is False

    def test_get_by_id_returns_none_for_nonexistent(self, sections: SectionRepository) -> None:
        assert sections.get_by_id(9999) is None


# --- Test EntryRepository ---


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


class TestSectionEdgeCases:
    """Test edge case sezioni."""

    def test_get_generale_id_creates_if_missing(self, db: Database) -> None:
        """Se 'Generale' non esiste, get_generale_id la crea."""
        # Elimina la sezione Generale
        db.connection.execute("DELETE FROM sections WHERE name = 'Generale'")
        db.connection.commit()

        sections = SectionRepository(db.connection)
        generale_id = sections.get_generale_id()
        assert generale_id is not None

        # Verifica che esista nel database
        section = sections.get_by_id(generale_id)
        assert section.name == "Generale"


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
