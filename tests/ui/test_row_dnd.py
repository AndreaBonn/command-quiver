"""Trascinamento delle righe: cosa porta la maniglia e cosa succede al rilascio."""

from tests.conftest import requires_display, wait_until


def _controller(widget, kind):
    controllers = widget.observe_controllers()
    found = [
        c
        for c in (controllers.get_item(i) for i in range(controllers.get_n_items()))
        if isinstance(c, kind)
    ]
    assert len(found) == 1
    return found[0]


@requires_display
class TestDropTarget:
    def _row(self, entry_id: int, on_reorder):
        from gi.repository import Gtk

        from command_quiver.ui.row_dnd import install_drop_target

        row = Gtk.Box()
        install_drop_target(row, entry_id, on_reorder)
        return row

    def test_drop_of_another_row_asks_reorder_with_both_ids(self, gtk_init) -> None:
        from gi.repository import Gtk

        calls: list[tuple[int, int]] = []
        row = self._row(entry_id=7, on_reorder=lambda moved, target: calls.append((moved, target)))
        target = _controller(row, Gtk.DropTarget)

        assert target.emit("drop", 3, 0.0, 0.0) is True

        # Il riordino è deferito: ricostruisce la lista, riga compresa
        assert calls == []
        assert wait_until(lambda: calls == [(3, 7)])

    def test_drop_on_itself_is_refused(self, gtk_init) -> None:
        from gi.repository import Gtk

        calls: list[tuple[int, int]] = []
        row = self._row(entry_id=7, on_reorder=lambda moved, target: calls.append((moved, target)))
        target = _controller(row, Gtk.DropTarget)

        assert target.emit("drop", 7, 0.0, 0.0) is False

        # Un secondo rilascio valido fa da sentinella: se il primo avesse accodato
        # qualcosa, comparirebbe prima di questo.
        assert target.emit("drop", 8, 0.0, 0.0) is True
        assert wait_until(lambda: calls != [])
        assert calls == [(8, 7)]


@requires_display
class TestDragHandle:
    def test_handle_drag_carries_its_entry_id(self, gtk_init) -> None:
        from unittest.mock import patch

        from gi.repository import Gdk, GObject, Gtk

        from command_quiver.ui.row_dnd import build_drag_handle

        handle = build_drag_handle(Gtk.Box(), entry_id=42)
        source = _controller(handle, Gtk.DragSource)
        offered: list[GObject.Value] = []
        real_new_for_value = Gdk.ContentProvider.new_for_value

        def capture(value: GObject.Value) -> Gdk.ContentProvider:
            offered.append(value)
            return real_new_for_value(value)

        # Il binding GI non sa rileggere il valore dal provider: si osserva al
        # boundary GTK cosa la maniglia consegna al trascinamento
        with patch.object(Gdk.ContentProvider, "new_for_value", side_effect=capture):
            provider = source.emit("prepare", 0.0, 0.0)

        assert [(v.g_type, v.get_int()) for v in offered] == [(GObject.TYPE_INT, 42)]
        assert provider is not None
