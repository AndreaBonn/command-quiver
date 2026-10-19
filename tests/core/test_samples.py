"""Test delle voci di esempio per il primo avvio."""

import pytest

from command_quiver.core.samples import sample_entries


@pytest.mark.parametrize("language", ["it", "en"])
def test_sample_entries_three_shell_three_prompt(language: str) -> None:
    samples = sample_entries(language)
    assert len(samples) == 6
    assert sum(1 for s in samples if s["type"] == "shell") == 3
    assert sum(1 for s in samples if s["type"] == "prompt") == 3


@pytest.mark.parametrize("language", ["it", "en"])
def test_sample_entries_are_complete(language: str) -> None:
    for sample in sample_entries(language):
        assert sample["name"].strip()
        assert sample["content"].strip()


def test_sample_entries_shell_commands_are_read_only() -> None:
    # Gli esempi si possono eseguire con un clic: niente sudo né comandi distruttivi.
    forbidden = ("sudo", "rm ", "reset", "--force", ">")
    for sample in sample_entries("it"):
        if sample["type"] == "shell":
            assert not any(word in sample["content"] for word in forbidden)


def test_sample_entries_unknown_language_falls_back_to_italian() -> None:
    assert sample_entries("xx") == sample_entries("it")
