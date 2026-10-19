"""Azioni sulla libreria avviate dal menu o dagli stati vuoti: import, export, esempi."""

import logging
from collections.abc import Callable
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

from command_quiver.core.i18n import get_language, t
from command_quiver.core.library_io import InvalidExportError, parse_import, serialize_export
from command_quiver.core.samples import sample_entries
from command_quiver.db.queries import EntryCreate, EntryRepository, Section, SectionRepository

logger = logging.getLogger(__name__)

EXPORT_FILE_NAME = "command-quiver-export.json"
# Sezione tipica di ogni tipo, riconosciuta dall'icona di seed (i nomi cambiano con la lingua)
SECTION_ICON_BY_TYPE = {"shell": "utilities-terminal", "prompt": "format-text-bold"}
_GIT_SECTION_ICON = "vcs-commit"


def section_for_sample(sample: dict[str, str], sections: list[Section]) -> int | None:
    """Sezione di destinazione di un esempio: Git per i comandi git, poi per tipo, poi default."""
    wanted = SECTION_ICON_BY_TYPE.get(sample["type"], "")
    if sample["content"].startswith("git "):
        wanted = _GIT_SECTION_ICON
    for icon in (wanted, SECTION_ICON_BY_TYPE.get(sample["type"], "")):
        match = next((s for s in sections if s.icon == icon), None)
        if match is not None:
            return match.id
    default = next((s for s in sections if s.is_default), None)
    return default.id if default else None


def add_sample_entries(entry_repo: EntryRepository, section_repo: SectionRepository) -> int:
    """Crea le voci di esempio nella lingua corrente. Restituisce quante ne ha create."""
    sections = section_repo.get_all()
    samples = sample_entries(get_language())
    for sample in samples:
        entry_repo.create(
            EntryCreate(
                name=sample["name"],
                content=sample["content"],
                section_id=section_for_sample(sample, sections),
                type=sample["type"],
                tags=sample["tags"],
            )
        )
    return len(samples)


def _json_filters() -> Gio.ListStore:
    json_filter = Gtk.FileFilter(name="JSON")
    json_filter.add_pattern("*.json")
    filters = Gio.ListStore.new(Gtk.FileFilter)
    filters.append(json_filter)
    return filters


def export_library(
    window: Gtk.Window, entry_repo: EntryRepository, on_message: Callable[[str], None]
) -> None:
    """Chiede dove salvare e scrive tutte le voci in JSON."""
    dialog = Gtk.FileDialog(
        title=t("menu.export"), initial_name=EXPORT_FILE_NAME, filters=_json_filters()
    )

    def on_chosen(source: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            path = Path(source.save_finish(result).get_path())
        except GLib.Error:
            return  # Annullato dall'utente
        entries = entry_repo.export_all()
        try:
            path.write_text(serialize_export(entries), encoding="utf-8")
        except OSError:
            logger.exception("Export fallito: %s", path)
            on_message(t("toast.export_failed"))
            return
        on_message(t("toast.exported", count=len(entries)))

    dialog.save(window, None, on_chosen)


def import_library(
    window: Gtk.Window,
    entry_repo: EntryRepository,
    section_repo: SectionRepository,
    on_done: Callable[[str, bool], None],
) -> None:
    """Chiede un file di export e ne importa le voci. ``on_done(messaggio, cambiato)``."""
    dialog = Gtk.FileDialog(title=t("menu.import"), filters=_json_filters())

    def on_chosen(source: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            path = Path(source.open_finish(result).get_path())
        except GLib.Error:
            return
        try:
            entries = parse_import(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, InvalidExportError):
            logger.warning("Import rifiutato: %s", path, exc_info=True)
            on_done(t("toast.import_failed"), False)
            return
        count = entry_repo.import_entries(entries, section_repo=section_repo)
        on_done(t("toast.imported", count=count), count > 0)

    dialog.open(window, None, on_chosen)
