"""Scenari di sync end-to-end: database reale su tmp, remoto GitHub finto in memoria."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from command_quiver.core.github_client import FileContent
from command_quiver.core.settings import Settings
from command_quiver.core.sync_engine import SyncEngine
from command_quiver.db.database import Database
from command_quiver.db.entry_repository import EntryRepository
from command_quiver.db.models import EntryCreate, EntryUpdate
from command_quiver.db.section_repository import SectionRepository
from command_quiver.db.sync_repository import SyncRepository
from command_quiver.db.tombstone_repository import TombstoneRepository

# Timestamp nel passato recente: ordine certo rispetto ad "adesso" e dentro i 90 giorni
# oltre i quali il sync elimina le tombstones
_PAST = (datetime.now() - timedelta(days=2)).isoformat()
_PAST_LATER = (datetime.now() - timedelta(days=1)).isoformat()


class FakeRemote:
    """File remoto in memoria con SHA progressivo, come la Contents API."""

    def __init__(self) -> None:
        self.content: str | None = None
        self.sha = ""

    def get_file(self, path: str) -> FileContent | None:
        if self.content is None:
            return None
        return FileContent(content=self.content, sha=self.sha)

    def put_file(self, path: str, content: str, sha: str = "") -> str:
        self.content = content
        self.sha = str(int(self.sha or "0") + 1)
        return self.sha

    @property
    def state(self) -> dict:
        return json.loads(self.content or "{}")

    def edit(self, **changes: list) -> None:
        """Sostituisce chiavi dello stato remoto, come farebbe un altro dispositivo."""
        state = self.state
        state.update(changes)
        self.content = json.dumps(state)


class Device:
    """Un'installazione dell'app: database proprio, stesso remoto condiviso."""

    def __init__(self, db_path: Path, remote: FakeRemote) -> None:
        self.db = Database(db_path=db_path)
        self.db.initialize(language="it")
        self.engine = SyncEngine(db=self.db, settings=Settings())
        self.engine._create_client = lambda: remote
        self.entries = EntryRepository(self.db.connection)
        self.sections = SectionRepository(self.db.connection)
        self.sync_repo = SyncRepository(connection=self.db.connection)

    def add_entry(self, name: str) -> str:
        """Crea una voce nella sezione di default e ne restituisce l'uuid."""
        section_id = self.sections.get_default_section_id()
        entry = self.entries.create(EntryCreate(name=name, content="echo", section_id=section_id))
        return entry.uuid

    def set_entry_updated_at(self, entry_uuid: str, updated_at: str) -> None:
        self.db.connection.execute(
            "UPDATE entries SET updated_at = ? WHERE uuid = ?", (updated_at, entry_uuid)
        )
        self.db.connection.commit()

    def entry_uuids(self) -> set[str]:
        rows = self.db.connection.execute("SELECT uuid FROM entries").fetchall()
        return {row["uuid"] for row in rows}


@pytest.fixture(autouse=True)
def _no_settings_write(monkeypatch: pytest.MonkeyPatch) -> None:
    # Il sync salva sha e data dell'ultimo sync: nei test non deve toccare il file reale
    monkeypatch.setattr("command_quiver.core.sync_engine.save_settings", lambda s: None)


@pytest.fixture
def remote() -> FakeRemote:
    return FakeRemote()


@pytest.fixture
def device(tmp_path: Path, remote: FakeRemote):
    dev = Device(db_path=tmp_path / "a.db", remote=remote)
    yield dev
    dev.db.close()


def _remote_entry_uuids(remote: FakeRemote) -> set[str]:
    return {entry["uuid"] for entry in remote.state["entries"]}


def _remote_tombstone_uuids(remote: FakeRemote) -> set[str]:
    return {tombstone["uuid"] for tombstone in remote.state["tombstones"]}


