"""Tests del estudio 03.1.2 (sensor local + red SIAR): reglas de construccion de la red y escenarios.

Reglas que se comprueban (config/thresholds_v3_1_2.json -> network_features):
- exclusion de la propia estacion (y de la estacion de validacion en la validacion interna, para TODAS las filas);
- PM y distancias ordenadas por cercania, nunca por nombre de estacion;
- pool incompleto (relleno con la ultima disponible) y pool vacio (NaN).
"""
import importlib.util
import sys
import unittest
from pathlib import Path

HAVE = all(importlib.util.find_spec(m) for m in ("numpy", "pandas", "sklearn"))
ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "studies/03_1_2_loso_sensor_red"
HAVE_DATA = (ROOT / "data/reference/reference_2004_2019.csv").exists()


def _synthetic():
    """5 estaciones en una recta; el orden alfabetico (A..E) NO coincide con el orden por distancia desde X."""
    import numpy as np
    import pandas as pd
    pos = {"X": 0.0, "E": 1.0, "A": 2.0, "D": 3.0, "B": 5.0, "C": 8.0}
    dist = {(a, b): abs(pos[a] - pos[b]) for a in pos for b in pos}
    dates = ["2020-01-01", "2020-01-02", "2020-01-03"]
    # PM = valor que identifica la estacion; la propia X lleva un centinela que nunca debe aparecer
    pm = pd.DataFrame({s: [v] * 3 for s, v in {"X": 999.0, "E": 1.0, "A": 2.0, "D": 3.0, "B": 5.0, "C": 8.0}.items()},
                      index=dates)
    pm.loc["2020-01-02", ["E", "A"]] = np.nan          # dia 2: faltan las dos mas cercanas
    pm.loc["2020-01-03", ["E", "A", "D", "B"]] = np.nan  # dia 3: solo queda C
    return pos, dist, pm, dates


