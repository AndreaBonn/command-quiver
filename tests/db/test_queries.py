"""Test per i repository CRUD di sezioni e voci."""

from pathlib import Path

import pytest

from command_quiver.db.database import Database
from command_quiver.db.queries import (
    DuplicateSectionError,
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
        generale_id = sections.get_default_section_id()

        # Crea voce nella sezione Shell
        entries.create(EntryCreate(name="ls", content="ls -la", section_id=shell_id, type="shell"))

        # Elimina la sezione
        sections.delete(shell_id)

        # La voce deve essere in Generale
        all_entries = entries.get_all(section_id=generale_id)
        assert any(e.name == "ls" for e in all_entries)

    def test_cannot_delete_generale(self, sections: SectionRepository) -> None:
        generale_id = sections.get_default_section_id()
        result = sections.delete(generale_id)
        assert result is False

    def test_get_by_id_returns_none_for_nonexistent(self, sections: SectionRepository) -> None:
        assert sections.get_by_id(9999) is None

    def test_create_duplicate_section_raises(self, sections: SectionRepository) -> None:
        sections.create(name="Docker")
        with pytest.raises(DuplicateSectionError):
            sections.create(name="Docker")

    def test_create_duplicate_case_insensitive_raises(self, sections: SectionRepository) -> None:
        sections.create(name="Docker")
        with pytest.raises(DuplicateSectionError):
            sections.create(name="docker")

    def test_rename_to_duplicate_raises(self, sections: SectionRepository) -> None:
        all_sections = sections.get_all()
        with pytest.raises(DuplicateSectionError):
            sections.rename(section_id=all_sections[0].id, new_name="AI Prompts")

    def test_rename_same_name_different_case_raises(self, sections: SectionRepository) -> None:
        all_sections = sections.get_all()
        with pytest.raises(DuplicateSectionError):
            sections.rename(section_id=all_sections[0].id, new_name="ai prompts")

    def test_exists_case_insensitive(self, sections: SectionRepository) -> None:
        assert sections.exists("shell commands") is True
        assert sections.exists("Shell Commands") is True
        assert sections.exists("nonexistent") is False


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


class TestSectionEdgeCases:
    """Test edge case sezioni."""

    def test_get_default_section_id_creates_if_missing(self, db: Database) -> None:
        """Se nessuna sezione default esiste, get_default_section_id la crea."""
        # Elimina tutte le sezioni default
        db.connection.execute("DELETE FROM sections WHERE is_default = 1")
        db.connection.execute("DELETE FROM sections WHERE name = 'Generale'")
        db.connection.commit()

        sections = SectionRepository(db.connection)
        default_id = sections.get_default_section_id()
        assert default_id is not None

        # Verifica che esista nel database con flag is_default
        section = sections.get_by_id(default_id)
        assert section.name == "Generale"
        assert section.is_default == 1


class TestExportImport:
    """Test export e import voci."""

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

    def test_import_creates_entries(
        self, entries: EntryRepository, sections: SectionRepository
    ) -> None:
        data = [
            {"name": "test1", "content": "echo test", "type": "shell", "section_name": "Git"},
            {"name": "test2", "content": "prompt text", "type": "prompt", "section_name": "Git"},
        ]

        imported = entries.import_entries(data=data, section_repo=sections)
        assert imported == 2
        assert entries.count_all() == 2

    def test_import_creates_missing_sections(
        self, entries: EntryRepository, sections: SectionRepository
    ) -> None:
        data = [
            {"name": "x", "content": "y", "section_name": "NewSection"},
        ]
        entries.import_entries(data=data, section_repo=sections)

        all_sections = sections.get_all()
        names = [s.name for s in all_sections]
        assert "NewSection" in names

    def test_import_skips_invalid_entries(
        self, entries: EntryRepository, sections: SectionRepository
    ) -> None:
        data = [
            {"name": "", "content": "no name"},
            {"name": "no content", "content": ""},
            {"name": "valid", "content": "ok"},
        ]
        imported = entries.import_entries(data=data, section_repo=sections)
        assert imported == 1

    def test_export_import_roundtrip(
        self, entries: EntryRepository, sections: SectionRepository
    ) -> None:
        shell_id = sections.get_all()[0].id
        entries.create(
            EntryCreate(
                name="roundtrip",
                content="echo hello",
                section_id=shell_id,
                type="shell",
                tags="test,rt",
            )
        )

        exported = entries.export_all()
        assert len(exported) == 1

        # Pulisci e reimporta
        entries.delete(entries.get_all()[0].id)
        assert entries.count_all() == 0

        imported = entries.import_entries(data=exported, section_repo=sections)
        assert imported == 1

        result = entries.get_all()
        assert result[0].name == "roundtrip"
        assert result[0].tags == "test,rt"

    def test_get_default_section_id_finds_renamed_default(self, db: Database) -> None:
        """Se la sezione default viene rinominata, il flag is_default la identifica."""
        # Rinomina "Generale" ma mantieni is_default=1
        db.connection.execute("UPDATE sections SET name = 'Archivio' WHERE is_default = 1")
        db.connection.commit()

        sections = SectionRepository(db.connection)
        default_id = sections.get_default_section_id()
        section = sections.get_by_id(default_id)
        assert section.name == "Archivio"


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


class TestImportEdgeCases:
    """Test edge case import voci."""

    @pytest.fixture
    def sections(self, db: Database) -> SectionRepository:
        return SectionRepository(db.connection)

    @pytest.fixture
    def entries(self, db: Database) -> EntryRepository:
        return EntryRepository(db.connection)

    def test_import_truncates_over_limit(
        self, entries: EntryRepository, sections: SectionRepository
    ) -> None:
        """Import tronca dataset oltre MAX_IMPORT_ENTRIES."""
        # Usiamo un limite ridotto per il test
        original_limit = EntryRepository.MAX_IMPORT_ENTRIES
        EntryRepository.MAX_IMPORT_ENTRIES = 3
        try:
            data = [{"name": f"entry_{i}", "content": f"content_{i}"} for i in range(10)]
            imported = entries.import_entries(data=data, section_repo=sections)
            assert imported == 3
        finally:
            EntryRepository.MAX_IMPORT_ENTRIES = original_limit

    def test_import_invalid_type_defaults_to_prompt(
        self, entries: EntryRepository, sections: SectionRepository
    ) -> None:
        """Tipo non valido viene normalizzato a 'prompt'."""
        data = [
            {"name": "test", "content": "content", "type": "invalid_type"},
        ]
        imported = entries.import_entries(data=data, section_repo=sections)
        assert imported == 1

        all_entries = entries.get_all()
        assert all_entries[0].type == "prompt"

    def test_import_whitespace_only_name_skipped(
        self, entries: EntryRepository, sections: SectionRepository
    ) -> None:
        """Voci con nome solo whitespace vengono saltate."""
        data = [
            {"name": "   ", "content": "content"},
        ]
        imported = entries.import_entries(data=data, section_repo=sections)
        assert imported == 0

    def test_import_missing_fields_handled(
        self, entries: EntryRepository, sections: SectionRepository
    ) -> None:
        """Voci senza campi obbligatori vengono gestite (convertite a str vuota)."""
        data = [
            {},  # Né nome né contenuto
            {"name": "valid", "content": "ok"},
        ]
        imported = entries.import_entries(data=data, section_repo=sections)
        assert imported == 1


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
