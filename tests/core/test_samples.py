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


@pytest.mark.parametrize("language", ["it", "en"])
def test_sample_entries_shell_commands_are_read_only(language: str) -> None:
    # Gli esempi si possono eseguire con un clic: niente sudo né comandi distruttivi.
    forbidden = ("sudo", "rm ", "reset", "--force", ">")
    for sample in sample_entries(language):
        if sample["type"] == "shell":
            assert not any(word in sample["content"] for word in forbidden)


def test_sample_entries_unknown_language_falls_back_to_italian() -> None:
    assert sample_entries("xx") == sample_entries("it")


def test_sample_entries_english_are_in_english() -> None:
    names = [sample["name"] for sample in sample_entries("en")]

    assert "Free disk space" in names


def test_sample_entries_returns_independent_copies() -> None:
    """Modificare una voce restituita non deve cambiare gli esempi della chiamata successiva."""
    first = sample_entries("it")
    first[0]["name"] = "modificata"

    assert sample_entries("it")[0]["name"] != "modificata"
