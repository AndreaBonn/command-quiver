"""Test dello stato di sincronizzazione: mai "OK" prima di un esito reale."""

from datetime import datetime

import pytest

from command_quiver.core import i18n
from command_quiver.core.sync_status import SyncState, describe_sync_status

NOW = datetime(2026, 10, 19, 12, 0, 0)
FIVE_MIN_AGO = "2026-10-19T11:55:00"


@pytest.fixture(autouse=True)
def _italian() -> None:
    i18n.init("it")


def _describe(**overrides):
    params = {"enabled": True, "pending": False, "outcome": None, "last_sync": "", "now": NOW}
    params.update(overrides)
    return describe_sync_status(**params)


def test_disabled_says_local_only_with_action() -> None:
    view = _describe(enabled=False, last_sync=FIVE_MIN_AGO)
    assert view.state is SyncState.LOCAL
    assert view.text == "Salvato solo su questo computer"
    assert view.action == "Sincronizza tra dispositivi"


def test_enabled_never_synced_is_not_ok() -> None:
    view = _describe()
    assert view.state is not SyncState.OK
    assert view.text == "Non ancora sincronizzato"


def test_pending_wins_over_previous_success() -> None:
    view = _describe(pending=True, last_sync=FIVE_MIN_AGO, outcome=(True, 0, 0))
    assert view.state is SyncState.PENDING


def test_success_shows_relative_time() -> None:
    view = _describe(last_sync=FIVE_MIN_AGO, outcome=(True, 0, 0))
    assert view.state is SyncState.OK
    assert view.text == "Sincronizzato 5 minuti fa"


def test_success_with_changes_shows_real_counts() -> None:
    view = _describe(last_sync=FIVE_MIN_AGO, outcome=(True, 2, 3))
    assert view.text == "Sincronizzato 5 minuti fa: 2 ricevute, 3 inviate"


def test_previous_session_sync_shown_without_outcome() -> None:
    view = _describe(last_sync=FIVE_MIN_AGO)
    assert view.state is SyncState.OK


def test_failure_offers_details() -> None:
    view = _describe(last_sync=FIVE_MIN_AGO, outcome=(False, 0, 0))
    assert view.state is SyncState.ERROR
    assert view.action == "Dettagli"


def test_disabled_while_pending_still_says_local() -> None:
    view = _describe(enabled=False, pending=True)

    assert view.state is SyncState.LOCAL


def test_enabled_never_synced_is_pending_with_never_text() -> None:
    """Mai "OK" prima di un esito reale: senza sync riuscite lo stato è in attesa."""
    view = _describe()

    assert (view.state, view.text) == (SyncState.PENDING, "Non ancora sincronizzato")


@pytest.mark.parametrize(
    ("pulled", "pushed", "expected"),
    [
        (2, 0, "Sincronizzato 5 minuti fa: 2 ricevute, 0 inviate"),
        (0, 3, "Sincronizzato 5 minuti fa: 0 ricevute, 3 inviate"),
        (0, 0, "Sincronizzato 5 minuti fa"),
    ],
    ids=["only-pulled", "only-pushed", "nothing-moved"],
)
def test_ok_shows_counts_only_when_something_moved(pulled: int, pushed: int, expected: str) -> None:
    view = _describe(outcome=(True, pulled, pushed), last_sync=FIVE_MIN_AGO)

    assert (view.state, view.text) == (SyncState.OK, expected)
