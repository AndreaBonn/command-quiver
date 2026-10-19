"""entry_payload: nome dedotto e scelta fra creazione e modifica, senza finestra."""

from command_quiver.db.models import EntryCreate, EntryUpdate


class TestEntryPayload:
    """entry_payload è pura: decide nome e tipo di salvataggio senza finestra."""

    def test_entry_payload_blank_name_takes_first_content_line(self) -> None:
        from command_quiver.ui.editor_request import entry_payload

        draft = EntryCreate(name="   ", content="ls -la /tmp\nsecond", section_id=2)

        assert entry_payload(draft=draft, entry_id=None).name == "ls -la /tmp"

    def test_entry_payload_written_name_wins_over_content(self) -> None:
        from command_quiver.ui.editor_request import entry_payload

        draft = EntryCreate(name=" Elenco tmp ", content="ls -la /tmp")

        assert entry_payload(draft=draft, entry_id=None).name == "Elenco tmp"

    def test_entry_payload_new_entry_is_a_create_with_all_fields(self) -> None:
        from command_quiver.ui.editor_request import entry_payload

        draft = EntryCreate(
            name="Build", content="make", section_id=3, type="shell", tags="ci,make"
        )

        assert entry_payload(draft=draft, entry_id=None) == EntryCreate(
            name="Build", content="make", section_id=3, type="shell", tags="ci,make"
        )

    def test_entry_payload_edited_entry_is_an_update_of_that_id(self) -> None:
        from command_quiver.ui.editor_request import entry_payload

        draft = EntryCreate(
            name="Build", content="make", section_id=3, type="shell", tags="ci,make"
        )

        assert entry_payload(draft=draft, entry_id=7) == EntryUpdate(
            id=7, name="Build", content="make", section_id=3, type="shell", tags="ci,make"
        )
