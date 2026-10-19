"""Riga del pannello sezioni: icona, nome, conteggio e menu ⋯; scelta delle icone dal tema."""

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk, Pango

from command_quiver.core.i18n import t
from command_quiver.db.models import Section

ALL_ENTRIES_ICON = "view-grid-symbolic"
FALLBACK_ICON = "folder-symbolic"
# Icone salvate nel DB (nomi storici) -> candidati simbolici, il primo presente nel tema vince
_ICON_CANDIDATES: dict[str, tuple[str, ...]] = {
    "utilities-terminal": ("utilities-terminal-symbolic",),
    "format-text-bold": ("edit-paste-symbolic", "format-text-bold-symbolic"),
    "vcs-commit": ("vcs-commit-symbolic", "emblem-shared-symbolic"),
    "folder": (FALLBACK_ICON,),
}


def resolve_section_icon(icon: str, has_icon: Callable[[str], bool]) -> str:
    """Nome dell'icona simbolica da mostrare, con fallback se il tema non la contiene."""
    candidates = _ICON_CANDIDATES.get(icon, (f"{icon}-symbolic", icon))
    return next((name for name in candidates if has_icon(name)), FALLBACK_ICON)


def theme_has_icon(name: str) -> bool:
    display = Gdk.Display.get_default()
    return display is not None and Gtk.IconTheme.get_for_display(display).has_icon(name)


class SectionRow(Gtk.Box):
    """Riga nella lista sezioni: icona, nome, conteggio e (se gestibile) menu azioni."""

    def __init__(
        self,
        label: str,
        section_id: int | None,
        section: Section | None = None,
        count: int = 0,
        icon_name: str = FALLBACK_ICON,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.add_css_class("section-row")
        self.section_id = section_id
        self.section = section
        self.menu_button: Gtk.MenuButton | None = None

        self.append(Gtk.Image(icon_name=icon_name))
        name_label = Gtk.Label(label=label, xalign=0, ellipsize=Pango.EllipsizeMode.END)
        name_label.set_hexpand(True)
        self.append(name_label)
        self.count_label = Gtk.Label(label=str(count), valign=Gtk.Align.CENTER)
        self.count_label.add_css_class("section-count")
        self.append(self.count_label)

    def add_menu(self, popover: Gtk.Popover) -> None:
        """Aggiunge il pulsante ⋯ che apre il menu della sezione."""
        self.menu_button = Gtk.MenuButton(
            icon_name="view-more-symbolic",
            popover=popover,
            valign=Gtk.Align.CENTER,
            tooltip_text=t(
                "sidebar.section_actions", name=self.section.name if self.section else ""
            ),
        )
        self.menu_button.add_css_class("flat")
        self.menu_button.add_css_class("section-menu-btn")
        self.insert_child_after(self.menu_button, self.get_first_child().get_next_sibling())