@unittest.skipUnless(HAVE, "requiere numpy, pandas y scikit-learn")
class NetworkRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(STUDY))
        import network
        cls.nw = network

    def test_own_station_never_in_pool(self):
        _, dist, pm, dates = _synthetic()
        pool = ["X", "A", "B", "C", "D", "E"]        # aunque la propia estacion venga en el pool, se excluye
        f = self.nw.network_features(["X"] * 3, dates, pool, pm, dist)
        for c in ("PM_1", "PM_2", "PM_3", "IDW_PM"):
            self.assertFalse((f[c] == 999.0).any(), c)
        self.assertTrue((f[["d1_km", "d2_km", "d3_km"]] > 0).all().all())
        self.assertNotIn("X", self.nw.ordered_pool("X", pool, dist))

    def test_validation_station_out_of_every_row(self):
        _, dist, pm, dates = _synthetic()
        pool = ["A", "B", "C", "D", "E"]
        # filas de varias estaciones (incluida la de validacion E); E fuera del pool de todas
        st = ["X", "A", "E", "B"]
        f = self.nw.network_features(st, ["2020-01-01"] * 4, pool, pm, dist, exclude=("E",))
        for c in ("PM_1", "PM_2", "PM_3"):
            self.assertFalse((f[c] == 1.0).any(), f"{c} usa la estacion de validacion")
        for s in st:
            self.assertNotIn("E", self.nw.ordered_pool(s, pool, dist, exclude=("E",)))
            self.assertNotIn(s, self.nw.ordered_pool(s, pool, dist, exclude=("E",)))

    def test_ordered_by_distance_not_by_name(self):
        _, dist, pm, dates = _synthetic()
        f = self.nw.network_features(["X"], ["2020-01-01"], ["A", "B", "C", "D", "E"], pm, dist).iloc[0]
        # por distancia desde X: E (1), A (2), D (3); por nombre seria A, B, C
        self.assertEqual([f.PM_1, f.PM_2, f.PM_3], [1.0, 2.0, 3.0])
        self.assertEqual([f.d1_km, f.d2_km, f.d3_km], [1.0, 2.0, 3.0])
        self.assertLessEqual(f.d1_km, f.d2_km)
        self.assertLessEqual(f.d2_km, f.d3_km)

    def test_invariant_to_station_names(self):
        """Renombrar las estaciones (permutacion de codigos) no cambia ninguna columna: no hay indexado por nombre."""
        _, dist, pm, dates = _synthetic()
        ren = {"A": "Q", "B": "M", "C": "Z", "D": "K", "E": "W", "X": "X"}
        dist2 = {(ren[a], ren[b]): v for (a, b), v in dist.items()}
        pm2 = pm.rename(columns=ren)
        f1 = self.nw.network_features(["X"] * 3, dates, list("ABCDE"), pm, dist)
        f2 = self.nw.network_features(["X"] * 3, dates, [ren[s] for s in "ABCDE"], pm2, dist2)
        self.assertTrue(f1.equals(f2))

    def test_available_by_day_and_incomplete_pool(self):
        _, dist, pm, dates = _synthetic()
        f = self.nw.network_features(["X"] * 3, dates, list("ABCDE"), pm, dist)
        # dia 2: sin E ni A -> D, B, C
        self.assertEqual(list(f.loc[1, ["PM_1", "PM_2", "PM_3"]]), [3.0, 5.0, 8.0])
        # dia 3: solo C -> se repite la ultima disponible
        self.assertEqual(list(f.loc[2, ["PM_1", "PM_2", "PM_3"]]), [8.0, 8.0, 8.0])
        self.assertEqual(list(f.loc[2, ["d1_km", "d2_km", "d3_km"]]), [8.0, 8.0, 8.0])
        self.assertEqual(f.loc[2, "IDW_PM"], 8.0)
        self.assertEqual(list(f.n_pool), [5, 3, 1])

    def test_empty_pool_is_nan(self):
        import numpy as np
        _, dist, pm, dates = _synthetic()
        f = self.nw.network_features(["X"], ["2020-01-03"], ["A", "B"], pm, dist)
        self.assertTrue(np.isnan(f.loc[0, ["IDW_PM", "PM_1", "PM_3", "d1_km"]].astype(float)).all())
        f = self.nw.network_features(["X"], ["2020-01-01"], ["X"], pm, dist)   # pool = solo la propia
        self.assertTrue(np.isnan(f.loc[0, "IDW_PM"]))

    def test_idw_power_2(self):
        _, dist, pm, dates = _synthetic()
        f = self.nw.network_features(["X"], ["2020-01-01"], ["E", "A"], pm, dist)
        w = [1 / 1 ** 2, 1 / 2 ** 2]
        self.assertAlmostEqual(f.loc[0, "IDW_PM"], (w[0] * 1 + w[1] * 2) / sum(w), 12)


