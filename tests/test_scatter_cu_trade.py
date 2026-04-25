"""Unit tests for Scatter 1 — CU × trade balance, period-aligned."""
from pathlib import Path
import json
import shutil
import tempfile
import unittest

from analysis.scatters import cu_trade


FIXTURES = Path(__file__).parent / "fixtures" / "scatters"


class TestCuTrade(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cache = self.tmp / "cache" / "2026-02"
        self.cache.mkdir(parents=True)
        shutil.copy(FIXTURES / "bcs.json", self.cache / "bcs.json")
        shutil.copy(
            FIXTURES / "country_trade_balance.json",
            self.cache / "country_trade_balance.json",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _compute(self):
        return cu_trade.compute("2026-02", {"cache_dir": self.cache})

    def test_structure(self):
        sd = self._compute()
        self.assertEqual(sd.scatter_id, "cu_trade")
        self.assertEqual(len(sd.points), 7)
        self.assertIn("x_ref", sd.reference_lines)
        self.assertEqual(sd.reference_lines["y_ref"], 0.0)

    def test_points_match_fixture(self):
        sd = self._compute()
        de = next(p for p in sd.points if p.label == "DE")
        self.assertAlmostEqual(de.x, 77.0, places=1)
        self.assertAlmostEqual(de.y, 5.2, places=1)

    def test_signal_strength_bounds(self):
        sd = self._compute()
        self.assertGreaterEqual(sd.signal_strength, 0.0)
        self.assertLessEqual(sd.signal_strength, 1.0)

    def test_cu_proxy_flagged_in_annotations(self):
        sd = self._compute()
        for p in sd.points:
            self.assertEqual(p.annotations.get("cu_proxy"), "manufacturing")
            self.assertIn("manufacturing", p.annotations.get("cu_note", ""))

    def test_all_x_are_percent_positive(self):
        sd = self._compute()
        for p in sd.points:
            self.assertGreater(p.x, 50.0, "CU should be at least 50%")
            self.assertLess(p.x, 100.0, "CU cannot exceed 100%")

    def test_axis_labels_carry_quarter(self):
        sd = self._compute()
        self.assertIn("2025-Q4", sd.x_axis_label)
        self.assertIn("2025-Q4", sd.y_axis_label)
        for p in sd.points:
            self.assertEqual(p.annotations["period"], "2025-Q4")
            self.assertEqual(
                p.annotations["period_months"],
                ["2025-10", "2025-11", "2025-12"],
            )

    def test_period_mismatch_raises(self):
        """If bcs.json and country_trade_balance.json cover different periods,
        compute() must refuse to mix them."""
        bcs_path = self.cache / "bcs.json"
        bcs = json.loads(bcs_path.read_text())
        bcs["latest_quarter"] = "2025-Q3"
        bcs["quarter_months"] = ["2025-07", "2025-08", "2025-09"]
        bcs_path.write_text(json.dumps(bcs))
        with self.assertRaises(RuntimeError):
            self._compute()


if __name__ == "__main__":
    unittest.main()
