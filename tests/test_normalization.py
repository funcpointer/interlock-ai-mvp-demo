from interlock_mvp.core.plausibility import decimal_slip_notes, values_equivalent


def test_unit_equivalence_suppresses_kva_mva() -> None:
    equivalent, notes, forced = values_equivalent("150", "kVA", "0.15", "MVA")
    assert equivalent
    assert forced is None
    assert "pint_equivalence" in notes


def test_decimal_shift_detected() -> None:
    assert decimal_slip_notes("1000", "100")


def test_impedance_base_difference_forces_engineer_review() -> None:
    equivalent, notes, forced = values_equivalent(
        "5.75",
        "%",
        "5.75",
        "%",
        a_context="Impedance 5.75% on 100 MVA",
        b_context="Impedance 5.75% on 50 MVA",
    )
    assert not equivalent
    assert forced == "needs_engineer_review"
    assert notes
