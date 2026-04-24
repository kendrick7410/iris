"""
Integration test for the Phase A scatter pipeline.

Drives the orchestrator against a fully synthetic scenario so the test is
self-contained and independent of the real Eurostat caches. We:

1. Stage a tmp data/cache/{month}/ populated from tests/fixtures/scatters/
2. Stage a tmp data/baselines/ populated from fixtures
3. Build a tiny synthetic parquet for the concentration scatter
4. Run `build_scatters.build_all` and assert the 4 SVG + 4 JSON exist,
   each JSON has the expected top-level schema, and the signal_strength
   ranking is a permutation of the 4 scatter ids.
"""
from pathlib import Path
import json
import shutil
import tempfile
import unittest

import pandas as pd

from scripts import build_scatters


FIXTURES = Path(__file__).parent / "fixtures" / "scatters"
MONTH = "2026-02"


class TestScatterIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cache = self.tmp / "cache"
        self.baselines = self.tmp / "baselines"
        self.processed = self.tmp / "processed"
        self.charts = self.tmp / "charts"
        month_cache = self.cache / MONTH
        month_cache.mkdir(parents=True)
        self.baselines.mkdir(parents=True)

        # Stage all fixture caches
        for name in ("production", "bcs", "subsectors", "country_trade_balance"):
            shutil.copy(FIXTURES / f"{name}.json", month_cache / f"{name}.json")
        for name in ("precrisis_by_country", "jan2020_by_country"):
            shutil.copy(FIXTURES / f"{name}.json", self.baselines / f"{name}.json")

        # Synthetic parquet for the concentration scatter — two chapters, one
        # maximally concentrated (29), one diversified (30).
        rows = []
        period = pd.Timestamp("2026-02-28")
        rows.append({
            "period": period, "declarant": "EU", "partner": "US",
            "product_nc": "29000001", "cpa2015": "2014", "chapter_cn": "29",
            "flow": 2, "flow_label": "export", "value_in_euros": 1e9,
            "quantity_in_kg": 1e3,
        })
        for partner in ["US", "CN", "GB", "JP"]:
            for pc in ["30000001", "30000002", "30000003", "30000004"]:
                rows.append({
                    "period": period, "declarant": "EU", "partner": partner,
                    "product_nc": pc, "cpa2015": "2110", "chapter_cn": "30",
                    "flow": 2, "flow_label": "export", "value_in_euros": 2.5e8,
                    "quantity_in_kg": 100.0,
                })
        self.parquet_path = self.tmp / "mini.parquet"
        pd.DataFrame(rows).to_parquet(self.parquet_path)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _run(self):
        return build_scatters.build_all(
            MONTH,
            cache_dir=self.cache,
            baselines_dir=self.baselines,
            processed_dir=self.processed,
            charts_dir=self.charts,
            parquet_path=str(self.parquet_path),
        )

    def test_builds_all_four_without_error(self):
        results = self._run()
        self.assertEqual(len(results), 4)
        for r in results:
            self.assertEqual(r["status"], "ok", f"{r['scatter_id']}: {r.get('error')}")

    def test_svg_and_json_written(self):
        results = self._run()
        for r in results:
            self.assertTrue(Path(r["svg_path"]).exists(), r["svg_path"])
            self.assertTrue(Path(r["json_path"]).exists(), r["json_path"])

    def test_json_has_expected_schema(self):
        results = self._run()
        for r in results:
            blob = json.loads(Path(r["json_path"]).read_text())
            self.assertEqual(blob["scatter_id"], r["scatter_id"])
            for key in (
                "title", "x_axis_label", "y_axis_label",
                "points", "reference_lines", "signal_strength",
                "signal_explanation", "metadata",
            ):
                self.assertIn(key, blob, f"missing {key} in {r['scatter_id']}")
            self.assertIsInstance(blob["points"], list)
            for p in blob["points"]:
                for key in ("label", "x", "y", "annotations"):
                    self.assertIn(key, p)

    def test_signal_strength_in_unit_interval(self):
        results = self._run()
        for r in results:
            sig = r["signal_strength"]
            self.assertGreaterEqual(sig, 0.0, f"{r['scatter_id']} signal < 0")
            self.assertLessEqual(sig, 1.0, f"{r['scatter_id']} signal > 1")

    def test_scatter_ids_are_the_expected_four(self):
        results = self._run()
        got = sorted(r["scatter_id"] for r in results)
        self.assertEqual(got, sorted(["cu_trade", "price_volume", "trajectory", "concentration"]))

    def test_summary_print_does_not_raise(self):
        """print_summary must handle a mix of ok + error entries."""
        build_scatters.print_summary(self._run())


if __name__ == "__main__":
    unittest.main()
