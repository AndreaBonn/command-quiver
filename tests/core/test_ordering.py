"""Test del riordino personale per trascinamento (M8)."""

from command_quiver.core.ordering import reorder_positions

# (id, personal_pos) nell'ordine mostrato
ROWS = [(1, 0), (2, 1), (3, 2), (4, 3)]


def test_move_down_takes_target_place() -> None:
    # 1 trascinata su 3: ordine 2, 3, 1, 4
    assert reorder_positions(ROWS, moved_id=1, target_id=3) == {2: 0, 3: 1, 1: 2}


def test_move_up_takes_target_place() -> None:
    # 4 trascinata su 2: ordine 1, 4, 2, 3
    assert reorder_positions(ROWS, moved_id=4, target_id=2) == {4: 1, 2: 2, 3: 3}


def test_drop_on_itself_changes_nothing() -> None:
    assert reorder_positions(ROWS, moved_id=2, target_id=2) == {}


def test_unknown_ids_change_nothing() -> None:
    assert reorder_positions(ROWS, moved_id=9, target_id=2) == {}
    assert reorder_positions(ROWS, moved_id=2, target_id=9) == {}


def test_keeps_existing_position_values_of_the_visible_rows() -> None:
    # In una sezione filtrata le posizioni non partono da 0: si riusano quelle visibili
    rows = [(10, 5), (11, 9), (12, 12)]
    assert reorder_positions(rows, moved_id=12, target_id=10) == {12: 5, 10: 9, 11: 12}


def test_duplicate_positions_are_spread_so_the_move_sticks() -> None:
    rows = [(1, 0), (2, 0), (3, 0)]
    result = reorder_positions(rows, moved_id=3, target_id=1)
    final = {**dict(rows), **result}
    ordered = sorted(final.items(), key=lambda item: item[1])
    assert [entry_id for entry_id, _ in ordered] == [3, 1, 2]


def test_duplicate_positions_become_consecutive_from_the_lowest() -> None:
    """Con posizioni tutte uguali e base non zero lo scambio resta visibile."""
    rows = [(1, 5), (2, 5), (3, 5)]

    # La voce 3 prende la posizione 5, che già aveva: restituite solo quelle che cambiano
    assert reorder_positions(rows, moved_id=3, target_id=1) == {1: 6, 2: 7}
