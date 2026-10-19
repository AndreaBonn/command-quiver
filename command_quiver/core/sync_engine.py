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
from command_quiver.core.sync_merge import (
    RemoteChangePlan,
    build_sync_state,
    count_pushed,
    merge_states,
    plan_remote_changes,
)
from command_quiver.core.timestamps import utc_now_iso
from command_quiver.db.database import Database
from command_quiver.db.models import SyncedEntry
from command_quiver.db.section_repository import SectionRepository
from command_quiver.db.sync_repository import SyncRepository
from command_quiver.db.tombstone_repository import TombstoneRepository

logger = logging.getLogger(__name__)

# Messaggi azionabili per gli errori GitHub piu' comuni durante il sync.
_NETWORK_ERROR_MESSAGE = "Impossibile raggiungere GitHub. Controlla la connessione di rete."
_HTTP_ERROR_MESSAGES = {
    401: (
        "Token GitHub non valido o scaduto. "
        "Aggiorna il token nelle impostazioni di sincronizzazione."
    ),
    403: (
        "Accesso negato: permessi insufficienti sul repository "
        "o limite di richieste GitHub raggiunto. Riprova piu' tardi."
    ),
    404: (
        "Repository o percorso file non trovato. "
        "Verifica owner e nome del repository nelle impostazioni."
    ),
    409: "Conflitto di versione durante il salvataggio su GitHub. Riprova il sync.",
    422: ("Dati o percorso file non accettati da GitHub. Verifica il percorso del file di sync."),
}


def humanize_github_error(err: GitHubApiError) -> str:
    """Traduce un errore GitHub in un messaggio comprensibile e azionabile.

    Parameters
    ----------
    err : GitHubApiError
        Errore sollevato dal client GitHub. ``status_code == 0`` indica un
        errore di rete (nessuna risposta HTTP ricevuta).

    Returns
    -------
    str
        Messaggio in italiano orientato all'azione dell'utente.
    """
    if err.status_code == 0:
        return _NETWORK_ERROR_MESSAGE
    return _HTTP_ERROR_MESSAGES.get(
        err.status_code,
        f"Errore GitHub (codice {err.status_code}). Riprova piu' tardi.",
    )


@dataclass
class SyncResult:
    """Risultato di un'operazione di sync."""

    success: bool
    message: str = ""
    entries_pulled: int = 0
    entries_pushed: int = 0
    sections_pulled: int = 0


