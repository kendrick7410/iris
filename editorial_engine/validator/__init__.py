"""Editorial validator for Iris.

Public surface: `compute_flags(section_text, fiche, section_type)`.
See validator.py for the entry point.
"""
from .flag import Flag, Severity, ValidationReport
from .validator import compute_flags, compute_flags_inter

__all__ = ["Flag", "Severity", "ValidationReport", "compute_flags", "compute_flags_inter"]
