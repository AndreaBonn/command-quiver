"""Campo tag: la virgola conferma l'etichetta, il testo non confermato non si perde."""

from tests.conftest import requires_display


@requires_display
class TestTagInput:
    def test_typing_a_comma_turns_the_text_into_a_tag(self, gtk_init) -> None:
        from command_quiver.ui.tag_input import TagInput

        tag_input = TagInput()

        tag_input.entry.set_text("git,")

        assert tag_input.tags == ["git"]
        assert tag_input.entry.get_text() == ""

    def test_text_without_comma_stays_pending_but_is_still_returned(self, gtk_init) -> None:
        from command_quiver.ui.tag_input import TagInput

        tag_input = TagInput()

        tag_input.entry.set_text("git")

        assert tag_input.entry.get_text() == "git"
        assert tag_input.tags == ["git"]

    def test_clicking_a_suggestion_adds_it_once(self, gtk_init) -> None:
        from command_quiver.ui.tag_input import TagInput
        from tests.conftest import button_labelled

        tag_input = TagInput(known_tags=["docker", "git"])

        button_labelled(tag_input, "docker").emit("clicked")

        assert tag_input.tags == ["docker"]
        # Una volta scelto, non è più proposto
        assert _suggestion_labels(tag_input) == ["git"]


def _suggestion_labels(tag_input) -> list[str]:
    from gi.repository import Gtk

    from tests.conftest import descendants

    return [w.get_label() for w in descendants(tag_input._suggestions) if isinstance(w, Gtk.Button)]