def test_sync_entry_deleted_locally_is_not_restored_from_remote(
    device: Device, remote: FakeRemote
) -> None:
    """Regressione B7: una voce cancellata dopo l'ultimo sync non risorge dal remoto."""
    entry_uuid = device.add_entry("da cancellare")
    device.engine.sync()
    entry_id = device.sync_repo.get_entry_by_uuid(entry_uuid).id
    device.entries.delete(entry_id)

    result = device.engine.sync()

    assert result.success is True
    assert entry_uuid not in device.entry_uuids()
    assert entry_uuid not in _remote_entry_uuids(remote)
    assert entry_uuid in _remote_tombstone_uuids(remote)


def test_sync_entry_kept_locally_stays_on_remote(device: Device, remote: FakeRemote) -> None:
    """Positivo appaiato di B7: senza cancellazione la voce resta ovunque."""
    entry_uuid = device.add_entry("da tenere")
    device.engine.sync()

    device.engine.sync()

    assert entry_uuid in device.entry_uuids()
    assert entry_uuid in _remote_entry_uuids(remote)


def test_sync_remote_tombstone_older_than_local_edit_keeps_entry(
    device: Device, remote: FakeRemote
) -> None:
    """Regressione B3: una modifica locale successiva alla cancellazione remota vince."""
    entry_uuid = device.add_entry("modificata dopo")
    device.engine.sync()
    device.set_entry_updated_at(entry_uuid, _PAST_LATER)
    remote.edit(
        entries=[],
        tombstones=[{"uuid": entry_uuid, "entity_type": "entry", "deleted_at": _PAST}],
    )

    device.engine.sync()

    assert entry_uuid in device.entry_uuids()
    assert entry_uuid in _remote_entry_uuids(remote)


def test_sync_remote_tombstone_newer_than_local_edit_deletes_entry(
    device: Device, remote: FakeRemote
) -> None:
    """Positivo appaiato di B3: la cancellazione remota più recente vince."""
    entry_uuid = device.add_entry("cancellata dopo")
    device.engine.sync()
    device.set_entry_updated_at(entry_uuid, _PAST)
    remote.edit(
        entries=[],
        tombstones=[{"uuid": entry_uuid, "entity_type": "entry", "deleted_at": _PAST_LATER}],
    )

    device.engine.sync()

    assert entry_uuid not in device.entry_uuids()
    assert entry_uuid not in _remote_entry_uuids(remote)


def _remote_entry(entry_uuid: str, updated_at: str) -> dict:
    """Voce come la scriverebbe nel remoto un altro dispositivo."""
    return {
        "uuid": entry_uuid,
        "name": "scritta altrove",
        "content": "echo",
        "type": "shell",
        "tags": "",
        "section_uuid": "",
        "created_at": _PAST,
        "updated_at": updated_at,
    }


def test_sync_remote_entry_newer_than_its_tombstone_is_pulled(
    device: Device, remote: FakeRemote
) -> None:
    """Regressione B3b: voce remota modificata dopo la propria cancellazione arriva in locale."""
    device.engine.sync()
    remote.edit(
        entries=[_remote_entry("e-1", updated_at=_PAST_LATER)],
        tombstones=[{"uuid": "e-1", "entity_type": "entry", "deleted_at": _PAST}],
    )

    device.engine.sync()

    assert "e-1" in device.entry_uuids()


def test_sync_remote_entry_older_than_its_tombstone_is_not_pulled(
    device: Device, remote: FakeRemote
) -> None:
    """Positivo appaiato di B3b: se la cancellazione è più recente la voce non arriva."""
    device.engine.sync()
    remote.edit(
        entries=[_remote_entry("e-1", updated_at=_PAST)],
        tombstones=[{"uuid": "e-1", "entity_type": "entry", "deleted_at": _PAST_LATER}],
    )

    device.engine.sync()

    assert "e-1" not in device.entry_uuids()


def _set_section_updated_at(device: Device, section_uuid: str, updated_at: str) -> None:
    device.db.connection.execute(
        "UPDATE sections SET updated_at = ? WHERE uuid = ?", (updated_at, section_uuid)
    )
    device.db.connection.commit()


