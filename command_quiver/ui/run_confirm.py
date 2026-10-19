"""Conferma prima di lanciare un comando nel terminale, con "non chiedere più" per voce."""

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk

from command_quiver.core.i18n import t
from command_quiver.core.settings import Settings, save_settings
from command_quiver.db.queries import Entry
from command_quiver.ui.entry_list import run_entry

_MAX_PREVIEW_CHARS = 600


class RunConfirmDialog(Gtk.Window):
    """Mostra il comando esatto e chiede conferma; Invio esegue, Esc annulla.

    ``on_confirm(entry, remember)`` riceve ``remember=True`` se l'utente ha
    spuntato "Non chiedere più per questa voce".
    """

    def __init__(
        self,
        parent: Gtk.Window,
        entry: Entry,
        on_confirm: Callable[[Entry, bool], None],
    ) -> None:
        super().__init__(
            title=t("run.title"),
            transient_for=parent,
            modal=True,
            default_width=460,
            resizable=False,
        )
        self._entry = entry
        self._on_confirm = on_confirm

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(16)
        self.set_child(box)

        name = Gtk.Label(label=entry.name, xalign=0, wrap=True)
        name.add_css_class("heading")
        box.append(name)

        command = Gtk.Label(
            label=entry.content[:_MAX_PREVIEW_CHARS], xalign=0, wrap=True, selectable=True
        )
        command.add_css_class("command-preview")
        box.append(command)

        self._remember = Gtk.CheckButton(label=t("run.dont_ask"))
        box.append(self._remember)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        buttons.set_halign(Gtk.Align.END)
        cancel = Gtk.Button(label=t("common.cancel"))
        cancel.connect("clicked", lambda _: self.close())
        self._run_btn = Gtk.Button(label=t("run.run"))
        self._run_btn.add_css_class("suggested-action")
        self._run_btn.connect("clicked", lambda _: self.confirm())
        buttons.append(cancel)
        buttons.append(self._run_btn)
        box.append(buttons)

        self.set_default_widget(self._run_btn)
        # Focus su Esegui: altrimenti la label selezionabile lo prende e seleziona tutto il comando
        self.set_focus(self._run_btn)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key_pressed)
        self.add_controller(keys)

    def confirm(self) -> None:
        """Esegue la conferma e chiude."""
        self._on_confirm(self._entry, self._remember.get_active())
        self.close()

    def _on_key_pressed(
        self, _controller: Gtk.EventControllerKey, keyval: int, _keycode: int, _state
    ) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False


def request_run(
    parent: Gtk.Window,
    entry: Entry,
    settings: Settings,
    on_use: Callable[[int], None],
) -> None:
    """Esegue subito solo le voci per cui l'utente ha scelto "non chiedere più"."""
    if entry.uuid and entry.uuid in settings.skip_run_confirm:
        run_entry(entry, on_use=on_use, parent=parent)
        return

    def on_confirm(confirmed: Entry, remember: bool) -> None:
        confirm_and_run(parent, confirmed, settings, on_use, remember)

    RunConfirmDialog(parent=parent, entry=entry, on_confirm=on_confirm).present()


def confirm_and_run(
    parent: Gtk.Window,
    entry: Entry,
    settings: Settings,
    on_use: Callable[[int], None],
    remember: bool,
) -> None:
    """Esegue dopo la conferma; con ``remember`` salva la voce tra quelle senza conferma."""
    if remember and entry.uuid and entry.uuid not in settings.skip_run_confirm:
        settings.skip_run_confirm.append(entry.uuid)
        save_settings(settings)
    run_entry(entry, on_use=on_use, parent=parent)
