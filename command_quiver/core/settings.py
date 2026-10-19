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
_TOKEN_FILE_MODE = 0o600  # lettura e scrittura solo per il proprietario

VALID_LANGUAGES = ("it", "en")
# Larghezza in cui pannello sezioni (224 px) e lista stanno senza troncare i nomi
DEFAULT_WINDOW_WIDTH = 640
# Sotto questa larghezza la lista resta troppo stretta e i nomi si troncano
MIN_WINDOW_WIDTH = 600
VALID_SORT_ORDERS = (
    "alpha_asc",
    "alpha_desc",
    "chronological_asc",
    "chronological_desc",
    "personal",
    "usage",
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
    window_width: int = DEFAULT_WINDOW_WIDTH
    window_height: int = 600
    theme: str = "auto"
    language: str = "it"
    sync: SyncSettings = field(default_factory=SyncSettings)
    # UUID delle voci che l'utente esegue senza conferma ("non chiedere più")
    skip_run_confirm: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Valida i valori dopo l'inizializzazione."""
        if not isinstance(self.skip_run_confirm, list):
            self.skip_run_confirm = []
        if self.sort_order not in VALID_SORT_ORDERS:
            self.sort_order = "chronological_desc"
        if self.language not in VALID_LANGUAGES:
            self.language = "it"
        if self.window_width < MIN_WINDOW_WIDTH:
            self.window_width = DEFAULT_WINDOW_WIDTH
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
        # UnicodeDecodeError è un ValueError, come JSONDecodeError; OSError copre
        # un path illeggibile (permessi, directory al posto del file)
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.exception("File impostazioni illeggibile o corrotto, uso valori di default")
        return Settings()
    if not isinstance(data, dict):
        logger.error("File impostazioni senza un oggetto JSON (%s), uso valori di default", path)
        return Settings()
    try:
        # Filtra solo i campi validi del dataclass
        valid_fields = {f.name for f in Settings.__dataclass_fields__.values() if f.init}
        return Settings(**{k: v for k, v in data.items() if k in valid_fields})
    except TypeError:
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
    except (OSError, UnicodeDecodeError):
        logger.exception("Errore lettura token sync")
        return ""


def save_sync_token(token: str) -> None:
    """Salva il token GitHub in un file con permessi restrittivi (600)."""
    SYNC_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Creato già 600: con write_text e chmod dopo, il file restava per un attimo
    # leggibile coi permessi dell'umask. fchmod stringe un file già esistente.
    fd = os.open(SYNC_TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, _TOKEN_FILE_MODE)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        os.fchmod(handle.fileno(), _TOKEN_FILE_MODE)
        handle.write(token + "\n")
    logger.info("Token sync salvato: %s", SYNC_TOKEN_PATH)


def delete_sync_token() -> None:
    """Rimuove il file token."""
    if SYNC_TOKEN_PATH.exists():
        SYNC_TOKEN_PATH.unlink()
        logger.info("Token sync rimosso")
