"""Validation report writers — JSON for traceability, Markdown for human
eyes, and an MDX-frontmatter injector so Sveltia surfaces flags above the
section body.

All writers under `editorial/drafts/{month}/` ride the same edition
lifecycle as the section drafts. The frontmatter injection is destructive
(commit-écrasement): the latest validation block replaces the previous
one in `site/src/content/editions/{month}.mdx`, so git history shows the
flags evolving but no permanent "Moncef missed this" trail accumulates.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .flag import ValidationReport


SEVERITY_BADGE = {
    "critical": "🔴 critical",
    "warning":  "🟠 warning",
    "info":     "🔵 info",
}


def write_json(report: ValidationReport, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "validation_report.json"
    path.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def write_markdown(report: ValidationReport, out_dir: Path) -> Path:
    """Human-readable companion to the JSON. Grouped by section, severity-
    sorted within. Designed for Moncef to skim before opening the CMS."""
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = report.summary()
    lines: list[str] = []
    lines.append(f"# Validation report — {report.edition_month}")
    lines.append("")
    lines.append(f"_Validated at {report.validated_at}_")
    lines.append("")
    lines.append(
        f"**Summary:** {summary['critical_count']} critical, "
        f"{summary['warning_count']} warning, {summary['info_count']} info "
        f"across {summary['sections_validated']} sections."
    )
    lines.append("")
    if not report.flags:
        lines.append("No flags surfaced. Nothing to verify.")
        return _write(out_dir / "validation_report.md", lines)

    by_section: dict[str, list] = {}
    for flag in report.flags:
        by_section.setdefault(flag.section, []).append(flag)

    severity_order = {"critical": 0, "warning": 1, "info": 2}
    for section in sorted(by_section):
        flags = sorted(by_section[section], key=lambda f: severity_order.get(f.severity, 9))
        lines.append(f"## `{section}`  ({len(flags)} flag{'s' if len(flags) != 1 else ''})")
        lines.append("")
        for f in flags:
            badge = SEVERITY_BADGE.get(f.severity, f.severity)
            lines.append(f"### {badge} · {f.flag_id}")
            lines.append("")
            lines.append(f.message)
            if f.citation:
                lines.append("")
                lines.append(f"> {f.citation}")
            if f.pattern_ref:
                lines.append("")
                lines.append(f"_ref: {f.pattern_ref}_")
            if f.suggested_resolution:
                lines.append("")
                lines.append(f"**Suggested:** {f.suggested_resolution}")
            lines.append("")
    return _write(out_dir / "validation_report.md", lines)


def _write(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ──────────────────────────────────────────────────────────────────────
# MDX frontmatter injection — surfaces flags in the Sveltia editor
# ──────────────────────────────────────────────────────────────────────

# Marker pair so we can rewrite our block on every pipeline run without
# touching anything Moncef may have added by hand to the frontmatter.
_BEGIN = "# ↓ validator (auto-generated, edit nothing here) ↓"
_END   = "# ↑ validator ↑"


def _yaml_escape(s: str) -> str:
    """Minimal YAML string escape sufficient for our messages/citations."""
    if not s:
        return '""'
    s = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")
    return f'"{s}"'


def _render_block(report: ValidationReport) -> str:
    """The YAML block we splice into the MDX frontmatter."""
    summary = report.summary()
    lines = [
        _BEGIN,
        "validation:",
        f"  generated_at: {_yaml_escape(report.validated_at)}",
        "  summary:",
        f"    critical: {summary['critical_count']}",
        f"    warning: {summary['warning_count']}",
        f"    info: {summary['info_count']}",
        f"    sections_validated: {summary['sections_validated']}",
    ]
    if not report.flags:
        lines.append("  flags: []")
    else:
        lines.append("  flags:")
        for f in report.flags:
            lines.append(f"    - section: {f.section}")
            lines.append(f"      severity: {f.severity}")
            lines.append(f"      flag_id: {f.flag_id}")
            lines.append(f"      message: {_yaml_escape(f.message)}")
            if f.citation:
                lines.append(f"      citation: {_yaml_escape(f.citation)}")
            if f.pattern_ref:
                lines.append(f"      pattern_ref: {_yaml_escape(f.pattern_ref)}")
            if f.suggested_resolution:
                lines.append(f"      suggested_resolution: {_yaml_escape(f.suggested_resolution)}")
    lines.append(_END)
    return "\n".join(lines)


_BLOCK_RX = re.compile(
    rf"\n*{re.escape(_BEGIN)}.*?{re.escape(_END)}\n*",
    re.DOTALL,
)


def inject_into_mdx(report: ValidationReport, mdx_path: Path) -> bool:
    """Splice / replace the validation block inside the MDX frontmatter.

    Returns True on a successful rewrite, False if the file has no YAML
    frontmatter (in which case we leave it untouched — the validator must
    not invent structure for the human reviewer)."""
    if not mdx_path.exists():
        return False
    content = mdx_path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return False
    # Locate the closing '---' of the frontmatter block
    match = re.match(r"---\n(.*?)\n---\n", content, re.DOTALL)
    if not match:
        return False

    head = match.group(1)
    # Drop any previous block we wrote
    head_clean = _BLOCK_RX.sub("\n", head).rstrip()
    # Append the freshly rendered block
    new_head = head_clean + "\n" + _render_block(report)
    new_content = "---\n" + new_head + "\n---\n" + content[match.end():]
    mdx_path.write_text(new_content, encoding="utf-8")
    return True
