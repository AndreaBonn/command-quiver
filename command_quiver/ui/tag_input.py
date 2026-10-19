"""Campo tag a etichette: Invio o virgola aggiunge, x rimuove, i tag già usati sono proposti."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Pango

from command_quiver.core.i18n import t
from command_quiver.core.presentation import split_tags

_MAX_SUGGESTIONS = 8


class TagInput(Gtk.Box):
    """Etichette + campo di testo + suggerimenti cliccabili.

    ``tags`` comprende anche il testo non ancora confermato con Invio, così
    chi salva senza premere Invio non perde l'ultimo tag scritto.
    """

    def __init__(self, known_tags: list[str] | None = None) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._tags: list[str] = []
        self._known = known_tags or []

        self._chips = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=8)
        self._chips.set_visible(False)
        self.append(self._chips)

        self._tag_entry = Gtk.Entry(placeholder_text=t("editor.tags_placeholder"))
        self._tag_entry.connect("activate", lambda _: self.commit_pending())
        self._tag_entry.connect("changed", self._on_changed)
        self.append(self._tag_entry)

        self._suggestions = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=_MAX_SUGGESTIONS + 1
        )
        self.append(self._suggestions)
        self._render_suggestions()

    @property
    def entry(self) -> Gtk.Entry:
        """Campo di testo interno (per focus e test)."""
        return self._tag_entry

    @property
    def tags(self) -> list[str]:
        """Tag confermati più quelli scritti e non ancora confermati."""
        pending = split_tags(self._tag_entry.get_text())
        return split_tags(",".join(self._tags + pending))

    def set_tags(self, tags: list[str]) -> None:
        """Sostituisce i tag mostrati."""
        self._tags = split_tags(",".join(tags))
        self._render_chips()
        self._render_suggestions()

    def add_tag(self, tag: str) -> None:
        """Aggiunge un tag, ignorando duplicati senza distinzione di maiuscole."""
        self.set_tags([*self._tags, tag])

    def remove_tag(self, tag: str) -> None:
        self.set_tags([existing for existing in self._tags if existing != tag])

    def commit_pending(self) -> None:
        """Trasforma il testo scritto in etichette."""
        pending = split_tags(self._tag_entry.get_text())
        self._tag_entry.set_text("")
        if pending:
            self.set_tags([*self._tags, *pending])

    def _on_changed(self, entry: Gtk.Entry) -> None:
        if entry.get_text().endswith(","):
            self.commit_pending()

    def _render_chips(self) -> None:
        self._chips.remove_all()
        for tag in self._tags:
            chip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
            chip.add_css_class("tag-chip")
            chip.append(Gtk.Label(label=tag, ellipsize=Pango.EllipsizeMode.END))
            remove = Gtk.Button(
                icon_name="window-close-symbolic", tooltip_text=t("editor.tag_remove", tag=tag)
            )
            remove.add_css_class("flat")
            remove.connect("clicked", lambda _b, value=tag: self.remove_tag(value))
            chip.append(remove)
            self._chips.append(chip)
        self._chips.set_visible(bool(self._tags))

    def _render_suggestions(self) -> None:
        self._suggestions.remove_all()
        current = {tag.casefold() for tag in self._tags}
        available = [tag for tag in self._known if tag.casefold() not in current]
        if not available:
            self._suggestions.set_visible(False)
            return
        label = Gtk.Label(label=t("editor.tags_used"))
        label.add_css_class("dim-label")
        label.add_css_class("caption")
        self._suggestions.append(label)
        for tag in available[:_MAX_SUGGESTIONS]:
            button = Gtk.Button(label=tag)
            button.add_css_class("flat")
            button.add_css_class("tag-suggestion")
            button.connect("clicked", lambda _b, value=tag: self.add_tag(value))
            self._suggestions.append(button)
        self._suggestions.set_visible(True)
