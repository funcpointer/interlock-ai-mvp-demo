from __future__ import annotations

import math

from .normalization import equivalent_quantities, parse_base_mva


def values_equivalent(
    a_value: str,
    a_unit: str,
    b_value: str,
    b_unit: str,
    *,
    a_context: str = "",
    b_context: str = "",
) -> tuple[bool, list[str], str | None]:
    notes: list[str] = []
    unit_a = a_unit.strip()
    unit_b = b_unit.strip()

    if unit_a.lower() in {"%z", "%"} or unit_b.lower() in {"%z", "%"}:
        base_a = parse_base_mva(a_context)
        base_b = parse_base_mva(b_context)
        if base_a != base_b and (base_a is not None or base_b is not None):
            notes.append(f"impedance base differs or is incomplete: A={base_a}, B={base_b}")
            return False, notes, "needs_engineer_review"
        equivalent = _float_close(a_value, b_value)
        if not equivalent:
            notes.extend(decimal_slip_notes(a_value, b_value))
        return equivalent, notes, None

    equivalent, reason = equivalent_quantities(a_value, unit_a, b_value, unit_b)
    notes.append(reason)
    if equivalent:
        return True, notes, None
    notes.extend(decimal_slip_notes(a_value, b_value))
    return False, notes, None


def decimal_slip_notes(a_value: str, b_value: str) -> list[str]:
    try:
        a_num = float(a_value.replace(",", ""))
        b_num = float(b_value.replace(",", ""))
    except ValueError:
        return []
    if a_num == 0 or b_num == 0:
        return []
    ratio = max(abs(a_num), abs(b_num)) / min(abs(a_num), abs(b_num))
    notes: list[str] = []
    for target in (10, 100, 1000):
        if math.isclose(ratio, target, rel_tol=0.02):
            notes.append(f"possible decimal or magnitude shift: ratio approximately {target}:1")
            break
    return notes


def _float_close(a_value: str, b_value: str) -> bool:
    try:
        return abs(float(a_value.replace(",", "")) - float(b_value.replace(",", ""))) <= 1e-9
    except ValueError:
        return a_value.strip().lower() == b_value.strip().lower()
