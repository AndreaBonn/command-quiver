"""Dialog modale per creazione e modifica voci."""

import logging

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk

from command_quiver.core.clipboard import copy_to_clipboard
from command_quiver.db.queries import Entry, EntryCreate, EntryUpdate, Section

logger = logging.getLogger(__name__)


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
        on_save: callable | None = None,
        on_delete: callable | None = None,
    ) -> None:
        super().__init__(
            title="Modifica voce" if entry else "Nuova voce",
            transient_for=parent,
            modal=True,
            default_width=500,
            default_height=480,
        )
        self._entry = entry
        self._sections = sections
        self._on_save = on_save
        self._on_delete = on_delete
        self._is_edit = entry is not None

        self._setup_keyboard_shortcuts()
        self._build_ui()
        self._populate_fields()

    def _setup_keyboard_shortcuts(self) -> None:
        """Configura le scorciatoie da tastiera."""
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
            if keyval == Gdk.KEY_Return:
                self._do_save_and_copy()
                return True

        return False

    def _build_ui(self) -> None:
        """Costruisce l'interfaccia del dialog."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        main_box.set_margin_top(16)
        main_box.set_margin_bottom(16)
        main_box.set_margin_start(16)
        main_box.set_margin_end(16)
        self.set_child(main_box)

        # --- Campo Nome ---
        name_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        name_label = Gtk.Label(label="Nome", xalign=0)
        name_label.add_css_class("caption")
        name_box.append(name_label)

        self._name_entry = Gtk.Entry(
            placeholder_text="Nome della voce...",
            max_length=100,
        )
        name_box.append(self._name_entry)

        self._name_error = Gtk.Label(label="", xalign=0, visible=False)
        self._name_error.add_css_class("error-label")
        name_box.append(self._name_error)
        main_box.append(name_box)

        # --- Tipo (radio button) ---
        type_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        type_label = Gtk.Label(label="Tipo:")
        type_box.append(type_label)

        self._radio_prompt = Gtk.CheckButton(label="Prompt AI")
        self._radio_shell = Gtk.CheckButton(label="Comando Shell")
        self._radio_shell.set_group(self._radio_prompt)
        self._radio_prompt.set_active(True)
        type_box.append(self._radio_prompt)
        type_box.append(self._radio_shell)
        main_box.append(type_box)

        # --- Sezione (dropdown) ---
        section_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        section_label = Gtk.Label(label="Sezione", xalign=0)
        section_label.add_css_class("caption")
        section_box.append(section_label)

        self._section_dropdown = Gtk.DropDown()
        section_names = [s.name for s in self._sections]
        self._section_dropdown.set_model(Gtk.StringList.new(section_names))
        section_box.append(self._section_dropdown)
        main_box.append(section_box)

        # --- Contenuto (text area multiriga) ---
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        content_label = Gtk.Label(label="Contenuto", xalign=0)
        content_label.add_css_class("caption")
        content_box.append(content_label)

        self._content_view = Gtk.TextView(
            vexpand=True,
            monospace=True,
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
            top_margin=8,
            bottom_margin=8,
            left_margin=8,
            right_margin=8,
        )
        self._content_view.add_css_class("content-editor")

        content_scroll = Gtk.ScrolledWindow(vexpand=True, min_content_height=150)
        content_scroll.set_child(self._content_view)
        content_scroll.add_css_class("content-scroll")
        content_box.append(content_scroll)

        self._content_error = Gtk.Label(label="", xalign=0, visible=False)
        self._content_error.add_css_class("error-label")
        content_box.append(self._content_error)
        main_box.append(content_box)

        # --- Tag ---
        tag_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        tag_label = Gtk.Label(label="Tag (separati da virgola)", xalign=0)
        tag_label.add_css_class("caption")
        tag_box.append(tag_label)

        self._tag_entry = Gtk.Entry(placeholder_text="es: git, deploy, backup")
        tag_box.append(self._tag_entry)
        main_box.append(tag_box)

        # --- Bottoni azione ---
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.END)

        # Elimina (solo in modifica, allineato a sinistra)
        if self._is_edit:
            delete_btn = Gtk.Button(label="Elimina")
            delete_btn.add_css_class("destructive-action")
            delete_btn.connect("clicked", self._on_delete_clicked)
            delete_btn.set_hexpand(True)
            delete_btn.set_halign(Gtk.Align.START)
            button_box.append(delete_btn)

        cancel_btn = Gtk.Button(label="Annulla")
        cancel_btn.connect("clicked", lambda _: self.close())
        button_box.append(cancel_btn)

        save_copy_btn = Gtk.Button(label="Salva e Copia")
        save_copy_btn.connect("clicked", lambda _: self._do_save_and_copy())
        button_box.append(save_copy_btn)

        save_btn = Gtk.Button(label="Salva")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", lambda _: self._do_save())
        button_box.append(save_btn)

        main_box.append(button_box)

    def _populate_fields(self) -> None:
        """Popola i campi con i dati della voce in modifica."""
        if self._entry is None:
            return

        self._name_entry.set_text(self._entry.name)

        if self._entry.type == "shell":
            self._radio_shell.set_active(True)
        else:
            self._radio_prompt.set_active(True)

        # Seleziona la sezione corretta nel dropdown
        for i, section in enumerate(self._sections):
            if section.id == self._entry.section_id:
                self._section_dropdown.set_selected(i)
                break

        # Popola il contenuto
        buffer = self._content_view.get_buffer()
        buffer.set_text(self._entry.content)

        # Tag
        self._tag_entry.set_text(self._entry.tags)

    def _validate(self) -> bool:
        """Valida i campi obbligatori. Restituisce True se validi."""
        is_valid = True

        # Validazione nome
        name = self._name_entry.get_text().strip()
        if not name:
            self._name_error.set_label("Il nome è obbligatorio")
            self._name_error.set_visible(True)
            self._name_entry.add_css_class("error")
            is_valid = False
        else:
            self._name_error.set_visible(False)
            self._name_entry.remove_css_class("error")

        # Validazione contenuto
        buffer = self._content_view.get_buffer()
        start, end = buffer.get_bounds()
        content = buffer.get_text(start, end, include_hidden_chars=False).strip()
        if not content:
            self._content_error.set_label("Il contenuto è obbligatorio")
            self._content_error.set_visible(True)
            self._content_view.add_css_class("error")
            is_valid = False
        else:
            self._content_error.set_visible(False)
            self._content_view.remove_css_class("error")

        return is_valid

    def _collect_data(self) -> EntryCreate | EntryUpdate:
        """Raccoglie i dati dai campi del form."""
        name = self._name_entry.get_text().strip()
        entry_type = "shell" if self._radio_shell.get_active() else "prompt"

        selected_idx = self._section_dropdown.get_selected()
        section_id = self._sections[selected_idx].id if selected_idx < len(self._sections) else None

        buffer = self._content_view.get_buffer()
        start, end = buffer.get_bounds()
        content = buffer.get_text(start, end, include_hidden_chars=False).strip()

        tags = self._tag_entry.get_text().strip()

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
            name=name,
            content=content,
            section_id=section_id,
            type=entry_type,
            tags=tags,
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

        # Copia il contenuto
        buffer = self._content_view.get_buffer()
        start, end = buffer.get_bounds()
        content = buffer.get_text(start, end, include_hidden_chars=False).strip()
        copy_to_clipboard(content)

        if self._on_save:
            self._on_save(data)
        self.close()

    def _on_delete_clicked(self, _button: Gtk.Button) -> None:
        """Richiede conferma prima di eliminare la voce."""
        dialog = Gtk.AlertDialog(
            message="Eliminare questa voce?",
            detail=f'La voce "{self._entry.name}" verrà eliminata definitivamente.',
        )
        dialog.set_buttons(["Annulla", "Elimina"])
        dialog.set_cancel_button(0)
        dialog.set_default_button(0)
        dialog.choose(self, None, self._on_delete_confirmed)

    def _on_delete_confirmed(
        self,
        dialog: Gtk.AlertDialog,
        result,
    ) -> None:
        """Callback conferma eliminazione."""
        try:
            choice = dialog.choose_finish(result)
            if choice == 1 and self._on_delete:  # "Elimina"
                self._on_delete(self._entry.id)
                self.close()
        except Exception:
            logger.exception("Errore nella conferma eliminazione")
