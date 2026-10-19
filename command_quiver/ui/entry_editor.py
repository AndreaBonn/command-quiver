"""Dialog modale per creazione e modifica voci."""

import logging
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk

from command_quiver.core.clipboard import copy_to_clipboard
from command_quiver.core.i18n import t
from command_quiver.core.presentation import join_tags, name_from_content, split_tags
from command_quiver.db.models import Entry, EntryCreate, EntryUpdate, Section
from command_quiver.ui.editor_widgets import (
    ContentField,
    SectionPicker,
    button_with_hint,
    caption,
    type_card,
)
from command_quiver.ui.tag_input import TagInput

logger = logging.getLogger(__name__)

_NAME_MAX_LENGTH = 100


class EntryEditorDialog(Gtk.Window):
    """Dialog per creare o modificare una voce (prompt o comando shell).

    Supporta shortcut da tastiera:
    - Ctrl+S → Salva
    - Ctrl+Enter → Salva e Copia
    - Ctrl+W / Escape → Chiudi
    """

    def __init__(
        self,
        parent: Gtk.Window,
        sections: list[Section],
        entry: Entry | None = None,
        on_save: Callable[[EntryCreate | EntryUpdate], None] | None = None,
        on_delete: Callable[[int], None] | None = None,
        initial_section_id: int | None = None,
        known_tags: list[str] | None = None,
    ) -> None:
        super().__init__(
            title=t("editor.title_edit") if entry else t("editor.title_new"),
            transient_for=parent,
            modal=True,
            default_width=520,
            default_height=600,
        )
        self._entry = entry
        self._sections = sections
        self._on_save = on_save
        self._on_delete = on_delete
        self._is_edit = entry is not None
        self._known_tags = known_tags or []

        self._setup_keyboard_shortcuts()
        self._build_ui()
        self._populate_fields(initial_section_id)

    def _setup_keyboard_shortcuts(self) -> None:
        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(controller)

    def _on_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        """Gestisce le scorciatoie da tastiera."""
        ctrl = state & Gdk.ModifierType.CONTROL_MASK
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        if ctrl:
            if keyval == Gdk.KEY_s:
                self._do_save()
                return True
            if keyval == Gdk.KEY_w:
                self.close()
                return True
            if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
                self._do_save_and_copy()
                return True
        return False

    # --- Costruzione ---

    def _build_ui(self) -> None:
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        for side in ("top", "bottom", "start", "end"):
            getattr(main_box, f"set_margin_{side}")(16)
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        scroller.set_child(main_box)
        # Pulsanti fuori dallo scroll: restano visibili anche con contenuti lunghi
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.append(scroller)
        buttons = self._build_buttons()
        for side in ("bottom", "start", "end"):
            getattr(buttons, f"set_margin_{side}")(16)
        buttons.set_margin_top(8)
        outer.append(buttons)
        self.set_child(outer)

        main_box.append(self._build_name_field())
        main_box.append(self._build_type_selector())
        main_box.append(self._build_section_field())
        main_box.append(self._build_content_field())

        tag_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        tag_box.append(caption(t("editor.tags_label")))
        self._tag_input = TagInput(known_tags=self._known_tags)
        self._tag_entry = self._tag_input.entry
        tag_box.append(self._tag_input)
        main_box.append(tag_box)

    def _build_name_field(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.append(caption(t("editor.name_label")))
        self._name_entry = Gtk.Entry(
            placeholder_text=t("editor.name_placeholder"), max_length=_NAME_MAX_LENGTH
        )
        box.append(self._name_entry)
        hint = Gtk.Label(label=t("editor.name_hint"), xalign=0, wrap=True)
        hint.add_css_class("dim-label")
        hint.add_css_class("caption")
        box.append(hint)
        return box

    def _build_type_selector(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, homogeneous=True)
        self._radio_prompt = type_card(
            t("editor.type_prompt"), t("editor.type_prompt_desc"), "edit-paste-symbolic"
        )
        self._radio_shell = type_card(
            t("editor.type_shell"), t("editor.type_shell_desc"), "utilities-terminal-symbolic"
        )
        self._radio_shell.set_group(self._radio_prompt)
        self._radio_prompt.set_active(True)
        for card in (self._radio_prompt, self._radio_shell):
            card.connect("toggled", lambda _: self._on_type_toggled())
        box.append(self._radio_prompt)
        box.append(self._radio_shell)
        return box

    def _build_section_field(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.append(caption(t("editor.section_label")))
        self._section_dropdown = SectionPicker(self._sections)
        box.append(self._section_dropdown)
        return box

    def _build_content_field(self) -> Gtk.Box:
        field = ContentField(t("editor.content_label"))
        self._content_view = field.view
        self._content_placeholder = field.placeholder
        self._content_error = field.error
        self._content_view.get_buffer().connect("changed", lambda _: self._update_placeholder())
        return field

    def _build_buttons(self) -> Gtk.Box:
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.FILL)
        spacer = Gtk.Box(hexpand=True)
        if self._is_edit:
            delete_btn = Gtk.Button(label=t("editor.btn_delete"))
            delete_btn.add_css_class("destructive-action")
            delete_btn.connect("clicked", self._on_delete_clicked)
            button_box.append(delete_btn)
        button_box.append(spacer)

        cancel_btn = Gtk.Button(label=t("editor.btn_cancel"))
        cancel_btn.connect("clicked", lambda _: self.close())
        button_box.append(cancel_btn)

        save_copy_btn = button_with_hint(t("editor.btn_save_copy"), "Ctrl+↵")
        save_copy_btn.connect("clicked", lambda _: self._do_save_and_copy())
        button_box.append(save_copy_btn)

        save_btn = button_with_hint(t("editor.btn_save"), "Ctrl+S")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", lambda _: self._do_save())
        button_box.append(save_btn)
        return button_box

    def _update_placeholder(self) -> None:
        key = self._entry_type()
        self._content_placeholder.set_label(t(f"editor.content_placeholder_{key}"))
        self._content_placeholder.set_visible(self._content_view.get_buffer().get_char_count() == 0)

    # --- Dati ---

    def _entry_type(self) -> str:
        return "shell" if self._radio_shell.get_active() else "prompt"

    def _on_type_toggled(self) -> None:
        self._update_placeholder()
        self._section_dropdown.on_type_changed(self._entry_type())

    def _populate_fields(self, initial_section_id: int | None) -> None:
        """Popola i campi: dalla voce in modifica, o con la sezione aperta per una voce nuova.

        Voce nuova da "Tutti" (nessuna sezione aperta): la sezione segue il tipo
        finché l'utente non ne sceglie una a mano.
        """
        if self._entry is None and initial_section_id is None:
            self._section_dropdown.follow_type(self._entry_type())
        else:
            self._section_dropdown.select_section(
                self._entry.section_id if self._entry else initial_section_id
            )

        if self._entry is not None:
            self._name_entry.set_text(self._entry.name)
            if self._entry.type == "shell":
                self._radio_shell.set_active(True)
            self._content_view.get_buffer().set_text(self._entry.content)
            self._tag_input.set_tags(split_tags(self._entry.tags))
        self._update_placeholder()

    def _content_text(self) -> str:
        buffer = self._content_view.get_buffer()
        start, end = buffer.get_bounds()
        return buffer.get_text(start, end, include_hidden_chars=False).strip()

    def _validate(self) -> bool:
        """Solo il contenuto è obbligatorio: il nome, se manca, si ricava dal contenuto."""
        if not self._content_text():
            self._content_error.set_label(t("editor.error_content_required"))
            self._content_error.set_visible(True)
            self._content_view.add_css_class("error")
            return False
        self._content_error.set_visible(False)
        self._content_view.remove_css_class("error")
        return True

    def _collect_data(self) -> EntryCreate | EntryUpdate:
        """Raccoglie i dati dai campi del form."""
        content = self._content_text()
        name = self._name_entry.get_text().strip() or name_from_content(content)
        entry_type = self._entry_type()
        section_id = self._section_dropdown.selected_section_id
        tags = join_tags(self._tag_input.tags)

        if self._is_edit:
            return EntryUpdate(
                id=self._entry.id,
                name=name,
                content=content,
                section_id=section_id,
                type=entry_type,
                tags=tags,
            )
        return EntryCreate(
            name=name, content=content, section_id=section_id, type=entry_type, tags=tags
        )

    def _do_save(self) -> None:
        """Salva la voce e chiude il dialog."""
        if not self._validate():
            return
        data = self._collect_data()
        if self._on_save:
            self._on_save(data)
        self.close()

    def _do_save_and_copy(self) -> None:
        """Salva, copia il contenuto negli appunti e chiude."""
        if not self._validate():
            return
        data = self._collect_data()
        copy_to_clipboard(data.content)
        if self._on_save:
            self._on_save(data)
        self.close()

    def _on_delete_clicked(self, _button: Gtk.Button | None) -> None:
        """Elimina senza conferma: la lista mostra "Eliminata · Annulla" per qualche secondo."""
        if self._on_delete and self._entry is not None:
            self._on_delete(self._entry.id)
        self.close()
