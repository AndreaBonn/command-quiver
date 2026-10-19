"""Contratti delle trasformazioni pure dello stato di sincronizzazione."""

import copy

import pytest

from command_quiver.core.sync_merge import (
    build_sync_state,
    count_pushed,
    merge_entities,
    merge_states,
    merge_tombstones,
    plan_remote_changes,
    tombstone_wins,
)

OLD = "2026-10-10 10:00:00"
NEW = "2026-10-10T12:00:00+00:00"
NOW = "2026-10-19T12:00:00+00:00"


def entity(updated_at: str = OLD, **fields: str) -> dict:
    return {"uuid": "x", "updated_at": updated_at, **fields}


def tombstone(deleted_at: str = NEW, entity_type: str = "entry") -> dict:
    return {"uuid": "x", "entity_type": entity_type, "deleted_at": deleted_at}


@pytest.mark.parametrize(
    "local_time,remote_time,winner",
    [(OLD, NEW, "remote"), (NEW, OLD, "local"), (NEW, NEW, "local")],
    ids=["remote-newer", "local-newer", "tie-keeps-local"],
)
def test_merge_tombstones_versions_newest_retained(
    local_time: str, remote_time: str, winner: str
) -> None:
    local = {**tombstone(deleted_at=local_time), "source": "local"}
    remote = {**tombstone(deleted_at=remote_time), "source": "remote"}

    result = merge_tombstones(
        local_state={"tombstones": [local]}, remote_state={"tombstones": [remote]}
    )

    assert result["x"]["source"] == winner


@pytest.mark.parametrize("deleted_at,expected", [(None, False), (OLD, False), (NEW, True)])
def test_tombstone_wins_timestamp_strictly_newer_required(
    deleted_at: str | None, expected: bool
) -> None:
    deletion = None if deleted_at is None else tombstone(deleted_at=deleted_at)

    result = tombstone_wins(entity=entity(), tombstone=deletion)

    assert result is expected
    assert tombstone_wins(entity=entity(), tombstone=tombstone()) is True


@pytest.mark.parametrize(
    "local,remote,deletion,expected",
    [
        (
            entity(updated_at=NEW, name="local"),
            entity(updated_at=OLD),
            None,
            entity(updated_at=NEW, name="local"),
        ),
        (
            entity(updated_at=OLD),
            entity(updated_at=NEW, name="remote"),
            None,
            entity(updated_at=NEW, name="remote"),
        ),
        (
            entity(updated_at=NEW, name="local"),
            entity(updated_at=NEW),
            None,
            entity(updated_at=NEW, name="local"),
        ),
        (entity(), None, None, entity()),
        (None, entity(), None, entity()),
        (entity(), None, tombstone(), None),
        (None, entity(), tombstone(), None),
        (
            entity(updated_at=NEW),
            entity(updated_at=NEW),
            tombstone(deleted_at=OLD),
            entity(updated_at=NEW),
        ),
    ],
)
def test_merge_entities_versions_expected_entity_selected(
    local: dict | None, remote: dict | None, deletion: dict | None, expected: dict | None
) -> None:
    local_map = {} if local is None else {"x": local}
    remote_map = {} if remote is None else {"x": remote}
    tombstones = {} if deletion is None else {"x": deletion}

    result = merge_entities(local_map=local_map, remote_map=remote_map, tombstones=tombstones)

    assert result == ({} if expected is None else {"x": expected})
    assert merge_entities(local_map={"x": entity()}, remote_map={}, tombstones={}) == {
        "x": entity()
    }


@pytest.mark.parametrize("deleted_at,expected_time", [(NEW, None), (OLD, NEW)])
def test_merge_states_injected_clock_complete_state_returned(
    deleted_at: str, expected_time: str | None
) -> None:
    section = {"uuid": "s", "updated_at": NEW}
    deletion = tombstone(deleted_at=deleted_at)
    local = {"sections": [section], "entries": [entity()], "tombstones": [deletion]}
    remote = {"entries": [entity(updated_at=NEW)]}
    before = copy.deepcopy((local, remote))

    result = merge_states(local_state=local, remote_state=remote, now=NOW)

    assert result == {
        "format_version": 1,
        "last_modified": NOW,
        "sections": [section],
        "entries": [] if expected_time is None else [entity(updated_at=expected_time)],
        "tombstones": [deletion],
    }
    assert (local, remote) == before
    assert merge_states(local_state={"entries": [entity()]}, remote_state={}, now=NOW)[
        "entries"
    ] == [entity()]


