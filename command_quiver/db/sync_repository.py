import logging
import sqlite3

from command_quiver.core.timestamps import utc_now_iso
from command_quiver.db.entry_repository import ENTRY_SELECT, EntryRepository
from command_quiver.db.models import Entry, Section, SyncedEntry
from command_quiver.db.section_repository import SectionRepository

logger = logging.getLogger(__name__)


class SyncRepository:
    """Operazioni per UUID usate dalla sincronizzazione."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection
        self._sections = SectionRepository(connection=connection)
        self._entries = EntryRepository(connection=connection)

    def get_section_by_uuid(self, section_uuid: str) -> Section | None:
        """Restituisce una sezione per UUID."""
        cursor = self._conn.execute(
            "SELECT id, name, icon, position, is_default, created_at, uuid, updated_at "
            "FROM sections WHERE uuid = ?",
            (section_uuid,),
        )
        row = cursor.fetchone()
        return Section(**dict(row)) if row else None

    def create_section_with_uuid(
        self,
        name: str,
        section_uuid: str,
        icon: str = "folder",
    ) -> Section:
        """Crea una sezione con UUID specifico (usato dal sync engine)."""
        cursor = self._conn.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM sections")
        next_pos = cursor.fetchone()[0]
        now = utc_now_iso()

        cursor = self._conn.execute(
            "INSERT INTO sections (name, icon, position, uuid, updated_at) VALUES (?, ?, ?, ?, ?)",
            (name, icon, next_pos, section_uuid, now),
        )
        self._conn.commit()
        logger.info("Sezione creata via sync: %s (uuid=%s)", name, section_uuid)
        return self._sections.get_by_id(section_id=cursor.lastrowid)

    def update_section_from_sync(
        self,
        section_uuid: str,
        name: str,
        icon: str,
        updated_at: str,
    ) -> bool:
        """Aggiorna una sezione dal sync engine (sovrascrive dati remoti)."""
        cursor = self._conn.execute(
            "UPDATE sections SET name = ?, icon = ?, updated_at = ? WHERE uuid = ?",
            (name, icon, updated_at, section_uuid),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def delete_section_by_uuid(self, section_uuid: str) -> bool:
        """Elimina una sezione per UUID (usato dal sync engine per tombstones)."""
        section = self.get_section_by_uuid(section_uuid=section_uuid)
        if section is None:
            return False
        return self._sections.delete(section_id=section.id)

    def adopt_uuid(self, section_id: int, section_uuid: str) -> None:
        """Assegna a una sezione locale l'uuid della sua omonima remota.

        Due installazioni creano le sezioni iniziali con uuid propri: al primo
        sync la sezione locale prende l'identità di quella remota con lo stesso
        nome. Le voci la referenziano per id, quindi restano al loro posto.
        """
        self._conn.execute("UPDATE sections SET uuid = ? WHERE id = ?", (section_uuid, section_id))
        self._conn.commit()
        logger.info("Sezione id=%d allineata all'uuid remoto %s", section_id, section_uuid)

    def get_entry_by_uuid(self, entry_uuid: str) -> Entry | None:
        """Restituisce una voce per UUID."""
        cursor = self._conn.execute(
            f"{ENTRY_SELECT} WHERE e.uuid = ?",
            (entry_uuid,),
        )
        row = cursor.fetchone()
        return Entry(**dict(row)) if row else None

    def create_from_sync(self, data: SyncedEntry) -> Entry:
        """Crea una voce con UUID e timestamp remoti; quelli vuoti usano l'ora UTC."""
        cursor = self._conn.execute(
            "SELECT COALESCE(MAX(personal_pos), -1) + 1 FROM entries WHERE section_id = ?",
            (data.section_id,),
        )
        next_pos = cursor.fetchone()[0]
        now = utc_now_iso()
        cursor = self._conn.execute(
            "INSERT INTO entries (name, content, section_id, type, tags, personal_pos, "
            "uuid, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                data.name,
                data.content,
                data.section_id,
                data.entry_type,
                data.tags,
                next_pos,
                data.entry_uuid,
                data.created_at or now,
                data.updated_at or now,
            ),
        )
        self._conn.commit()
        logger.info("Voce creata via sync: %s (uuid=%s)", data.name, data.entry_uuid)
        return self._entries.get_by_id(entry_id=cursor.lastrowid)

    def update_entry_from_sync(self, data: SyncedEntry) -> bool:
        """Aggiorna i dati remoti di una voce, preservando created_at e le statistiche locali."""
        cursor = self._conn.execute(
            "UPDATE entries SET name = ?, content = ?, section_id = ?, type = ?, "
            "tags = ?, updated_at = ? WHERE uuid = ?",
            (
                data.name,
                data.content,
                data.section_id,
                data.entry_type,
                data.tags,
                data.updated_at,
                data.entry_uuid,
            ),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def delete_entry_by_uuid(self, entry_uuid: str) -> bool:
        """Elimina una voce per UUID (usato dal sync engine per tombstones remoti)."""
        cursor = self._conn.execute(
            "DELETE FROM entries WHERE uuid = ?",
            (entry_uuid,),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def export_for_sync(self) -> list[dict]:
        """Esporta tutte le voci con UUID e timestamp per il sync."""
        cursor = self._conn.execute("""
            SELECT e.uuid, e.name, e.content, e.type, e.tags,
                   e.created_at, e.updated_at,
                   COALESCE(s.uuid, '') AS section_uuid
            FROM entries e
            LEFT JOIN sections s ON s.id = e.section_id
            ORDER BY e.created_at ASC
        """)
        return [dict(row) for row in cursor.fetchall()]
