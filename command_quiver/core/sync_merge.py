"""Trasformazioni pure dello stato di sincronizzazione."""

from dataclasses import dataclass

from command_quiver.core.timestamps import parse_timestamp

FORMAT_VERSION = 1


@dataclass(frozen=True)
class RemoteChangePlan:
    """Scritture ordinate per categoria, senza identificatori locali del database."""

    tombstones: tuple[dict, ...]
    new_sections: tuple[dict, ...]
    updated_sections: tuple[dict, ...]
    new_entries: tuple[dict, ...]
    updated_entries: tuple[dict, ...]


def merge_tombstones(local_state: dict, remote_state: dict) -> dict[str, dict]:
    """Unisce le cancellazioni, conservando per UUID quella più recente.

    Parameters
    ----------
    local_state, remote_state : dict
        Stati di sincronizzazione.

    Returns
    -------
    dict[str, dict]
        Tombstone indicizzate per UUID; a parità vince la locale.
    """
    merged: dict[str, dict] = {}
    for tombstone in local_state.get("tombstones", []) + remote_state.get("tombstones", []):
        uid = tombstone["uuid"]
        if uid not in merged or parse_timestamp(tombstone["deleted_at"]) > parse_timestamp(
            merged[uid]["deleted_at"]
        ):
            merged[uid] = tombstone
    return merged


def tombstone_wins(entity: dict, tombstone: dict | None) -> bool:
    """Confronta cancellazione e modifica; il pareggio conserva l'entità.

    Parameters
    ----------
    entity : dict
        Entità con updated_at.
    tombstone : dict or None
        Cancellazione candidata.

    Returns
    -------
    bool
        True solo per una cancellazione strettamente più recente.
    """
    return tombstone is not None and parse_timestamp(tombstone["deleted_at"]) > parse_timestamp(
        entity.get("updated_at")
    )


def merge_entities(local_map: dict, remote_map: dict, tombstones: dict) -> dict[str, dict]:
    """Seleziona le versioni LWW delle entità non cancellate.

    Parameters
    ----------
    local_map, remote_map, tombstones : dict
        Entità e cancellazioni indicizzate per UUID.

    Returns
    -------
    dict[str, dict]
        Versioni unificate; il locale vince i pareggi.
    """
    merged = {}
    for uid in set(local_map) | set(remote_map):
        local = local_map.get(uid)
        remote = remote_map.get(uid)
        candidate = local if local is not None else remote
        if tombstone_wins(entity=candidate, tombstone=tombstones.get(uid)):
            continue
        if local is not None and remote is not None:
            candidate = (
                local
                if parse_timestamp(local.get("updated_at"))
                >= parse_timestamp(remote.get("updated_at"))
                else remote
            )
        merged[uid] = candidate
    return merged


def merge_states(local_state: dict, remote_state: dict, now: str) -> dict:
    """Unifica due stati con un istante fornito dal chiamante.

    Parameters
    ----------
    local_state, remote_state : dict
        Stati da unificare.
    now : str
        Timestamp del risultato.

    Returns
    -------
    dict
        Stato completo pronto per il push.
    """
    tombstones = merge_tombstones(local_state=local_state, remote_state=remote_state)
    merged = {}
    for category in ("sections", "entries"):
        entities = merge_entities(
            local_map={item["uuid"]: item for item in local_state.get(category, [])},
            remote_map={item["uuid"]: item for item in remote_state.get(category, [])},
            tombstones=tombstones,
        )
        merged[category] = list(entities.values())
    return {
        "format_version": FORMAT_VERSION,
        "last_modified": now,
        **merged,
        "tombstones": list(tombstones.values()),
    }


def count_pushed(merged: list[dict], remote: list[dict]) -> int:
    """Conta le voci nuove o con versione diversa dal remoto.

    Parameters
    ----------
    merged, remote : list[dict]
        Voci unificate e voci già remote.

    Returns
    -------
    int
        Numero di versioni da inviare.
    """
    versions = {item["uuid"]: item.get("updated_at") for item in remote}
    return sum(
        1
        for item in merged
        if item["uuid"] not in versions or versions[item["uuid"]] != item.get("updated_at")
    )


def build_sync_state(
    sections: list[dict], entries: list[dict], tombstones: list[dict], now: str
) -> dict:
    """Proietta i dati locali nel formato JSON condiviso.

    Parameters
    ----------
    sections, entries, tombstones : list[dict]
        Dati locali; le sezioni possono contenere campi esclusivamente locali.
    now : str
        Timestamp dello stato esportato.

    Returns
    -------
    dict
        Stato serializzabile senza identificatori locali delle sezioni.
    """
    projected = []
    for section in sections:
        fields = {key: section[key] for key in ("uuid", "name", "icon", "position", "is_default")}
        fields["updated_at"] = section["updated_at"] or section["created_at"]
        projected.append(fields)
    return {
        "format_version": FORMAT_VERSION,
        "last_modified": now,
        "sections": projected,
        "entries": entries,
        "tombstones": tombstones,
    }


def _plan_entities(local: dict, remote: dict, tombstones: dict) -> tuple[tuple, tuple]:
    new, updated = [], []
    for uid, item in remote.items():
        if tombstone_wins(entity=item, tombstone=tombstones.get(uid)):
            continue
        if uid not in local:
            new.append(item)
        elif parse_timestamp(item.get("updated_at", "")) > parse_timestamp(
            local[uid].get("updated_at", "")
        ):
            updated.append(item)
    return tuple(new), tuple(updated)


def _plan_tombstones(local_state: dict, remote_state: dict, entities: dict) -> tuple[dict, ...]:
    local = {item["uuid"]: item for item in local_state.get("tombstones", [])}
    remote = {item["uuid"]: item for item in remote_state.get("tombstones", [])}
    planned = []
    for uid in set(remote) - set(local):
        item = entities.get(uid)
        if item and not tombstone_wins(entity=item, tombstone=remote[uid]):
            continue
        planned.append(remote[uid])
    return tuple(planned)


def plan_remote_changes(local_state: dict, remote_state: dict) -> RemoteChangePlan:
    """Calcola le scritture remote senza accedere al database.

    Parameters
    ----------
    local_state, remote_state : dict
        Snapshot precedenti al pull.

    Returns
    -------
    RemoteChangePlan
        Cancellazioni e versioni remote applicabili.
    """
    tombstones = merge_tombstones(local_state=local_state, remote_state=remote_state)
    local_sections = {s["uuid"]: s for s in local_state.get("sections", [])}
    local_entries = {e["uuid"]: e for e in local_state.get("entries", [])}
    remote_sections = {s["uuid"]: s for s in remote_state.get("sections", [])}
    remote_entries = {e["uuid"]: e for e in remote_state.get("entries", [])}
    sections = _plan_entities(local=local_sections, remote=remote_sections, tombstones=tombstones)
    entries = _plan_entities(local=local_entries, remote=remote_entries, tombstones=tombstones)
    local = {**local_sections, **local_entries}
    deleted = _plan_tombstones(local_state=local_state, remote_state=remote_state, entities=local)
    return RemoteChangePlan(
        tombstones=deleted,
        new_sections=sections[0],
        updated_sections=sections[1],
        new_entries=entries[0],
        updated_entries=entries[1],
    )
