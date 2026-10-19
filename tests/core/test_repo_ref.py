"""Test parsing del riferimento al repository GitHub (campo unico owner/repo)."""

import pytest

from command_quiver.core.repo_ref import format_repo_ref, parse_repo_ref


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("mrossi/command-quiver-sync", ("mrossi", "command-quiver-sync")),
        ("  mrossi/vault  ", ("mrossi", "vault")),
        ("https://github.com/mrossi/vault", ("mrossi", "vault")),
        ("https://github.com/mrossi/vault.git", ("mrossi", "vault")),
        ("https://github.com/mrossi/vault/tree/main", ("mrossi", "vault")),
        ("github.com/mrossi/vault/", ("mrossi", "vault")),
        ("git@github.com:mrossi/vault.git", ("mrossi", "vault")),
    ],
)
def test_parse_repo_ref_accepts_common_forms(text: str, expected: tuple[str, str]) -> None:
    assert parse_repo_ref(text) == expected


@pytest.mark.parametrize(
    "text",
    ["", "   ", "mrossi", "/vault", "mrossi/", "https://gitlab.com/mrossi/vault", "a b/c"],
)
def test_parse_repo_ref_rejects_incomplete_or_foreign(text: str) -> None:
    assert parse_repo_ref(text) is None


def test_format_repo_ref_joins_owner_and_name() -> None:
    assert format_repo_ref(owner="mrossi", name="vault") == "mrossi/vault"


def test_format_repo_ref_empty_when_not_configured() -> None:
    assert format_repo_ref(owner="", name="") == ""
