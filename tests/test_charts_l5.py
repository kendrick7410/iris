"""Smoke tests for L5 chart templates.

Each template renders synthetic data to /tmp and asserts the SVG is non-empty.
"""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from charts.templates import stacked_bars_nace, waterfall_contribution, kpi_card


def test_stacked_bars_stacked_mode():
    data = {
        "2021": {"20.14": 4.2, "20.15": 2.1, "20.16": 3.0},
        "2022": {"20.14": 4.5, "20.15": 2.4, "20.16": 3.3},
        "2023": {"20.14": 4.8, "20.15": 2.6, "20.16": 3.5},
        "2024": {"20.14": 5.1, "20.15": 2.7, "20.16": 3.6},
        "2025": {"20.14": 5.5, "20.15": 2.9, "20.16": 3.8},
    }
    labels = {"20.14": "Other organic basic chemicals",
              "20.15": "Fertilisers", "20.16": "Plastics"}
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "stacked.svg"
        path = stacked_bars_nace.render(
            data, labels, "volume", "Stacked test", out, 2026,
            mode="stacked", annotate_yoy_last=True,
        )
        assert path is not None
        assert out.exists() and out.stat().st_size > 5000
    print("  stacked_bars stacked mode OK")


def test_stacked_bars_clustered_mode():
    data = {"2024": {"A": 1.0, "B": 2.0}, "2025": {"A": 1.2, "B": 2.3}}
    labels = {"A": "Alpha", "B": "Beta"}
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "clustered.svg"
        path = stacked_bars_nace.render(
            data, labels, "value", "Clustered test", out, 2026,
            mode="clustered", annotate_yoy_last=True,
        )
        assert path is not None
        assert out.exists()
    print("  stacked_bars clustered mode OK")


def test_waterfall_contribution():
    contribs = [
        {"label": "29091990 (acyclic ethers)", "value": 7.6},
        {"label": "29335995 (heterocyclic cmpds)", "value": 5.7},
        {"label": "29371900 (polypeptide hormones)", "value": 5.6},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "wf.svg"
        path = waterfall_contribution.render(
            contribs, 12.1, "Total change 2020-2025", "value",
            "Waterfall test", out, 2026,
        )
        assert path is not None
        assert out.exists() and out.stat().st_size > 3000
    print("  waterfall OK")


def test_kpi_card_with_sparkline():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "kpi.svg"
        path = kpi_card.render(
            "Chemical output", 80.5, "index 2021=100", 0.9, "% YoY", "up",
            out, sparkline_data=[79.0, 79.2, 79.5, 79.8, 80.0, 80.2, 80.3, 80.4, 80.5, 80.6, 80.5, 80.5],
        )
        assert path is not None
        assert out.exists()
    print("  kpi_card with sparkline OK")


def test_kpi_card_no_sparkline():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "kpi2.svg"
        kpi_card.render("Trade balance", 1.09, "€ bn", -3.3, "€ bn YoY", "down", out)
        assert out.exists()
    print("  kpi_card plain OK")


if __name__ == "__main__":
    print("Testing L5 chart templates...")
    test_stacked_bars_stacked_mode()
    test_stacked_bars_clustered_mode()
    test_waterfall_contribution()
    test_kpi_card_with_sparkline()
    test_kpi_card_no_sparkline()
    print("All L5 chart tests passed.")