class SyncEngine:
    """Orchestra il sync con repository creati sulla connessione del thread corrente.

    ``sync()`` gira in un thread daemon separato dal thread GTK e SQLite vieta di
    condividere una connessione fra thread: i repository nascono in ``sync()``
    su una connessione dedicata (``Database.create_connection``).
    """

    def __init__(self, db: Database, settings: Settings) -> None:
        self._db = db
        self._settings = settings

    def _create_client(self) -> GitHubClient | None:
        sync = self._settings.sync
        token = load_sync_token()
        if not all([sync.enabled, sync.repo_owner, sync.repo_name, token]):
            return None
        return GitHubClient(token=token, owner=sync.repo_owner, repo=sync.repo_name)

    def sync(self) -> SyncResult:
        """Esegue pull e push sulla connessione dedicata al thread chiamante.

        Returns
        -------
        SyncResult
            Esito e conteggi, oppure messaggio di errore.
        """
        client = self._create_client()
        if client is None:
            return SyncResult(success=False, message="Sync non configurato")
        connection = self._db.create_connection()
        self._section_repo = SectionRepository(connection=connection)
        self._sync_repo = SyncRepository(connection=connection)
        self._tombstone_repo = TombstoneRepository(connection=connection)
        try:
            merged, sha, result = self._pull_and_apply(client=client)
            new_sha = self._push(client=client, merged=merged, sha=sha)
            return self._record_success(new_sha=new_sha, result=result)
        except GitHubApiError as err:
            logger.error("Sync fallito: %s", err)
            return SyncResult(success=False, message=humanize_github_error(err))
        # ValueError copre JSON, base64 e UTF-8 non validi del file remoto
        except (ValueError, KeyError, TypeError) as err:
            logger.exception("Sync fallito (dati corrotti): %s", err)
            return SyncResult(success=False, message=f"Dati remoti corrotti: {err}")
        finally:
            connection.close()

    def _pull_and_apply(self, client: GitHubClient) -> tuple[dict, str, SyncResult]:
        local = self._export_local()
        remote_file = client.get_file(path=self._settings.sync.file_path)
        if remote_file is None:
            result = SyncResult(success=True, message="Primo sync")
            result.entries_pushed = len(local.get("entries", []))
            return local, "", result
        remote = json.loads(remote_file.content)
        plan = plan_remote_changes(local_state=local, remote_state=remote)
        result = self._apply_plan(plan=plan, local_state=local, remote_state=remote)
        merged = merge_states(
            local_state=self._export_local(), remote_state=remote, now=utc_now_iso()
        )
        result.entries_pushed = count_pushed(
            merged=merged["entries"], remote=remote.get("entries", [])
        )
        return merged, remote_file.sha, result

    def _push(self, client: GitHubClient, merged: dict, sha: str) -> str:
        return client.put_file(
            path=self._settings.sync.file_path,
            content=json.dumps(merged, indent=2, ensure_ascii=False),
            sha=sha,
        )

    def _record_success(self, new_sha: str, result: SyncResult) -> SyncResult:
        self._settings.sync.last_sha = new_sha
        self._settings.sync.last_sync = datetime.now().isoformat()
        save_settings(self._settings)
        self._tombstone_repo.cleanup(max_age_days=90)
        if not result.message:
            result.message = "Sync completato"
        logger.info(
            "Sync completato: %d entries pulled, %d sections pulled",
            result.entries_pulled,
            result.sections_pulled,
        )
        return result

    def _export_local(self) -> dict:
        return build_sync_state(
            sections=[vars(s) for s in self._section_repo.get_all()],
            entries=self._sync_repo.export_for_sync(),
            tombstones=self._tombstone_repo.get_all(),
            now=utc_now_iso(),
        )

    def _apply_plan(
        self, plan: RemoteChangePlan, local_state: dict, remote_state: dict
    ) -> SyncResult:
        result = SyncResult(success=True)
        local = {s["uuid"]: s for s in local_state.get("sections", [])}
        for tombstone in plan.tombstones:
            self._apply_tombstone(tombstone=tombstone, local_sections=local)
        remote_sections = {s["uuid"]: s for s in remote_state.get("sections", [])}
        new_sections = {s["uuid"] for s in plan.new_sections}
        updated_sections = {s["uuid"] for s in plan.updated_sections}
        for uid, section in remote_sections.items():
            if uid in new_sections:
                result.sections_pulled += self._pull_new_section(
                    uid=uid, remote_sec=section, remote_sections=remote_sections
                )
            elif uid in updated_sections:
                result.sections_pulled += self._update_section(section=section)
        # La mappa segue le cancellazioni e le adozioni UUID per evitare id orfani (B10).
        section_ids = {s.uuid: s.id for s in self._section_repo.get_all()}
        default_id = self._section_repo.get_default_section_id()
        new_entries = {e["uuid"] for e in plan.new_entries}
        updated_entries = {e["uuid"] for e in plan.updated_entries}
        remote_entries = {e["uuid"]: e for e in remote_state.get("entries", [])}
        for uid, entry in remote_entries.items():
            if uid in new_entries or uid in updated_entries:
                section_id = section_ids.get(entry.get("section_uuid", "")) or default_id
                self._apply_entry(entry=entry, section_id=section_id, is_new=uid in new_entries)
                result.entries_pulled += 1
        return result

    def _apply_tombstone(self, tombstone: dict, local_sections: dict) -> None:
        uid = tombstone["uuid"]
        entity_type = tombstone["entity_type"]
        if entity_type == "entry":
            self._sync_repo.delete_entry_by_uuid(entry_uuid=uid)
        elif uid in local_sections and not self._sync_repo.delete_section_by_uuid(section_uuid=uid):
            # La sezione predefinita riaffermata deve vincere nel push senza tombstone (B4).
            section = local_sections[uid]
            self._sync_repo.update_section_from_sync(
                section_uuid=uid,
                name=section["name"],
                icon=section["icon"],
                updated_at=utc_now_iso(),
            )
            return
        self._tombstone_repo.add(
            tombstone_uuid=uid, entity_type=entity_type, deleted_at=tombstone["deleted_at"]
        )

    def _update_section(self, section: dict) -> int:
        uid = section["uuid"]
        taken = self._section_repo.get_by_name(name=section["name"])
        if taken is not None and taken.uuid != uid:
            logger.warning(
                "Sync: rinomina remota di %s ignorata, nome '%s' già in uso", uid, section["name"]
            )
            return 0
        self._sync_repo.update_section_from_sync(
            section_uuid=uid,
            name=section["name"],
            icon=section.get("icon", "folder"),
            updated_at=section.get("updated_at", ""),
        )
        return 1

    def _apply_entry(self, entry: dict, section_id: int | None, is_new: bool) -> None:
        data = SyncedEntry(
            entry_uuid=entry["uuid"],
            name=entry["name"],
            content=entry["content"],
            section_id=section_id,
            entry_type=entry.get("type", "prompt"),
            tags=entry.get("tags", ""),
            updated_at=entry.get("updated_at", ""),
            created_at=entry.get("created_at", "") if is_new else "",
        )
        if is_new:
            self._sync_repo.create_from_sync(data=data)
        else:
            self._sync_repo.update_entry_from_sync(data=data)

    def _pull_new_section(self, uid: str, remote_sec: dict, remote_sections: dict) -> int:
        """Porta in locale una sezione remota nuova. Restituisce 1 se l'ha creata.

        Con un'omonima locale non ancora sincronizzata (le sezioni iniziali di
        un'altra installazione) ne adotta l'uuid invece di duplicarla (B1). Se
        l'omonima è già nel remoto è un conflitto di rinomina: si salta.
        """
        same_name = self._section_repo.get_by_name(name=remote_sec["name"])
        if same_name is None:
            self._sync_repo.create_section_with_uuid(
                name=remote_sec["name"],
                section_uuid=uid,
                icon=remote_sec.get("icon", "folder"),
            )
            return 1
        if same_name.uuid not in remote_sections:
            self._sync_repo.adopt_uuid(section_id=same_name.id, section_uuid=uid)
        else:
            logger.warning(
                "Sync: sezione remota %s ignorata, nome '%s' già in uso", uid, remote_sec["name"]
            )
        return 0
