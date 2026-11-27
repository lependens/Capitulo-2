import io
import json
import sys
import tempfile
import unittest
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import capture_oficial as c  # noqa: E402
from openmeteo_et0 import store  # noqa: E402


SIAR_CSV = "Fecha;Kc;ET0;ETc;Pe;ETc - Pe\n27/11/2026;0,65;1,52;0,99;0;0,99\n28/11/2026;0,65;1,8;1,17;2,3;-1,13\n".encode("iso-8859-15")

AEMET = [{
    "elaborado": "2026-11-27T08:51:38",
    "nombre": "Palma",
    "prediccion": {"dia": [
        {
            "fecha": "2026-11-27T00:00:00",
            "temperatura": {"maxima": 18, "minima": 9},
            "humedadRelativa": {"maxima": 90, "minima": 55},
            "viento": [{"periodo": "00-24", "velocidad": 15}, {"periodo": "00-12", "velocidad": 20}],
            "probPrecipitacion": [{"periodo": "00-24", "value": 10}],
            "uvMax": 2,
        },
        {
            "fecha": "2026-12-02T00:00:00",
            "temperatura": {"maxima": 16, "minima": ""},
            "humedadRelativa": {"maxima": 85, "minima": 60},
            "viento": [{"velocidad": 10}],
            "probPrecipitacion": [{"value": ""}],
        },
    ]},
}]


class SiarTests(unittest.TestCase):
    def test_csv_decimales_coma(self):
        vals = c.parse_siar_csv(SIAR_CSV)
        et0 = {d: v for d, var, v in vals if var == "et0"}
        self.assertEqual(et0[date(2026, 11, 27)], 1.52)
        self.assertIn("etc_pe", {var for _d, var, _v in vals})
        self.assertEqual(len({d for d, _v, _x in vals}), 2)

    def test_cabecera_inesperada(self):
        with self.assertRaises(ValueError):
            c.parse_siar_csv(b"<html>error</html>")

    def test_zip_un_fichero(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("prevision.csv", SIAR_CSV)
        name, data = c.single_csv(buf.getvalue())
        self.assertEqual(name, "prevision.csv")
        self.assertEqual(data, SIAR_CSV)

    def test_no_zip(self):
        with self.assertRaises(RuntimeError):
            c.single_csv(b"<html>sesion caducada</html>")

    def test_validacion(self):
        self.assertTrue(c._validation_ok(b""))
        self.assertTrue(c._validation_ok(b"{}"))
        self.assertFalse(c._validation_ok(b'{"idEstacion":"obligatorio"}'))


class AemetTests(unittest.TestCase):
    def test_diaria(self):
        issued, vals = c.parse_aemet_diaria(json.dumps(AEMET).encode("iso-8859-15"), "ISO-8859-15")
        self.assertEqual(issued, "2026-11-27T08:51:38")
        d = {(dd, var): v for dd, var, v in vals}
        self.assertEqual(d[(date(2026, 11, 27), "tmax_c")], 18)
        self.assertEqual(d[(date(2026, 11, 27), "viento_kmh_00_24")], 15)
        self.assertEqual(d[(date(2026, 11, 27), "viento_kmh_max_periodos")], 20)
        self.assertNotIn((date(2026, 12, 2), "tmin_c"), d)  # cadena vacia: ausente, no cero
        self.assertEqual(d[(date(2026, 12, 2), "viento_kmh_00_24")], 10)

    def test_municipio_cercano(self):
        munis = [
            {"id": "id07040", "nombre": "Palma", "latitud_dec": "39.57", "longitud_dec": "2.65"},
            {"id": "id07027", "nombre": "Inca", "latitud_dec": "39.72", "longitud_dec": "2.91"},
        ]
        self.assertEqual(c.nearest_municipio(39.6836, 2.9383, munis)["id"], "07027")


class SalidaTests(unittest.TestCase):
    def test_filas_horizonte(self):
        now = datetime(2026, 11, 27, 7, 0, tzinfo=timezone.utc)
        rows = c.to_rows("siar", "IB04", "4_7", "", [(date(2026, 11, 29), "et0", 1.8)], now, "f", "h")
        self.assertEqual(rows[0]["horizon_days"], 2)
        self.assertEqual(set(rows[0]), set(c.OUT_FIELDS))

    def test_save_raw_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = store.save_raw("x", "IB04", "t", "u", b"abc", raw_dir=Path(tmp), ext="csv")
            self.assertTrue(p.name.endswith(".csv.gz"))
            self.assertEqual(store.verify(Path(tmp)), [])


if __name__ == "__main__":
    unittest.main()
