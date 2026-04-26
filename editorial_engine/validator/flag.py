"""Flag dataclass — a single point of vigilance flagged for the human reviewer.

A Flag never asserts an error; it asks Moncef to verify. Each carries enough
context (citation + suggested resolution + traceable pattern_ref) that he can
act in seconds rather than rereading the whole section.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Literal

Severity = Literal["critical", "warning", "info"]


@dataclass
class Flag:
    flag_id: str
    severity: Severity
    section: str
    message: str
    citation: str = ""
    location_hint: str = ""
    pattern_ref: str | None = None
    suggested_resolution: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ValidationReport:
    edition_month: str
    validated_at: str
    sections_validated: list[str] = field(default_factory=list)
    flags: list[Flag] = field(default_factory=list)

    def summary(self) -> dict:
        counts = {"critical": 0, "warning": 0, "info": 0}
        for f in self.flags:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        return {
            "critical_count": counts["critical"],
            "warning_count": counts["warning"],
            "info_count": counts["info"],
            "sections_validated": len(self.sections_validated),
        }

    def to_dict(self) -> dict:
        return {
            "edition_month": self.edition_month,
            "validated_at": self.validated_at,
            "summary": self.summary(),
            "sections_validated": self.sections_validated,
            "flags": [f.to_dict() for f in self.flags],
        }
