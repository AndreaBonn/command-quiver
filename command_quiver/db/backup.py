"""Backup periodici SQLite e conservazione delle copie recenti."""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_BACKUP_EVERY_N = 5
_BACKUP_SUFFIX = ".auto.bak"
_MAX_BACKUPS = 3


def auto_backup(connection: sqlite3.Connection, db_path: Path) -> None:
    """Crea un backup ogni N avvii, mantenendo le copie più recenti."""
    if not db_path.exists():
        return
    count = _increment_counter(db_path.parent / ".backup_counter")
    if count is None or count % _BACKUP_EVERY_N != 0:
        return
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    backup_path = db_path.parent / f"vault{_BACKUP_SUFFIX}.{timestamp}"
    try:
        _copy_database(source=connection, target=backup_path)
    except sqlite3.Error:
        logger.exception("Errore durante backup automatico")
        # Una copia incompleta conterebbe fra le ultime N, scalzandone una buona
        backup_path.unlink(missing_ok=True)
        return
    logger.info("Backup automatico creato: %s", backup_path.name)
    _prune_backups(db_path.parent)


def _copy_database(source: sqlite3.Connection, target: Path) -> None:
    """Copia il database in ``target``, chiudendo la connessione di destinazione anche su errore."""
    target_conn = sqlite3.connect(str(target))
    try:
        source.backup(target_conn)
    finally:
        target_conn.close()


def _increment_counter(counter_file: Path) -> int | None:
    """Incrementa il contatore, oppure restituisce None se non può scriverlo."""
    count = 0
    if counter_file.exists():
        try:
            count = int(counter_file.read_text().strip())
        except (ValueError, OSError):
            count = 0
    count += 1
    try:
        counter_file.write_text(str(count))
    except OSError:
        logger.warning("Impossibile aggiornare contatore backup")
        return None
    return count


def _prune_backups(backup_dir: Path) -> None:
    """Conserva solo gli ultimi N backup senza interrompersi su errori del filesystem."""
    backups = sorted(backup_dir.glob(f"vault{_BACKUP_SUFFIX}.*"), reverse=True)
    for old_backup in backups[_MAX_BACKUPS:]:
        try:
            old_backup.unlink()
            logger.debug("Backup obsoleto rimosso: %s", old_backup.name)
        except OSError:
            logger.warning("Impossibile rimuovere backup obsoleto: %s", old_backup)
