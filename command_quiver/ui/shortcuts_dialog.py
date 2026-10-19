"""Finestra con l'elenco delle scorciatoie da tastiera (Ctrl+?)."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk

from command_quiver.core.i18n import t

# (combinazione mostrata, chiave della descrizione)
SHORTCUTS: tuple[tuple[str, str], ...] = (
    ("Ctrl+F", "shortcuts.search"),
    ("Ctrl+N", "shortcuts.new"),
    ("Invio / Enter", "shortcuts.copy_first"),
    ("Esc", "shortcuts.clear"),
    ("Alt+↑ / Alt+↓", "shortcuts.reorder"),
    ("Ctrl+S", "shortcuts.save"),
    ("Ctrl+Invio / Ctrl+Enter", "shortcuts.save_copy"),
    ("Ctrl+?", "shortcuts.help"),
    ("Ctrl+Q", "shortcuts.quit"),
)


class ShortcutsDialog(Gtk.Window):
    """Elenco semplice combinazione -> azione. Esc chiude."""

    def __init__(self, parent: Gtk.Window) -> None:
        super().__init__(
            title=t("shortcuts.title"), transient_for=parent, modal=True, resizable=False
        )
        grid = Gtk.Grid(column_spacing=24, row_spacing=10)
        for side in ("top", "bottom", "start", "end"):
            getattr(grid, f"set_margin_{side}")(20)
        for row, (keys, key) in enumerate(SHORTCUTS):
            combo = Gtk.Label(label=keys, xalign=1)
            combo.add_css_class("dim-label")
            combo.add_css_class("monospace")
            grid.attach(combo, 0, row, 1, 1)
            grid.attach(Gtk.Label(label=t(key), xalign=0), 1, row, 1, 1)
        self.set_child(grid)

        keys_ctrl = Gtk.EventControllerKey()
        keys_ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(keys_ctrl)

    def _on_key_pressed(self, _ctrl: Gtk.EventControllerKey, keyval: int, _code: int, _st) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False
