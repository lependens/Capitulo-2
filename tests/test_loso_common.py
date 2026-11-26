"""Tests de las piezas comunes de los estudios 03.1/03.2. Se omiten si faltan numpy/pandas (la CI base no los instala)."""
import importlib.util
import sys
import unittest
from pathlib import Path

HAVE = all(importlib.util.find_spec(m) for m in ("numpy", "pandas"))
STUDY = Path(__file__).resolve().parents[1] / "studies/03_1_loso_inputs_siar"


@unittest.skipUnless(HAVE, "requiere numpy y pandas")
class LosoCommonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(STUDY))
        import loso_common
        cls.lc = loso_common

    def test_ra_matches_library(self):
        from openmeteo_et0 import pm
        for doy, iso in ((1, "2023-01-01"), (180, "2023-06-29"), (365, "2023-12-31")):
            self.assertAlmostEqual(float(self.lc.ra_fao56(39.5, doy)), pm.extraterrestrial_radiation(39.5, iso), 9)

    def test_folds_disjoint_and_match_thresholds(self):
        folds = self.lc.build_folds()
        self.assertEqual(len(folds), 12)
        for f in folds:
            self.assertFalse(set(f["train"]) & set(f["test"]))
            self.assertEqual(sorted(f["train"] + f["test"]), sorted(self.lc.STATIONS))
        self.assertEqual([f["criterio"] for f in folds].count(False), 1)  # solo Mallorca es informativo

    def test_paired_ci_zero_for_identical_predictions(self):
        import numpy as np
        ref = np.array([1.0, 2.0, 3.0, 4.0])
        blocks = np.array([0, 0, 1, 1])
        d0, lo, hi = self.lc.paired_delta_ci(ref + 0.1, ref + 0.1, ref, blocks, self.lc.boot_draws(2, reps=50))
        self.assertEqual((d0, lo, hi), (0.0, 0.0, 0.0))

    def test_paired_ci_sign(self):
        import numpy as np
        rng = np.random.default_rng(0)
        ref = rng.uniform(1, 6, 400)
        blocks = np.repeat(np.arange(20), 20)
        d0, lo, hi = self.lc.paired_delta_ci(ref + rng.normal(0, 0.2, 400), ref + rng.normal(0, 0.6, 400), ref,
                                             blocks, self.lc.boot_draws(20, reps=200))
        self.assertLess(d0, 0)
        self.assertLess(hi, 0)

    def test_ahc_is_ols_through_origin(self):
        import numpy as np
        x = np.array([1.0, 2.0, 3.0])
        c = self.lc.ahc_coefficients(x, 0.9 * x, np.zeros(3, int))
        self.assertAlmostEqual(c[0], 0.9, 12)

    def test_formula_hs_ra_value(self):
        import pandas as pd
        d = pd.DataFrame({"TempMin": [10.06], "TempMax": [15.2], "Ra": [31.616142556]})
        expected = 0.0023 * 0.408 * 31.616142556 * (12.63 + 17.8) * (15.2 - 10.06) ** 0.5
        self.assertAlmostEqual(float(self.lc.formula("HS_RA", d).iloc[0]), expected, 12)


if __name__ == "__main__":
    unittest.main()
