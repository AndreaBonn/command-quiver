"""Test dei widget del dialog di modifica voce."""

from unittest.mock import MagicMock

from tests.conftest import requires_display


@requires_display
class TestTypeSelector:
    def test_type_selector_defaults_to_prompt(self, gtk_init) -> None:
        from command_quiver.ui.editor_widgets import TypeSelector

        assert TypeSelector(on_changed=MagicMock()).entry_type == "prompt"

    def test_type_selector_initial_selection_does_not_notify(self, gtk_init) -> None:
        from command_quiver.ui.editor_widgets import TypeSelector

        on_changed = MagicMock()
        TypeSelector(on_changed=on_changed)

        on_changed.assert_not_called()

    def test_type_selector_setting_shell_reads_back_shell(self, gtk_init) -> None:
        from command_quiver.ui.editor_widgets import TypeSelector

        selector = TypeSelector(on_changed=MagicMock())
        selector.entry_type = "shell"

        assert selector.entry_type == "shell"

    def test_type_selector_setting_prompt_after_shell_reads_back_prompt(self, gtk_init) -> None:
        from command_quiver.ui.editor_widgets import TypeSelector

        selector = TypeSelector(on_changed=MagicMock())
        selector.entry_type = "shell"
        selector.entry_type = "prompt"

        assert selector.entry_type == "prompt"

    def test_type_selector_switch_notifies_with_the_new_type(self, gtk_init) -> None:
        from command_quiver.ui.editor_widgets import TypeSelector

        on_changed = MagicMock()
        selector = TypeSelector(on_changed=on_changed)
        selector.entry_type = "shell"

        assert on_changed.call_args_list[-1].args == ("shell",)

    def test_type_selector_shows_exactly_the_selected_card_as_pressed(self, gtk_init) -> None:
        from command_quiver.ui.editor_widgets import TypeSelector

        selector = TypeSelector(on_changed=MagicMock())
        assert (selector._prompt.get_active(), selector._shell.get_active()) == (True, False)

        selector.entry_type = "shell"
        assert (selector._prompt.get_active(), selector._shell.get_active()) == (False, True)
