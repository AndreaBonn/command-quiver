"""Trascinamento delle righe nell'ordine Personale (M8): maniglia e punto di rilascio."""

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, GObject, Gtk

from command_quiver.core.i18n import t


def build_drag_handle(row: Gtk.Widget, entry_id: int) -> Gtk.Image:
    """Maniglia da cui trascinare la riga; da tastiera si usa Alt+↑/↓ sulla lista."""
    handle = Gtk.Image(
        icon_name="list-drag-handle-symbolic", tooltip_text=t("entry_list.drag_tooltip")
    )
    handle.add_css_class("drag-handle")
    handle.set_cursor(Gdk.Cursor.new_from_name("grab"))
    source = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
    source.connect(
        "prepare",
        lambda _s, _x, _y: Gdk.ContentProvider.new_for_value(
            GObject.Value(GObject.TYPE_INT, entry_id)
        ),
    )
    # L'anteprima del trascinamento è la riga intera, non solo l'icona
    source.connect("drag-begin", lambda s, _d: s.set_icon(Gtk.WidgetPaintable.new(row), 0, 0))
    handle.add_controller(source)
    return handle


def install_drop_target(
    row: Gtk.Widget, entry_id: int, on_reorder: Callable[[int, int], None]
) -> None:
    """Rilasciando una riga su questa, ``on_reorder(trascinata, destinazione)``."""

    def on_drop(_target: Gtk.DropTarget, moved_id: int, _x: float, _y: float) -> bool:
        if moved_id == entry_id:
            return False
        # Deferito: il riordino ricostruisce la lista, inclusa questa riga
        GLib.idle_add(on_reorder, moved_id, entry_id)
        return True

    target = Gtk.DropTarget.new(GObject.TYPE_INT, Gdk.DragAction.MOVE)
    target.connect("drop", on_drop)
    row.add_controller(target)
