"""Test per i repository CRUD di sezioni e voci."""

import pytest

from command_quiver.db.database import Database
from command_quiver.db.entry_repository import EntryRepository
from command_quiver.db.models import EntryCreate, SyncedEntry
from command_quiver.db.section_repository import SectionRepository
from command_quiver.db.sync_repository import SyncRepository
from command_quiver.db.tombstone_repository import TombstoneRepository


def _create_remote_entry(
    entries: EntryRepository,
    sections: SectionRepository,
    sync_repo: SyncRepository,
    **timestamps: str,
):
    section_id = sections.get_default_section_id()
    return sync_repo.create_from_sync(
        data=SyncedEntry(
            name="Remote",
            content="echo remote",
            entry_uuid="remote-entry",
            section_id=section_id,
            entry_type="shell",
            tags="sync,remote",
            **timestamps,
        )
    )


def _sync_changes(sections: SectionRepository) -> dict[str, str | int]:
    return dict(
        name="After",
        content="new",
        section_id=sections.get_default_section_id(),
        entry_type="shell",
        tags="remote",
        updated_at="2026-01-02T03:04:05",
    )


def test_create_with_uuid_custom_values_returns_created_section(
    sync_repo: SyncRepository,
    sections: SectionRepository,
) -> None:
    created = sync_repo.create_section_with_uuid(
        name="Remote", section_uuid="remote-section", icon="star"
    )

    assert (created.name, created.uuid, created.icon) == ("Remote", "remote-section", "star")


def test_create_with_uuid_appends_section_after_existing_ones(
    sync_repo: SyncRepository,
    sections: SectionRepository,
) -> None:
    last_position = max(section.position for section in sections.get_all())

    sync_repo.create_section_with_uuid(name="Remote", section_uuid="remote-section")

    stored = sync_repo.get_section_by_uuid(section_uuid="remote-section")
    assert stored.position == last_position + 1


def test_create_with_uuid_section_is_found_by_uuid(
    sync_repo: SyncRepository, sections: SectionRepository
) -> None:
    created = sync_repo.create_section_with_uuid(
        name="Remote", section_uuid="remote-section", icon="star"
    )

    fetched = sync_repo.get_section_by_uuid(section_uuid="remote-section")

    assert (fetched.id, fetched.name, fetched.icon, fetched.uuid) == (
        created.id,
        "Remote",
        "star",
        "remote-section",
    )


def test_get_by_uuid_section_absent_returns_none(
    sync_repo: SyncRepository, sections: SectionRepository
) -> None:
    assert sync_repo.get_section_by_uuid(section_uuid="absent") is None


def test_update_from_sync_section_existing_updates_fields(
    sync_repo: SyncRepository, sections: SectionRepository
) -> None:
    created = sections.create(name="Before")
    timestamp = "2026-01-02T03:04:05"

    sync_repo.update_section_from_sync(
        section_uuid=created.uuid, name="After", icon="star", updated_at=timestamp
    )

    result = sync_repo.get_section_by_uuid(section_uuid=created.uuid)
    assert (result.id, result.name, result.icon, result.updated_at) == (
        created.id,
        "After",
        "star",
        timestamp,
    )


def test_update_from_sync_section_existing_returns_true(
    sync_repo: SyncRepository, sections: SectionRepository
) -> None:
    created = sections.create(name="Before")

    changed = sync_repo.update_section_from_sync(
        section_uuid=created.uuid, name="After", icon="star", updated_at="2026-01-02T03:04:05"
    )

    assert changed is True


def test_update_from_sync_section_absent_returns_false_and_creates_nothing(
    sync_repo: SyncRepository,
    sections: SectionRepository,
) -> None:
    count_before = len(sections.get_all())

    changed = sync_repo.update_section_from_sync(
        section_uuid="absent", name="Ghost", icon="folder", updated_at="2026-01-02T03:04:05"
    )

    assert changed is False
    assert len(sections.get_all()) == count_before


def test_delete_section_empty_uuid_deletes_without_tombstone(
    sync_repo: SyncRepository, db: Database, sections: SectionRepository
) -> None:
    legacy = sync_repo.create_section_with_uuid(name="Legacy", section_uuid="")

    deleted = sections.delete(section_id=legacy.id)

    assert deleted is True
    assert sections.get_by_id(section_id=legacy.id) is None
    assert TombstoneRepository(connection=db.connection).get_all() == []


