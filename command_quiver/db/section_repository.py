import logging
import sqlite3
import uuid as uuid_mod

from command_quiver.core.timestamps import utc_now_iso
from command_quiver.db.models import DuplicateSectionError, Section
from command_quiver.db.tombstone_repository import insert_tombstone

logger = logging.getLogger(__name__)


class SectionRepository:
    """Operazioni CRUD sulle sezioni per la UI."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def get_all(self) -> list[Section]:
        """Restituisce tutte le sezioni ordinate per posizione, con conteggio voci."""
        cursor = self._conn.execute("""
            SELECT s.id, s.name, s.icon, s.position, s.is_default, s.created_at,
                   s.uuid, s.updated_at,
                   COUNT(e.id) AS entry_count
            FROM sections s
            LEFT JOIN entries e ON e.section_id = s.id
            GROUP BY s.id
            ORDER BY s.position ASC
        """)
        return [Section(**dict(row)) for row in cursor.fetchall()]

    def get_by_id(self, section_id: int) -> Section | None:
        """Restituisce una sezione per ID."""
        cursor = self._conn.execute(
            "SELECT id, name, icon, position, is_default, created_at, uuid, updated_at "
            "FROM sections WHERE id = ?",
            (section_id,),
        )
        row = cursor.fetchone()
        return Section(**dict(row)) if row else None

    def get_by_name(self, name: str) -> Section | None:
        """Restituisce la sezione con questo nome, senza distinguere maiuscole."""
        cursor = self._conn.execute(
            "SELECT id, name, icon, position, is_default, created_at, uuid, updated_at "
            "FROM sections WHERE UNICODE_LOWER(name) = UNICODE_LOWER(?)",
            (name,),
        )
        row = cursor.fetchone()
        return Section(**dict(row)) if row else None

    def get_default_section_id(self) -> int:
        """Restituisce l'ID della sezione di default (fallback per voci orfane)."""
        cursor = self._conn.execute("SELECT id FROM sections WHERE is_default = 1")
        row = cursor.fetchone()
        if row:
            return row["id"]
        # Fallback: cerca per nome legacy, poi crea se non esiste
        cursor = self._conn.execute("SELECT id FROM sections WHERE name = 'Generale'")
        row = cursor.fetchone()
        if row:
            self._conn.execute("UPDATE sections SET is_default = 1 WHERE id = ?", (row["id"],))
            self._conn.commit()
            return row["id"]
        cursor = self._conn.execute(
            "INSERT INTO sections (name, icon, position, is_default, uuid) "
            "VALUES ('Generale', 'folder', 999, 1, ?)",
            (str(uuid_mod.uuid4()),),
        )
        self._conn.commit()
        return cursor.lastrowid

    def exists(self, name: str) -> bool:
        """Verifica se una sezione con questo nome esiste già (case-insensitive)."""
        cursor = self._conn.execute(
            "SELECT 1 FROM sections WHERE UNICODE_LOWER(name) = UNICODE_LOWER(?)",
            (name,),
        )
        return cursor.fetchone() is not None

    def create(self, name: str, icon: str = "folder") -> Section:
        """Crea una nuova sezione. La posizione viene assegnata automaticamente.

        Raises
        ------
        DuplicateSectionError
            Se una sezione con lo stesso nome esiste già.
        """
        if self.exists(name=name):
            raise DuplicateSectionError(name)

        # Prossima posizione disponibile
        cursor = self._conn.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM sections")
        next_pos = cursor.fetchone()[0]
        new_uuid = str(uuid_mod.uuid4())
        now = utc_now_iso()

        cursor = self._conn.execute(
            "INSERT INTO sections (name, icon, position, uuid, updated_at) VALUES (?, ?, ?, ?, ?)",
            (name, icon, next_pos, new_uuid, now),
        )
        self._conn.commit()
        logger.info("Sezione creata: %s (id=%d)", name, cursor.lastrowid)
        return self.get_by_id(section_id=cursor.lastrowid)

    def rename(self, section_id: int, new_name: str) -> bool:
        """Rinomina una sezione. Restituisce True se modificata.

        Raises
        ------
        DuplicateSectionError
            Se una sezione con lo stesso nome esiste già.
        """
        # Verifica duplicato escludendo la sezione corrente
        cursor = self._conn.execute(
            "SELECT 1 FROM sections WHERE UNICODE_LOWER(name) = UNICODE_LOWER(?) AND id != ?",
            (new_name, section_id),
        )
        if cursor.fetchone() is not None:
            raise DuplicateSectionError(new_name)

        now = utc_now_iso()
        cursor = self._conn.execute(
            "UPDATE sections SET name = ?, updated_at = ? WHERE id = ?",
            (new_name, now, section_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def delete(self, section_id: int) -> bool:
        """Elimina una sezione. Le voci vengono spostate in 'Generale'."""
        generale_id = self.get_default_section_id()
        if section_id == generale_id:
            logger.warning(
                "Tentativo di eliminare la sezione di default \u2014 operazione ignorata"
            )
            return False

        section = self.get_by_id(section_id=section_id)
        section_uuid = section.uuid if section else ""

        # Una transazione sola: senza tombstone il sync ricreerebbe la sezione (B8)
        with self._conn:
            self._conn.execute(
                "UPDATE entries SET section_id = ? WHERE section_id = ?",
                (generale_id, section_id),
            )
            cursor = self._conn.execute(
                "DELETE FROM sections WHERE id = ?",
                (section_id,),
            )
            if cursor.rowcount > 0 and section_uuid:
                insert_tombstone(
                    connection=self._conn, tombstone_uuid=section_uuid, entity_type="section"
                )
                logger.info("Sezione eliminata (id=%d), voci spostate in Generale", section_id)

        return cursor.rowcount > 0
