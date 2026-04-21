"""Smoke tests for analysis/indicators module."""
import json
import tempfile
from pathlib import Path
from analysis.indicators import build_fiches


def _make_mock_cache(cache_dir: Path):
    """Create minimal mock cache files for testing."""
    prod = {
        "dataset": "sts_inpr_m", "month": "2026-02", "unit": "I21", "s_adj": "SCA",
        "eu27": {"2025-02": 82.5, "2026-01": 78.9, "2026-02": 79.3},
        "by_country": {
            "DE": {"2025-02": 80.1, "2026-02": 77.3},
            "FR": {"2025-02": 92.5, "2026-02": 93.5},
        },
        "by_sector": {
            "C": {"2025-02": 100.6, "2026-02": 100.2},
            "C20": {"2025-02": 82.5, "2026-02": 79.3},
        },
    }
    (cache_dir / "production.json").write_text(json.dumps(prod))

    prices = {
        "dataset": "sts_inppd_m", "month": "2026-02", "unit": "I21", "s_adj": "NSA",
        "eu27": {"2025-02": 120.6, "2026-02": 117.2},
        "by_country": {"DE": {"2025-02": 121.0, "2026-02": 119.0}},
        "by_sector": {"C": {"2025-02": 120.0, "2026-02": 120.2}},
    }
    (cache_dir / "prices.json").write_text(json.dumps(prices))


def test_build_fiches():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        cache_dir = base / "data" / "cache" / "2026-02"
        cache_dir.mkdir(parents=True)
        (base / "data" / "baselines").mkdir(parents=True)

        _make_mock_cache(cache_dir)

        fiches = build_fiches(cache_dir, "2026-02")
        assert len(fiches) >= 2, f"Expected >=2 fiches, got {len(fiches)}"

        for f in fiches:
            data = json.loads(f.read_text())
            assert "section_type" in data
            assert "period" in data
            assert "data" in data
            assert data["data"]["current"]["value"] is not None
            assert data["data"]["previous_year"]["delta_pct"] is not None
            print(f"  Fiche {data['section_type']}: current={data['data']['current']['value']}, "
                  f"YoY={data['data']['previous_year']['delta_pct']}%")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    print("Testing indicators...")
    test_build_fiches()
    print("All indicator tests passed.")
