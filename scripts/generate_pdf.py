"""Generate the Iris edition PDF via Playwright headless Chromium.

    python scripts/generate_pdf.py --month 2026-02
    python scripts/generate_pdf.py --month 2026-02 --site-url http://localhost:4321

Output: site/public/downloads/YYYY-MM.pdf
"""
import argparse
import logging
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOWNLOADS_DIR = PROJECT_ROOT / "site" / "public" / "downloads"

logger = logging.getLogger("iris.generate_pdf")


def _wait_for_server(url: str, timeout_s: int = 30) -> bool:
    import urllib.request
    import urllib.error
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(0.5)
    return False


def generate(month: str, site_url: str, output: Path) -> Path:
    from playwright.sync_api import sync_playwright

    full_url = f"{site_url.rstrip('/')}/editions/{month}/print-layout"
    output.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Rendering {full_url}")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 1240, "height": 1754},
            device_scale_factor=2,
        )
        page = ctx.new_page()
        page.goto(full_url, wait_until="networkidle", timeout=30_000)
        # SVG charts are inline so they render with the DOM; wait for fonts
        page.evaluate("document.fonts ? document.fonts.ready : Promise.resolve()")
        page.wait_for_function("() => document.querySelectorAll('svg').length >= 4", timeout=10_000)
        time.sleep(0.5)

        footer_html = (
            '<div style="font-size: 9pt; color: #666; width: 100%; text-align: center; '
            'padding: 0 18mm; font-family: Lato, Arial, sans-serif;">'
            f'Iris, {month} &middot; page <span class="pageNumber"></span> '
            'of <span class="totalPages"></span>'
            '</div>'
        )
        page.pdf(
            path=str(output),
            format="A4",
            margin={"top": "20mm", "bottom": "20mm", "left": "18mm", "right": "18mm"},
            print_background=True,
            display_header_footer=True,
            footer_template=footer_html,
            header_template="<div></div>",
        )
        browser.close()

    logger.info(f"PDF written: {output} ({output.stat().st_size // 1024} KB)")
    return output


def ensure_chromium() -> None:
    """Install the Chromium binary that Playwright needs if missing."""
    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=False, capture_output=True, timeout=180,
        )
    except Exception as e:
        logger.warning(f"playwright install chromium failed (may already be present): {e}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", required=True, help="Edition month (YYYY-MM)")
    parser.add_argument("--site-url", default="http://localhost:4321", help="Running Astro server URL")
    parser.add_argument("--skip-chromium-install", action="store_true",
                        help="Do not attempt to install the Chromium binary")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stderr,
    )

    if not args.skip_chromium_install:
        ensure_chromium()

    if not _wait_for_server(args.site_url, timeout_s=20):
        logger.error(f"No Astro server responding at {args.site_url}. "
                     f"Start it with `cd site && npx astro dev --host 0.0.0.0 --port 4321` "
                     f"or `cd site && npx astro preview` after a build.")
        sys.exit(2)

    out = DOWNLOADS_DIR / f"{args.month}.pdf"
    generate(args.month, args.site_url, out)


if __name__ == "__main__":
    main()
