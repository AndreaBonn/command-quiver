"""Test per i repository CRUD di sezioni e voci."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from command_quiver.db.database import Database
from command_quiver.db.queries import (
    DuplicateSectionError,
    EntryCreate,
    EntryRepository,
    EntryUpdate,
    SectionRepository,
    TombstoneRepository,
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


def test_get_default_section_id_flagged_section_returns_its_id(
    sections: SectionRepository,
) -> None:
    flagged = next(section for section in sections.get_all() if section.is_default)
    count_before = len(sections.get_all())

    default_id = sections.get_default_section_id()

    assert default_id == flagged.id
    assert len(sections.get_all()) == count_before


def test_get_default_section_id_legacy_generale_returns_generale_id(
    legacy_sections: SectionRepository,
) -> None:
    generale = next(section for section in legacy_sections.get_all() if section.name == "Generale")

    assert legacy_sections.get_default_section_id() == generale.id


def test_get_default_section_id_legacy_generale_flags_it_as_default(
    legacy_sections: SectionRepository,
) -> None:
    default_id = legacy_sections.get_default_section_id()

    assert legacy_sections.get_by_id(section_id=default_id).is_default == 1


def test_get_default_section_id_missing_generale_creates_default_section(
    sections_without_default: SectionRepository,
) -> None:
    count_before = len(sections_without_default.get_all())

    default_id = sections_without_default.get_default_section_id()

    created = sections_without_default.get_by_id(section_id=default_id)
    assert (created.name, created.icon, created.is_default) == ("Generale", "folder", 1)
    assert len(sections_without_default.get_all()) == count_before + 1


def test_get_default_section_id_missing_generale_assigns_uuid(
    sections_without_default: SectionRepository,
) -> None:
    default_id = sections_without_default.get_default_section_id()

    assert sections_without_default.get_by_id(section_id=default_id).uuid


def test_get_default_section_id_missing_generale_repeated_call_returns_same_section(
    sections_without_default: SectionRepository,
) -> None:
    first = sections_without_default.get_default_section_id()
    count_after_first = len(sections_without_default.get_all())

    second = sections_without_default.get_default_section_id()

    assert second == first
    assert len(sections_without_default.get_all()) == count_after_first


def test_create_with_uuid_custom_values_returns_created_section(
    sections: SectionRepository,
) -> None:
    created = sections.create_with_uuid(name="Remote", section_uuid="remote-section", icon="star")

    assert (created.name, created.uuid, created.icon) == ("Remote", "remote-section", "star")


def test_create_with_uuid_appends_section_after_existing_ones(
    sections: SectionRepository,
) -> None:
    last_position = max(section.position for section in sections.get_all())

    sections.create_with_uuid(name="Remote", section_uuid="remote-section")

    stored = sections.get_by_uuid(section_uuid="remote-section")
    assert stored.position == last_position + 1


def test_create_with_uuid_section_is_found_by_uuid(sections: SectionRepository) -> None:
    created = sections.create_with_uuid(name="Remote", section_uuid="remote-section", icon="star")

    fetched = sections.get_by_uuid(section_uuid="remote-section")

    assert (fetched.id, fetched.name, fetched.icon, fetched.uuid) == (
        created.id,
        "Remote",
        "star",
        "remote-section",
    )


def test_get_by_uuid_section_absent_returns_none(sections: SectionRepository) -> None:
    assert sections.get_by_uuid(section_uuid="absent") is None


def test_update_from_sync_section_existing_updates_fields(sections: SectionRepository) -> None:
    created = sections.create(name="Before")
    timestamp = "2026-01-02T03:04:05"

    sections.update_from_sync(
        section_uuid=created.uuid, name="After", icon="star", updated_at=timestamp
    )

    result = sections.get_by_uuid(section_uuid=created.uuid)
    assert (result.id, result.name, result.icon, result.updated_at) == (
        created.id,
        "After",
        "star",
        timestamp,
    )


def test_update_from_sync_section_existing_returns_true(sections: SectionRepository) -> None:
    created = sections.create(name="Before")

    changed = sections.update_from_sync(
        section_uuid=created.uuid, name="After", icon="star", updated_at="2026-01-02T03:04:05"
    )

    assert changed is True


def test_update_from_sync_section_absent_returns_false_and_creates_nothing(
    sections: SectionRepository,
) -> None:
    count_before = len(sections.get_all())

    changed = sections.update_from_sync(
        section_uuid="absent", name="Ghost", icon="folder", updated_at="2026-01-02T03:04:05"
    )

    assert changed is False
    assert len(sections.get_all()) == count_before


@pytest.mark.parametrize("renamed", [False, True], ids=["generale", "renamed-default"])
def test_delete_default_section_preserves_section(
    sections: SectionRepository, renamed: bool
) -> None:
    default_id = sections.get_default_section_id()
    if renamed:
        sections.rename(section_id=default_id, new_name="Archive")
    expected = sections.get_by_id(section_id=default_id)

    deleted = sections.delete(section_id=default_id)

    assert deleted is False
    assert sections.get_by_id(section_id=default_id) == expected


def test_delete_section_removes_it_and_returns_true(sections: SectionRepository) -> None:
    source = sections.create(name="Temporary")

    deleted = sections.delete(section_id=source.id)

    assert deleted is True
    assert sections.get_by_id(section_id=source.id) is None


def test_delete_section_moves_its_entries_to_default_section(
    sections: SectionRepository, entries: EntryRepository
) -> None:
    source = sections.create(name="Temporary")
    default_id = sections.get_default_section_id()
    moved = entries.create(data=EntryCreate(name="Move", content="text", section_id=source.id))

    sections.delete(section_id=source.id)

    assert entries.get_by_id(entry_id=moved.id).section_id == default_id


def test_delete_section_leaves_other_entries_untouched(
    sections: SectionRepository, entries: EntryRepository
) -> None:
    source = sections.create(name="Temporary")
    default_id = sections.get_default_section_id()
    entries.create(data=EntryCreate(name="Move", content="text", section_id=source.id))
    kept = entries.create(data=EntryCreate(name="Keep", content="text", section_id=default_id))

    sections.delete(section_id=source.id)

    assert entries.get_by_id(entry_id=kept.id) == kept


def test_delete_section_with_uuid_records_tombstone(
    db: Database, sections: SectionRepository
) -> None:
    source = sections.create(name="Temporary")

    sections.delete(section_id=source.id)

    tombstones = TombstoneRepository(connection=db.connection)
    assert [(row["uuid"], row["entity_type"]) for row in tombstones.get_all()] == [
        (source.uuid, "section")
    ]


def test_delete_section_empty_uuid_deletes_without_tombstone(
    db: Database, sections: SectionRepository
) -> None:
    legacy = sections.create_with_uuid(name="Legacy", section_uuid="")

    deleted = sections.delete(section_id=legacy.id)

    assert deleted is True
    assert sections.get_by_id(section_id=legacy.id) is None
    assert TombstoneRepository(connection=db.connection).get_all() == []


def test_delete_section_absent_returns_false(sections: SectionRepository) -> None:
    assert sections.delete(section_id=9999) is False


def test_delete_by_uuid_section_existing_removes_it_and_returns_true(
    sections: SectionRepository,
) -> None:
    created = sections.create(name="Remote")

    deleted = sections.delete_by_uuid(section_uuid=created.uuid)

    assert deleted is True
    assert sections.get_by_uuid(section_uuid=created.uuid) is None


def test_delete_by_uuid_section_absent_returns_false(sections: SectionRepository) -> None:
    assert sections.delete_by_uuid(section_uuid="absent") is False


def test_delete_by_uuid_default_section_returns_false_and_preserves_it(
    sections: SectionRepository,
) -> None:
    default = sections.get_by_id(section_id=sections.get_default_section_id())

    deleted = sections.delete_by_uuid(section_uuid=default.uuid)

    assert deleted is False
    assert sections.get_by_uuid(section_uuid=default.uuid) == default


def _create_remote_entry(entries: EntryRepository, sections: SectionRepository, **timestamps: str):
    section_id = sections.get_default_section_id()
    return entries.create_from_sync(
        name="Remote",
        content="echo remote",
        entry_uuid="remote-entry",
        section_id=section_id,
        entry_type="shell",
        tags="sync,remote",
        **timestamps,
    )


def test_create_from_sync_entry_persists_given_fields(
    entries: EntryRepository, sections: SectionRepository
) -> None:
    section_id = sections.get_default_section_id()

    result = _create_remote_entry(entries, sections)

    assert (result.name, result.content, result.uuid, result.section_id) == (
        "Remote",
        "echo remote",
        "remote-entry",
        section_id,
    )
    assert (result.type, result.tags) == ("shell", "sync,remote")


def test_create_from_sync_entry_is_appended_to_personal_order(
    entries: EntryRepository, sections: SectionRepository
) -> None:
    entries.create(
        data=EntryCreate(name="First", content="text", section_id=sections.get_default_section_id())
    )

    result = _create_remote_entry(entries, sections)

    assert result.personal_pos == 1


def test_create_from_sync_entry_is_found_by_uuid(
    entries: EntryRepository, sections: SectionRepository
) -> None:
    result = _create_remote_entry(entries, sections)

    assert entries.get_by_uuid(entry_uuid="remote-entry") == result


def test_get_by_uuid_entry_absent_returns_none(entries: EntryRepository) -> None:
    assert entries.get_by_uuid(entry_uuid="absent") is None


def test_create_from_sync_entry_with_remote_timestamps_keeps_them(
    entries: EntryRepository, sections: SectionRepository
) -> None:
    result = _create_remote_entry(
        entries,
        sections,
        created_at="2025-01-01T00:00:00",
        updated_at="2025-02-01T00:00:00",
    )

    assert (result.created_at, result.updated_at) == ("2025-01-01T00:00:00", "2025-02-01T00:00:00")


def test_create_from_sync_entry_without_timestamps_generates_them(
    entries: EntryRepository, sections: SectionRepository
) -> None:
    result = _create_remote_entry(entries, sections)

    assert result.created_at
    assert result.updated_at


def _sync_changes(sections: SectionRepository) -> dict[str, str | int]:
    return dict(
        name="After",
        content="new",
        section_id=sections.get_default_section_id(),
        entry_type="shell",
        tags="remote",
        updated_at="2026-01-02T03:04:05",
    )


def test_update_from_sync_entry_existing_updates_fields(
    entries: EntryRepository, sections: SectionRepository
) -> None:
    created = entries.create(data=EntryCreate(name="Before", content="old"))
    changes = _sync_changes(sections)

    entries.update_from_sync(entry_uuid=created.uuid, **changes)

    result = entries.get_by_uuid(entry_uuid=created.uuid)
    assert (result.id, result.name, result.content, result.section_id) == (
        created.id,
        "After",
        "new",
        changes["section_id"],
    )
    assert (result.type, result.tags, result.updated_at) == (
        "shell",
        "remote",
        changes["updated_at"],
    )


def test_update_from_sync_entry_existing_keeps_created_at(
    entries: EntryRepository, sections: SectionRepository
) -> None:
    created = entries.create(data=EntryCreate(name="Before", content="old"))

    entries.update_from_sync(entry_uuid=created.uuid, **_sync_changes(sections))

    assert entries.get_by_uuid(entry_uuid=created.uuid).created_at == created.created_at


def test_update_from_sync_entry_existing_returns_true(
    entries: EntryRepository, sections: SectionRepository
) -> None:
    created = entries.create(data=EntryCreate(name="Before", content="old"))

    assert entries.update_from_sync(entry_uuid=created.uuid, **_sync_changes(sections)) is True


def test_update_from_sync_entry_absent_returns_false(
    entries: EntryRepository, sections: SectionRepository
) -> None:
    assert entries.update_from_sync(entry_uuid="absent", **_sync_changes(sections)) is False


def test_delete_by_uuid_entry_existing_removes_only_target(entries: EntryRepository) -> None:
    removed = entries.create(data=EntryCreate(name="Remove", content="text"))
    kept = entries.create(data=EntryCreate(name="Keep", content="text"))

    deleted = entries.delete_by_uuid(entry_uuid=removed.uuid)

    assert deleted is True
    assert entries.get_by_uuid(entry_uuid=removed.uuid) is None
    assert entries.get_by_uuid(entry_uuid=kept.uuid) == kept


def test_delete_by_uuid_entry_absent_returns_false(entries: EntryRepository) -> None:
    assert entries.delete_by_uuid(entry_uuid="absent") is False


@pytest.mark.parametrize("entry_uuid", ["entry-id", ""], ids=["uuid", "legacy-empty-uuid"])
def test_delete_entry_removes_only_target(
    entries: EntryRepository,
    entry_uuid: str,
) -> None:
    removed = entries.create_from_sync(
        name="Remove", content="text", entry_uuid=entry_uuid, section_id=None
    )
    kept = entries.create(data=EntryCreate(name="Keep", content="text"))

    deleted = entries.delete(entry_id=removed.id)

    assert deleted is True
    assert entries.get_by_id(entry_id=removed.id) is None
    assert entries.get_by_id(entry_id=kept.id) == kept


def test_delete_entry_with_uuid_records_tombstone(db: Database, entries: EntryRepository) -> None:
    removed = entries.create_from_sync(
        name="Remove", content="text", entry_uuid="entry-id", section_id=None
    )

    entries.delete(entry_id=removed.id)

    tombstones = TombstoneRepository(connection=db.connection)
    assert [(row["uuid"], row["entity_type"]) for row in tombstones.get_all()] == [
        ("entry-id", "entry")
    ]


def test_delete_entry_empty_uuid_records_no_tombstone(
    db: Database, entries: EntryRepository
) -> None:
    removed = entries.create_from_sync(
        name="Remove", content="text", entry_uuid="", section_id=None
    )

    entries.delete(entry_id=removed.id)

    assert TombstoneRepository(connection=db.connection).get_all() == []


@pytest.mark.parametrize(
    "invalid_item",
    [
        {},
        {"name": "   ", "content": "text"},
        {"name": "name", "content": "   "},
        {"name": "", "content": "text"},
        {"name": "name", "content": ""},
    ],
    ids=["no-fields", "blank-name", "blank-content", "empty-name", "empty-content"],
)
def test_import_entries_invalid_item_is_skipped(
    entries: EntryRepository, sections: SectionRepository, invalid_item: dict
) -> None:
    data = [invalid_item, {"name": "valid", "content": "text"}]

    imported = entries.import_entries(data=data, section_repo=sections)

    assert imported == 1
    assert [row.name for row in entries.get_all()] == ["valid"]


def test_import_entries_strips_surrounding_whitespace(
    entries: EntryRepository, sections: SectionRepository
) -> None:
    data = [{"name": " shell ", "content": " echo hi "}]

    entries.import_entries(data=data, section_repo=sections)

    result = entries.get_all()[0]
    assert (result.name, result.content) == ("shell", "echo hi")


@pytest.mark.parametrize(
    ("given_type", "stored_type"),
    [("shell", "shell"), ("prompt", "prompt"), ("invalid", "prompt")],
    ids=["shell-kept", "prompt-kept", "invalid-falls-back-to-prompt"],
)
def test_import_entries_type_is_validated(
    entries: EntryRepository, sections: SectionRepository, given_type: str, stored_type: str
) -> None:
    data = [{"name": "name", "content": "text", "type": given_type}]

    entries.import_entries(data=data, section_repo=sections)

    assert entries.get_all()[0].type == stored_type


def test_import_entries_without_section_name_uses_generale(
    entries: EntryRepository, sections: SectionRepository
) -> None:
    data = [{"name": "name", "content": "text"}]

    entries.import_entries(data=data, section_repo=sections)

    assert entries.get_all()[0].section_name == "Generale"


def test_import_entries_same_new_section_is_created_once(
    entries: EntryRepository, sections: SectionRepository
) -> None:
    count_before = len(sections.get_all())
    data = [
        {"name": "one", "content": "text", "section_name": "Imported"},
        {"name": "two", "content": "text", "section_name": "Imported"},
    ]

    entries.import_entries(data=data, section_repo=sections)

    imported = next(section for section in sections.get_all() if section.name == "Imported")
    assert imported.entry_count == 2
    assert len(sections.get_all()) == count_before + 1


def test_import_entries_over_limit_imports_only_prefix(
    entries: EntryRepository,
    sections: SectionRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(EntryRepository, "MAX_IMPORT_ENTRIES", 2)
    data = [{"name": f"entry-{index}", "content": "text"} for index in range(3)]

    assert entries.import_entries(data=data, section_repo=sections) == 2

    assert [row.name for row in entries.get_all(sort_order="alpha_asc")] == ["entry-0", "entry-1"]
    assert len(data) == 3


def test_import_entries_long_fields_truncates_stored_values(
    entries: EntryRepository,
    sections: SectionRepository,
) -> None:
    limit = EntryRepository.MAX_FIELD_LENGTH
    data = [{"name": "n" * (limit + 1), "content": "c" * (limit + 1), "tags": "t" * (limit + 1)}]

    assert entries.import_entries(data=data, section_repo=sections) == 1

    result = entries.get_all()[0]
    assert (result.name, result.content, result.tags) == ("n" * limit, "c" * limit, "t" * limit)
    assert len(data[0]["name"]) == limit + 1


def test_add_tombstone_existing_uuid_replaces_remote_data(db: Database) -> None:
    tombstones = TombstoneRepository(connection=db.connection)
    tombstones.add(tombstone_uuid="remote", entity_type="entry", deleted_at="2025-01-01")

    tombstones.add(tombstone_uuid="remote", entity_type="section", deleted_at="2025-02-01")

    assert tombstones.get_all() == [
        {"uuid": "remote", "entity_type": "section", "deleted_at": "2025-02-01"}
    ]


def _tombstones_with_old_recent_and_new(db: Database) -> TombstoneRepository:
    tombstones = TombstoneRepository(connection=db.connection)
    old = (datetime.now() - timedelta(days=100)).isoformat()
    recent = (datetime.now() - timedelta(days=10)).isoformat()
    tombstones.add(tombstone_uuid="old", entity_type="entry", deleted_at=old)
    tombstones.add(tombstone_uuid="recent", entity_type="section", deleted_at=recent)
    tombstones.add(tombstone_uuid="now", entity_type="entry")
    return tombstones


def test_cleanup_tombstones_removes_only_expired_ones(db: Database) -> None:
    tombstones = _tombstones_with_old_recent_and_new(db)

    removed = tombstones.cleanup()

    assert removed == 1
    assert {row["uuid"] for row in tombstones.get_all()} == {"recent", "now"}


def test_cleanup_tombstones_repeated_removes_nothing(db: Database) -> None:
    tombstones = _tombstones_with_old_recent_and_new(db)
    tombstones.cleanup()

    assert tombstones.cleanup() == 0


# --- Identità delle sezioni fra dispositivi ---


def test_get_by_name_ignores_case(sections: SectionRepository) -> None:
    created = sections.create(name="Lavoro")

    found = sections.get_by_name("LAVORO")

    assert found.id == created.id


def test_get_by_name_unknown_returns_none(sections: SectionRepository) -> None:
    sections.create(name="Lavoro")

    assert sections.get_by_name("Svago") is None


def test_adopt_uuid_replaces_identity_and_keeps_entries(
    sections: SectionRepository, entries: EntryRepository
) -> None:
    section = sections.create(name="Lavoro")
    entry = entries.create(EntryCreate(name="e", content="c", section_id=section.id))

    sections.adopt_uuid(section_id=section.id, section_uuid="remote-uuid")

    assert sections.get_by_uuid("remote-uuid").id == section.id
    assert sections.get_by_uuid(section.uuid) is None
    assert entries.get_by_id(entry.id).section_id == section.id


# --- Formato unico dei timestamp (B2) ---


def _is_recent_utc(value: str) -> bool:
    moment = datetime.fromisoformat(value)
    return moment.utcoffset() == timedelta(0) and (
        datetime.now(timezone.utc) - moment < timedelta(minutes=1)
    )


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


def test_create_section_writes_utc_timestamp(sections: SectionRepository) -> None:
    sections.create(name="Lavoro")

    assert _is_recent_utc(sections.get_by_name("Lavoro").updated_at)


def test_rename_section_writes_utc_timestamp(sections: SectionRepository) -> None:
    section = sections.create(name="Lavoro")

    sections.rename(section_id=section.id, new_name="Studio")

    assert _is_recent_utc(sections.get_by_id(section.id).updated_at)


def test_delete_entry_writes_utc_tombstone(entries: EntryRepository, db: Database) -> None:
    created = entries.create(EntryCreate(name="e", content="c"))

    entries.delete(created.id)

    tombstone = TombstoneRepository(db.connection).get_all()[0]
    assert _is_recent_utc(tombstone["deleted_at"])
