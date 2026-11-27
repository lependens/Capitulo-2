import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import capture_ecmwf as c  # noqa: E402
from openmeteo_et0.stations import Station  # noqa: E402


class CaptureEcmwfTests(unittest.TestCase):
    def test_add_points_estructura(self):
        st = Station("IB01", "x", 39.01, 1.4397, 120)
        p = c.empty_payload(st)
        c.add_points(p, "2t", 6, [{"lat": 39.0, "lon": 1.5, "value": 290.1, "distance": 7.3}])
        self.assertEqual(p["fields"]["2t"]["6"][0]["value"], 290.1)
        self.assertEqual(p["fields"]["2t"]["6"][0]["distance_km"], 7.3)

    def test_pasos(self):
        self.assertEqual(c.STEPS[0], 0)
        self.assertEqual(c.STEPS[-1], 240)
        self.assertEqual(len(c.STEPS), len(set(c.STEPS)))
        self.assertIn(144, c.STEPS)
        self.assertNotIn(147, c.STEPS)


if __name__ == "__main__":
    unittest.main()
