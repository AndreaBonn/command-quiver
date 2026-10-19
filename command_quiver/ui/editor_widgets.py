"""Widget riusati dalla finestra di modifica voce."""

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from command_quiver.core.i18n import t
from command_quiver.db.models import Section
from command_quiver.ui.library_actions import SECTION_ICON_BY_TYPE


def caption(text: str) -> Gtk.Label:
    label = Gtk.Label(label=text, xalign=0)
    label.add_css_class("caption")
    return label


def type_card(title: str, description: str, icon: str) -> Gtk.ToggleButton:
    """Scelta del tipo come scheda: titolo e cosa succede con quel tipo."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    head.append(Gtk.Image(icon_name=icon))
    heading = Gtk.Label(label=title, xalign=0)
    heading.add_css_class("heading")
    head.append(heading)
    box.append(head)
    desc = Gtk.Label(label=description, xalign=0, wrap=True)
    desc.add_css_class("type-desc")
    box.append(desc)
    button = Gtk.ToggleButton(hexpand=True)
    button.set_child(box)
    button.add_css_class("type-card")
    return button


def button_with_hint(label: str, hint: str) -> Gtk.Button:
    """Pulsante con la scorciatoia scritta accanto all'etichetta."""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    box.append(Gtk.Label(label=label))
    hint_label = Gtk.Label(label=hint)
    hint_label.add_css_class("kbd-hint")
    box.append(hint_label)
    button = Gtk.Button(tooltip_text=f"{label} ({hint})")
    button.set_child(box)
    return button


class TypeSelector(Gtk.Box):
    """Scelta del tipo voce con due schede esclusive: prompt o comando shell."""

    def __init__(self, on_changed: Callable[[str], None]) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, homogeneous=True)
        self._prompt = type_card(
            t("editor.type_prompt"), t("editor.type_prompt_desc"), "edit-paste-symbolic"
        )
        self._shell = type_card(
            t("editor.type_shell"), t("editor.type_shell_desc"), "utilities-terminal-symbolic"
        )
        self._shell.set_group(self._prompt)
        self._prompt.set_active(True)
        # Collegato dopo l'attivazione iniziale: la scelta di partenza non è un cambio
        for card in (self._prompt, self._shell):
            card.connect("toggled", lambda _: on_changed(self.entry_type))
        self.append(self._prompt)
        self.append(self._shell)

    @property
    def entry_type(self) -> str:
        """Tipo selezionato: "shell" oppure "prompt"."""
        return "shell" if self._shell.get_active() else "prompt"

    @entry_type.setter
    def entry_type(self, value: str) -> None:
        (self._shell if value == "shell" else self._prompt).set_active(True)


class SectionPicker(Gtk.DropDown):
    """Menu a tendina delle sezioni che, se richiesto, segue il tipo della voce.

    Per una voce nuova creata da "Tutti" la sezione proposta segue il tipo
    (prompt -> sezione dei prompt, comando -> sezione dei comandi) finché
    l'utente non ne sceglie una a mano.
    """

    def __init__(self, sections: list[Section]) -> None:
        super().__init__()
        self._sections = sections
        self._follows_type = False
        self._programmatic = False
        self.set_model(Gtk.StringList.new([s.name for s in sections]))
        self.connect("notify::selected", self._on_selected)

    @property
    def selected_section_id(self) -> int | None:
        index = self.get_selected()
        return self._sections[index].id if index < len(self._sections) else None

    def select_section(self, section_id: int | None) -> None:
        """Selezione dal codice: non conta come scelta dell'utente."""
        for i, section in enumerate(self._sections):
            if section.id == section_id:
                self._programmatic = True
                self.set_selected(i)
                self._programmatic = False
                return

    def follow_type(self, entry_type: str) -> None:
        """Attiva l'aggancio al tipo e seleziona la sezione corrispondente."""
        self._follows_type = True
        self.on_type_changed(entry_type)

    def on_type_changed(self, entry_type: str) -> None:
        if not self._follows_type:
            return
        icon = SECTION_ICON_BY_TYPE.get(entry_type)
        match = next((s for s in self._sections if s.icon == icon), None)
        if match is not None:
            self.select_section(match.id)

    def _on_selected(self, _dropdown: Gtk.DropDown, _pspec) -> None:
        if not self._programmatic:
            self._follows_type = False


class ContentField(Gtk.Box):
    """Etichetta, area di testo monospazio con segnaposto, e riga d'errore."""

    def __init__(self, label: str) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.append(caption(label))
        self.view = Gtk.TextView(
            vexpand=True,
            monospace=True,
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
            top_margin=8,
            bottom_margin=8,
            left_margin=8,
            right_margin=8,
        )
        self.view.add_css_class("content-editor")

        # GtkTextView non ha placeholder: etichetta sovrapposta, visibile a campo vuoto
        self.placeholder = Gtk.Label(
            xalign=0, yalign=0, wrap=True, can_target=False, margin_top=8, margin_start=10
        )
        self.placeholder.add_css_class("dim-label")
        self.placeholder.add_css_class("content-editor")
        self.placeholder.set_halign(Gtk.Align.START)
        self.placeholder.set_valign(Gtk.Align.START)
        # La TextView resta figlia diretta dello scroll (riempie il riquadro e riceve i clic);
        # il segnaposto sta sopra allo scroll, non dentro
        scroll = Gtk.ScrolledWindow(vexpand=True, min_content_height=150)
        scroll.set_child(self.view)
        scroll.add_css_class("content-scroll")
        overlay = Gtk.Overlay(vexpand=True)
        overlay.set_child(scroll)
        overlay.add_overlay(self.placeholder)
        self.append(overlay)

        self.error = Gtk.Label(label="", xalign=0, visible=False)
        self.error.add_css_class("error-label")
        self.append(self.error)
