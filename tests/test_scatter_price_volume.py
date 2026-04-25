"""Unit tests for Scatter 2 — price × volume by country (NACE C20)."""
from pathlib import Path
import shutil
import tempfile
import unittest

from analysis.scatters import price_volume


FIXTURES = Path(__file__).parent / "fixtures" / "scatters"


class TestPriceVolume(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cache = self.tmp / "cache" / "2026-02"
        self.cache.mkdir(parents=True)
        shutil.copy(FIXTURES / "production.json", self.cache / "production.json")
        shutil.copy(FIXTURES / "prices.json", self.cache / "prices.json")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _compute(self):
        return price_volume.compute("2026-02", {"cache_dir": self.cache})

    def test_structure(self):
        sd = self._compute()
        self.assertEqual(sd.scatter_id, "price_volume")
        self.assertEqual(len(sd.points), 7)
        self.assertEqual(sd.reference_lines["x_ref"], 0.0)
        self.assertEqual(sd.reference_lines["y_ref"], 0.0)

    def test_signal_strength_bounds(self):
        sd = self._compute()
        self.assertGreaterEqual(sd.signal_strength, 0.0)
        self.assertLessEqual(sd.signal_strength, 1.0)

    def test_points_are_countries(self):
        sd = self._compute()
        labels = {p.label for p in sd.points}
        self.assertEqual(labels, {"DE", "FR", "IT", "NL", "ES", "BE", "PL"})

    def test_netherlands_in_demand_weakness_quadrant(self):
        """NL: prices -9.2% (down), volume -9.6% (down) → both-sides contraction."""
        sd = self._compute()
        nl = next(p for p in sd.points if p.label == "NL")
        self.assertLess(nl.x, 0)
        self.assertLess(nl.y, 0)
        self.assertIn("both-sides", nl.annotations["quadrant"])

    def test_yoy_anchor_recorded(self):
        sd = self._compute()
        for p in sd.points:
            self.assertEqual(p.annotations["yoy_anchor"], "2025-02")
            self.assertEqual(p.annotations["nace"], "C20")


if __name__ == "__main__":
    unittest.main()
