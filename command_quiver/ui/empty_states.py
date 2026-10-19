"""Stati vuoti della lista: primo avvio, sezione vuota, ricerca senza risultati."""

from collections.abc import Callable
from dataclasses import dataclass

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from command_quiver.core.i18n import t

_MARGIN = 24


@dataclass
class EmptyContext:
    """Cosa sta guardando l'utente quando la lista è vuota."""

    library_empty: bool
    query: str = ""
    section_name: str | None = None  # None = "Tutti"


@dataclass
class EmptyActions:
    """Azioni offerte dagli stati vuoti."""

    on_create: Callable[[], None]
    on_add_samples: Callable[[], None]
    on_search_all: Callable[[], None]
    on_clear_search: Callable[[], None]


def build_empty_state(context: EmptyContext, actions: EmptyActions) -> Gtk.Widget:
    """Sceglie lo stato vuoto adatto: ricerca, primo avvio o sezione vuota."""
    if context.query:
        return _search_empty(context, actions)
    if context.library_empty:
        return _welcome(actions)
    return _section_empty(context.section_name or t("sidebar.all_entries"), actions)


def _button(label: str, callback: Callable[[], None], suggested: bool = False) -> Gtk.Button:
    button = Gtk.Button(label=label)
    if suggested:
        button.add_css_class("suggested-action")
    button.connect("clicked", lambda _: callback())
    return button


def _centered_box() -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, valign=Gtk.Align.CENTER)
    for side in ("top", "bottom", "start", "end"):
        getattr(box, f"set_margin_{side}")(_MARGIN)
    return box


def _welcome(actions: EmptyActions) -> Gtk.Widget:
    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    card.add_css_class("welcome-card")
    title = Gtk.Label(label=t("empty.welcome_title"), xalign=0, wrap=True)
    title.add_css_class("welcome-title")
    card.append(title)
    for key in ("empty.welcome_prompt", "empty.welcome_shell", "empty.welcome_sections"):
        card.append(Gtk.Label(label=f"• {t(key)}", xalign=0, wrap=True))

    buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    buttons.append(_button(t("empty.create_first"), actions.on_create, suggested=True))
    buttons.append(_button(t("empty.add_samples"), actions.on_add_samples))
    card.append(buttons)
    note = Gtk.Label(label=t("empty.samples_note"), xalign=0, wrap=True)
    note.add_css_class("dim-label")
    note.add_css_class("caption")
    card.append(note)

    box = _centered_box()
    box.set_valign(Gtk.Align.START)
    box.append(card)
    return box


def _section_empty(section_name: str, actions: EmptyActions) -> Gtk.Widget:
    box = _centered_box()
    title = Gtk.Label(label=t("empty.section_title", section=section_name), wrap=True)
    title.add_css_class("empty-title")
    box.append(title)
    hint = Gtk.Label(label=t("empty.section_hint"), wrap=True, justify=Gtk.Justification.CENTER)
    hint.add_css_class("dim-label")
    box.append(hint)
    add = _button(t("empty.section_add", section=section_name), actions.on_create, True)
    add.set_halign(Gtk.Align.CENTER)
    box.append(add)
    return box


def _search_empty(context: EmptyContext, actions: EmptyActions) -> Gtk.Widget:
    box = _centered_box()
    if context.section_name:
        text = t("empty.search_title_in", query=context.query, section=context.section_name)
    else:
        text = t("empty.search_title", query=context.query)
    title = Gtk.Label(label=text, wrap=True, justify=Gtk.Justification.CENTER)
    title.add_css_class("empty-title")
    box.append(title)

    buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.CENTER)
    if context.section_name:
        hint = Gtk.Label(label=t("empty.search_hint_section"), wrap=True)
        hint.add_css_class("dim-label")
        box.append(hint)
        buttons.append(_button(t("empty.search_all"), actions.on_search_all, suggested=True))
    buttons.append(_button(t("empty.search_clear"), actions.on_clear_search))
    box.append(buttons)
    return box
