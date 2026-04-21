"""
Git commit helper for Iris editions.

Contract:
  - commit_edition(month, project_root) → creates branch edition/YYYY-MM, commits artifacts
  - NEVER pushes
"""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("iris.scripts.commit")


def commit_edition(month: str, project_root: Path):
    """Create a git branch and commit the edition artifacts."""
    branch = f"edition/{month}"

    def run(cmd):
        result = subprocess.run(cmd, cwd=str(project_root), capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Git command failed: {' '.join(cmd)}\n{result.stderr}")
            raise RuntimeError(f"Git error: {result.stderr.strip()}")
        return result.stdout.strip()

    run(["git", "checkout", "-b", branch])

    files_to_add = [
        f"editorial/drafts/{month}/edition.md",
        f"editorial/drafts/{month}/manifest.json",
        f"editorial/drafts/{month}/summary.md",
        f"editorial/drafts/{month}/sections/",
        f"site/src/content/editions/{month}.mdx",
        f"site/public/charts/{month}/",
    ]

    for f in files_to_add:
        full = project_root / f
        if full.exists():
            run(["git", "add", str(f)])

    run(["git", "commit", "-m", f"edition: {month}"])
    logger.info(f"Committed edition {month} on branch {branch}")
    logger.info("*** No push — review via PR before publishing ***")