def _remote_section_uuids(remote: FakeRemote) -> set[str]:
    return {section["uuid"] for section in remote.state["sections"]}


def _local_tombstone_uuids(device: Device) -> set[str]:
    rows = device.db.connection.execute("SELECT uuid FROM sync_tombstones").fetchall()
    return {row["uuid"] for row in rows}


def test_sync_remote_tombstone_on_default_section_keeps_it_everywhere(
    device: Device, remote: FakeRemote
) -> None:
    """Regressione B4: la sezione di default non si cancella, nemmeno da un altro dispositivo."""
    default_uuid = device.sections.get_by_id(device.sections.get_default_section_id()).uuid
    _set_section_updated_at(device, default_uuid, _PAST)
    device.engine.sync()
    remote.edit(
        tombstones=[{"uuid": default_uuid, "entity_type": "section", "deleted_at": _PAST_LATER}]
    )

    device.engine.sync()

    assert device.sync_repo.get_section_by_uuid(default_uuid) is not None
    assert default_uuid not in _local_tombstone_uuids(device)
    assert default_uuid in _remote_section_uuids(remote)


def test_sync_remote_tombstone_on_other_section_deletes_it_everywhere(
    device: Device, remote: FakeRemote
) -> None:
    """Positivo appaiato di B4: una sezione qualsiasi cancellata altrove sparisce."""
    section = device.sections.create(name="Effimera")
    _set_section_updated_at(device, section.uuid, _PAST)
    device.engine.sync()
    remote.edit(
        tombstones=[{"uuid": section.uuid, "entity_type": "section", "deleted_at": _PAST_LATER}]
    )

    device.engine.sync()

    assert device.sync_repo.get_section_by_uuid(section.uuid) is None
    assert section.uuid in _local_tombstone_uuids(device)
    assert section.uuid not in _remote_section_uuids(remote)


@pytest.fixture
def other_device(tmp_path: Path, remote: FakeRemote):
    """Seconda installazione con il proprio seed: stessi nomi, uuid diversi."""
    dev = Device(db_path=tmp_path / "b.db", remote=remote)
    yield dev
    dev.db.close()


def _section_names(device: Device) -> list[str]:
    return sorted(section.name for section in device.sections.get_all())


def test_sync_second_device_with_own_seed_succeeds(device: Device, other_device: Device) -> None:
    """Regressione B1: il primo sync del secondo dispositivo non fallisce sui nomi del seed."""
    device.engine.sync()

    result = other_device.engine.sync()

    assert result.success is True


def test_sync_second_device_adopts_remote_uuid_for_same_name_sections(
    device: Device, other_device: Device
) -> None:
    """Regressione B1: sezioni omonime diventano la stessa sezione, senza duplicati."""
    device.engine.sync()
    other_device.engine.sync()

    device.engine.sync()

    uuids_a = {s.name: s.uuid for s in device.sections.get_all()}
    uuids_b = {s.name: s.uuid for s in other_device.sections.get_all()}
    assert uuids_b == uuids_a
    assert _section_names(device) == ["Comandi shell", "Generale", "Git", "Prompt AI"]


def test_sync_entries_of_both_devices_meet_in_same_section(
    device: Device, other_device: Device
) -> None:
    """Le voci dei due dispositivi si ritrovano nella stessa sezione dopo l'adozione."""
    uuid_a = device.add_entry("da A")
    device.engine.sync()
    uuid_b = other_device.add_entry("da B")
    other_device.engine.sync()

    device.engine.sync()

    assert device.entry_uuids() == {uuid_a, uuid_b}
    assert other_device.entry_uuids() == {uuid_a, uuid_b}
    section_a = device.sync_repo.get_entry_by_uuid(uuid_b).section_id
    assert section_a == device.sections.get_default_section_id()


