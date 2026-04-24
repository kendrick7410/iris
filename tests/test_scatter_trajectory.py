"""Unit tests for Scatter 3 — trajectory (crisis onset vs current)."""
from pathlib import Path
import json
import shutil
import tempfile
import unittest

from analysis.scatters import trajectory


FIXTURES = Path(__file__).parent / "fixtures" / "scatters"


class TestTrajectory(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cache = self.tmp / "cache" / "2026-02"
        self.base = self.tmp / "baselines"
        self.cache.mkdir(parents=True)
        self.base.mkdir(parents=True)
        shutil.copy(FIXTURES / "production.json", self.cache / "production.json")
        shutil.copy(FIXTURES / "precrisis_by_country.json", self.base / "precrisis_by_country.json")
        shutil.copy(FIXTURES / "jan2020_by_country.json", self.base / "jan2020_by_country.json")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _compute(self):
        return trajectory.compute(
            "2026-02",
            {"cache_dir": self.cache, "baselines_dir": self.base},
        )

    def test_structure(self):
        sd = self._compute()
        self.assertEqual(sd.scatter_id, "trajectory")
        self.assertEqual(len(sd.points), 7, "seven target countries")
        self.assertTrue(sd.reference_lines.get("diagonal"))
        self.assertIn("Jan 2020", sd.x_axis_label)
        self.assertGreater(len(sd.title), 10)

    def test_signal_strength_bounds(self):
        sd = self._compute()
        self.assertGreaterEqual(sd.signal_strength, 0.0)
        self.assertLessEqual(sd.signal_strength, 1.0)

    def test_math_pct_of_precrisis(self):
        """DE: precrisis=100, current=75.0 → y ≈ 75.0; jan2020=95 → x ≈ 95.0."""
        sd = self._compute()
        de = next(p for p in sd.points if p.label == "DE")
        self.assertAlmostEqual(de.x, 95.0, places=1)
        self.assertAlmostEqual(de.y, 75.0, places=1)

    def test_point_on_diagonal_when_identical(self):
        """A synthetic country where jan2020 = current must sit on y = x."""
        # Patch the jan2020 baseline so DE matches its current value.
        prod = json.loads((self.cache / "production.json").read_text())
        de_current = prod["by_country"]["DE"]["2026-02"]  # 75.0
        precrisis = json.loads((self.base / "precrisis_by_country.json").read_text())
        jan2020 = json.loads((self.base / "jan2020_by_country.json").read_text())
        # Force: precrisis = 100, jan2020 = 75 → x=75, y=75 → exactly on diagonal
        precrisis["precrisis_avg_i21_by_country"]["DE"] = 100.0
        jan2020["jan_2020_i21_by_country"]["DE"] = de_current
        (self.base / "precrisis_by_country.json").write_text(json.dumps(precrisis))
        (self.base / "jan2020_by_country.json").write_text(json.dumps(jan2020))
        sd = self._compute()
        de = next(p for p in sd.points if p.label == "DE")
        self.assertAlmostEqual(de.x, de.y, places=1)
        self.assertAlmostEqual(de.annotations["delta_from_diagonal_pp"], 0.0, places=1)

    def test_metadata_month(self):
        sd = self._compute()
        self.assertEqual(sd.metadata["edition_month"], "2026-02")
        self.assertEqual(sd.metadata["year"], 2026)


if __name__ == "__main__":
    unittest.main()
