"""Tests for the reviewed-edition guard in pipelines/monthly_run.py.

Two layers:
  - unit   : _mdx_has_reviewed_flag as a pure function over tmp files
  - integ  : invoke the CLI via click's CliRunner, monkey-patch
             PROJECT_ROOT and step_fetch to prove the guard's
             behaviour without hitting Eurostat / Anthropic.
"""
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

# Ensure project root on path (mirrors monthly_run.py)
PROJECT_ROOT_TEST = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT_TEST))

import pipelines.monthly_run as pipeline_module  # noqa: E402
from pipelines.monthly_run import _mdx_has_reviewed_flag, main  # noqa: E402


# ---------------------------------------------------------------------------
# Unit tests — _mdx_has_reviewed_flag
# ---------------------------------------------------------------------------

def test_false_when_file_missing():
    with tempfile.TemporaryDirectory() as tmp:
        assert _mdx_has_reviewed_flag(Path(tmp) / "missing.mdx") is False


def test_true_when_reviewed_true():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "e.mdx"
        p.write_text("---\nmonth: 2026-02\nreviewed: true\n---\n\nbody\n")
        assert _mdx_has_reviewed_flag(p) is True


def test_false_when_reviewed_false():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "e.mdx"
        p.write_text("---\nmonth: 2026-02\nreviewed: false\n---\n\nbody\n")
        assert _mdx_has_reviewed_flag(p) is False


def test_false_when_field_absent():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "e.mdx"
        p.write_text("---\nmonth: 2026-02\n---\n\nbody\n")
        assert _mdx_has_reviewed_flag(p) is False


def test_false_when_no_frontmatter():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "e.mdx"
        p.write_text("no frontmatter\n")
        assert _mdx_has_reviewed_flag(p) is False


def test_case_insensitive_key_and_value():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "e.mdx"
        p.write_text("---\nmonth: 2026-02\nReviewed: TRUE\n---\n\nbody\n")
        assert _mdx_has_reviewed_flag(p) is True


def test_ignores_reviewed_in_body():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "e.mdx"
        p.write_text("---\nmonth: 2026-02\n---\n\nreviewed: true in prose\n")
        assert _mdx_has_reviewed_flag(p) is False


# ---------------------------------------------------------------------------
# Integration tests — CLI guard behaviour
# ---------------------------------------------------------------------------

def _setup_fake_project(tmp_root: Path, month: str, *, reviewed: bool) -> Path:
    """Create a minimal site/src/content/editions/{month}.mdx under tmp_root."""
    mdx_dir = tmp_root / "site" / "src" / "content" / "editions"
    mdx_dir.mkdir(parents=True, exist_ok=True)
    mdx_path = mdx_dir / f"{month}.mdx"
    body = f"---\nmonth: {month}\n"
    if reviewed:
        body += "reviewed: true\n"
    body += "---\n\nexisting human-edited content\n"
    mdx_path.write_text(body, encoding="utf-8")
    return mdx_path


def _run_cli(tmp_root: Path, args: list, *, fetch_sentinel: dict | None = None):
    """Invoke the CLI with PROJECT_ROOT redirected to tmp_root.

    If fetch_sentinel is provided, step_fetch is replaced with a stub that
    records invocation and raises to short-circuit the pipeline (we don't
    want tests hitting Eurostat).
    """
    def fake_fetch(month, force):
        if fetch_sentinel is not None:
            fetch_sentinel["called"] = True
        raise RuntimeError("stop-for-test")

    runner = CliRunner(mix_stderr=True)
    with patch.object(pipeline_module, "PROJECT_ROOT", tmp_root), \
         patch.object(pipeline_module, "step_fetch", fake_fetch):
        return runner.invoke(main, args, catch_exceptions=False) if False \
               else runner.invoke(main, args)


def test_cli_skips_when_reviewed_and_no_force():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_fake_project(tmp_path, "2026-02", reviewed=True)
        sentinel = {"called": False}
        result = _run_cli(tmp_path, ["--month", "2026-02"], fetch_sentinel=sentinel)
        assert result.exit_code == 0, f"expected 0, got {result.exit_code}\n{result.output}"
        assert "reviewed=True" in result.output
        assert "refusing to regenerate" in result.output
        assert sentinel["called"] is False, "step_fetch must not run when guard fires"


def test_cli_proceeds_with_force_on_reviewed():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_fake_project(tmp_path, "2026-02", reviewed=True)
        sentinel = {"called": False}
        result = _run_cli(tmp_path, ["--month", "2026-02", "--force"],
                          fetch_sentinel=sentinel)
        # Pipeline continues into fetch (then raises our stop-for-test).
        # The exit code is 1 (exception path). What matters is the sentinel.
        assert sentinel["called"] is True, "--force must bypass the guard"
        assert "will overwrite human-edited content" in result.output


def test_cli_runs_when_mdx_not_reviewed():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_fake_project(tmp_path, "2026-02", reviewed=False)
        sentinel = {"called": False}
        result = _run_cli(tmp_path, ["--month", "2026-02"], fetch_sentinel=sentinel)
        assert sentinel["called"] is True, "no reviewed flag → pipeline should run"
        assert "refusing to regenerate" not in result.output


def test_cli_runs_when_mdx_absent():
    """New edition (no MDX yet) → pipeline runs normally."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # No _setup_fake_project call → no MDX on disk.
        sentinel = {"called": False}
        result = _run_cli(tmp_path, ["--month", "2026-03"], fetch_sentinel=sentinel)
        assert sentinel["called"] is True, "missing MDX must not block fresh months"


def test_cli_variant_bypasses_guard():
    """--variant writes to a side-by-side folder; guard must not block it."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_fake_project(tmp_path, "2026-02", reviewed=True)
        sentinel = {"called": False}
        result = _run_cli(tmp_path, ["--month", "2026-02", "--variant", "v2"],
                          fetch_sentinel=sentinel)
        assert sentinel["called"] is True, "variants must not be blocked by reviewed flag"
        assert "refusing to regenerate" not in result.output


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    tests = [
        (name, fn) for name, fn in sorted(globals().items())
        if name.startswith("test_") and callable(fn)
    ]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"ok - {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL - {name}\n    {e}")
        except Exception as e:
            failed += 1
            print(f"ERROR - {name}\n    {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed.")
    sys.exit(1 if failed else 0)