def _remote_section(section_uuid: str, name: str, updated_at: str) -> dict:
    return {
        "uuid": section_uuid,
        "name": name,
        "icon": "folder",
        "position": 9,
        "is_default": 0,
        "updated_at": updated_at,
    }


def test_sync_remote_rename_onto_existing_name_is_skipped(
    device: Device, remote: FakeRemote
) -> None:
    """Regressione B1: una rinomina remota su un nome già usato non fa fallire il sync."""
    work = device.sections.create(name="Lavoro")
    other = device.sections.create(name="Altro")
    _set_section_updated_at(device, other.uuid, _PAST)
    device.engine.sync()
    sections = [s for s in remote.state["sections"] if s["uuid"] != other.uuid]
    remote.edit(sections=[*sections, _remote_section(other.uuid, "Lavoro", _PAST_LATER)])

    result = device.engine.sync()

    assert result.success is True
    assert device.sync_repo.get_section_by_uuid(other.uuid).name == "Altro"
    assert device.sync_repo.get_section_by_uuid(work.uuid).name == "Lavoro"


def test_sync_remote_rename_onto_free_name_is_applied(device: Device, remote: FakeRemote) -> None:
    """Positivo appaiato: una rinomina remota su un nome libero arriva in locale."""
    other = device.sections.create(name="Altro")
    _set_section_updated_at(device, other.uuid, _PAST)
    device.engine.sync()
    sections = [s for s in remote.state["sections"] if s["uuid"] != other.uuid]
    remote.edit(sections=[*sections, _remote_section(other.uuid, "Rinominata", _PAST_LATER)])

    device.engine.sync()

    assert device.sync_repo.get_section_by_uuid(other.uuid).name == "Rinominata"


def test_sync_new_remote_section_named_like_synced_local_one_is_skipped(
    device: Device, remote: FakeRemote
) -> None:
    """Regressione B1: due sezioni remote con lo stesso nome non fanno fallire il sync."""
    work = device.sections.create(name="Lavoro")
    device.engine.sync()
    sections = remote.state["sections"]
    remote.edit(sections=[*sections, _remote_section("s-new", "Lavoro", _PAST_LATER)])

    result = device.engine.sync()

    assert result.success is True
    assert device.sync_repo.get_section_by_uuid("s-new") is None
    assert device.sync_repo.get_section_by_uuid(work.uuid) is not None


def test_sync_remote_entry_with_unknown_section_lands_in_default(
    device: Device, remote: FakeRemote
) -> None:
    """Regressione B10: una voce la cui sezione non esiste più finisce in Generale."""
    device.engine.sync()
    orphan = _remote_entry("e-1", updated_at=_PAST_LATER)
    orphan["section_uuid"] = "sezione-cancellata"
    remote.edit(entries=[orphan])

    device.engine.sync()

    assert (
        device.sync_repo.get_entry_by_uuid("e-1").section_id
        == device.sections.get_default_section_id()
    )


def _remote_edit_of(remote: FakeRemote, entry_uuid: str, content: str, updated_at: str) -> None:
    entries = remote.state["entries"]
    for entry in entries:
        if entry["uuid"] == entry_uuid:
            entry.update(content=content, updated_at=updated_at)
    remote.edit(entries=entries)


def _remote_content(remote: FakeRemote, entry_uuid: str) -> str:
    return next(e["content"] for e in remote.state["entries"] if e["uuid"] == entry_uuid)


def test_sync_local_edit_in_sqlite_format_beats_older_remote_iso_edit(
    device: Device, remote: FakeRemote
) -> None:
    """Regressione B2: alle 12:00 UTC locali contro le 11:00 UTC remote vince il locale.

    Confrontati come stringhe "2026-10-10 12:00:00" < "2026-10-10T11:00:00+00:00":
    lo spazio perde sempre contro la "T" e vinceva la modifica più vecchia.
    """
    entry_uuid = device.add_entry("conteso")
    device.engine.sync()
    device.set_entry_updated_at(entry_uuid, "2026-10-10 12:00:00")
    _remote_edit_of(remote, entry_uuid, content="remoto", updated_at="2026-10-10T11:00:00+00:00")

    device.engine.sync()

    assert device.sync_repo.get_entry_by_uuid(entry_uuid).content == "echo"
    assert _remote_content(remote, entry_uuid) == "echo"


