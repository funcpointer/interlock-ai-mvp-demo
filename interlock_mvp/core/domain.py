from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .normalization import normalize_key


@dataclass(frozen=True)
class EquipmentTerm:
    kind: str
    aliases: tuple[str, ...] = ()
    tag_prefixes: tuple[str, ...] = ()
    part_families: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParameterTerm:
    name: str
    aliases: tuple[str, ...] = ()
    units: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContextTerm:
    name: str
    kind: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class DomainDictionary:
    schema_version: str = "interlock_mvp.glossary.v1"
    aliases: dict[str, tuple[str, ...]] = field(default_factory=dict)
    equipment: dict[str, EquipmentTerm] = field(default_factory=dict)
    parameters: dict[str, ParameterTerm] = field(default_factory=dict)
    contexts: dict[str, ContextTerm] = field(default_factory=dict)
    references: tuple[str, ...] = ()

    @classmethod
    def empty(cls) -> "DomainDictionary":
        return cls()

    @classmethod
    def from_yaml(cls, path: Path | None) -> "DomainDictionary":
        if not path or not path.exists():
            return cls.empty()
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls.from_mapping(payload)

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "DomainDictionary":
        aliases = {
            str(key): tuple(str(value) for value in values or [])
            for key, values in (payload.get("aliases") or {}).items()
        }
        equipment = {
            str(name): EquipmentTerm(
                kind=str(record.get("kind") or name),
                aliases=_tuple(record.get("aliases")),
                tag_prefixes=_tuple(record.get("tag_prefixes")),
                part_families=_tuple(record.get("part_families")),
            )
            for name, record in (payload.get("equipment") or {}).items()
        }
        parameters = {
            str(name): ParameterTerm(
                name=str(record.get("name") or name),
                aliases=_tuple(record.get("aliases")),
                units=tuple(unit.lower() for unit in _tuple(record.get("units"))),
            )
            for name, record in (payload.get("parameters") or {}).items()
        }
        contexts = {
            str(name): ContextTerm(
                name=str(record.get("name") or name),
                kind=str(record.get("kind") or name),
                aliases=_tuple(record.get("aliases")),
            )
            for name, record in (payload.get("contexts") or {}).items()
        }
        references = _tuple(payload.get("references"))
        return cls(
            schema_version=str(payload.get("schema_version") or "interlock_mvp.glossary.v1"),
            aliases=aliases,
            equipment=equipment,
            parameters=parameters,
            contexts=contexts,
            references=references,
        )

    def search_aliases(self) -> dict[str, tuple[str, ...]]:
        merged: dict[str, list[str]] = {key: list(values) for key, values in self.aliases.items()}
        for name, term in self.equipment.items():
            merged.setdefault(name, []).extend([*term.aliases, *term.tag_prefixes, *term.part_families])
        for name, term in self.parameters.items():
            merged.setdefault(name, []).extend([*term.aliases, *term.units])
        for name, term in self.contexts.items():
            merged.setdefault(name, []).extend(term.aliases)
        return {key: tuple(_dedup(values)) for key, values in merged.items()}

    def subject_patterns(self) -> list[re.Pattern[str]]:
        patterns: list[re.Pattern[str]] = []
        for term in self.equipment.values():
            acronym_prefixes = [prefix for prefix in [*term.tag_prefixes, *term.aliases] if _looks_like_acronym_prefix(prefix)]
            natural_prefixes = [
                prefix
                for prefix in [*term.tag_prefixes, *term.aliases]
                if _looks_like_tag_prefix(prefix) and not _looks_like_acronym_prefix(prefix)
            ]
            if acronym_prefixes:
                prefix_pattern = "|".join(re.escape(prefix) for prefix in sorted(acronym_prefixes, key=len, reverse=True))
                patterns.append(re.compile(rf"\b(?:{prefix_pattern})(?:\s*[-#]\s*|)(?:[A-Z0-9-]*\d[A-Z0-9-]*)\b", re.I))
            if natural_prefixes:
                prefix_pattern = "|".join(re.escape(prefix) for prefix in sorted(natural_prefixes, key=len, reverse=True))
                patterns.append(re.compile(rf"\b(?:{prefix_pattern})\s+[-# ]?\s*[A-Z0-9-]*\d[A-Z0-9-]*\b", re.I))
            for family in term.part_families:
                escaped = re.escape(family)
                patterns.append(re.compile(rf"\b{escaped}[-A-Z0-9]*\d[A-Z]*\b", re.I))
        return patterns

    def parameter_for(self, text: str, unit: str) -> str | None:
        lowered = text.lower()
        unit_lower = unit.lower()
        for name, term in self.parameters.items():
            if unit_lower in term.units and any(alias.lower() in lowered for alias in term.aliases):
                return name
        for name, term in self.parameters.items():
            if not term.units and any(alias.lower() in lowered for alias in term.aliases):
                return name
        for name, term in self.parameters.items():
            if name in {"rating", "voltage", "current"} and unit_lower in term.units:
                return name
        return None

    def context_for(self, text: str) -> tuple[str, str, str] | None:
        lowered = text.lower()
        for name, term in self.contexts.items():
            for alias in term.aliases:
                alias_lower = alias.lower()
                if alias_lower not in lowered:
                    continue
                raw = _raw_alias(text, alias) or alias
                number = _nearby_number(text, alias)
                canonical = _canonical_context(name, number)
                return canonical, term.kind, raw
        return None

    def metrics(self) -> dict[str, int | str]:
        return {
            "schema_version": self.schema_version,
            "alias_terms": sum(len(values) for values in self.aliases.values()),
            "equipment_terms": len(self.equipment),
            "parameter_terms": len(self.parameters),
            "context_terms": len(self.contexts),
            "reference_terms": len(self.references),
        }


def _tuple(value: Any) -> tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


def _dedup(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(value)
    return result


def _looks_like_tag_prefix(value: str) -> bool:
    cleaned = value.strip()
    if not cleaned:
        return False
    if len(cleaned) <= 5 and cleaned.upper() == cleaned:
        return True
    return cleaned.lower() in {"transformer", "relay", "breaker", "fuse", "feeder", "bus", "panel", "switchboard"}


def _looks_like_acronym_prefix(value: str) -> bool:
    cleaned = value.strip()
    return bool(cleaned) and len(cleaned) <= 5 and cleaned.upper() == cleaned


def _raw_alias(text: str, alias: str) -> str | None:
    match = re.search(re.escape(alias), text, flags=re.I)
    return match.group(0) if match else None


def _nearby_number(text: str, alias: str) -> str:
    match = re.search(rf"{re.escape(alias)}\s*#?\s*(\d+)", text, flags=re.I)
    return match.group(1) if match else ""


def _canonical_context(name: str, number: str) -> str:
    normalized = normalize_key(name)
    if normalized in {"tcc", "time_current_curve", "coordination_curve"} and number:
        return f"tcc{number}"
    if number:
        return f"{normalized}_{number}"
    return normalized
