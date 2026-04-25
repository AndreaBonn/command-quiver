"""Repository CRUD per sezioni e voci del database."""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


# --- Modelli dati ---


@dataclass
class Section:
    """Rappresenta una sezione/categoria di voci."""

    id: int
    name: str
    icon: str = "folder"
    position: int = 0
    is_default: int = 0
    created_at: str = ""
    entry_count: int = 0  # Calcolato via query, non persistito


@dataclass
class Entry:
    """Rappresenta una voce (prompt o comando shell)."""

    id: int
    name: str
    content: str
    section_id: int | None = None
    type: str = "prompt"
    tags: str = ""
    personal_pos: int = 0
    created_at: str = ""
    updated_at: str = ""
    section_name: str = ""  # Calcolato via JOIN, non persistito


@dataclass
class EntryCreate:
    """Dati per la creazione di una nuova voce."""

    name: str
    content: str
    section_id: int | None = None
    type: str = "prompt"
    tags: str = ""


@dataclass
class EntryUpdate:
    """Dati per l'aggiornamento di una voce esistente."""

    id: int
    name: str
    content: str
    section_id: int | None = None
    type: str = "prompt"
    tags: str = ""


# --- Repository Sezioni ---


class SectionRepository:
    """Operazioni CRUD sulle sezioni."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def get_all(self) -> list[Section]:
        """Restituisce tutte le sezioni ordinate per posizione, con conteggio voci."""
        cursor = self._conn.execute("""
            SELECT s.id, s.name, s.icon, s.position, s.is_default, s.created_at,
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
            "SELECT id, name, icon, position, is_default, created_at FROM sections WHERE id = ?",
            (section_id,),
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
            "INSERT INTO sections (name, icon, position, is_default) "
            "VALUES ('Generale', 'folder', 999, 1)"
        )
        self._conn.commit()
        return cursor.lastrowid

    def create(self, name: str, icon: str = "folder") -> Section:
        """Crea una nuova sezione. La posizione viene assegnata automaticamente."""
        # Prossima posizione disponibile
        cursor = self._conn.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM sections")
        next_pos = cursor.fetchone()[0]

        cursor = self._conn.execute(
            "INSERT INTO sections (name, icon, position) VALUES (?, ?, ?)",
            (name, icon, next_pos),
        )
        self._conn.commit()
        logger.info("Sezione creata: %s (id=%d)", name, cursor.lastrowid)
        return Section(id=cursor.lastrowid, name=name, icon=icon, position=next_pos)

    def rename(self, section_id: int, new_name: str) -> bool:
        """Rinomina una sezione. Restituisce True se modificata."""
        cursor = self._conn.execute(
            "UPDATE sections SET name = ? WHERE id = ?",
            (new_name, section_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def delete(self, section_id: int) -> bool:
        """Elimina una sezione. Le voci vengono spostate in 'Generale'."""
        generale_id = self.get_default_section_id()
        if section_id == generale_id:
            logger.warning("Tentativo di eliminare la sezione di default — operazione ignorata")
            return False

        # Sposta le voci nella sezione Generale
        self._conn.execute(
            "UPDATE entries SET section_id = ? WHERE section_id = ?",
            (generale_id, section_id),
        )
        cursor = self._conn.execute(
            "DELETE FROM sections WHERE id = ?",
            (section_id,),
        )
        self._conn.commit()
        logger.info("Sezione eliminata (id=%d), voci spostate in Generale", section_id)
        return cursor.rowcount > 0


# --- Repository Voci ---


class EntryRepository:
    """Operazioni CRUD sulle voci (prompt e comandi shell)."""

    # Mapping ordinamento → clausola SQL ORDER BY
    _SORT_CLAUSES = {
        "alpha_asc": "e.name ASC",
        "alpha_desc": "e.name DESC",
        "chronological_desc": "e.created_at DESC",
        "chronological_asc": "e.created_at ASC",
        "personal": "e.personal_pos ASC, e.name ASC",
    }

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def get_all(
        self,
        section_id: int | None = None,
        search: str = "",
        sort_order: str = "chronological_desc",
    ) -> list[Entry]:
        """Restituisce le voci filtrate per sezione e/o ricerca, ordinate."""
        order = self._SORT_CLAUSES.get(sort_order, "e.created_at DESC")
        conditions: list[str] = []
        params: list[str | int] = []

        if section_id is not None:
            conditions.append("e.section_id = ?")
            params.append(section_id)

        if search:
            conditions.append(
                "(UNICODE_LOWER(e.name) LIKE '%' || UNICODE_LOWER(?) || '%'"
                " OR UNICODE_LOWER(e.content) LIKE '%' || UNICODE_LOWER(?) || '%'"
                " OR UNICODE_LOWER(e.tags) LIKE '%' || UNICODE_LOWER(?) || '%')"
            )
            params.extend([search, search, search])

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        cursor = self._conn.execute(
            f"""
            SELECT e.id, e.name, e.content, e.section_id, e.type,
                   e.tags, e.personal_pos, e.created_at, e.updated_at,
                   COALESCE(s.name, 'Generale') AS section_name
            FROM entries e
            LEFT JOIN sections s ON s.id = e.section_id
            {where}
            ORDER BY {order}
        """,
            params,
        )
        return [Entry(**dict(row)) for row in cursor.fetchall()]

    def get_by_id(self, entry_id: int) -> Entry | None:
        """Restituisce una voce per ID."""
        cursor = self._conn.execute(
            """
            SELECT e.id, e.name, e.content, e.section_id, e.type,
                   e.tags, e.personal_pos, e.created_at, e.updated_at,
                   COALESCE(s.name, 'Generale') AS section_name
            FROM entries e
            LEFT JOIN sections s ON s.id = e.section_id
            WHERE e.id = ?
        """,
            (entry_id,),
        )
        row = cursor.fetchone()
        return Entry(**dict(row)) if row else None

    def create(self, data: EntryCreate) -> Entry:
        """Crea una nuova voce."""
        # Prossima posizione personale disponibile (per sezione)
        cursor = self._conn.execute(
            "SELECT COALESCE(MAX(personal_pos), -1) + 1 FROM entries WHERE section_id = ?",
            (data.section_id,),
        )
        next_pos = cursor.fetchone()[0]

        cursor = self._conn.execute(
            """
            INSERT INTO entries (name, content, section_id, type, tags, personal_pos)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (data.name, data.content, data.section_id, data.type, data.tags, next_pos),
        )
        self._conn.commit()

        entry = self.get_by_id(cursor.lastrowid)
        logger.info("Voce creata: %s (id=%d, tipo=%s)", data.name, entry.id, data.type)
        return entry

    def update(self, data: EntryUpdate) -> Entry | None:
        """Aggiorna una voce esistente."""
        now = datetime.now().isoformat()
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
        return self.get_by_id(data.id)

    def delete(self, entry_id: int) -> bool:
        """Elimina una voce. Restituisce True se eliminata."""
        cursor = self._conn.execute(
            "DELETE FROM entries WHERE id = ?",
            (entry_id,),
        )
        self._conn.commit()
        deleted = cursor.rowcount > 0
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
