"""Gestione impostazioni persistenti in formato JSON."""

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "command-quiver"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "settings.json"
SYNC_TOKEN_PATH = DEFAULT_CONFIG_DIR / ".sync_token"

VALID_LANGUAGES = ("it", "en")
VALID_SORT_ORDERS = (
    "alpha_asc",
    "alpha_desc",
    "chronological_asc",
    "chronological_desc",
    "personal",
)


@dataclass
class SyncSettings:
    """Configurazione sincronizzazione GitHub."""

    enabled: bool = False
    repo_owner: str = ""
    repo_name: str = ""
    file_path: str = "vault.json"
    last_sha: str = ""
    last_sync: str = ""


@dataclass
class Settings:
    """Impostazioni dell'applicazione con valori di default."""

    sort_order: str = "chronological_desc"
    last_section_id: int | None = None
    window_width: int = 520
    window_height: int = 600
    theme: str = "auto"
    language: str = "it"
    sync: SyncSettings = field(default_factory=SyncSettings)

    def __post_init__(self) -> None:
        """Valida i valori dopo l'inizializzazione."""
        if self.sort_order not in VALID_SORT_ORDERS:
            self.sort_order = "chronological_desc"
        if self.language not in VALID_LANGUAGES:
            self.language = "it"
        if self.window_width < 300:
            self.window_width = 520
        if self.window_height < 300:
            self.window_height = 600
        # Converte dict in SyncSettings se caricato da JSON
        if isinstance(self.sync, dict):
            self.sync = SyncSettings(
                **{k: v for k, v in self.sync.items() if k in SyncSettings.__dataclass_fields__}
            )


def load_settings(config_path: Path | None = None) -> Settings:
    """Carica le impostazioni dal file JSON.

    Se il file non esiste o è corrotto, restituisce i valori di default.
    """
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        logger.info("File impostazioni non trovato, uso valori di default")
        return Settings()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # Filtra solo i campi validi del dataclass
        valid_fields = {f.name for f in Settings.__dataclass_fields__.values() if f.init}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return Settings(**filtered)
    except (json.JSONDecodeError, TypeError):
        logger.exception("File impostazioni corrotto, uso valori di default")
        return Settings()


def save_settings(settings: Settings, config_path: Path | None = None) -> None:
    """Salva le impostazioni nel file JSON."""
    path = config_path or DEFAULT_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    data = asdict(settings)

    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info("Impostazioni salvate: %s", path)


def load_sync_token() -> str:
    """Carica il token GitHub dal file dedicato."""
    if not SYNC_TOKEN_PATH.exists():
        return ""
    try:
        return SYNC_TOKEN_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        logger.exception("Errore lettura token sync")
        return ""


def save_sync_token(token: str) -> None:
    """Salva il token GitHub in un file con permessi restrittivi (600)."""
    SYNC_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    SYNC_TOKEN_PATH.write_text(token + "\n", encoding="utf-8")
    os.chmod(SYNC_TOKEN_PATH, 0o600)
    logger.info("Token sync salvato: %s", SYNC_TOKEN_PATH)


def delete_sync_token() -> None:
    """Rimuove il file token."""
    if SYNC_TOKEN_PATH.exists():
        SYNC_TOKEN_PATH.unlink()
        logger.info("Token sync rimosso")
