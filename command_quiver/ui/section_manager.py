"""Dialog per gestione sezioni: creazione, rinomina, eliminazione."""

import logging
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from command_quiver.core.i18n import t
from command_quiver.db.queries import Section

logger = logging.getLogger(__name__)


class SectionCreateDialog(Gtk.Window):
    """Dialog per creare una nuova sezione."""

    def __init__(
        self,
        parent: Gtk.Window,
        on_create: Callable,
    ) -> None:
        super().__init__(
            title=t("section.title_new"),
            transient_for=parent,
            modal=True,
            default_width=350,
            default_height=150,
        )
        self._on_create = on_create
        self._build_ui()

    def _build_ui(self) -> None:
        """Costruisce l'interfaccia del dialog."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)
        self.set_child(box)

        # Campo nome
        label = Gtk.Label(label=t("section.name_label"), xalign=0)
        label.add_css_class("caption")
        box.append(label)

        self._name_entry = Gtk.Entry(placeholder_text=t("section.name_placeholder"))
        self._name_entry.connect("activate", lambda _: self._do_create())
        box.append(self._name_entry)

        self._error_label = Gtk.Label(label="", xalign=0, visible=False)
        self._error_label.add_css_class("error-label")
        box.append(self._error_label)

        # Bottoni
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label=t("common.cancel"))
        cancel_btn.connect("clicked", lambda _: self.close())
        btn_box.append(cancel_btn)

        create_btn = Gtk.Button(label=t("section.btn_create"))
        create_btn.add_css_class("suggested-action")
        create_btn.connect("clicked", lambda _: self._do_create())
        btn_box.append(create_btn)

        box.append(btn_box)

    def _do_create(self) -> None:
        """Valida e crea la sezione."""
        name = self._name_entry.get_text().strip()
        if not name:
            self._error_label.set_label(t("section.error_name_required"))
            self._error_label.set_visible(True)
            return

        self._on_create(name)
        self.close()


class SectionRenameDialog(Gtk.Window):
    """Dialog per rinominare una sezione esistente."""

    def __init__(
        self,
        parent: Gtk.Window,
        section: Section,
        on_rename: Callable,
    ) -> None:
        super().__init__(
            title=t("section.title_rename"),
            transient_for=parent,
            modal=True,
            default_width=350,
            default_height=150,
        )
        self._section = section
        self._on_rename = on_rename
        self._build_ui()

    def _build_ui(self) -> None:
        """Costruisce l'interfaccia del dialog."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)
        self.set_child(box)

        label = Gtk.Label(label=t("section.new_name_label"), xalign=0)
        label.add_css_class("caption")
        box.append(label)

        self._name_entry = Gtk.Entry()
        self._name_entry.set_text(self._section.name)
        self._name_entry.connect("activate", lambda _: self._do_rename())
        box.append(self._name_entry)

        self._error_label = Gtk.Label(label="", xalign=0, visible=False)
        self._error_label.add_css_class("error-label")
        box.append(self._error_label)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label=t("common.cancel"))
        cancel_btn.connect("clicked", lambda _: self.close())
        btn_box.append(cancel_btn)

        rename_btn = Gtk.Button(label=t("section.btn_rename"))
        rename_btn.add_css_class("suggested-action")
        rename_btn.connect("clicked", lambda _: self._do_rename())
        btn_box.append(rename_btn)

        box.append(btn_box)

    def _do_rename(self) -> None:
        """Valida e rinomina la sezione."""
        new_name = self._name_entry.get_text().strip()
        if not new_name:
            self._error_label.set_label(t("section.error_name_required"))
            self._error_label.set_visible(True)
            return
        if new_name != self._section.name:
            self._on_rename(self._section.id, new_name)
        self.close()


def show_delete_section_dialog(
    parent: Gtk.Window,
    section: Section,
    on_confirm: Callable,
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