def test_sync_newer_remote_iso_edit_beats_local_sqlite_format_edit(
    device: Device, remote: FakeRemote
) -> None:
    """Positivo appaiato di B2: la modifica remota delle 13:00 UTC vince."""
    entry_uuid = device.add_entry("conteso")
    device.engine.sync()
    device.set_entry_updated_at(entry_uuid, "2026-10-10 12:00:00")
    _remote_edit_of(remote, entry_uuid, content="remoto", updated_at="2026-10-10T13:00:00+00:00")

    device.engine.sync()

    assert device.sync_repo.get_entry_by_uuid(entry_uuid).content == "remoto"
    assert _remote_content(remote, entry_uuid) == "remoto"


def test_sync_remote_entry_in_section_deleted_by_same_pull_lands_in_default(
    device: Device, remote: FakeRemote
) -> None:
    """Regressione B10: la sezione cancellata nello stesso pull non lascia un id orfano.

    La mappa uuid->id costruita prima delle tombstone conservava l'id della
    sezione appena cancellata: l'inserimento della voce violava la foreign key.
    """
    section = device.sections.create(name="Effimera")
    _set_section_updated_at(device, section.uuid, _PAST)
    device.engine.sync()
    entry = _remote_entry("e-9", updated_at=_PAST_LATER)
    entry["section_uuid"] = section.uuid
    remote.edit(
        entries=[entry],
        tombstones=[{"uuid": section.uuid, "entity_type": "section", "deleted_at": _PAST_LATER}],
    )

    result = device.engine.sync()

    assert result.success is True
    assert (
        device.sync_repo.get_entry_by_uuid("e-9").section_id
        == device.sections.get_default_section_id()
    )


def test_sync_new_remote_section_created_with_remote_uuid(
    device: Device, remote: FakeRemote
) -> None:
    device.engine.sync()
    remote.edit(sections=[*remote.state["sections"], _remote_section("new", "New", _PAST)])

    result = device.engine.sync()

    assert result.sections_pulled == 1
    assert device.sync_repo.get_section_by_uuid("new").name == "New"


def test_sync_local_and_remote_equal_timestamp_keeps_local_version(
    device: Device, remote: FakeRemote
) -> None:
    uid = device.add_entry("local")
    device.engine.sync()
    device.set_entry_updated_at(uid, _PAST)
    _remote_edit_of(remote, uid, content="remote", updated_at=_PAST)

    result = device.engine.sync()

    assert result.entries_pulled == 0
    assert device.sync_repo.get_entry_by_uuid(uid).content == "echo"
    assert _remote_content(remote, uid) == "echo"


def test_sync_section_rename_before_creation_frees_name_in_remote_order(
    device: Device, remote: FakeRemote
) -> None:
    section = device.sections.create(name="Old")
    _set_section_updated_at(device, section.uuid, _PAST)
    device.engine.sync()
    remote.edit(
        sections=[
            _remote_section(section.uuid, "Renamed", _PAST_LATER),
            _remote_section("new", "Old", _PAST_LATER),
        ]
    )

    result = device.engine.sync()

    assert result.sections_pulled == 2
    assert device.sync_repo.get_section_by_uuid(section.uuid).name == "Renamed"
    assert device.sync_repo.get_section_by_uuid("new").name == "Old"


