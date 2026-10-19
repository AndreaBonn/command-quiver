"""Test del formato di import/export della libreria."""

import json

import pytest

from command_quiver.core.library_io import InvalidExportError, parse_import, serialize_export

ENTRY = {"name": "Log", "content": "git log", "type": "shell", "tags": "git", "section_name": "Git"}


def test_roundtrip_keeps_entries() -> None:
    assert parse_import(serialize_export([ENTRY])) == [ENTRY]


def test_serialize_has_format_header() -> None:
    data = json.loads(serialize_export([ENTRY]))
    assert data["format"] == "command-quiver-export"
    assert data["version"] == 1


def test_parse_accepts_bare_list() -> None:
    assert parse_import(json.dumps([ENTRY])) == [ENTRY]


def test_parse_skips_entries_without_name_or_content() -> None:
    text = json.dumps([ENTRY, {"name": "x"}, {"content": "y"}, "spazzatura"])
    assert parse_import(text) == [ENTRY]


@pytest.mark.parametrize(
    "text",
    [
        "non json",
        json.dumps({"format": "altro", "entries": [ENTRY]}),
        json.dumps({"qualcosa": 1}),
        json.dumps([]),
        json.dumps([{"name": "", "content": ""}]),
        json.dumps(42),
    ],
)
def test_parse_rejects_foreign_or_empty_files(text: str) -> None:
    with pytest.raises(InvalidExportError):
        parse_import(text)


@pytest.mark.parametrize("bad", [["x"], None, 5, "", "   ", {"a": 1}])
def test_parse_normalizes_invalid_section_name(bad) -> None:
    entry = {**ENTRY, "section_name": bad}
    assert parse_import(json.dumps([entry]))[0]["section_name"] == "Generale"


def test_parse_keeps_valid_section_name_trimmed() -> None:
    entry = {**ENTRY, "section_name": "  Git  "}
    assert parse_import(json.dumps([entry]))[0]["section_name"] == "Git"


def test_parse_rejects_non_string_name_or_content() -> None:
    with pytest.raises(InvalidExportError):
        parse_import(json.dumps([{"name": ["x"], "content": {"a": 1}}]))
