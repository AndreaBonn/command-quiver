"""Riordino personale delle voci per trascinamento (funzione pura, senza GTK né DB)."""


def reorder_positions(rows: list[tuple[int, int]], moved_id: int, target_id: int) -> dict[int, int]:
    """Nuove posizioni dopo aver trascinato ``moved_id`` sulla riga ``target_id``.

    La voce trascinata prende il posto della destinazione; le altre scorrono.
    Si riusano i valori di posizione delle righe visibili, così in una sezione
    filtrata l'ordine rispetto alle voci non mostrate non cambia.

    Parameters
    ----------
    rows : list[tuple[int, int]]
        Coppie (id, personal_pos) nell'ordine mostrato.
    moved_id, target_id : int
        Voce trascinata e riga su cui è stata rilasciata.

    Returns
    -------
    dict[int, int]
        Solo le voci la cui posizione cambia: id -> nuova posizione.
    """
    order = [entry_id for entry_id, _ in rows]
    if moved_id == target_id or moved_id not in order or target_id not in order:
        return {}

    target_index = order.index(target_id)
    order.remove(moved_id)
    order.insert(target_index, moved_id)

    slots = sorted(position for _, position in rows)
    if len(set(slots)) < len(slots):
        # Posizioni duplicate: lo scambio non si vedrebbe, si rendono consecutive
        slots = list(range(slots[0], slots[0] + len(slots)))

    current = dict(rows)
    new_positions = dict(zip(order, slots, strict=True))
    return {eid: pos for eid, pos in new_positions.items() if current[eid] != pos}
