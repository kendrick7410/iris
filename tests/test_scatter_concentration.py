"""Unit tests for Scatter 4 — concentration (partner HHI × product HHI).

Builds a tiny synthetic parquet in a temp dir and points `concentration.compute`
at it. This avoids depending on the full production parquet for unit tests.
"""
from pathlib import Path
import shutil
import tempfile
import unittest

import pandas as pd

from analysis.scatters import concentration


class TestConcentration(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cache = self.tmp / "cache" / "2026-02"
        self.cache.mkdir(parents=True)
        # Tiny synthetic parquet: 2 chapters, a few partners and CN8 codes.
        # Chapter 29 = very concentrated (1 partner, 1 product); Chapter 30 =
        # diversified (4 partners, 4 products, equal shares).
        rows = []
        period = pd.Timestamp("2026-02-28")
        # Chapter 29: 100% US, 100% CN8=29000001
        rows.append({
            "period": period, "declarant": "EU", "partner": "US",
            "product_nc": "29000001", "cpa2015": "2014", "chapter_cn": "29",
            "flow": 2, "flow_label": "export", "value_in_euros": 1_000_000_000.0,
            "quantity_in_kg": 1_000.0,
        })
        # Chapter 30: 4 partners × 4 products, equal shares -> HHI ≈ 2500 each
        for i, partner in enumerate(["US", "CN", "GB", "JP"]):
            for j, pc in enumerate(["30000001", "30000002", "30000003", "30000004"]):
                rows.append({
                    "period": period, "declarant": "EU", "partner": partner,
                    "product_nc": pc, "cpa2015": "2110", "chapter_cn": "30",
                    "flow": 2, "flow_label": "export",
                    "value_in_euros": 250_000_000.0,
                    "quantity_in_kg": 100.0,
                })

        df = pd.DataFrame(rows)
        self.parquet_path = self.tmp / "mini.parquet"
        df.to_parquet(self.parquet_path)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _compute(self):
        return concentration.compute(
            "2026-02",
            {
                "parquet_path": str(self.parquet_path),
                "cache_dir": self.cache,
                "window_months": 1,
            },
        )

    def test_structure(self):
        sd = self._compute()
        self.assertEqual(sd.scatter_id, "concentration")
        self.assertGreaterEqual(len(sd.points), 2)
        self.assertIn("x_thresholds", sd.reference_lines)
        self.assertIn("y_thresholds", sd.reference_lines)

    def test_chapter_29_is_maximally_concentrated(self):
        """One partner + one CN8 => HHI = 10000 on both axes."""
        sd = self._compute()
        ch29 = next(p for p in sd.points if p.label == "29")
        self.assertAlmostEqual(ch29.x, 10000.0, places=0)
        self.assertAlmostEqual(ch29.y, 10000.0, places=0)
        self.assertEqual(ch29.annotations["top_partner_share_pct"], 100.0)

    def test_chapter_30_is_balanced(self):
        """4 partners × 4 products at equal share => HHI ≈ 2500 each."""
        sd = self._compute()
        ch30 = next(p for p in sd.points if p.label == "30")
        # 4 equal shares -> HHI = 4 × (25)^2 = 2500
        self.assertAlmostEqual(ch30.x, 2500.0, delta=50)
        # 16 equal product rows aggregated to 4 products -> HHI on CN8 = 2500
        self.assertAlmostEqual(ch30.y, 2500.0, delta=50)

    def test_signal_strength_bounds(self):
        sd = self._compute()
        self.assertGreaterEqual(sd.signal_strength, 0.0)
        self.assertLessEqual(sd.signal_strength, 1.0)

    def test_raw_aggregation_persisted(self):
        self._compute()
        self.assertTrue((self.cache / "concentration_raw.json").exists())


if __name__ == "__main__":
    unittest.main()
