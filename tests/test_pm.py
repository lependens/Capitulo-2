import unittest

from openmeteo_et0 import pm


class PenmanMonteithTest(unittest.TestCase):
    def test_fao56_example_18_brussels(self):
        # FAO-56, ejemplo 18 (Bruselas, 6 de julio): ET0 ~ 3,9 mm/dia con G = 0
        et0 = pm.et0_pm(21.5, 12.3, 84, 63, 2.078, 22.07, 50.80, 100, "2026-07-06")
        self.assertAlmostEqual(et0, 3.9, delta=0.15)

    def test_wind_conversion_factor(self):
        self.assertAlmostEqual(pm.WIND_10M_TO_2M, 0.748, places=3)

    def test_more_wind_means_more_et0_in_dry_air(self):
        base = pm.et0_pm(28, 18, 80, 40, 1.0, 20, 39.6, 50, "2026-07-01")
        windy = pm.et0_pm(28, 18, 80, 40, 3.0, 20, 39.6, 50, "2026-07-01")
        self.assertGreater(windy, base)


if __name__ == "__main__":
    unittest.main()