def test_delete_by_uuid_section_existing_removes_it_and_returns_true(
    sync_repo: SyncRepository,
    sections: SectionRepository,
) -> None:
    created = sections.create(name="Remote")

    deleted = sync_repo.delete_section_by_uuid(section_uuid=created.uuid)

    assert deleted is True
    assert sync_repo.get_section_by_uuid(section_uuid=created.uuid) is None


def test_delete_by_uuid_section_absent_returns_false(
    sync_repo: SyncRepository, sections: SectionRepository
) -> None:
    assert sync_repo.delete_section_by_uuid(section_uuid="absent") is False


def test_delete_by_uuid_default_section_returns_false_and_preserves_it(
    sync_repo: SyncRepository,
    sections: SectionRepository,
) -> None:
    default = sections.get_by_id(section_id=sections.get_default_section_id())

    deleted = sync_repo.delete_section_by_uuid(section_uuid=default.uuid)

    assert deleted is False
    assert sync_repo.get_section_by_uuid(section_uuid=default.uuid) == default


def test_create_from_sync_entry_is_found_by_uuid(
    sync_repo: SyncRepository, entries: EntryRepository, sections: SectionRepository
) -> None:
    result = _create_remote_entry(entries, sections, sync_repo=sync_repo)

    assert sync_repo.get_entry_by_uuid(entry_uuid="remote-entry") == result


def test_get_by_uuid_entry_absent_returns_none(
    sync_repo: SyncRepository, entries: EntryRepository
) -> None:
    assert sync_repo.get_entry_by_uuid(entry_uuid="absent") is None


def test_update_from_sync_entry_existing_updates_fields(
    sync_repo: SyncRepository, entries: EntryRepository, sections: SectionRepository
) -> None:
    created = entries.create(data=EntryCreate(name="Before", content="old"))
    changes = _sync_changes(sections)

    sync_repo.update_entry_from_sync(data=SyncedEntry(entry_uuid=created.uuid, **changes))

    result = sync_repo.get_entry_by_uuid(entry_uuid=created.uuid)
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
    sync_repo: SyncRepository, entries: EntryRepository, sections: SectionRepository
) -> None:
    created = entries.create(data=EntryCreate(name="Before", content="old"))

    sync_repo.update_entry_from_sync(
        data=SyncedEntry(entry_uuid=created.uuid, **_sync_changes(sections))
    )

    assert sync_repo.get_entry_by_uuid(entry_uuid=created.uuid).created_at == created.created_at


def test_update_from_sync_entry_existing_returns_true(
    sync_repo: SyncRepository, entries: EntryRepository, sections: SectionRepository
) -> None:
    created = entries.create(data=EntryCreate(name="Before", content="old"))

    assert (
        sync_repo.update_entry_from_sync(
            data=SyncedEntry(entry_uuid=created.uuid, **_sync_changes(sections))
        )
        is True
    )


def test_update_from_sync_entry_absent_returns_false(
    sync_repo: SyncRepository, entries: EntryRepository, sections: SectionRepository
) -> None:
    assert (
        sync_repo.update_entry_from_sync(
            data=SyncedEntry(entry_uuid="absent", **_sync_changes(sections))
        )
        is False
    )


def test_delete_by_uuid_entry_existing_removes_only_target(
    sync_repo: SyncRepository, entries: EntryRepository
) -> None:
    removed = entries.create(data=EntryCreate(name="Remove", content="text"))
    kept = entries.create(data=EntryCreate(name="Keep", content="text"))

    deleted = sync_repo.delete_entry_by_uuid(entry_uuid=removed.uuid)

    assert deleted is True
    assert sync_repo.get_entry_by_uuid(entry_uuid=removed.uuid) is None
    assert sync_repo.get_entry_by_uuid(entry_uuid=kept.uuid) == kept


def test_delete_by_uuid_entry_absent_returns_false(
    sync_repo: SyncRepository, entries: EntryRepository
) -> None:
    assert sync_repo.delete_entry_by_uuid(entry_uuid="absent") is False


