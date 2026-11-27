"""Tests del estudio 03.3 (Open-Meteo + ML + red del dia; objetivo residual y control de dominio).

Reglas de construccion (prompt del 03.3 y config/thresholds_v3_3.json):
(a) la estacion evaluada nunca esta en el pool de red;
(b) en la validacion interna, la estacion de validacion sale del pool de TODAS las filas;
(c) en residuo_IDW, el residuo de cada estacion de entrenamiento viene de un HGB-S0 entrenado sin ella ni la evaluada;
(d) objetivo residual: prediccion = ET0_OM + modelo;
(e) recorte de altitud al rango de entrenamiento de la particion.
Ademas: cohorte comun (interseccion), control de dominio, regla de interpretacion literal y guion de Kaggle.
"""
import importlib.util
import re
import subprocess
import sys
import unittest
from pathlib import Path

HAVE = all(importlib.util.find_spec(m) for m in ("numpy", "pandas", "sklearn"))
ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "studies/03_3_om_red_residual"
HAVE_DATA = (ROOT / "data/reference/reference_2004_2019.csv").exists()


def _load(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _fold(lc, fid):
    return [f for f in lc.build_folds() if f["id"] == fid][0]


class KaggleScript033Test(unittest.TestCase):
    def test_script_syntax_cap_and_pinned_versions(self):
        sh = (STUDY / "kaggle_session.sh").read_text(encoding="utf-8")
        self.assertIn("--max-hours 8", sh)
        self.assertIn("03_2_loso_openmeteo_ml/requirements.txt", sh.replace('"$D32/', "03_2_loso_openmeteo_ml/"))
        self.assertIn("check_env.py", sh)
        r = subprocess.run(["bash", "-n", str(STUDY / "kaggle_session.sh")], capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_recovery_pattern_only_03_3_cells(self):
        sh = (STUDY / "kaggle_session.sh").read_text(encoding="utf-8")
        m = re.search(r'pat = re.compile\(r"(.+?)"\s*\n\s*r"(.+?)"\)', sh)
        pat = re.compile(m.group(1) + m.group(2))
        for ok in ("F1_IB01__S0_res__ANN_M.json.gz", "F2_Mallorca_informativo__S0+R1__HGB.json.gz",
                   "F1_IB05__anidado_IB02__HGB.json.gz", "F2_Ibiza__S0+R1_ayer__HGB.json.gz"):
            self.assertTrue(pat.match(ok), ok)
        for bad in ("F1_IB01__S0__ANN_M.json.gz", "F1_IB01__S0__RF.json.gz",
                    "F1_IB01__B__S_R1__HS_RA__HGB.json.gz"):
            self.assertFalse(pat.match(bad), bad)


@unittest.skipUnless(HAVE and HAVE_DATA, "requiere numpy, pandas, scikit-learn y los datos")
class Study033Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = _load("estudio03_3_run", STUDY / "run.py")
        cls.rp = _load("estudio03_3_report", STUDY / "report.py")
        cls.lc, cls.nw = cls.r.lc, cls.r.nw
        cls.df = cls.r.panel()

    # ---------------------------------------------------------------- protocolo
    def test_thresholds_frozen_and_cells_match_plan(self):
        import json
        thr = json.loads((ROOT / "config/thresholds_v3_3.json").read_text(encoding="utf-8"))
        self.assertEqual(thr["status"], "CONGELADO")
        m = thr["methods"]
        self.assertEqual(set(m["Ridge"]["arms"]), {a for a, ms in self.r.ARMS.items() if "Ridge" in ms})
        self.assertEqual(set(m["ANN_M"]["arms"]), {a for a, ms in self.r.ARMS.items() if "ANN_M" in ms})
        self.assertTrue(all("HGB" in ms for ms in self.r.ARMS.values()))
        self.assertEqual(self.r.W_GRID, [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
        cells = self.r.all_cells()
        count = lambda pred: sum(1 for c in cells if pred(c))  # noqa: E731
        self.assertEqual(count(lambda c: c[2] == "ANN_M"), 36)          # 3 brazos x 12 particiones
        self.assertEqual(count(lambda c: c[2] == "Ridge"), 24)
        self.assertEqual(count(lambda c: c[2] == "HGB" and not c[1].startswith("anidado")), 84)
        self.assertEqual(count(lambda c: c[1].startswith("anidado")),
                         sum(len(f["train"]) for f in self.lc.build_folds()))
        self.assertEqual(self.lm_grid(), [{"learning_rate": a, "max_leaf_nodes": b} for a in (0.03, 0.1)
                                          for b in (15, 31)])

    def lm_grid(self):
        return self.r.lm.GRIDS["HGB"]

    def test_folds_identical_to_03_2(self):
        import json
        f32 = json.loads((ROOT / "studies/03_2_loso_openmeteo_ml/results/folds.json").read_text())["folds"]
        self.assertEqual(f32, self.lc.build_folds())

    def test_s0_s2_features_identical_to_03_2(self):
        import numpy as np
        rows = self.df.iloc[:500]
        np.testing.assert_array_equal(self.r.arm_X("S0_res", rows), self.r.r32.features("S0", rows))
        self.assertEqual(self.r.feature_names("S2+R1")[:-2], self.r.r32.feature_names("S2"))
        self.assertNotIn("altitude_m", self.r.feature_names("S0_sin_alt"))
        self.assertEqual(len(self.r.feature_names("S0_res_sin_alt")), 12)

    # ---------------------------------------------------------------- (a) evaluada fuera del pool
    def test_a_evaluated_station_never_in_pool(self):
        import numpy as np
        for fid in ("F1_IB01", "F2_Ibiza"):
            f = _fold(self.lc, fid)
            P = self.r.prepare(f, "S0+R1", max_train_rows=500)
            te = P["test"]
            # IDW de TEST = comparador IDW del 03.1/03.2 (pool = estaciones de entrenamiento)
            _, idw, _ = self.lc.pm_nearest_and_idw(self.df, te, f["train"], self.r.dist())
            np.testing.assert_allclose(P["Xt"][:, -2], idw, rtol=0, atol=1e-12)
            # y la estacion evaluada no entra: con su PM cambiada a un centinela, la red no cambia
            pmw = self.r.pmw().copy()
            pmw[f["test"]] = 999.0
            alt = self.nw.network_features(te.station_code.to_numpy(), te.date.to_numpy(), f["train"] + f["test"],
                                           pmw, self.r.dist())
            self.assertFalse((alt.IDW_PM.to_numpy() >= 999.0).any())
            self.assertFalse(set(P["train"].station_code) & set(f["test"]))

    def test_a_training_rows_exclude_own_station(self):
        import numpy as np
        f = _fold(self.lc, "F1_IB03")
        P = self.r.prepare(f, "S0+R1", max_train_rows=800)
        tr = P["train"]
        pmw = self.r.pmw()
        dist = self.r.dist()
        for i in range(0, len(tr), 97):
            s, d = tr.station_code.iloc[i], tr.date.iloc[i]
            pool = [t for t in f["train"] if t != s and np.isfinite(pmw.loc[d, t])]
            w = np.array([1 / dist[(s, t)] ** 2 for t in pool])
            exp = float(np.sum(w * pmw.loc[d, pool].to_numpy()) / w.sum())
            self.assertAlmostEqual(P["X"][i, -2], exp, places=10)

    # ---------------------------------------------------------------- (b) validacion fuera del pool de todas las filas
    def test_b_validation_station_out_of_every_row(self):
        import numpy as np
        f = _fold(self.lc, "F1_IB01")
        P = self.r.prepare(f, "S0+R1", max_train_rows=800)
        tr, pmw, dist = P["train"], self.r.pmw(), self.r.dist()
        v = "IB05"
        Xi = P["X_inner"][v]
        for i in range(0, len(tr), 53):
            s, d = tr.station_code.iloc[i], tr.date.iloc[i]
            pool = [t for t in f["train"] if t not in (s, v) and np.isfinite(pmw.loc[d, t])]
            w = np.array([1 / dist[(s, t)] ** 2 for t in pool])
            exp = float(np.sum(w * pmw.loc[d, pool].to_numpy()) / w.sum())
            self.assertAlmostEqual(Xi[i, -2], exp, places=10)
        self.assertEqual(sorted(P["X_inner"]), sorted(f["train"]))

    def test_select_and_fit_net_equals_select_and_fit_without_network(self):
        import numpy as np
        rng = np.random.default_rng(0)
        X = rng.normal(size=(300, 4))
        y = X @ np.array([1.0, -2.0, 0.5, 0.0]) + rng.normal(scale=0.1, size=300)
        g = np.repeat(["A", "B", "C"], 100)
        Xt = rng.normal(size=(20, 4))
        a = self.r.lm.select_and_fit("Ridge", X, y, g, np.zeros(300), Xt)
        b = self.r.select_and_fit_net("Ridge", X, {s: X for s in "ABC"}, g, y, Xt)
        self.assertEqual(a["params"], b["params"])
        self.assertEqual([c["mean_rmse"] for c in a["cv"]], [c["mean_rmse"] for c in b["cv"]])
        np.testing.assert_array_equal(a["pred"], b["pred"])

    def test_r1_ayer_uses_previous_day(self):
        import numpy as np
        f = _fold(self.lc, "F1_IB10")
        te = self.lc.test_cohort(self.df)
        te = te[te.station_code == "IB10"].iloc[:50].reset_index(drop=True)
        ayer = self.r.network(te, "S0+R1_ayer", f["train"])
        prev = te.copy()
        prev["date"] = self.r.shift_dates(te.date, -1)
        hoy = self.r.network(prev, "S0+R1", f["train"])
        np.testing.assert_array_equal(ayer.IDW_PM.to_numpy(), hoy.IDW_PM.to_numpy())

    # ---------------------------------------------------------------- (c) residuos anidados
    def test_c_nested_model_excludes_s_and_evaluated(self):
        for fid in ("F1_IB01", "F2_Menorca"):
            f = _fold(self.lc, fid)
            for s in f["train"][:3]:
                tr, X, pr, Xp, train = self.r.nested_rows(f, s, max_train_rows=500)
                self.assertNotIn(s, set(tr.station_code))
                self.assertFalse(set(tr.station_code) & set(f["test"]))
                self.assertEqual(set(pr.station_code), {s})
                self.assertLessEqual(tr.date.max(), self.lc.DEV[1])
                self.assertEqual(train, [t for t in f["train"] if t != s])

    def test_c_residual_idw_uses_each_station_own_nested_residual(self):
        """Con residuos sinteticos conocidos por estacion, la correccion es su IDW (potencia 2) y nunca la propia."""
        import numpy as np
        f = _fold(self.lc, "F1_IB01")
        te = self.lc.test_cohort(self.df)
        te = te[te.station_code == "IB01"].iloc[:30].reset_index(drop=True)
        nested = []
        for k, s in enumerate(f["train"]):
            rows = self.df[(self.df.station_code == s) & self.df.date.isin(te.date) & self.df.target_ok]
            nested.append({"station_code": rows.station_code.tolist(), "date": rows.date.tolist(),
                           "pred": (rows.ET0_PM_FAO56_V1 - (k + 1)).tolist()})     # residuo = k + 1
        restab = self.rp.residual_table(nested, self.df)
        pred, corr = self.rp.residuo_idw(te, np.zeros(len(te)), f, restab)
        dist = self.r.dist()
        w = np.array([1 / dist[("IB01", s)] ** 2 for s in f["train"]])
        exp = float(np.sum(w * np.arange(1, len(f["train"]) + 1)) / w.sum())
        full = np.array([restab.loc[d].notna().all() for d in te.date])
        np.testing.assert_allclose(corr[full], exp, atol=1e-9)

    # ---------------------------------------------------------------- (d) objetivo residual
    def test_d_residual_target_and_prediction(self):
        import numpy as np
        rows = self.df[self.df.target_ok & np.isfinite(self.df.et0_om_mm)].iloc[:200]
        y = self.r.target("S0_res", rows)
        np.testing.assert_allclose(y, rows.ET0_PM_FAO56_V1 - rows.et0_om_mm)
        np.testing.assert_allclose(self.r.to_pm("S0_res", rows, y), rows.ET0_PM_FAO56_V1)
        np.testing.assert_allclose(self.r.to_pm("S0_res_sin_alt", rows, np.zeros(200)), rows.et0_om_mm)
        np.testing.assert_allclose(self.r.to_pm("S0_sin_alt", rows, np.ones(200)), 1.0)
        np.testing.assert_allclose(self.r.target("S0+R1", rows), rows.ET0_PM_FAO56_V1)

    # ---------------------------------------------------------------- (e) recorte de altitud
    def test_e_altitude_clipped_to_training_range(self):
        import numpy as np
        j = self.r.r32.feature_names("S0").index("altitude_m")
        f = _fold(self.lc, "F1_IB01")
        P = self.r.prepare(f, "S0_alt_recortada", max_train_rows=500)
        self.assertEqual(P["alt_clip"], (4.0, 82.0))
        self.assertTrue((P["Xt"][:, j] == 82.0).all())                 # IB01 (120 m) -> 82 m
        self.assertTrue((P["X"][:, j] <= 82.0).all() and (P["X"][:, j] >= 4.0).all())
        f6 = _fold(self.lc, "F1_IB06")
        P6 = self.r.prepare(f6, "S0_alt_recortada", max_train_rows=500)
        self.assertEqual(P6["alt_clip"][0], 7.0)
        self.assertTrue((P6["Xt"][:, j] == 7.0).all())                 # IB06 (4 m) -> 7 m
        P0 = self.r.prepare(f, "S0_sin_alt", max_train_rows=500)
        self.assertEqual(P0["X"].shape[1], 12)

    # ---------------------------------------------------------------- informe
    def test_common_cohort_drops_rows_from_all_methods(self):
        import numpy as np
        import pandas as pd
        pred = pd.DataFrame({"fold": "F1_X", "scheme": "F1_loso", "station_code": ["A"] * 4,
                             "date": ["2020-01-0%d" % i for i in range(1, 5)], "pm": [1.0] * 4,
                             "d1_km": 1.0, "n_pool": 1, "m1": [1, 2, np.nan, 4.0], "m2": [1, 2, 3, 4.0]})
        meth = self.rp.methods(pred)
        pred["en_cohorte"] = np.isfinite(pred[meth].to_numpy()).all(1)
        d = self.rp.scopes(pred)["F1"]
        self.assertEqual(len(d), 3)
        self.assertEqual(self.rp.methods(pred), ["m1", "m2"])

    def test_ci95_equals_loso_common(self):
        import numpy as np
        rng = np.random.default_rng(1)
        ref = rng.gamma(2, 1.5, 1000)
        a, b = ref + rng.normal(0, 0.4, 1000), ref + rng.normal(0, 0.45, 1000)
        blocks = np.repeat(np.arange(20), 50)
        draws = self.lc.boot_draws(20)
        d0, lo, hi = self.lc.paired_delta_ci(a, b, ref, blocks, draws)
        e0, elo, ehi, lo9, hi9 = self.rp.paired_delta_ci2(a, b, ref, blocks, draws)
        self.assertEqual((d0, lo, hi), (e0, elo, ehi))
        self.assertTrue(elo <= lo9 <= hi9 <= ehi)

    def test_domain_flags(self):
        import numpy as np
        tr = np.column_stack([np.linspace(0, 100, 1001), np.array([4.0, 82.0] * 500 + [40.0])])
        te = np.array([[0.1, 120.0], [50.0, 50.0], [99.9, 4.0], [100.0, 3.0]])
        f = self.rp.domain_flags(tr, te, ["x", "altitude_m"])
        self.assertEqual(f.x.tolist(), [True, False, True, True])       # fuera de [p0.5, p99.5] = [0.5, 99.5]
        self.assertEqual(f.altitude_m.tolist(), [True, False, False, True])

    def test_interpretation_rule_cases(self):
        import pandas as pd
        rp = self.rp

        def pc(d1, ci1, d2, ci2, f2i=0.0, f2m=0.0):
            rows = []
            for sc, b, d, ci in (("F1", rp.HGB_S0, d1, ci1), ("F1", rp.IDW, d2, ci2),
                                 ("F2_Ibiza", rp.HGB_S0, f2i, (f2i - .01, f2i + .01)),
                                 ("F2_Menorca", rp.HGB_S0, f2m, (f2m - .01, f2m + .01))):
                rows.append({"scope": sc, "A": rp.PRIMARY_L3, "B": b, "rmse_A": .4, "rmse_B": .4, "delta_rmse": d,
                             "ci95_lo": ci[0], "ci95_hi": ci[1], "ci90_lo": ci[0], "ci90_hi": ci[1]})
            return pd.DataFrame(rows)

        c = lambda *a: rp.l3_case(pc(*a), rp.PRIMARY_L3)["caso"]  # noqa: E731
        self.assertEqual(c(-.06, (-.08, -.04), -.07, (-.09, -.05)), 1)
        self.assertEqual(c(-.06, (-.08, -.04), -.07, (-.09, -.05), .08), 2)
        self.assertEqual(c(-.03, (-.05, -.01), -.07, (-.09, -.05)), 3)
        r = rp.l3_case(pc(-.06, (-.08, -.04), -.01, (-.03, .01)), rp.PRIMARY_L3)   # hueco: aclaracion previa
        self.assertEqual((r["caso"], r["caso_por_texto_literal"]), (3, False))
        self.assertEqual(c(-.01, (-.03, .01), .02, (-.01, .05)), 4)


if __name__ == "__main__":
    unittest.main()
