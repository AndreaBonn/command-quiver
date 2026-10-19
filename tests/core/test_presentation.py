"""Test delle funzioni pure di presentazione: tempo relativo, nome, tag, anteprima."""

from datetime import datetime

import pytest

from command_quiver.core import i18n
from command_quiver.core.presentation import (
    collect_tags,
    content_preview,
    format_relative_time,
    join_tags,
    name_from_content,
    split_tags,
)

NOW = datetime(2026, 10, 19, 12, 0, 0)


@pytest.fixture(autouse=True)
def _italian() -> None:
    i18n.init("it")


@pytest.mark.parametrize(
    ("iso", "expected"),
    [
        ("2026-10-19T11:59:30", "adesso"),
        ("2026-10-19T11:55:00", "5 minuti fa"),
        ("2026-10-19T11:59:00", "1 minuto fa"),
        ("2026-10-19T09:00:00", "3 ore fa"),
        ("2026-10-19T11:00:00", "1 ora fa"),
        ("2026-10-17T12:00:00", "2 giorni fa"),
        ("2026-10-18T12:00:00", "1 giorno fa"),
    ],
)
def test_format_relative_time_buckets(iso: str, expected: str) -> None:
    assert format_relative_time(iso=iso, now=NOW) == expected


def test_format_relative_time_old_dates_show_day() -> None:
    assert format_relative_time(iso="2026-09-01T08:12:44.123", now=NOW) == "01/09/2026"


def test_format_relative_time_invalid_returns_empty() -> None:
    assert format_relative_time(iso="non-una-data", now=NOW) == ""
    assert format_relative_time(iso="", now=NOW) == ""


def test_format_relative_time_english() -> None:
    i18n.init("en")
    assert format_relative_time(iso="2026-10-19T11:55:00", now=NOW) == "5 minutes ago"


def test_name_from_content_uses_first_non_empty_line() -> None:
    assert name_from_content("\n\n  git log --oneline -10  \nsecond") == "git log --oneline -10"


def test_name_from_content_truncates_to_max_length() -> None:
    assert name_from_content("x" * 150) == "x" * 99 + "…"


def test_name_from_content_empty_content_gives_empty_name() -> None:
    assert name_from_content("  \n ") == ""


def test_split_tags_trims_dedupes_and_drops_empty() -> None:
    assert split_tags(" git, deploy ,,Git, deploy") == ["git", "deploy"]


def test_split_tags_empty_string() -> None:
    assert split_tags("") == []


def test_join_tags_is_inverse_of_split() -> None:
    assert join_tags(["git", "deploy"]) == "git, deploy"
    assert split_tags(join_tags(["a", "b"])) == ["a", "b"]


def test_collect_tags_unique_sorted_case_insensitive() -> None:
    assert collect_tags(["git, deploy", "Backup", "", "git"]) == ["Backup", "deploy", "git"]


def test_content_preview_first_line_collapsed() -> None:
    assert (
        content_preview("  sudo apt update\nsudo apt upgrade")
        == "sudo apt update ↵ sudo apt upgrade"
    )


def test_content_preview_truncated() -> None:
    assert content_preview("a" * 200, max_length=10) == "a" * 9 + "…"


def test_collect_tags_mixed_case_uses_alphabetical_order() -> None:
    assert collect_tags(tag_strings=["Banana", "apple"]) == ["apple", "Banana"]


def test_name_from_content_exactly_100_characters_stays_whole() -> None:
    assert name_from_content(content="x" * 100) == "x" * 100


@pytest.mark.parametrize(
    ("iso", "expected"),
    [("2026-10-13T12:00:00", "6 giorni fa"), ("2026-10-12T12:00:00", "12/10/2026")],
)
def test_format_relative_time_week_boundary(iso: str, expected: str) -> None:
    assert format_relative_time(iso=iso, now=NOW) == expected


def test_content_preview_blank_lines_do_not_add_empty_segments() -> None:
    assert content_preview(content="a\n\nb") == "a ↵ b"
