from __future__ import annotations

import re
from dataclasses import dataclass

from pint import UnitRegistry

_UREG = UnitRegistry()

UNIT_MAP = {
    "v": "volt",
    "kv": "kilovolt",
    "a": "ampere",
    "ka": "kiloampere",
    "va": "volt_ampere",
    "kva": "kilovolt_ampere",
    "mva": "megavolt_ampere",
    "ohm": "ohm",
    "ω": "ohm",
    "uf": "microfarad",
    "μf": "microfarad",
}

TEXT_REPLACEMENTS = {
    "\u03bc": "u",
    "\u03a9": "ohm",
    "\u03c9": "ohm",
    "\u0394": "delta",
    "\u03b4": "delta",
}


@dataclass(frozen=True)
class ParsedQuantity:
    value: float
    unit: str
    kind: str
    base_mva: float | None = None


def normalize_text(text: str) -> str:
    value = text or ""
    for src, dst in TEXT_REPLACEMENTS.items():
        value = value.replace(src, dst)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_key(text: str) -> str:
    text = normalize_text(text).lower()
    text = text.replace("#", "")
    text = re.sub(r"[^a-z0-9.%]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def normalize_subject(text: str) -> str:
    text = normalize_text(text).upper()
    text = text.replace("TRANSFORMER", "XFMR")
    text = re.sub(r"\bT\s*[-# ]?\s*(\d+[A-Z]?)\b", r"XFMR-\1", text)
    text = re.sub(r"\bTX\s*[-# ]?\s*(\d+[A-Z]?)\b", r"XFMR-\1", text)
    text = re.sub(r"\bXFMR\s*[-# ]?\s*(\d+[A-Z]?)\b", r"XFMR-\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_number(raw: str) -> float:
    return float(raw.replace(",", ""))


def parse_quantity(value: str, unit: str, context: str = "") -> ParsedQuantity | None:
    unit_norm = normalize_text(unit).lower().replace(" ", "")
    value_num = parse_number(value)
    if unit_norm in {"%z", "%"}:
        base_mva = parse_base_mva(context)
        return ParsedQuantity(value=value_num, unit="%Z" if unit_norm == "%z" else "%", kind="impedance_percent" if "%z" in unit_norm or "impedance" in context.lower() else "percent", base_mva=base_mva)
    mapped = UNIT_MAP.get(unit_norm)
    if not mapped:
        return None
    return ParsedQuantity(value=value_num, unit=mapped, kind="quantity")


def parse_base_mva(context: str) -> float | None:
    match = re.search(r"\b(?:on|base|@)\s*(\d+(?:\.\d+)?)\s*(MVA|kVA)\b", context, flags=re.I)
    if not match:
        return None
    value = parse_number(match.group(1))
    unit = match.group(2).lower()
    return value if unit == "mva" else value / 1000.0


def equivalent_quantities(a_value: str, a_unit: str, b_value: str, b_unit: str) -> tuple[bool, str]:
    qa = parse_quantity(a_value, a_unit)
    qb = parse_quantity(b_value, b_unit)
    if not qa or not qb:
        return False, "quantity_parse_failed"
    if qa.kind != "quantity" or qb.kind != "quantity":
        return False, "custom_quantity_required"
    try:
        a_qty = _UREG.Quantity(qa.value, qa.unit)
        b_qty = _UREG.Quantity(qb.value, qb.unit)
        if not a_qty.check(b_qty.dimensionality):
            return False, "dimension_mismatch"
        return abs(a_qty.to_base_units().magnitude - b_qty.to_base_units().magnitude) <= 1e-9, "pint_equivalence"
    except Exception as exc:  # pragma: no cover - exact Pint errors vary
        return False, f"pint_error:{exc}"


def display_value(value: str, unit: str) -> str:
    return f"{value} {unit}".strip()
