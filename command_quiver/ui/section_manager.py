"""Dialog per gestione sezioni: creazione, rinomina, eliminazione."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from command_quiver.core.i18n import t
from command_quiver.db.models import Section

logger = logging.getLogger(__name__)


class NameCheck(Enum):
    """Esito della validazione del nome di una sezione."""

    OK = "ok"
    EMPTY = "empty"
    UNCHANGED = "unchanged"


def validate_section_name(name: str, current: str | None = None) -> NameCheck:
    """Valuta il nome digitato per una sezione.

    I duplicati non si controllano qui: l'unicità la decide il repository (con le
    sue regole) e il messaggio torna dalla callback di conferma.

    Parameters
    ----------
    name : str
        Testo digitato, già senza spazi ai bordi.
    current : str | None
        Nome attuale in caso di rinomina, None in creazione.
    """
    if not name:
        return NameCheck.EMPTY
    if name == current:
        return NameCheck.UNCHANGED
    return NameCheck.OK


@dataclass(frozen=True)
class DialogTexts:
    """Testi (già tradotti) del dialog nome sezione."""

    title: str
    label: str
    button: str
    placeholder: str = ""


class SectionNameDialog(Gtk.Window):
    """Dialog per creare o rinominare una sezione, parametrizzato da testi e callback.

    Parameters
    ----------
    parent : Gtk.Window
        Finestra proprietaria (il dialog è modale).
    texts : DialogTexts
        Titolo, etichetta del campo, pulsante di conferma e suggerimento.
    on_confirm : Callable[[str], str | None]
        Riceve il nome valido; restituisce il messaggio d'errore o None se è andata bene.
    current : str | None
        Nome attuale (rinomina): precompila il campo e, se non cambia, chiude senza confermare.
    """

    def __init__(
        self,
        parent: Gtk.Window,
        texts: DialogTexts,
        on_confirm: Callable[[str], str | None],
        current: str | None = None,
    ) -> None:
        super().__init__(
            title=texts.title,
            transient_for=parent,
            modal=True,
            default_width=350,
            default_height=150,
        )
        self._on_confirm = on_confirm
        self._current = current
        self._build_ui(texts)

    def _build_ui(self, texts: DialogTexts) -> None:
        """Costruisce l'interfaccia del dialog."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)
        self.set_child(box)

        caption = Gtk.Label(label=texts.label, xalign=0)
        caption.add_css_class("caption")
        box.append(caption)

        self._name_entry = Gtk.Entry(placeholder_text=texts.placeholder)
        if self._current is not None:
            self._name_entry.set_text(self._current)
        self._name_entry.connect("activate", lambda _: self._do_confirm())
        box.append(self._name_entry)

        self._error_label = Gtk.Label(label="", xalign=0, visible=False)
        self._error_label.add_css_class("error-label")
        box.append(self._error_label)

        box.append(self._build_buttons(texts.button))

    def _build_buttons(self, button_label: str) -> Gtk.Box:
        """Riga con Annulla e il pulsante di conferma."""
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label=t("common.cancel"))
        cancel_btn.connect("clicked", lambda _: self.close())
        btn_box.append(cancel_btn)

        confirm_btn = Gtk.Button(label=button_label)
        confirm_btn.add_css_class("suggested-action")
        confirm_btn.connect("clicked", lambda _: self._do_confirm())
        btn_box.append(confirm_btn)
        return btn_box

    def _show_error(self, message: str) -> None:
        self._error_label.set_label(message)
        self._error_label.set_visible(True)

    def _do_confirm(self) -> None:
        """Valida il nome e lo passa alla callback; chiude solo se non ci sono errori."""
        name = self._name_entry.get_text().strip()
        check = validate_section_name(name, self._current)
        if check is NameCheck.EMPTY:
            self._show_error(t("section.error_name_required"))
            return
        if check is NameCheck.OK:
            error = self._on_confirm(name)
            if error:
                self._show_error(error)
                return
        self.close()


def create_section_dialog(
    parent: Gtk.Window, on_create: Callable[[str], str | None]
) -> SectionNameDialog:
    """Dialog di creazione sezione."""
    return SectionNameDialog(
        parent=parent,
        texts=DialogTexts(
            title=t("section.title_new"),
            label=t("section.name_label"),
            button=t("section.btn_create"),
            placeholder=t("section.name_placeholder"),
        ),
        on_confirm=on_create,
    )


def rename_section_dialog(
    parent: Gtk.Window,
    section: Section,
    on_rename: Callable[[int, str], str | None],
) -> SectionNameDialog:
    """Dialog di rinomina sezione."""
    return SectionNameDialog(
        parent=parent,
        texts=DialogTexts(
            title=t("section.title_rename"),
            label=t("section.new_name_label"),
            button=t("section.btn_rename"),
        ),
        on_confirm=lambda name: on_rename(section.id, name),
        current=section.name,
    )


def show_delete_section_dialog(
    parent: Gtk.Window,
    section: Section,
    on_confirm: Callable[[int], None],
) -> None:
    """Mostra un dialog di conferma eliminazione sezione."""
    dialog = Gtk.AlertDialog(
        message=t("section.confirm_delete_title", name=section.name),
        detail=t("section.confirm_delete_detail"),
    )
    dialog.set_buttons([t("common.cancel"), t("common.delete")])
    dialog.set_cancel_button(0)
    dialog.set_default_button(0)

    def _on_response(dialog_obj: Gtk.AlertDialog, result) -> None:
        try:
            choice = dialog_obj.choose_finish(result)
            if choice == 1:
                on_confirm(section.id)
        except GLib.Error:
            logger.debug("Dialog eliminazione sezione annullato dall'utente")

    dialog.choose(parent, None, _on_response)