@pytest.mark.parametrize(
    "remote,expected", [([], 1), ([entity()], 0), ([entity(updated_at=NEW)], 1)]
)
def test_count_pushed_remote_version_changed_counted(remote: list, expected: int) -> None:
    result = count_pushed(merged=[entity()], remote=remote)

    assert result == expected
    assert count_pushed(merged=[entity()], remote=[]) == 1


@pytest.mark.parametrize("updated_at,expected", [("", OLD), (NEW, NEW)])
def test_build_sync_state_sections_projected_with_timestamp_fallback(
    updated_at: str, expected: str
) -> None:
    section = {
        "uuid": "x",
        "name": "Work",
        "icon": "folder",
        "position": 3,
        "is_default": 0,
        "created_at": OLD,
        "updated_at": updated_at,
        "id": 9,
    }

    result = build_sync_state(
        sections=[section], entries=[entity()], tombstones=[tombstone()], now=NOW
    )

    assert result == {
        "format_version": 1,
        "last_modified": NOW,
        "sections": [
            {
                "uuid": "x",
                "name": "Work",
                "icon": "folder",
                "position": 3,
                "is_default": 0,
                "updated_at": expected,
            }
        ],
        "entries": [entity()],
        "tombstones": [tombstone()],
    }


@pytest.mark.parametrize("category", ["sections", "entries"])
@pytest.mark.parametrize(
    "local_time,remote_time,action",
    [(None, NEW, "new"), (OLD, NEW, "updated"), (NEW, OLD, None), (NEW, NEW, None)],
)
def test_plan_remote_changes_entity_version_expected_category(
    category: str, local_time: str | None, remote_time: str, action: str | None
) -> None:
    local = {category: [] if local_time is None else [entity(updated_at=local_time)]}
    remote = {category: [entity(updated_at=remote_time)]}

    plan = plan_remote_changes(local_state=local, remote_state=remote)

    assert getattr(plan, f"new_{category}") == (
        (entity(updated_at=remote_time),) if action == "new" else ()
    )
    assert getattr(plan, f"updated_{category}") == (
        (entity(updated_at=remote_time),) if action == "updated" else ()
    )
    positive = plan_remote_changes(local_state={}, remote_state=remote)
    assert getattr(positive, f"new_{category}") == (entity(updated_at=remote_time),)


@pytest.mark.parametrize("category", ["sections", "entries"])
@pytest.mark.parametrize("source", ["local", "remote"])
@pytest.mark.parametrize(
    "remote_time,expected",
    [(OLD, ()), (NEW, (entity(updated_at=NEW),)), (NOW, (entity(updated_at=NOW),))],
)
def test_plan_remote_changes_united_tombstones_filter_resurrection(
    category: str, source: str, remote_time: str, expected: tuple
) -> None:
    local = {}
    remote = {category: [entity(updated_at=remote_time)]}
    target = local if source == "local" else remote
    target["tombstones"] = [tombstone(deleted_at=NEW)]

    plan = plan_remote_changes(local_state=local, remote_state=remote)

    assert getattr(plan, f"new_{category}") == expected
    assert getattr(
        plan_remote_changes(local_state={}, remote_state={category: [entity(updated_at=NEW)]}),
        f"new_{category}",
    ) == (entity(updated_at=NEW),)


@pytest.mark.parametrize("category", ["sections", "entries"])
@pytest.mark.parametrize(
    "local_time,existing,expected",
    [(None, False, True), (OLD, False, True), (NEW, False, False), (None, True, False)],
)
def test_plan_remote_changes_remote_deletion_respects_local_edit(
    category: str, local_time: str | None, existing: bool, expected: bool
) -> None:
    deletion = tombstone()
    local = {
        category: [] if local_time is None else [entity(updated_at=local_time)],
        "tombstones": [deletion] if existing else [],
    }

    plan = plan_remote_changes(local_state=local, remote_state={"tombstones": [deletion]})

    assert plan.tombstones == ((deletion,) if expected else ())
    assert plan_remote_changes(
        local_state={}, remote_state={"tombstones": [deletion]}
    ).tombstones == (deletion,)
