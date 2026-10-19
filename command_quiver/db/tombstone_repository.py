import sqlite3
from datetime import datetime, timedelta, timezone

from command_quiver.core.timestamps import utc_now_iso


def insert_tombstone(
    connection: sqlite3.Connection, tombstone_uuid: str, entity_type: str, deleted_at: str = ""
) -> None:
    """Inserisce una tombstone nella transazione del chiamante, senza commit."""
    connection.execute(
        "INSERT OR REPLACE INTO sync_tombstones (uuid, entity_type, deleted_at) VALUES (?, ?, ?)",
        (tombstone_uuid, entity_type, deleted_at or utc_now_iso()),
    )


class TombstoneRepository:
    """Gestione tombstones per sincronizzazione cross-device."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def get_all(self) -> list[dict]:
        """Restituisce tutte le tombstones attive."""
        cursor = self._conn.execute(
            "SELECT uuid, entity_type, deleted_at FROM sync_tombstones ORDER BY deleted_at DESC"
        )
        return [dict(row) for row in cursor.fetchall()]

    def add(self, tombstone_uuid: str, entity_type: str, deleted_at: str = "") -> None:
        """Aggiunge una tombstone (da sync remoto)."""
        insert_tombstone(
            connection=self._conn,
            tombstone_uuid=tombstone_uuid,
            entity_type=entity_type,
            deleted_at=deleted_at,
        )
        self._conn.commit()

    def cleanup(self, max_age_days: int = 90) -> int:
        """Rimuove tombstones più vecchie di max_age_days."""
        # Confronto fra stringhe: con formati misti sbaglia al più di qualche ora,
        # irrilevante su una soglia di mesi
        cursor = self._conn.execute(
            "DELETE FROM sync_tombstones WHERE deleted_at < ?",
            (_days_ago(days=max_age_days),),
        )
        self._conn.commit()
        return cursor.rowcount


def _days_ago(days: int) -> str:
    """Restituisce l'istante ISO UTC di N giorni fa."""
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
