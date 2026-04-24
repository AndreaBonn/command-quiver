"""Gestione impostazioni persistenti in formato JSON."""

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "command-quiver"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "settings.json"


@dataclass
class Settings:
    """Impostazioni dell'applicazione con valori di default."""

    sort_order: str = "chronological_desc"
    last_section_id: int | None = None
    window_width: int = 520
    window_height: int = 600
    theme: str = "auto"

    # Valori ammessi per sort_order
    VALID_SORT_ORDERS: tuple[str, ...] = field(
        default=("alpha_asc", "alpha_desc", "chronological_asc", "chronological_desc", "personal"),
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        """Valida i valori dopo l'inizializzazione."""
        if self.sort_order not in self.VALID_SORT_ORDERS:
            self.sort_order = "chronological_desc"
        if self.window_width < 300:
            self.window_width = 520
        if self.window_height < 300:
            self.window_height = 600


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
    # Rimuovi campi non serializzabili
    data.pop("VALID_SORT_ORDERS", None)

    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info("Impostazioni salvate: %s", path)