@unittest.skipUnless(HAVE and HAVE_DATA, "requiere numpy, pandas, scikit-learn y los datos del repo")
class ScenarioRealDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(STUDY))
        import design
        cls.ds = design
        cls.lc = design.lc

    def test_cell_counts_match_plan(self):
        cells = self.ds.all_cells()
        rh = [c for c in cells if c[3] in ("Ridge", "HGB")]
        ann = [c for c in cells if c[3] == "ANN_M"]
        self.assertEqual(len(rh) * 12, 576)
        self.assertEqual(len(ann) * 12, 204)

    def test_cohorts(self):
        b = self.ds.scenario_frame("B")
        c = self.ds.scenario_frame("C")
        self.assertEqual(int(b.cohort.sum()), 19251)
        self.assertEqual(int(c.cohort.sum()), 19216)

    def test_c_uses_day_d_sensor_and_d1_target(self):
        import numpy as np
        b = self.ds.scenario_frame("B").set_index(["station_code", "date"])
        c = self.ds.scenario_frame("C")
        r = c[c.cohort].iloc[100]
        d = (np.datetime64(r.date) - np.timedelta64(1, "D")).astype(str)
        self.assertEqual(r.net_date, d)
        self.assertEqual(r.TempMax, b.loc[(r.station_code, d), "TempMax"])
        self.assertEqual(r.Ra, b.loc[(r.station_code, d), "Ra"])
        self.assertEqual(r.Ra_next, b.loc[(r.station_code, r.date), "Ra"])
        self.assertEqual(r.pm, b.loc[(r.station_code, r.date), "pm"])
        X = self.ds.features(c[c.cohort].iloc[[100]], "C", "S", "HG_RS")
        self.assertEqual(X.shape[1], 3)                    # [(Tmin+Tmax)/2, Rs] + Ra(d+1)

    def test_bayer_uses_previous_day_network(self):
        f = self.ds.scenario_frame("Bayer")
        r = f.iloc[5000]
        self.assertEqual(str((__import__("pandas").Timestamp(r.date) - __import__("pandas").Timedelta(days=1)).date()),
                         r.net_date)

    def test_test_rows_match_031_idw_and_nearest(self):
        """En TEST, IDW_PM y PM_1 de la red coinciden con los comparadores del 03.1 (IDW y estacion mas cercana)."""
        import numpy as np
        fold = [f for f in self.lc.build_folds() if f["id"] == "F1_IB05"][0]
        fr = self.ds.scenario_frame("B")
        te = fr[fr.cohort & fr.station_code.isin(fold["test"])]
        _, net = self.ds.build_X(te, "B", "S_R1", "VALIANTZAS", fold["train"])
        near, idw, _ = self.lc.pm_nearest_and_idw(self.ds.panel(), te, fold["train"], self.ds.dist())
        np.testing.assert_allclose(net.IDW_PM.to_numpy(), idw, rtol=0, atol=1e-12)
        np.testing.assert_allclose(net.PM_1.to_numpy(), near, rtol=0, atol=0)

    def test_training_rows_exclude_self_and_validation(self):
        """En entrenamiento, el pool de cada fila tiene como mucho len(train)-1 estaciones, y -2 con exclusion."""
        fold = [f for f in self.lc.build_folds() if f["id"] == "F1_IB01"][0]
        fr = self.ds.scenario_frame("B")
        tr = fr[fr.dev & fr.target_ok & fr.station_code.isin(fold["train"])].iloc[:3000]
        _, n0 = self.ds.build_X(tr, "B", "S_R3", "HS_RA", fold["train"])
        _, n1 = self.ds.build_X(tr, "B", "S_R3", "HS_RA", fold["train"], exclude=("IB02",))
        self.assertLessEqual(n0.n_pool.max(), len(fold["train"]) - 1)
        self.assertLessEqual(n1.n_pool.max(), len(fold["train"]) - 1)
        self.assertLessEqual(n1[tr.station_code.to_numpy() != "IB02"].n_pool.max(), len(fold["train"]) - 2)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(HAVE, "requiere numpy y pandas")
class CoastDistanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(STUDY))
        import coast
        cls.coast = coast

    def test_distance_to_meridian_segment(self):
        import numpy as np
        lat, lon = 39.5, 3.0
        line = np.array([[3.1, 39.0], [3.1, 40.0]])         # costa recta 0,1 grados al este
        km = self.coast.min_distance_km(lat, lon, [line])
        expect = float(self.coast.lc.haversine_km(lat, lon, lat, 3.1))
        self.assertAlmostEqual(km, expect, delta=0.01)

    def test_nearest_vertex_and_far_lines_ignored(self):
        lat, lon = 39.5, 3.0
        import numpy as np
        a = np.array([[3.0, 39.6], [3.2, 39.8]])            # vertice mas cercano a 0,1 grados al norte
        far = np.array([[20.0, 10.0], [21.0, 11.0]])
        km = self.coast.min_distance_km(lat, lon, [far, a])
        self.assertAlmostEqual(km, float(self.coast.lc.haversine_km(lat, lon, 39.6, 3.0)), delta=0.01)
