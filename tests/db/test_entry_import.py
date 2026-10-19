from copy import deepcopy

import pytest

from command_quiver.db import entry_import
from command_quiver.db.entry_import import import_entries, normalize_import_item
from command_quiver.db.entry_repository import EntryRepository
from command_quiver.db.models import EntryCreate
from command_quiver.db.section_repository import SectionRepository


@pytest.mark.parametrize(
    "invalid_item",
    [
        {},
        {"name": "   ", "content": "text"},
        {"name": "name", "content": "   "},
        {"name": "", "content": "text"},
        {"name": "name", "content": ""},
    ],
    ids=["no-fields", "blank-name", "blank-content", "empty-name", "empty-content"],
)
def test_import_entries_invalid_item_is_skipped(
    entries: EntryRepository, sections: SectionRepository, invalid_item: dict
) -> None:
    data = [invalid_item, {"name": "valid", "content": "text"}]

    imported = import_entries(entry_repo=entries, data=data, section_repo=sections)

    assert imported == 1
    assert [row.name for row in entries.get_all()] == ["valid"]


def test_import_entries_strips_surrounding_whitespace(
    entries: EntryRepository, sections: SectionRepository
) -> None:
    data = [{"name": " shell ", "content": " echo hi "}]

    import_entries(entry_repo=entries, data=data, section_repo=sections)

    result = entries.get_all()[0]
    assert (result.name, result.content) == ("shell", "echo hi")


@pytest.mark.parametrize(
    ("given_type", "stored_type"),
    [("shell", "shell"), ("prompt", "prompt"), ("invalid", "prompt")],
    ids=["shell-kept", "prompt-kept", "invalid-falls-back-to-prompt"],
)
def test_import_entries_type_is_validated(
    entries: EntryRepository, sections: SectionRepository, given_type: str, stored_type: str
) -> None:
    data = [{"name": "name", "content": "text", "type": given_type}]

    import_entries(entry_repo=entries, data=data, section_repo=sections)

    assert entries.get_all()[0].type == stored_type


def test_import_entries_without_section_name_uses_generale(
    entries: EntryRepository, sections: SectionRepository
) -> None:
    data = [{"name": "name", "content": "text"}]

    import_entries(entry_repo=entries, data=data, section_repo=sections)

    assert entries.get_all()[0].section_name == "Generale"


def test_import_entries_same_new_section_is_created_once(
    entries: EntryRepository, sections: SectionRepository
) -> None:
    count_before = len(sections.get_all())
    data = [
        {"name": "one", "content": "text", "section_name": "Imported"},
        {"name": "two", "content": "text", "section_name": "Imported"},
    ]

    import_entries(entry_repo=entries, data=data, section_repo=sections)

    imported = next(section for section in sections.get_all() if section.name == "Imported")
    assert imported.entry_count == 2
    assert len(sections.get_all()) == count_before + 1


def test_import_entries_over_limit_imports_only_prefix(
    entries: EntryRepository,
    sections: SectionRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(entry_import, "MAX_IMPORT_ENTRIES", 2)
    data = [{"name": f"entry-{index}", "content": "text"} for index in range(3)]

    assert import_entries(entry_repo=entries, data=data, section_repo=sections) == 2

    assert [row.name for row in entries.get_all(sort_order="alpha_asc")] == ["entry-0", "entry-1"]
    assert len(data) == 3


def test_import_entries_long_fields_truncates_stored_values(
    entries: EntryRepository,
    sections: SectionRepository,
) -> None:
    limit = entry_import.MAX_FIELD_LENGTH
    data = [{"name": "n" * (limit + 1), "content": "c" * (limit + 1), "tags": "t" * (limit + 1)}]

    assert import_entries(entry_repo=entries, data=data, section_repo=sections) == 1

    result = entries.get_all()[0]
    assert (result.name, result.content, result.tags) == ("n" * limit, "c" * limit, "t" * limit)
    assert len(data[0]["name"]) == limit + 1


class TestExportImport:
    def test_import_creates_entries(
        self, entries: EntryRepository, sections: SectionRepository
    ) -> None:
        data = [
            {"name": "test1", "content": "echo test", "type": "shell", "section_name": "Git"},
            {"name": "test2", "content": "prompt text", "type": "prompt", "section_name": "Git"},
        ]

        imported = import_entries(entry_repo=entries, data=data, section_repo=sections)
        assert imported == 2
        assert entries.count_all() == 2

    def test_import_creates_missing_sections(
        self, entries: EntryRepository, sections: SectionRepository
    ) -> None:
        data = [
            {"name": "x", "content": "y", "section_name": "NewSection"},
        ]
        import_entries(entry_repo=entries, data=data, section_repo=sections)

        all_sections = sections.get_all()
        names = [s.name for s in all_sections]
        assert "NewSection" in names

    def test_import_skips_invalid_entries(
        self, entries: EntryRepository, sections: SectionRepository
    ) -> None:
        data = [
            {"name": "", "content": "no name"},
            {"name": "no content", "content": ""},
            {"name": "valid", "content": "ok"},
        ]
        imported = import_entries(entry_repo=entries, data=data, section_repo=sections)
        assert imported == 1

    def test_export_import_roundtrip(
        self, entries: EntryRepository, sections: SectionRepository
    ) -> None:
        shell_id = sections.get_all()[0].id
        entries.create(
            EntryCreate(
                name="roundtrip",
                content="echo hello",
                section_id=shell_id,
                type="shell",
                tags="test,rt",
            )
        )

        exported = entries.export_all()
        assert len(exported) == 1

        # Pulisci e reimporta
        entries.delete(entries.get_all()[0].id)
        assert entries.count_all() == 0

        imported = import_entries(entry_repo=entries, data=exported, section_repo=sections)
        assert imported == 1

        result = entries.get_all()
        assert result[0].name == "roundtrip"
        assert result[0].tags == "test,rt"


def test_normalize_import_item_preserves_input_and_normalizes_fields() -> None:
    item = {"name": "  title  ", "content": " text \n", "tags": 42, "section_name": "Work"}
    original = deepcopy(item)

    result = normalize_import_item(item=item)

    assert result == {
        "name": "title",
        "content": "text",
        "type": "prompt",
        "tags": "42",
        "section_name": "Work",
    }
    assert item == original


@pytest.mark.parametrize("entry_type", ["shell", "prompt", "invalid", None, 42])
def test_normalize_import_item_validates_type(entry_type: object) -> None:
    result = normalize_import_item(item={"name": 12, "content": 34, "type": entry_type})

    assert result == {
        "name": "12",
        "content": "34",
        "type": entry_type if entry_type in ("shell", "prompt") else "prompt",
        "tags": "",
        "section_name": "Generale",
    }


@pytest.mark.parametrize("item", [{}, {"name": " ", "content": "ok"}, {"name": "ok"}])
def test_normalize_import_item_rejects_missing_text_and_accepts_complete_item(item: dict) -> None:
    assert normalize_import_item(item=item) is None
    assert normalize_import_item(item={"name": "n", "content": "c"}) == {
        "name": "n",
        "content": "c",
        "type": "prompt",
        "tags": "",
        "section_name": "Generale",
    }


def test_normalize_import_item_truncates_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entry_import, "MAX_FIELD_LENGTH", 3)

    result = normalize_import_item(item={"name": " abcd ", "content": " efgh ", "tags": " ijkl "})

    assert result == {
        "name": "abc",
        "content": "efg",
        "type": "prompt",
        "tags": " ij",
        "section_name": "Generale",
    }
