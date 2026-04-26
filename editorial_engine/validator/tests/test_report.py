"""Phase 3+4 tests — report writers + MDX frontmatter injection."""
import json
from pathlib import Path

from editorial_engine.validator import Flag, ValidationReport
from editorial_engine.validator.report import (
    inject_into_mdx, write_json, write_markdown,
)


def _make_report(month="2026-02") -> ValidationReport:
    return ValidationReport(
        edition_month=month,
        validated_at="2026-04-26T10:00:00+00:00",
        sections_validated=["macro_brief", "trade_exports"],
        flags=[
            Flag(
                flag_id="numerical_inconsistency",
                severity="critical",
                section="trade_exports",
                message="Prose cites '€34.5 bn' but fiche shows '€34.71 bn'.",
                citation="Exports amounted to €34.5 bn",
                suggested_resolution="Verify against fiche.",
            ),
            Flag(
                flag_id="banned_connector",
                severity="warning",
                section="macro_brief",
                message="'furthermore' is on the banned list.",
                pattern_ref="system.md §4.3",
            ),
        ],
    )


def test_write_json_round_trip(tmp_path: Path):
    report = _make_report()
    path = write_json(report, tmp_path)
    payload = json.loads(path.read_text())
    assert payload["edition_month"] == "2026-02"
    assert payload["summary"]["critical_count"] == 1
    assert payload["summary"]["warning_count"] == 1
    assert len(payload["flags"]) == 2


def test_write_markdown_groups_by_section(tmp_path: Path):
    report = _make_report()
    path = write_markdown(report, tmp_path)
    body = path.read_text()
    assert "# Validation report — 2026-02" in body
    assert "## `macro_brief`" in body
    assert "## `trade_exports`" in body
    assert "🔴 critical" in body
    assert "🟠 warning" in body


def test_write_markdown_no_flags(tmp_path: Path):
    report = ValidationReport(
        edition_month="2026-02",
        validated_at="2026-04-26T10:00:00+00:00",
        sections_validated=["macro_brief"],
        flags=[],
    )
    body = write_markdown(report, tmp_path).read_text()
    assert "No flags surfaced" in body


# ──────────────────────────────────────────────────────────────────────
# MDX injection
# ──────────────────────────────────────────────────────────────────────


def _seed_mdx(tmp_path: Path) -> Path:
    mdx = tmp_path / "2026-02.mdx"
    mdx.write_text(
        "---\n"
        "month: '2026-02'\n"
        "publication_date: '2026-04-23'\n"
        "reviewed: false\n"
        "---\n"
        "\n"
        "## EU27 chemical exports\n\n"
        "Body text here.\n",
        encoding="utf-8",
    )
    return mdx


def test_inject_creates_block(tmp_path: Path):
    mdx = _seed_mdx(tmp_path)
    assert inject_into_mdx(_make_report(), mdx) is True
    out = mdx.read_text()
    assert "validation:" in out
    assert 'generated_at: "2026-04-26T10:00:00+00:00"' in out
    assert "critical: 1" in out
    assert "section: trade_exports" in out
    # Body untouched
    assert "## EU27 chemical exports" in out
    assert "Body text here." in out


def test_inject_replaces_previous_block(tmp_path: Path):
    mdx = _seed_mdx(tmp_path)
    inject_into_mdx(_make_report(), mdx)
    # Re-inject a different report; the old block must be replaced, not duplicated
    second = ValidationReport(
        edition_month="2026-02",
        validated_at="2026-04-27T10:00:00+00:00",
        sections_validated=["macro_brief"],
        flags=[],
    )
    inject_into_mdx(second, mdx)
    out = mdx.read_text()
    # Only one validation block
    assert out.count("validation:") == 1
    # Latest content
    assert 'generated_at: "2026-04-27T10:00:00+00:00"' in out
    assert "flags: []" in out


def test_inject_returns_false_without_frontmatter(tmp_path: Path):
    mdx = tmp_path / "no_frontmatter.mdx"
    mdx.write_text("# A heading\nNo frontmatter here.\n", encoding="utf-8")
    assert inject_into_mdx(_make_report(), mdx) is False
    # File untouched
    assert mdx.read_text() == "# A heading\nNo frontmatter here.\n"


def test_inject_yaml_escapes_quotes(tmp_path: Path):
    mdx = _seed_mdx(tmp_path)
    report = ValidationReport(
        edition_month="2026-02",
        validated_at="2026-04-26T10:00:00+00:00",
        sections_validated=["x"],
        flags=[
            Flag(
                flag_id="numerical_inconsistency",
                severity="critical",
                section="x",
                message='He said "hello" then left.',
                citation='Quote: "this"',
            ),
        ],
    )
    inject_into_mdx(report, mdx)
    out = mdx.read_text()
    # The quoted string must contain escaped quotes inside double quotes
    assert '\\"hello\\"' in out
    assert '\\"this\\"' in out
