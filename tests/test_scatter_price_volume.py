"""Unit tests for Scatter 2 — price × volume by sub-sector."""
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
        shutil.copy(FIXTURES / "subsectors.json", self.cache / "subsectors.json")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _compute(self):
        return price_volume.compute("2026-02", {"cache_dir": self.cache})

    def test_structure(self):
        sd = self._compute()
        self.assertEqual(sd.scatter_id, "price_volume")
        # Fixture omits C2051 to exercise the graceful-drop path.
        self.assertEqual(len(sd.points), 9)
        self.assertEqual(sd.reference_lines["x_ref"], 0.0)
        self.assertEqual(sd.reference_lines["y_ref"], 0.0)

    def test_signal_strength_bounds(self):
        sd = self._compute()
        self.assertGreaterEqual(sd.signal_strength, 0.0)
        self.assertLessEqual(sd.signal_strength, 1.0)

    def test_fertilisers_is_extreme_quadrant(self):
        """C2015 (fertilisers) is +8.2% vol / +12.5% price → healthy-expansion quadrant."""
        sd = self._compute()
        c2015 = next(p for p in sd.points if p.label == "2015")
        self.assertAlmostEqual(c2015.x, 12.5, places=1)
        self.assertAlmostEqual(c2015.y, 8.2, places=1)
        self.assertIn("expansion", c2015.annotations["quadrant"])

    def test_organic_chemicals_both_negative(self):
        """C2014 is -5.4% vol / -6.2% price → both-sides contraction."""
        sd = self._compute()
        c2014 = next(p for p in sd.points if p.label == "2014")
        self.assertIn("both-sides", c2014.annotations["quadrant"])


if __name__ == "__main__":
    unittest.main()
