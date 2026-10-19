"""Test per i repository CRUD di sezioni e voci."""

from datetime import datetime, timedelta

from command_quiver.db.database import Database
from command_quiver.db.tombstone_repository import TombstoneRepository


def _tombstones_with_old_recent_and_new(db: Database) -> TombstoneRepository:
    tombstones = TombstoneRepository(connection=db.connection)
    old = (datetime.now() - timedelta(days=100)).isoformat()
    recent = (datetime.now() - timedelta(days=10)).isoformat()
    tombstones.add(tombstone_uuid="old", entity_type="entry", deleted_at=old)
    tombstones.add(tombstone_uuid="recent", entity_type="section", deleted_at=recent)
    tombstones.add(tombstone_uuid="now", entity_type="entry")
    return tombstones


def test_add_tombstone_existing_uuid_replaces_remote_data(db: Database) -> None:
    tombstones = TombstoneRepository(connection=db.connection)
    tombstones.add(tombstone_uuid="remote", entity_type="entry", deleted_at="2025-01-01")

    tombstones.add(tombstone_uuid="remote", entity_type="section", deleted_at="2025-02-01")

    assert tombstones.get_all() == [
        {"uuid": "remote", "entity_type": "section", "deleted_at": "2025-02-01"}
    ]


def test_cleanup_tombstones_removes_only_expired_ones(db: Database) -> None:
    tombstones = _tombstones_with_old_recent_and_new(db)

    removed = tombstones.cleanup()

    assert removed == 1
    assert {row["uuid"] for row in tombstones.get_all()} == {"recent", "now"}


def test_cleanup_tombstones_repeated_removes_nothing(db: Database) -> None:
    tombstones = _tombstones_with_old_recent_and_new(db)
    tombstones.cleanup()

    assert tombstones.cleanup() == 0
