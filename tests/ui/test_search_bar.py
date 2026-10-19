"""Riga di ricerca: debounce del testo e ordinamento scelto."""

from unittest.mock import MagicMock

import pytest

from command_quiver.core.i18n import init as i18n_init
from tests.conftest import requires_display, run_loop_for, wait_until


@pytest.fixture(autouse=True)
def _italian() -> None:
    i18n_init("it")


@requires_display
class TestSearchDebounce:
    def test_typed_text_reaches_callback_trimmed(self, gtk_init) -> None:
        from command_quiver.ui.search_bar import SearchBar

        received: list[str] = []
        bar = SearchBar(sort_order="alpha_asc", on_search=received.append)

        bar.entry.set_text("  docker  ")

        assert received == []  # debounce: non subito
        assert wait_until(lambda: received != [])
        assert received == ["docker"]

    def test_consecutive_changes_collapse_into_one_search(self, gtk_init) -> None:
        from command_quiver.ui.search_bar import SearchBar

        received: list[str] = []
        bar = SearchBar(sort_order="alpha_asc", on_search=received.append)

        bar.entry.set_text("d")
        bar.entry.set_text("do")
        bar.entry.set_text("doc")

        assert wait_until(lambda: received != [])
        assert received == ["doc"]

    def test_cancel_right_after_typing_drops_the_search(self, gtk_init) -> None:
        """Regressione: annullare subito dopo un tasto non deve lasciare una ricerca in coda.

        Col ritardo interno di "search-changed" il debounce si riarmava dopo il cancel e
        la ricerca partiva su una finestra già chiusa (cambio lingua, fine test).
        """
        from command_quiver.ui.search_bar import _SEARCH_DEBOUNCE_MS, SearchBar

        received: list[str] = []
        bar = SearchBar(sort_order="alpha_asc", on_search=received.append)
        bar.entry.set_text("docker")

        bar.cancel()

        run_loop_for(bar.entry.get_search_delay() + _SEARCH_DEBOUNCE_MS + 200)
        assert received == []

    def test_search_still_works_after_a_cancel(self, gtk_init) -> None:
        from command_quiver.ui.search_bar import SearchBar

        received: list[str] = []
        bar = SearchBar(sort_order="alpha_asc", on_search=received.append)
        bar.entry.set_text("a")
        bar.cancel()
        bar.entry.set_text("b")

        assert wait_until(lambda: received != [])
        assert received == ["b"]

    def test_stop_search_clears_the_field(self, gtk_init) -> None:
        from command_quiver.ui.search_bar import SearchBar

        bar = SearchBar(sort_order="alpha_asc", on_search=MagicMock())
        bar.entry.set_text("docker")

        bar.entry.emit("stop-search")

        assert bar.entry.get_text() == ""


@requires_display
@pytest.mark.parametrize("order", ["chronological_desc", "alpha_desc", "personal", "usage"])
def test_sort_order_reflects_the_initial_choice(gtk_init, order: str) -> None:
    from command_quiver.ui.search_bar import SearchBar

    assert SearchBar(sort_order=order, on_search=MagicMock()).sort_order == order


@requires_display
def test_sort_order_follows_the_dropdown_selection(gtk_init) -> None:
    from command_quiver.ui.search_bar import SORT_VALUES, SearchBar

    bar = SearchBar(sort_order="alpha_asc", on_search=MagicMock())
    bar.sort_dropdown.set_selected(SORT_VALUES.index("usage"))

    assert bar.sort_order == "usage"
