import gzip
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from openmeteo_et0 import cli, client, metrics, normalize, store
from openmeteo_et0.stations import load_stations


def fake_body(days=("2024-01-01", "2024-01-02"), et0=(1.0, 2.0)):
    daily = {
        "time": list(days),
        "et0_fao_evapotranspiration": list(et0),
        "temperature_2m_max": [15.0, 16.0],
        "temperature_2m_min": [5.0, 6.0],
        "shortwave_radiation_sum": [8.0, 9.0],
        "wind_speed_10m_max": [4.0, 5.0],
    }
    times, rh, ws = [], [], []
    for d in days:
        for h in range(24):
            times.append(f"{d}T{h:02d}:00")
            rh.append(50 + h)  # min 50, max 73, media 61.5
            ws.append(2.0)
    return json.dumps({"elevation": 78.0, "daily": daily,
                       "hourly": {"time": times, "relative_humidity_2m": rh, "wind_speed_10m": ws}}).encode()


class StationsTest(unittest.TestCase):
    def test_nine_stations_and_coordinates(self):
        st = {s.code: s for s in load_stations()}
        self.assertEqual(len(st), 9)
        self.assertNotIn("IB07", st)
        self.assertAlmostEqual(st["IB02"].longitude, 2 + 56 / 60 + 18 / 3600, places=4)
        self.assertAlmostEqual(st["IB02"].latitude, 39 + 41 / 60 + 1 / 3600, places=4)
        self.assertEqual(st["IB02"].altitude_m, 78)

    def test_unknown_station_fails(self):
        with self.assertRaises(ValueError):
            load_stations(codes=["IB99"])


class ClientTest(unittest.TestCase):
    def test_params_archive(self):
        st = load_stations(codes=["IB02"])[0]
        p = client.build_params("archive", st, start="2020-01-01", end="2020-12-31")
        self.assertEqual(p["timezone"], "Europe/Madrid")
        self.assertEqual(p["wind_speed_unit"], "ms")
        self.assertEqual(p["elevation"], "78")
        self.assertIn("et0_fao_evapotranspiration", p["daily"])
        self.assertIn("relative_humidity_2m", p["hourly"])
        self.assertEqual(p["start_date"], "2020-01-01")

    def test_params_forecast_has_no_dates(self):
        st = load_stations(codes=["IB02"])[0]
        p = client.build_params("forecast", st)
        self.assertNotIn("start_date", p)
        self.assertEqual(p["forecast_days"], "16")
        self.assertNotIn("hourly", p)

    def test_archive_needs_dates(self):
        with self.assertRaises(ValueError):
            client.build_params("archive", load_stations(codes=["IB01"])[0])

    def test_error_body_detected(self):
        with self.assertRaises(RuntimeError):
            client.check_body(b'{"error": true, "reason": "bad variable"}')


class StoreTest(unittest.TestCase):
    def test_save_verify_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            raw = Path(t)
            now = datetime(2026, 1, 1, 4, 0, 0, tzinfo=timezone.utc)
            body = fake_body()
            p = store.save_raw("archive", "IB02", "2024-01-01_2024-01-02", "http://x", body, raw, now=now)
            self.assertTrue(p.exists())
            self.assertEqual(store.load_raw(p.relative_to(raw), raw), body)
            self.assertEqual(store.verify(raw), [])
            self.assertTrue(store.already_fetched("archive", "IB02", "2024-01-01_2024-01-02", raw))
            with self.assertRaises(FileExistsError):
                store.save_raw("archive", "IB02", "2024-01-01_2024-01-02", "http://x", body, raw, now=now)
            # corrupcion detectada
            with gzip.open(p, "wb") as f:
                f.write(b"{}")
            self.assertEqual(len(store.verify(raw)), 1)


class NormalizeTest(unittest.TestCase):
    def test_humidity_aggregated_from_hourly(self):
        rows, elev = normalize.parse_response(fake_body())
        r = rows["2024-01-01"]
        self.assertEqual(elev, 78.0)
        self.assertEqual(r["rh_min_pct"], 50)
        self.assertEqual(r["rh_max_pct"], 73)
        self.assertAlmostEqual(r["rh_mean_pct"], 61.5)
        self.assertEqual(r["rh_hours"], 24)
        self.assertEqual(r["wind10_mean_ms"], 2.0)
        self.assertEqual(r["et0_om_mm"], 1.0)

    def test_null_values_stay_empty(self):
        body = json.loads(fake_body())
        body["daily"]["et0_fao_evapotranspiration"][0] = None
        rows, _ = normalize.parse_response(json.dumps(body).encode())
        self.assertEqual(rows["2024-01-01"]["et0_om_mm"], "")

    def test_build_processed_latest_fetch_wins(self):
        with tempfile.TemporaryDirectory() as t:
            raw, out = Path(t) / "raw", Path(t) / "out"
            tag = "2024-01-01_2024-01-02"
            store.save_raw("archive", "IB02", tag, "u", fake_body(et0=(1.0, 2.0)), raw,
                           now=datetime(2026, 1, 1, tzinfo=timezone.utc))
            store.save_raw("archive", "IB02", tag, "u", fake_body(et0=(1.5, 2.5)), raw,
                           now=datetime(2026, 2, 1, tzinfo=timezone.utc))
            path, n = normalize.build_processed("archive", raw, out)
            self.assertEqual(n, 2)
            text = path.read_text(encoding="utf-8")
            self.assertIn("1.5", text)
            self.assertNotIn(",1.0,", text)

    def test_forecast_lead_days(self):
        with tempfile.TemporaryDirectory() as t:
            raw, out = Path(t) / "raw", Path(t) / "out"
            store.save_raw("forecast", "IB02", "2024-01-01", "u", fake_body(), raw,
                           now=datetime(2024, 1, 1, 4, tzinfo=timezone.utc))
            rows = normalize.build_forecast(raw)
            self.assertEqual([r["lead_days"] for r in rows], [0, 1])