@pytest.mark.parametrize("entry_uuid", ["entry-id", ""], ids=["uuid", "legacy-empty-uuid"])
def test_delete_entry_removes_only_target(
    sync_repo: SyncRepository,
    entries: EntryRepository,
    entry_uuid: str,
) -> None:
    removed = sync_repo.create_from_sync(
        data=SyncedEntry(name="Remove", content="text", entry_uuid=entry_uuid, section_id=None)
    )
    kept = entries.create(data=EntryCreate(name="Keep", content="text"))

    deleted = entries.delete(entry_id=removed.id)

    assert deleted is True
    assert entries.get_by_id(entry_id=removed.id) is None
    assert entries.get_by_id(entry_id=kept.id) == kept


def test_delete_entry_with_uuid_records_tombstone(
    sync_repo: SyncRepository, db: Database, entries: EntryRepository
) -> None:
    removed = sync_repo.create_from_sync(
        data=SyncedEntry(name="Remove", content="text", entry_uuid="entry-id", section_id=None)
    )

    entries.delete(entry_id=removed.id)

    tombstones = TombstoneRepository(connection=db.connection)
    assert [(row["uuid"], row["entity_type"]) for row in tombstones.get_all()] == [
        ("entry-id", "entry")
    ]


def test_delete_entry_empty_uuid_records_no_tombstone(
    sync_repo: SyncRepository, db: Database, entries: EntryRepository
) -> None:
    removed = sync_repo.create_from_sync(
        data=SyncedEntry(name="Remove", content="text", entry_uuid="", section_id=None)
    )

    entries.delete(entry_id=removed.id)

    assert TombstoneRepository(connection=db.connection).get_all() == []


def test_adopt_uuid_replaces_identity_and_keeps_entries(
    sync_repo: SyncRepository, sections: SectionRepository, entries: EntryRepository
) -> None:
    section = sections.create(name="Lavoro")
    entry = entries.create(EntryCreate(name="e", content="c", section_id=section.id))

    sync_repo.adopt_uuid(section_id=section.id, section_uuid="remote-uuid")

    assert sync_repo.get_section_by_uuid("remote-uuid").id == section.id
    assert sync_repo.get_section_by_uuid(section.uuid) is None
    assert entries.get_by_id(entry.id).section_id == section.id


def test_create_with_uuid_returns_stored_created_at(
    sync_repo: SyncRepository, sections: SectionRepository
) -> None:
    created = sync_repo.create_section_with_uuid(name="Remota", section_uuid="r-1")

    assert created.created_at == sync_repo.get_section_by_uuid("r-1").created_at != ""


def test_create_from_sync_entry_persists_given_fields(
    sync_repo: SyncRepository, entries: EntryRepository, sections: SectionRepository
) -> None:
    section_id = sections.get_default_section_id()

    result = _create_remote_entry(entries, sections, sync_repo=sync_repo)

    assert (result.name, result.content, result.uuid, result.section_id) == (
        "Remote",
        "echo remote",
        "remote-entry",
        section_id,
    )
    assert (result.type, result.tags) == ("shell", "sync,remote")


def test_create_from_sync_entry_is_appended_to_personal_order(
    sync_repo: SyncRepository, entries: EntryRepository, sections: SectionRepository
) -> None:
    entries.create(
        data=EntryCreate(name="First", content="text", section_id=sections.get_default_section_id())
    )

    result = _create_remote_entry(entries, sections, sync_repo=sync_repo)

    assert result.personal_pos == 1


def test_create_from_sync_entry_with_remote_timestamps_keeps_them(
    sync_repo: SyncRepository, entries: EntryRepository, sections: SectionRepository
) -> None:
    result = _create_remote_entry(
        entries,
        sections,
        sync_repo=sync_repo,
        created_at="2025-01-01T00:00:00",
        updated_at="2025-02-01T00:00:00",
    )

    assert (result.created_at, result.updated_at) == ("2025-01-01T00:00:00", "2025-02-01T00:00:00")


def test_create_from_sync_entry_without_timestamps_generates_them(
    sync_repo: SyncRepository, entries: EntryRepository, sections: SectionRepository
) -> None:
    result = _create_remote_entry(entries, sections, sync_repo=sync_repo)

    assert result.created_at
    assert result.updated_at
