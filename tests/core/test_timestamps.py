"""Test della normalizzazione dei timestamp salvati in formati storici diversi."""

import logging
import time
from datetime import datetime, timedelta, timezone

import pytest

from command_quiver.core.timestamps import parse_timestamp, utc_now_iso


def test_parse_timestamp_sqlite_default_format_is_read_as_utc() -> None:
    # CURRENT_TIMESTAMP di SQLite: UTC, separatore spazio, senza offset
    parsed = parse_timestamp("2026-10-10 12:00:00")

    assert parsed == datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def rome_timezone(monkeypatch: pytest.MonkeyPatch):
    # Fuso diverso da UTC: su una macchina in UTC "locale" e "UTC" coinciderebbero
    monkeypatch.setenv("TZ", "Europe/Rome")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


@pytest.mark.usefixtures("rome_timezone")
def test_parse_timestamp_naive_iso_is_read_as_local_time() -> None:
    # datetime.now().isoformat(): ora locale, separatore "T", senza offset.
    # A ottobre Roma è UTC+2
    parsed = parse_timestamp("2026-10-10T12:00:00")

    assert parsed == datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc)


def test_parse_timestamp_with_offset_keeps_the_instant() -> None:
    parsed = parse_timestamp("2026-10-10T14:00:00+02:00")

    assert parsed == datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("value", ["", None, "non è una data"], ids=["empty", "none", "garbage"])
def test_parse_timestamp_missing_or_invalid_is_older_than_any_date(value: str | None) -> None:
    parsed = parse_timestamp(value)

    assert parsed < parse_timestamp("1970-01-01 00:00:00")


def test_parse_timestamp_orders_mixed_formats_by_instant() -> None:
    """Regressione B2: a confronto di stringhe "T" vinceva sempre sullo spazio."""
    earlier_utc = "2026-10-10T11:00:00+00:00"
    later_sqlite = "2026-10-10 12:00:00"

    assert parse_timestamp(later_sqlite) > parse_timestamp(earlier_utc)


def test_utc_now_iso_is_current_utc_instant_with_offset() -> None:
    before = datetime.now(timezone.utc)

    value = utc_now_iso()

    moment = datetime.fromisoformat(value)
    assert moment.utcoffset() == timedelta(0)
    assert before <= moment <= datetime.now(timezone.utc)


def test_parse_timestamp_unparsable_value_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    """Un timestamp corrotto perde ogni confronto LWW: almeno deve restare una traccia."""
    with caplog.at_level(logging.WARNING, logger="command_quiver.core.timestamps"):
        parse_timestamp("non è una data")

    assert "non è una data" in caplog.text


@pytest.mark.parametrize("value", ["", None], ids=["empty", "none"])
def test_parse_timestamp_missing_value_is_not_logged(
    caplog: pytest.LogCaptureFixture, value: str | None
) -> None:
    """Positivo appaiato: un timestamp assente è legittimo (record storici), niente avviso."""
    with caplog.at_level(logging.WARNING, logger="command_quiver.core.timestamps"):
        parse_timestamp(value)

    assert caplog.records == []