class CliTest(unittest.TestCase):
    def test_year_chunks(self):
        self.assertEqual(cli.year_chunks("2020-03-01", "2021-02-10"),
                         [("2020-03-01", "2020-12-31"), ("2021-01-01", "2021-02-10")])

    def test_backfill_is_idempotent_and_reports_failures(self):
        calls = []

        def fetcher(url):
            calls.append(url)
            if "IB03" in url or "latitude=39.5458" in url:
                raise RuntimeError("boom")
            return fake_body()

        with tempfile.TemporaryDirectory() as t:
            raw = Path(t)
            f1 = cli.run_backfill("archive", "2024-01-01", "2024-12-31", ["IB02", "IB03"], raw_dir=raw,
                                  fetcher=fetcher, sleep=lambda s: None)
            self.assertEqual(len(f1), 1)
            n = len(calls)
            f2 = cli.run_backfill("archive", "2024-01-01", "2024-12-31", ["IB02"], raw_dir=raw,
                                  fetcher=fetcher, sleep=lambda s: None)
            self.assertEqual(f2, [])
            self.assertEqual(len(calls), n)  # IB02 ya descargado: no se vuelve a pedir

    def test_daily_forecast_once_per_day(self):
        with tempfile.TemporaryDirectory() as t:
            raw = Path(t)
            now = datetime(2026, 5, 1, 4, tzinfo=timezone.utc)
            n = []
            fetcher = lambda url: (n.append(1), fake_body())[1]
            cli.run_daily_forecast(["IB01"], raw_dir=raw, fetcher=fetcher, sleep=lambda s: None, now=now)
            cli.run_daily_forecast(["IB01"], raw_dir=raw, fetcher=fetcher, sleep=lambda s: None, now=now)
            self.assertEqual(len(n), 1)

    def test_fetch_retries_then_fails(self):
        import urllib.error
        from unittest import mock
        sleeps = []
        err = urllib.error.HTTPError("u", 429, "Too Many", {}, None)
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(RuntimeError):
                client.fetch("http://x", retries=2, backoff=1, sleep=sleeps.append)
        self.assertEqual(sleeps, [1, 2])


class MetricsTest(unittest.TestCase):
    def test_basic_metrics(self):
        m = metrics.compute([(2.0, 1.0), (3.0, 3.0), (3.0, 5.0)])
        self.assertEqual(m["n"], 3)
        self.assertAlmostEqual(m["bias"], (1 + 0 - 2) / 3)
        self.assertAlmostEqual(m["rmse"], ((1 + 0 + 4) / 3) ** 0.5)
        self.assertAlmostEqual(m["mae"], 1.0)
        sst = (1 - 3) ** 2 + 0 + (5 - 3) ** 2
        self.assertAlmostEqual(m["r2"], 1 - 5 / sst)

    def test_r2_null_when_constant_reference(self):
        m = metrics.compute([(1.0, 2.0), (3.0, 2.0)])
        self.assertEqual(m["r2"], "")
        self.assertEqual(m["r2_status"], "sst_zero")

    def test_djf_assigns_december_to_next_year(self):
        self.assertEqual(metrics.season_key("2020-12-15"), (2021, "DJF"))
        self.assertEqual(metrics.season_key("2021-01-15"), (2021, "DJF"))
        self.assertEqual(metrics.season_key("2021-07-01"), (2021, "JJA"))

    def test_verdicts(self):
        th = json.loads((Path(__file__).resolve().parents[1] / "config" / "thresholds.json").read_text())
        self.assertEqual(metrics.verdict({"rmse": 0.55, "bias": 0.05}, 0.8, th), "COMPETITIVO")
        self.assertEqual(metrics.verdict({"rmse": 0.55, "bias": 0.05}, 1.2, th), "UTILIZABLE_NO_DIFERENCIAL")
        self.assertEqual(metrics.verdict({"rmse": 0.80, "bias": 0.0}, 0.9, th), "UTILIZABLE_NO_DIFERENCIAL")
        self.assertEqual(metrics.verdict({"rmse": 1.10, "bias": 0.0}, 1.5, th), "NO_COMPETITIVO")

    def test_cohort_hash_order_independent(self):
        a = [{"station_code": "IB01", "date": "2020-01-01"}, {"station_code": "IB02", "date": "2020-01-01"}]
        self.assertEqual(metrics.cohort_hash(a), metrics.cohort_hash(list(reversed(a))))


if __name__ == "__main__":
    unittest.main()
