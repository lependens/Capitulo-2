"""Tests del estudio 03.2 (Open-Meteo corregido con ML, LOSO). Se omiten si faltan numpy/pandas/sklearn."""
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HAVE = all(importlib.util.find_spec(m) for m in ("numpy", "pandas", "sklearn"))
ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "studies/03_loso_openmeteo_ml"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class KaggleScriptTest(unittest.TestCase):
    """No necesita librerias: comprueba el guion de Kaggle."""

    def test_script_syntax_and_cap(self):
        sh = (STUDY / "kaggle_session.sh").read_text(encoding="utf-8")
        self.assertIn("--max-hours 8", sh)
        self.assertNotIn("03_1_loso_inputs_siar", sh)  # no toca nada del 03.1
        r = subprocess.run(["bash", "-n", str(STUDY / "kaggle_session.sh")], capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_recovery_pattern_ignores_03_1_cells(self):
        sh = (STUDY / "kaggle_session.sh").read_text(encoding="utf-8")
        pat = re.compile(re.search(r'pat = re.compile\(r"(.+?)"\)', sh).group(1))
        self.assertTrue(pat.match("F1_IB01__S0__RF.json.gz"))
        self.assertTrue(pat.match("F2_Mallorca_informativo__S0_coord__ANN_M.json.gz"))
        self.assertFalse(pat.match("F1_IB01__HS_RA__principal__RF.json.gz"))
        self.assertFalse(pat.match("F1_IB01__VALIANTZAS__secundaria__ANN_S.json.gz"))


@unittest.skipUnless(HAVE, "requiere numpy, pandas y scikit-learn")
class Study032Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = _load("estudio03_2_run_test", STUDY / "run.py")
        cls.df = cls.r.lc.load_panel()

    def test_thresholds_frozen_values(self):
        thr = json.loads((ROOT / "config/thresholds_v3.json").read_text(encoding="utf-8"))
        self.assertEqual(thr["models"]["HGB_primario"]["max_iter"], 500)
        self.assertEqual(thr["statistics"]["practical_threshold_mm_dia"], 0.05)
        self.assertEqual(self.r.lm.GRIDS["HGB"], [{"learning_rate": a, "max_leaf_nodes": b}
                                                    for a in (0.03, 0.1) for b in (15, 31)])
        self.assertEqual(self.r.lm.GRIDS["RF"], [{"min_samples_leaf": 5}, {"min_samples_leaf": 20}])

    def test_scenarios_features(self):
        r = self.r
        self.assertEqual(len(r.feature_names("S0")), 13)
        self.assertNotIn("lat", r.feature_names("S0"))
        self.assertEqual(r.feature_names("S2")[-3:], ["TempMax", "TempMin", "HumedadMedia"])
        self.assertEqual(set(r.feature_names("S0_coord")) - set(r.feature_names("S0")), {"lat", "lon"})
        for s in ("L1", "L2"):
            self.assertFalse(set(r.feature_names(s)) & set(r.OM_COLS), "L1/L2 no usan Open-Meteo")

    def test_train_test_separation(self):
        r = self.r
        for f in r.lc.build_folds():
            dev, X, test, Xt = r.train_test(f, "S2", self.df)
            self.assertFalse(set(dev.station_code) & set(f["test"]))
            self.assertLessEqual(dev.date.max(), "2019-12-31")
            self.assertGreaterEqual(test.date.min(), "2020-01-01")
            self.assertTrue((test.common_core == 1).all())
            self.assertEqual(X.shape[1], Xt.shape[1])

    def test_f1_test_rows_cover_cohort(self):
        r = self.r
        n = sum(len(r.train_test(f, "S0", self.df)[2]) for f in r.lc.build_folds() if f["scheme"] == "F1_loso")
        self.assertEqual(n, 19251)

    def test_cell_grid(self):
        cells = self.r.select_cells(self.r.MODELS)
        self.assertEqual(len(cells), 12 * 6 * 5)
        self.assertEqual(len(self.r.select_cells(["RF"], fold_ids=["F1_loso"])), 9 * 6)

    def test_deadline_skips_without_training(self):
        fold = self.r.lc.build_folds()[0]
        msg, secs = self.r.fit_cell(fold, "S0", "RF", deadline=time.time() - 1)
        self.assertTrue(msg.startswith("OMITIDA"))
        self.assertEqual(secs, 0.0)

    def test_decision_literal(self):
        import pandas as pd
        rep = _load("estudio03_2_report_test", STUDY / "report.py")

        def row(h, a, b, d, lo, hi):
            return {"scope": "F1", "hypothesis": h, "A": a, "B": b, "rmse_A": 0.4, "rmse_B": 0.4 - d,
                    "delta_rmse": d, "ci95_lo": lo, "ci95_hi": hi}
        pc = pd.DataFrame([row("H1", "S0|HGB", rep.OM_AHC_T, -0.06, -0.09, -0.03),
                           row("H2", "S0|HGB", rep.PM_N, -0.02, -0.05, 0.01),
                           row("H3", "S2|HGB", "S0|HGB", -0.03, -0.04, -0.02),
                           row("H4_L1", "L1|HGB", "S0|HGB", 0.2, 0.15, 0.25),
                           row("H4_L2", "L2|HGB", "S0|HGB", 0.1, -0.01, 0.2)])
        d = rep.decision(pc)["hipotesis"]
        self.assertTrue(d["H1"]["cumple"])
        self.assertFalse(d["H2"]["cumple"])
        self.assertTrue(d["H3"]["cumple"] and d["H3"]["pequena"])
        self.assertFalse(d["H4"]["cumple"])  # exige las dos partes
        self.assertEqual(rep.verdict(-0.03, -0.04, -0.02), "A gana (significativa pero pequena)")
        self.assertEqual(rep.verdict(0.1, -0.01, 0.2), "empate (IC incluye 0)")

    def test_fit_cell_roundtrip_ridge(self):
        import gzip
        r = self.r
        with tempfile.TemporaryDirectory() as tmp:
            old = r.CELLS
            r.CELLS = Path(tmp)
            try:
                fold = [f for f in r.lc.build_folds() if f["id"] == "F2_Menorca"][0]
                name, _ = r.fit_cell(fold, "L1", "Ridge")
                c = json.load(gzip.open(Path(tmp) / name, "rt", encoding="utf-8"))
            finally:
                r.CELLS = old
        self.assertEqual(c["study"], "03.2")
        self.assertEqual(len(c["pred"]), len(c["date"]))
        self.assertEqual(set(c["station_code"]), {"IB08"})
        self.assertGreaterEqual(min(c["pred"]), 0.0)


if __name__ == "__main__":
    unittest.main()
