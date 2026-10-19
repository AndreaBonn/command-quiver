import logging
import sqlite3
import uuid as uuid_mod

from command_quiver.core.timestamps import utc_now_iso
from command_quiver.db.models import Entry, EntryCreate, EntryUpdate
from command_quiver.db.tombstone_repository import insert_tombstone

logger = logging.getLogger(__name__)

# Colonne e JOIN comuni a ogni lettura di voci, anche da SyncRepository
ENTRY_SELECT = """
    SELECT e.id, e.name, e.content, e.section_id, e.type,
           e.tags, e.personal_pos, e.created_at, e.updated_at,
           e.uuid, e.use_count, COALESCE(e.last_used_at, '') AS last_used_at,
           COALESCE(s.name, 'Generale') AS section_name
    FROM entries e
    LEFT JOIN sections s ON s.id = e.section_id
"""


def _entry_filters(section_id: int | None, search: str) -> tuple[str, list[str | int]]:
    conditions: list[str] = []
    params: list[str | int] = []
    if section_id is not None:
        conditions.append("e.section_id = ?")
        params.append(section_id)
    if search:
        # instr e non LIKE: nei comandi "_" e "%" sono testo, con LIKE facevano da jolly
        conditions.append(
            "(instr(UNICODE_LOWER(e.name), UNICODE_LOWER(?)) > 0"
            " OR instr(UNICODE_LOWER(e.content), UNICODE_LOWER(?)) > 0"
            " OR instr(UNICODE_LOWER(e.tags), UNICODE_LOWER(?)) > 0)"
        )
        params.extend([search, search, search])
    return f"WHERE {' AND '.join(conditions)}" if conditions else "", params


class EntryRepository:
    """Operazioni CRUD sulle voci per la UI."""

    DEFAULT_LIMIT = 500
    _SORT_CLAUSES = {
        "alpha_asc": "e.name ASC",
        "alpha_desc": "e.name DESC",
        "chronological_desc": "e.created_at DESC",
        "chronological_asc": "e.created_at ASC",
        "personal": "e.personal_pos ASC, e.name ASC",
        "usage": "e.use_count DESC, e.last_used_at DESC, e.name ASC",
    }

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def get_all(
        self,
        section_id: int | None = None,
        search: str = "",
        sort_order: str = "chronological_desc",
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Entry]:
        """Restituisce le voci filtrate, ordinate e paginate.

        Parameters
        ----------
        limit : int | None
            Numero massimo di risultati; None usa DEFAULT_LIMIT.
        offset : int
            Numero di risultati da saltare.
        """
        order = self._SORT_CLAUSES.get(sort_order, "e.created_at DESC")
        where, params = _entry_filters(section_id=section_id, search=search)
        params.extend([limit if limit is not None else self.DEFAULT_LIMIT, offset])
        cursor = self._conn.execute(
            f"{ENTRY_SELECT} {where} ORDER BY {order} LIMIT ? OFFSET ?", params
        )
        return [Entry(**dict(row)) for row in cursor.fetchall()]

    def get_by_id(self, entry_id: int) -> Entry | None:
        """Restituisce una voce per ID."""
        cursor = self._conn.execute(
            f"{ENTRY_SELECT} WHERE e.id = ?",
            (entry_id,),
        )
        row = cursor.fetchone()
        return Entry(**dict(row)) if row else None

    def bump_usage(self, entry_id: int) -> None:
        """Registra un uso della voce: incrementa il contatore e l'ultimo uso.

        Statistica locale al dispositivo, usata solo dall'ordinamento
        "più usati". Non tocca ``updated_at`` di proposito: il merge del sync
        è last-write-wins su ``updated_at``, quindi contare gli usi non deve
        far apparire la voce come modificata né propagarsi cross-device.
        """
        self._conn.execute(
            "UPDATE entries SET use_count = use_count + 1, last_used_at = ? WHERE id = ?",
            (utc_now_iso(), entry_id),
        )
        self._conn.commit()

    def create(self, data: EntryCreate) -> Entry:
        """Crea una nuova voce."""
        cursor = self._conn.execute(
            "SELECT COALESCE(MAX(personal_pos), -1) + 1 FROM entries WHERE section_id = ?",
            (data.section_id,),
        )
        next_pos = cursor.fetchone()[0]
        new_uuid = str(uuid_mod.uuid4())
        # Timestamp espliciti: il default CURRENT_TIMESTAMP ha un formato diverso (B2)
        now = utc_now_iso()
        cursor = self._conn.execute(
            "INSERT INTO entries (name, content, section_id, type, tags, personal_pos, uuid, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                data.name,
                data.content,
                data.section_id,
                data.type,
                data.tags,
                next_pos,
                new_uuid,
                now,
                now,
            ),
        )
        self._conn.commit()
        entry = self.get_by_id(entry_id=cursor.lastrowid)
        logger.info("Voce creata: %s (id=%d, tipo=%s)", data.name, entry.id, data.type)
        return entry

    def update(self, data: EntryUpdate) -> Entry | None:
        """Aggiorna una voce esistente."""
        now = utc_now_iso()
        cursor = self._conn.execute(
            """
            UPDATE entries
            SET name = ?, content = ?, section_id = ?, type = ?, tags = ?, updated_at = ?
            WHERE id = ?
        """,
            (data.name, data.content, data.section_id, data.type, data.tags, now, data.id),
        )
        self._conn.commit()

        if cursor.rowcount == 0:
            return None

        logger.info("Voce aggiornata: %s (id=%d)", data.name, data.id)
        return self.get_by_id(entry_id=data.id)

    def delete(self, entry_id: int) -> bool:
        """Elimina una voce. Restituisce True se eliminata."""
        # Recupera uuid per tombstone prima di eliminare
        entry = self.get_by_id(entry_id=entry_id)
        entry_uuid = entry.uuid if entry else ""

        # Una transazione sola: senza tombstone il sync ricreerebbe la voce (B8)
        with self._conn:
            cursor = self._conn.execute(
                "DELETE FROM entries WHERE id = ?",
                (entry_id,),
            )
            deleted = cursor.rowcount > 0
            if deleted and entry_uuid:
                insert_tombstone(
                    connection=self._conn, tombstone_uuid=entry_uuid, entity_type="entry"
                )

        if deleted:
            logger.info("Voce eliminata (id=%d)", entry_id)

        return deleted

    def update_position(self, entry_id: int, new_position: int) -> bool:
        """Aggiorna la posizione personale di una voce (drag-and-drop)."""
        cursor = self._conn.execute(
            "UPDATE entries SET personal_pos = ? WHERE id = ?",
            (new_position, entry_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def count_all(self) -> int:
        """Conteggio totale delle voci."""
        cursor = self._conn.execute("SELECT COUNT(*) FROM entries")
        return cursor.fetchone()[0]

    def export_all(self) -> list[dict]:
        """Esporta tutte le voci come lista di dizionari (per backup JSON)."""
        cursor = self._conn.execute("""
            SELECT e.name, e.content, e.type, e.tags,
                   COALESCE(s.name, 'Generale') AS section_name
            FROM entries e
            LEFT JOIN sections s ON s.id = e.section_id
            ORDER BY e.created_at ASC
        """)
        return [dict(row) for row in cursor.fetchall()]
