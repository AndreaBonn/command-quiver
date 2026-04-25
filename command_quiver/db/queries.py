"""Repository CRUD per sezioni e voci del database."""

import logging
import sqlite3
from datetime import datetime

from command_quiver.db.models import (
    DuplicateSectionError,
    Entry,
    EntryCreate,
    EntryUpdate,
    Section,
)

# Re-export per backward compatibility degli import esistenti
__all__ = [
    "DuplicateSectionError",
    "Entry",
    "EntryCreate",
    "EntryRepository",
    "EntryUpdate",
    "Section",
    "SectionRepository",
]

logger = logging.getLogger(__name__)


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
        if self.exists(name):
            raise DuplicateSectionError(name)

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

    # Limite ragionevole per evitare OOM con DB enormi
    DEFAULT_LIMIT = 500

    def get_all(
        self,
        section_id: int | None = None,
        search: str = "",
        sort_order: str = "chronological_desc",
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Entry]:
        """Restituisce le voci filtrate per sezione e/o ricerca, ordinate.

        Parameters
        ----------
        limit : int | None
            Numero massimo di risultati. Default: DEFAULT_LIMIT.
        offset : int
            Numero di risultati da saltare (per paginazione).
        """
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

        effective_limit = limit if limit is not None else self.DEFAULT_LIMIT
        params.extend([effective_limit, offset])

        cursor = self._conn.execute(
            f"""
            SELECT e.id, e.name, e.content, e.section_id, e.type,
                   e.tags, e.personal_pos, e.created_at, e.updated_at,
                   COALESCE(s.name, 'Generale') AS section_name
            FROM entries e
            LEFT JOIN sections s ON s.id = e.section_id
            {where}
            ORDER BY {order}
            LIMIT ? OFFSET ?
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

    def import_entries(
        self,
        data: list[dict],
        section_repo: "SectionRepository",
    ) -> int:
        """Importa voci da una lista di dizionari. Restituisce il numero importato.

        Crea sezioni mancanti automaticamente. Salta voci con dati invalidi.

        SECURITY: le voci importate con type='shell' verranno eseguite letteralmente
        dall'utente. Il file JSON è trattato come input fidato — vedi SECURITY.md.
        """
        imported = 0
        # Cache sezioni per nome
        section_map: dict[str, int] = {s.name: s.id for s in section_repo.get_all()}

        for item in data:
            name = item.get("name", "").strip()
            content = item.get("content", "").strip()
            if not name or not content:
                continue

            entry_type = item.get("type", "prompt")
            if entry_type not in ("prompt", "shell"):
                entry_type = "prompt"

            tags = item.get("tags", "")
            section_name = item.get("section_name", "Generale")

            # Crea sezione se non esiste
            if section_name not in section_map:
                section = section_repo.create(name=section_name)
                section_map[section_name] = section.id

            self.create(
                EntryCreate(
                    name=name,
                    content=content,
                    section_id=section_map[section_name],
                    type=entry_type,
                    tags=tags,
                )
            )
            imported += 1

        logger.info("Importate %d voci su %d", imported, len(data))
        return imported
