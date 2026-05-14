"""Motore di sincronizzazione: export, merge, push/pull via GitHub.

Strategia: last-write-wins per UUID. Tombstones per propagare cancellazioni.
Formato sync JSON:
{
    "format_version": 1,
    "last_modified": "ISO timestamp",
    "sections": [{uuid, name, icon, position, is_default, updated_at}, ...],
    "entries": [{uuid, name, content, type, tags, section_uuid, created_at, updated_at}, ...],
    "tombstones": [{uuid, entity_type, deleted_at}, ...]
}
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime

from command_quiver.core.github_client import GitHubApiError, GitHubClient
from command_quiver.core.settings import (
    Settings,
    load_sync_token,
    save_settings,
)
from command_quiver.db.database import Database
from command_quiver.db.queries import (
    EntryRepository,
    SectionRepository,
    TombstoneRepository,
)

logger = logging.getLogger(__name__)

FORMAT_VERSION = 1


@dataclass
class SyncResult:
    """Risultato di un'operazione di sync."""

    success: bool
    message: str = ""
    entries_pulled: int = 0
    entries_pushed: int = 0
    sections_pulled: int = 0


class SyncEngine:
    """Orchestrazione sync: export locale, merge con remoto, push/pull."""

    def __init__(self, db: Database, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._section_repo = SectionRepository(db.connection)
        self._entry_repo = EntryRepository(db.connection)
        self._tombstone_repo = TombstoneRepository(db.connection)

    def _create_client(self) -> GitHubClient | None:
        """Crea il client GitHub se la configurazione è completa."""
        sync = self._settings.sync
        token = load_sync_token()
        if not all([sync.enabled, sync.repo_owner, sync.repo_name, token]):
            return None
        return GitHubClient(token=token, owner=sync.repo_owner, repo=sync.repo_name)

    def sync(self) -> SyncResult:
        """Esegue sync completo: pull remoto, merge, push stato merged."""
        client = self._create_client()
        if client is None:
            return SyncResult(success=False, message="Sync non configurato")

        try:
            # 1. Esporta stato locale
            local_state = self._export_local()

            # 2. Scarica stato remoto
            file_path = self._settings.sync.file_path
            remote_file = client.get_file(path=file_path)

            if remote_file is not None:
                remote_state = json.loads(remote_file.content)
                current_sha = remote_file.sha

                # 3. Applica novità remote al DB locale
                result = self._apply_remote_changes(
                    local_state=local_state,
                    remote_state=remote_state,
                )

                # 4. Ri-esporta dopo apply (il DB locale è cambiato)
                updated_local = self._export_local()
                merged = self._merge(local_state=updated_local, remote_state=remote_state)
            else:
                # Primo sync: nessun file remoto
                merged = local_state
                current_sha = ""
                result = SyncResult(success=True, message="Primo sync")

            # 5. Push stato merged
            merged_json = json.dumps(merged, indent=2, ensure_ascii=False)
            new_sha = client.put_file(
                path=file_path,
                content=merged_json,
                sha=current_sha,
            )

            # 5. Aggiorna settings
            self._settings.sync.last_sha = new_sha
            self._settings.sync.last_sync = datetime.now().isoformat()
            save_settings(self._settings)

            # 6. Pulizia tombstones vecchie
            self._tombstone_repo.cleanup(max_age_days=90)

            result.success = True
            if not result.message:
                result.message = "Sync completato"
            logger.info(
                "Sync completato: %d entries pulled, %d sections pulled",
                result.entries_pulled,
                result.sections_pulled,
            )
            return result

        except GitHubApiError as err:
            logger.error("Sync fallito: %s", err)
            return SyncResult(success=False, message=str(err))
        except (json.JSONDecodeError, KeyError, TypeError) as err:
            logger.error("Sync fallito (dati corrotti): %s", err)
            return SyncResult(success=False, message=f"Dati remoti corrotti: {err}")

    def _export_local(self) -> dict:
        """Esporta stato locale nel formato sync."""
        sections = self._section_repo.get_all()
        entries_data = self._entry_repo.export_for_sync()
        tombstones = self._tombstone_repo.get_all()

        return {
            "format_version": FORMAT_VERSION,
            "last_modified": datetime.now().isoformat(),
            "sections": [
                {
                    "uuid": s.uuid,
                    "name": s.name,
                    "icon": s.icon,
                    "position": s.position,
                    "is_default": s.is_default,
                    "updated_at": s.updated_at or s.created_at,
                }
                for s in sections
            ],
            "entries": entries_data,
            "tombstones": tombstones,
        }

    def _merge(self, local_state: dict, remote_state: dict) -> dict:
        """Merge locale + remoto. Restituisce stato unificato per il push.

        Strategia: unione di tutti gli UUID, last-write-wins per conflitti.
        Le tombstones vincono se più recenti dell'entry.
        """
        # Unisci tombstones (dedup per uuid, tieni la più recente)
        all_tombstones: dict[str, dict] = {}
        for tombstone in local_state.get("tombstones", []) + remote_state.get("tombstones", []):
            uid = tombstone["uuid"]
            if (
                uid not in all_tombstones
                or tombstone["deleted_at"] > all_tombstones[uid]["deleted_at"]
            ):
                all_tombstones[uid] = tombstone

        # Merge sezioni
        local_sections = {s["uuid"]: s for s in local_state.get("sections", [])}
        remote_sections = {s["uuid"]: s for s in remote_state.get("sections", [])}
        merged_sections = self._merge_entities(
            local_map=local_sections,
            remote_map=remote_sections,
            tombstones=all_tombstones,
        )

        # Merge entries
        local_entries = {e["uuid"]: e for e in local_state.get("entries", [])}
        remote_entries = {e["uuid"]: e for e in remote_state.get("entries", [])}
        merged_entries = self._merge_entities(
            local_map=local_entries,
            remote_map=remote_entries,
            tombstones=all_tombstones,
        )

        return {
            "format_version": FORMAT_VERSION,
            "last_modified": datetime.now().isoformat(),
            "sections": list(merged_sections.values()),
            "entries": list(merged_entries.values()),
            "tombstones": list(all_tombstones.values()),
        }

    def _merge_entities(
        self,
        local_map: dict[str, dict],
        remote_map: dict[str, dict],
        tombstones: dict[str, dict],
    ) -> dict[str, dict]:
        """Merge generico per entità con UUID. Last-write-wins."""
        merged: dict[str, dict] = {}

        all_uuids = set(local_map) | set(remote_map)
        for uid in all_uuids:
            # Tombstone vince se più recente dell'entità
            if uid in tombstones:
                local_ent = local_map.get(uid)
                remote_ent = remote_map.get(uid)
                entity = local_ent or remote_ent
                if entity:
                    entity_time = entity.get("updated_at", "")
                    if tombstones[uid]["deleted_at"] > entity_time:
                        continue  # Cancellata, non includerla

            local_ent = local_map.get(uid)
            remote_ent = remote_map.get(uid)

            if local_ent and remote_ent:
                # Conflitto: vince il più recente
                local_time = local_ent.get("updated_at", "")
                remote_time = remote_ent.get("updated_at", "")
                merged[uid] = local_ent if local_time >= remote_time else remote_ent
            elif local_ent:
                merged[uid] = local_ent
            elif remote_ent:
                merged[uid] = remote_ent

        return merged

    def _apply_remote_changes(
        self,
        local_state: dict,
        remote_state: dict,
    ) -> SyncResult:
        """Applica al DB locale le novità dal remoto.

        Crea entries/sections nuove, aggiorna quelle con updated_at più recente,
        cancella quelle con tombstone remota.
        """
        result = SyncResult(success=True)

        # Mappa sezioni locali per UUID
        local_sections = {s["uuid"]: s for s in local_state.get("sections", [])}
        remote_sections = {s["uuid"]: s for s in remote_state.get("sections", [])}

        # Mappa UUID sezione -> ID locale (per risolvere section_uuid -> section_id)
        section_uuid_to_id: dict[str, int] = {}
        for section in self._section_repo.get_all():
            section_uuid_to_id[section.uuid] = section.id

        # Applica tombstones remote
        remote_tombstones = {t["uuid"]: t for t in remote_state.get("tombstones", [])}
        local_tombstones = {t["uuid"]: t for t in local_state.get("tombstones", [])}
        new_tombstones = set(remote_tombstones) - set(local_tombstones)

        for uid in new_tombstones:
            tombstone = remote_tombstones[uid]
            entity_type = tombstone["entity_type"]
            if entity_type == "entry":
                self._entry_repo.delete_by_uuid(uid)
            elif entity_type == "section":
                self._section_repo.delete_by_uuid(uid)
            self._tombstone_repo.add(
                tombstone_uuid=uid,
                entity_type=entity_type,
                deleted_at=tombstone["deleted_at"],
            )

        # Sync sezioni remote
        for uid, remote_sec in remote_sections.items():
            if uid in {t["uuid"] for t in remote_state.get("tombstones", [])}:
                continue

            if uid not in local_sections:
                # Nuova sezione dal remoto
                new_section = self._section_repo.create_with_uuid(
                    name=remote_sec["name"],
                    section_uuid=uid,
                    icon=remote_sec.get("icon", "folder"),
                )
                section_uuid_to_id[uid] = new_section.id
                result.sections_pulled += 1
            else:
                local_sec = local_sections[uid]
                remote_time = remote_sec.get("updated_at", "")
                local_time = local_sec.get("updated_at", "")
                if remote_time > local_time:
                    self._section_repo.update_from_sync(
                        section_uuid=uid,
                        name=remote_sec["name"],
                        icon=remote_sec.get("icon", "folder"),
                        updated_at=remote_time,
                    )
                    result.sections_pulled += 1

        # Aggiorna mappa dopo creazione sezioni
        for section in self._section_repo.get_all():
            section_uuid_to_id[section.uuid] = section.id

        # Sync entries remote
        local_entries = {e["uuid"]: e for e in local_state.get("entries", [])}
        remote_entries = {e["uuid"]: e for e in remote_state.get("entries", [])}

        for uid, remote_entry in remote_entries.items():
            if uid in {t["uuid"] for t in remote_state.get("tombstones", [])}:
                continue

            section_uuid = remote_entry.get("section_uuid", "")
            section_id = section_uuid_to_id.get(section_uuid)

            if uid not in local_entries:
                # Nuova entry dal remoto
                self._entry_repo.create_from_sync(
                    name=remote_entry["name"],
                    content=remote_entry["content"],
                    entry_uuid=uid,
                    section_id=section_id,
                    entry_type=remote_entry.get("type", "prompt"),
                    tags=remote_entry.get("tags", ""),
                    created_at=remote_entry.get("created_at", ""),
                    updated_at=remote_entry.get("updated_at", ""),
                )
                result.entries_pulled += 1
            else:
                local_entry = local_entries[uid]
                remote_time = remote_entry.get("updated_at", "")
                local_time = local_entry.get("updated_at", "")
                if remote_time > local_time:
                    self._entry_repo.update_from_sync(
                        entry_uuid=uid,
                        name=remote_entry["name"],
                        content=remote_entry["content"],
                        section_id=section_id,
                        entry_type=remote_entry.get("type", "prompt"),
                        tags=remote_entry.get("tags", ""),
                        updated_at=remote_time,
                    )
                    result.entries_pulled += 1

        return result
