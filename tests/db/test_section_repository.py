"""Test per i repository CRUD di sezioni e voci."""

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from command_quiver.db.database import Database
from command_quiver.db.entry_repository import EntryRepository
from command_quiver.db.models import DuplicateSectionError, EntryCreate
from command_quiver.db.section_repository import SectionRepository
from command_quiver.db.tombstone_repository import TombstoneRepository


def _is_recent_utc(value: str) -> bool:
    moment = datetime.fromisoformat(value)
    return moment.utcoffset() == timedelta(0) and (
        datetime.now(timezone.utc) - moment < timedelta(minutes=1)
    )


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


def test_delete_section_absent_returns_false(sections: SectionRepository) -> None:
    assert sections.delete(section_id=9999) is False


def test_create_section_writes_utc_timestamp(sections: SectionRepository) -> None:
    sections.create(name="Lavoro")

    assert _is_recent_utc(sections.get_by_name("Lavoro").updated_at)


def test_rename_section_writes_utc_timestamp(sections: SectionRepository) -> None:
    section = sections.create(name="Lavoro")

    sections.rename(section_id=section.id, new_name="Studio")

    assert _is_recent_utc(sections.get_by_id(section.id).updated_at)


@pytest.mark.usefixtures("failing_tombstones")
def test_delete_section_tombstone_failure_keeps_section_and_entries(
    sections: SectionRepository, entries: EntryRepository, db: Database
) -> None:
    section = sections.create(name="Lavoro")
    entry = entries.create(EntryCreate(name="e", content="c", section_id=section.id))

    with pytest.raises(sqlite3.IntegrityError):
        sections.delete(section.id)

    db.connection.rollback()
    assert sections.get_by_id(section.id) is not None
    assert entries.get_by_id(entry.id).section_id == section.id


def test_create_section_returns_stored_created_at(sections: SectionRepository) -> None:
    created = sections.create(name="Lavoro")

    assert created.created_at == sections.get_by_id(created.id).created_at != ""


class TestExportImport:
    def test_get_default_section_id_finds_renamed_default(self, db: Database) -> None:
        """Se la sezione default viene rinominata, il flag is_default la identifica."""
        # Rinomina "Generale" ma mantieni is_default=1
        db.connection.execute("UPDATE sections SET name = 'Archivio' WHERE is_default = 1")
        db.connection.commit()

        sections = SectionRepository(db.connection)
        default_id = sections.get_default_section_id()
        section = sections.get_by_id(default_id)
        assert section.name == "Archivio"


def test_get_by_name_ignores_case(sections: SectionRepository) -> None:
    created = sections.create(name="Lavoro")

    found = sections.get_by_name("LAVORO")

    assert found.id == created.id


def test_get_by_name_unknown_returns_none(sections: SectionRepository) -> None:
    sections.create(name="Lavoro")

    assert sections.get_by_name("Svago") is None
