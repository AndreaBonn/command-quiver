"""Stati vuoti della lista: cosa legge l'utente e quali azioni gli vengono offerte."""

from unittest.mock import MagicMock, call

import pytest

from command_quiver.core.i18n import init as i18n_init
from tests.conftest import button_labelled, descendants, requires_display


@pytest.fixture(autouse=True)
def _italian() -> None:
    i18n_init("it")


def _actions() -> dict[str, MagicMock]:
    return {
        name: MagicMock()
        for name in ("on_create", "on_add_samples", "on_search_all", "on_clear_search")
    }


def _build(**context):
    from command_quiver.ui.empty_states import EmptyActions, EmptyContext, build_empty_state

    actions = _actions()
    return build_empty_state(EmptyContext(**context), EmptyActions(**actions)), actions


def _texts(widget) -> list[str]:
    from gi.repository import Gtk

    return [w.get_label() for w in descendants(widget) if isinstance(w, Gtk.Label)]


def _button_labels(widget) -> list[str]:
    from gi.repository import Gtk

    return [w.get_label() for w in descendants(widget) if isinstance(w, Gtk.Button)]


@requires_display
class TestSearchEmpty:
    def test_query_takes_priority_over_empty_library(self, gtk_init) -> None:
        widget, _actions = _build(library_empty=True, query="zzz")

        assert "Nessun risultato per «zzz»" in _texts(widget)
        assert _button_labels(widget) == ["Cancella ricerca"]

    def test_search_in_all_sections_echoes_query_and_offers_only_clear(self, gtk_init) -> None:
        widget, actions = _build(library_empty=False, query="zzz", section_name=None)

        assert "Nessun risultato per «zzz»" in _texts(widget)
        assert _button_labels(widget) == ["Cancella ricerca"]
        button_labelled(widget, "Cancella ricerca").emit("clicked")
        actions["on_clear_search"].assert_called_once_with()

    def test_search_in_a_section_names_it_and_offers_to_widen(self, gtk_init) -> None:
        widget, actions = _build(library_empty=False, query="zzz", section_name="Git")

        assert "Nessun risultato per «zzz» in Git" in _texts(widget)
        assert "La ricerca guarda solo nella sezione selezionata." in _texts(widget)
        assert _button_labels(widget) == ["Cerca in tutte le sezioni", "Cancella ricerca"]
        button_labelled(widget, "Cerca in tutte le sezioni").emit("clicked")
        actions["on_search_all"].assert_called_once_with()


@requires_display
class TestWelcomeActions:
    @pytest.mark.parametrize(
        ("label", "callback"),
        [("Crea la prima voce", "on_create"), ("Prova con 6 esempi", "on_add_samples")],
    )
    def test_welcome_button_calls_matching_action(self, gtk_init, label, callback) -> None:
        widget, actions = _build(library_empty=True)

        button_labelled(widget, label).emit("clicked")

        assert {name: action.call_args_list for name, action in actions.items()} == {
            name: [call()] if name == callback else [] for name in actions
        }