@pytest.mark.parametrize("existing", [False, True], ids=["new", "updated"])
def test_sync_pulled_entry_preserves_remote_fields(
    device: Device, remote: FakeRemote, existing: bool
) -> None:
    entry_uuid = device.add_entry(name="locale") if existing else "remote-new"
    if existing:
        device.set_entry_updated_at(entry_uuid=entry_uuid, updated_at=_PAST)
    device.engine.sync()
    entry = _remote_entry(entry_uuid=entry_uuid, updated_at=_PAST_LATER)
    entry.update(name="Nome remoto", content="printf remote", tags="deploy, git")
    remote.edit(entries=[entry])

    device.engine.sync()

    local = device.sync_repo.get_entry_by_uuid(entry_uuid=entry_uuid)
    assert (local.name, local.content, local.type, local.tags, local.updated_at) == (
        "Nome remoto",
        "printf remote",
        "shell",
        "deploy, git",
        _PAST_LATER,
    )


def test_sync_pulled_entry_uses_remote_section_and_new_section_icon(
    device: Device, remote: FakeRemote
) -> None:
    device.engine.sync()
    section = _remote_section(section_uuid="remote-section", name="Remota", updated_at=_PAST)
    section["icon"] = "utilities-terminal"
    entry = _remote_entry(entry_uuid="remote-entry", updated_at=_PAST_LATER)
    entry["section_uuid"] = "remote-section"
    remote.edit(sections=[*remote.state["sections"], section], entries=[entry])

    device.engine.sync()

    local_section = device.sync_repo.get_section_by_uuid(section_uuid="remote-section")
    local_entry = device.sync_repo.get_entry_by_uuid(entry_uuid="remote-entry")
    assert (local_entry.section_id, local_section.name, local_section.icon) == (
        local_section.id,
        "Remota",
        "utilities-terminal",
    )


def test_sync_cleans_91_day_tombstone_and_keeps_2_day_tombstone(
    device: Device,
) -> None:
    tombstones = TombstoneRepository(connection=device.db.connection)
    now = datetime.now(timezone.utc)
    tombstones.add(
        tombstone_uuid="expired",
        entity_type="entry",
        deleted_at=(now - timedelta(days=91)).isoformat(),
    )
    tombstones.add(
        tombstone_uuid="recent",
        entity_type="entry",
        deleted_at=(now - timedelta(days=2)).isoformat(),
    )

    device.engine.sync()

    assert {item["uuid"] for item in tombstones.get_all()} == {"recent"}


def test_sync_remote_icon_only_section_update_is_applied(
    device: Device, remote: FakeRemote
) -> None:
    section = device.sections.create(name="Lavoro", icon="folder")
    _set_section_updated_at(device=device, section_uuid=section.uuid, updated_at=_PAST)
    device.engine.sync()
    sections = remote.state["sections"]
    for item in sections:
        if item["uuid"] == section.uuid:
            item.update(icon="starred", updated_at=_PAST_LATER)
    remote.edit(sections=sections)

    device.engine.sync()

    local = device.sync_repo.get_section_by_uuid(section_uuid=section.uuid)
    assert (local.name, local.icon) == ("Lavoro", "starred")


def test_sync_reports_one_entry_pulled_then_one_local_edit_pushed(
    device: Device, remote: FakeRemote
) -> None:
    device.engine.sync()
    remote.edit(entries=[_remote_entry(entry_uuid="remote-entry", updated_at=_PAST)])
    pulled = device.engine.sync()
    entry = device.sync_repo.get_entry_by_uuid(entry_uuid="remote-entry")
    device.entries.update(
        data=EntryUpdate(
            id=entry.id, name="Modificata", content="echo local", section_id=entry.section_id
        )
    )

    pushed = device.engine.sync()

    assert (pulled.entries_pulled, pushed.entries_pushed) == (1, 1)


def test_sync_success_records_parseable_last_sync(device: Device, remote: FakeRemote) -> None:
    settings = Settings()
    engine = SyncEngine(db=device.db, settings=settings)
    engine._create_client = lambda: remote
    before = datetime.now()

    result = engine.sync()

    assert (
        result.success
        and before <= datetime.fromisoformat(settings.sync.last_sync) <= datetime.now()
    )
