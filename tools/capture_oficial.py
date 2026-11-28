"""Captura de las previsiones oficiales de SIAR (ET0 prevista) y AEMET (prevision municipal diaria).

Por que: el estudio 04 necesita las previsiones oficiales tal como se emitieron, como rival a batir.
La serie no se puede reconstruir despues: cada dia sin captura se pierde.

Que es cada fuente:
- SIAR: pagina publica de "necesidades hidricas" de cada estacion. Devuelve un ZIP con un CSV de
  unos 7 dias (Fecha, Kc, ET0, ETc, Pe, ETc - Pe). Segun el propio SIAR, la prediccion de ET0 y de
  precipitacion efectiva la suministra AEMET. La ET0 no depende del cultivo elegido.
- AEMET OpenData: prediccion municipal diaria (7 dias). No trae ET0 ni radiacion; si temperaturas,
  humedad, viento y probabilidad de lluvia. Requiere la clave en la variable AEMET_API_KEY
  (en GitHub, un "secret" del repo; nunca en un fichero).

Que guarda:
- Crudos byte a byte (gzip) con SHA-256 en data/raw/<producto>/<estacion>/ y una fila en
  data/raw/manifest.csv (mismo almacen que el resto de capturas).
- Extracto normalizado en data/forecast_oficial/<fecha local de captura>.csv:
  una fila por (fuente, estacion, dia previsto, variable).

Modos:
    PYTHONPATH=src python tools/capture_oficial.py --mode prueba     # IB04 + Palma, mas exploracion
    PYTHONPATH=src python tools/capture_oficial.py --mode completo   # todas las de config/forecast_oficial.csv

Sale con codigo 1 si falta alguna captura esperada (el workflow falla y GitHub avisa por correo).
Solo usa la biblioteca estandar.
"""

import argparse
import csv
import io
import json
import math
import os
import re
import sys
import time
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path
from urllib import error, parse, request
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openmeteo_et0 import store  # noqa: E402
from openmeteo_et0.stations import REPO_ROOT, load_stations  # noqa: E402

TZ = ZoneInfo("Europe/Madrid")
CONFIG = REPO_ROOT / "config" / "forecast_oficial.csv"
OUT_DIR = REPO_ROOT / "data" / "forecast_oficial"
USER_AGENT = "Capitulo-2 forecast capture (research; github.com/lependens/Capitulo-2)"
TIMEOUT = 30
MAX_ZIP_BYTES = 5_000_000

SIAR_BASE = "https://servicio.mapa.gob.es/siarweb"
SIAR_PRODUCT = "siar_prevision"
# Contrato del formulario demostrado en Capitulo-1 (forecast_collector) para IB04.
# idEstacion, idComarca, comarcaEstacion y sEstacion cambian por estacion.
SIAR_FORM_BASE = {
    "esCalculo": "0",
    "tipoCalculo": "2",
    "idCultivo": "6",
    "idCAEstacion": "-1",
    "provinciaEstHidden": "7",
    "chkProvincia": "1",
    "radioProvCom": "on",
    "idProvinciaEstacion": "7",
    "chkComRegante": "0",
    "idComunidadRegantes": "-1",
    "chkComarca": "0",
    "comarcaSelect": "-1",
}

AEMET_BASE = "https://opendata.aemet.es/opendata/api"
AEMET_WRAPPER = "aemet_respuesta"
AEMET_PRODUCT = "aemet_municipio"
AEMET_PAUSE = 6  # segundos entre estaciones (2 peticiones cada una) para no rozar el limite por minuto

OUT_FIELDS = [
    "captured_at_utc", "issued_at", "source", "station_code", "location_id", "target_date",
    "horizon_days", "variable", "value", "raw_file", "raw_sha256",
]


# ---------------------------------------------------------------- HTTP minimo con cookies

class Http:
    def __init__(self):
        self.jar = CookieJar()
        self.opener = request.build_opener(request.HTTPCookieProcessor(self.jar))

    def call(self, method, url, data=None, headers=None, attempts=2):
        body = parse.urlencode(data).encode() if isinstance(data, dict) else data
        last = None
        for i in range(attempts):
            req = request.Request(url, data=body, method=method, headers={"User-Agent": USER_AGENT, **(headers or {})})
            try:
                with self.opener.open(req, timeout=TIMEOUT) as r:
                    return r.status, dict(r.headers), r.read(MAX_ZIP_BYTES + 1), r.geturl()
            except error.HTTPError as e:
                last = f"HTTP {e.code}"
                if e.code not in (429, 500, 502, 503, 504):
                    break
                wait = 5 * (i + 1)
                if e.code == 429:  # AEMET limita peticiones por minuto: esperar mas
                    try:
                        wait = max(int(e.headers.get("Retry-After", "0")), 20 * (i + 1))
                    except ValueError:
                        wait = 20 * (i + 1)
            except (error.URLError, TimeoutError, OSError) as e:
                last = f"{type(e).__name__}: {e}"
                wait = 5 * (i + 1)
            if i + 1 < attempts:
                time.sleep(min(wait, 90))
        raise RuntimeError(f"{method} {url_sin_query(url)}: {last}")


def url_sin_query(url):
    p = parse.urlsplit(url)
    return f"{p.scheme}://{p.netloc}{p.path}"


# ---------------------------------------------------------------- SIAR

class _StartPage(HTMLParser):
    """Lee de la pagina inicial: los dos valores CSRF (solo en memoria) y los desplegables (para explorar)."""

    def __init__(self):
        super().__init__()
        self.csrf_body = self.csrf_header = ""
        self.selects = {}
        self.inputs = []
        self.scripts = []
        self._sel = None
        self._opt = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "input":
            if a.get("name") == "_csrf":
                self.csrf_body = a.get("value") or ""
            elif a.get("name"):
                self.inputs.append({"name": a.get("name"), "type": a.get("type", "")})
        elif tag == "meta" and a.get("name") == "_csrf":
            self.csrf_header = a.get("content") or ""
        elif tag == "select":
            self._sel = a.get("name") or a.get("id") or f"select_{len(self.selects)}"
            self.selects[self._sel] = []
        elif tag == "option" and self._sel is not None:
            self._opt = {"value": a.get("value", ""), "text": ""}
            self.selects[self._sel].append(self._opt)
        elif tag == "script" and a.get("src"):
            self.scripts.append(a["src"])

    def handle_endtag(self, tag):
        if tag == "select":
            self._sel = None
        if tag == "option":
            self._opt = None

    def handle_data(self, data):
        if self._opt is not None:
            self._opt["text"] += data.strip()


def siar_start(http):
    status, _h, html, final_url = http.call("GET", f"{SIAR_BASE}/necesidadesHidricas/inicio")
    page = _StartPage()
    page.feed(html.decode("utf-8", errors="replace"))
    return page, final_url


def siar_form(row, station_name):
    return {
        **SIAR_FORM_BASE,
        "idEstacion": row["siar_station_form_id"],
        "idComarca": row["siar_id_comarca"],
        "comarcaEstacion": row["siar_comarca_nombre"],
        "sEstacion": f"{row['station_code']} - {station_name}",
    }


def siar_capture(http, row, station_name):
    """Devuelve (zip_bytes, csv_bytes, nombre_csv). Sigue el flujo inicio -> validarForm -> calculo -> exportCSV."""
    page, start_url = siar_start(http)
    if not page.csrf_body or not page.csrf_header:
        raise RuntimeError("SIAR: no aparecen los valores CSRF en la pagina inicial")
    form = {**siar_form(row, station_name), "_csrf": page.csrf_body}
    origin = "https://servicio.mapa.gob.es"
    base_h = {"Origin": origin, "Referer": start_url}
    _s, _h, val, _u = http.call(
        "POST", f"{SIAR_BASE}/necesidadesHidricasRest/validarForm", data=form,
        headers={**base_h, "X-Requested-With": "XMLHttpRequest", "X-XSRF-TOKEN": page.csrf_header, "Accept": "*/*"},
    )
    if not _validation_ok(val):
        raise RuntimeError(f"SIAR rechaza el formulario: {val[:200]!r}")
    _s, _h, calc_html, calc_url = http.call(
        "POST", f"{SIAR_BASE}/necesidadesHidricas/calculo", data=form,
        headers={**base_h, "Accept": "text/html,*/*"},
    )
    _s, headers, zbytes, _u = http.call(
        "GET", f"{SIAR_BASE}/necesidadesHidricas/exportCSV", headers={"Referer": calc_url, "Accept": "*/*"},
    )
    if len(zbytes) > MAX_ZIP_BYTES:
        raise RuntimeError("SIAR: exportacion demasiado grande")
    name, csv_bytes = single_csv(zbytes)
    return zbytes, csv_bytes, name, visible_text(calc_html, (page.csrf_body, page.csrf_header))


def visible_text(html_bytes, secrets=()):
    """Texto visible de la pagina de resultado, sin scripts ni valores de sesion (solo para diagnostico)."""
    t = _decode(html_bytes)
    t = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    for s in secrets:
        if s:
            t = t.replace(s, "[sesion]")
    return re.sub(r"\s+", " ", t).strip()


def _validation_ok(body):
    if not body.strip():
        return True
    try:
        v = json.loads(body)
    except ValueError:
        return False
    return v is not None and (not isinstance(v, (dict, list, str)) or len(v) == 0)


def single_csv(zbytes):
    try:
        with zipfile.ZipFile(io.BytesIO(zbytes)) as z:
            names = [n for n in z.namelist() if not n.endswith("/")]
            if len(names) != 1:
                raise RuntimeError(f"SIAR: el ZIP trae {len(names)} ficheros")
            info = z.getinfo(names[0])
            if info.file_size > MAX_ZIP_BYTES:
                raise RuntimeError("SIAR: CSV demasiado grande")
            return names[0], z.read(names[0])
    except zipfile.BadZipFile as e:
        raise RuntimeError(f"SIAR: la exportacion no es un ZIP ({zbytes[:80]!r})") from e


def _decode(b, charset=None):
    for enc in [c for c in (charset, "utf-8-sig", "iso-8859-15") if c]:
        try:
            return b.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return b.decode("latin-1")


def _parse_date(s):
    s = s.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"fecha no reconocida: {s!r}")


def _num(s):
    s = str(s).strip().replace(",", ".")
    if s == "" or s == "-":
        return None
    v = float(s)
    return v if math.isfinite(v) else None


def _var_name(col):
    return re.sub(r"[^a-z0-9]+", "_", col.strip().lower()).strip("_")


def parse_siar_csv(csv_bytes):
    """Lista de (fecha, variable, valor) para cada columna numerica del CSV de SIAR."""
    text = _decode(csv_bytes)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    delim = max(";\t,", key=lambda d: lines[0].count(d))
    rows = list(csv.reader(lines, delimiter=delim))
    header = [h.strip() for h in rows[0]]
    if not header or header[0].lower() != "fecha":
        raise ValueError(f"cabecera inesperada: {header}")
    out = []
    for r in rows[1:]:
        if not r or not r[0].strip():
            continue
        d = _parse_date(r[0])
        for col, val in zip(header[1:], r[1:]):
            try:
                v = _num(val)
            except ValueError:
                continue
            if v is not None:
                out.append((d, _var_name(col), v))
    return out


# ---------------------------------------------------------------- AEMET

def aemet_get(http, path, key):
    """Peticion a OpenData: respuesta inicial (con la URL de datos) y datos. Devuelve (inicial, datos, charset)."""
    _s, _h, wrapper, _u = http.call("GET", f"{AEMET_BASE}{path}", headers={"api_key": key, "Accept": "application/json"}, attempts=3)
    w = json.loads(_decode(wrapper))
    if w.get("estado") != 200 or not w.get("datos"):
        raise RuntimeError(f"AEMET: estado {w.get('estado')} ({w.get('descripcion')})")
    _s, h, payload, _u = http.call("GET", w["datos"], headers={"Accept": "application/json"}, attempts=3)
    m = re.search(r"charset=([\w-]+)", h.get("Content-Type", ""), re.I)
    return wrapper, payload, (m.group(1) if m else None)


def parse_aemet_diaria(payload, charset=None):
    """Devuelve (elaborado, lista de (fecha, variable, valor)) de la prediccion municipal diaria."""
    data = json.loads(_decode(payload, charset))
    item = data[0] if isinstance(data, list) else data
    issued = item.get("elaborado", "")
    out = []
    for dia in item.get("prediccion", {}).get("dia", []):
        d = _parse_date(dia["fecha"])

        def put(var, v):
            try:
                x = _num(v)
            except (ValueError, TypeError):
                return
            if x is not None:
                out.append((d, var, x))

        t = dia.get("temperatura") or {}
        put("tmax_c", t.get("maxima", ""))
        put("tmin_c", t.get("minima", ""))
        h = dia.get("humedadRelativa") or {}
        put("hr_max_pct", h.get("maxima", ""))
        put("hr_min_pct", h.get("minima", ""))
        put("uv_max", dia.get("uvMax", ""))
        vel = []
        for v in dia.get("viento") or []:
            try:
                x = _num(v.get("velocidad", ""))
            except (ValueError, TypeError):
                x = None
            if x is not None:
                vel.append(x)
                if v.get("periodo") in (None, "", "00-24"):
                    put("viento_kmh_00_24", x)
        if vel:
            put("viento_kmh_max_periodos", max(vel))
        for p in dia.get("probPrecipitacion") or []:
            if p.get("periodo") in (None, "", "00-24"):
                put("prob_precip_pct_00_24", p.get("value", ""))
    return issued, out


def aemet_municipios(http, key):
    """Maestro de municipios de Baleares (para proponer el municipio de cada estacion)."""
    _s, _h, body, _u = http.call("GET", f"{AEMET_BASE}/maestro/municipios", headers={"api_key": key, "Accept": "application/json"})
    data = json.loads(_decode(body))
    if isinstance(data, dict) and data.get("datos"):
        _s, h, body, _u = http.call("GET", data["datos"])
        data = json.loads(_decode(body))
    return [m for m in data if str(m.get("id", "")).startswith("id07")]


def nearest_municipio(lat, lon, municipios):
    def dist(m):
        try:
            mlat, mlon = float(m["latitud_dec"]), float(m["longitud_dec"])
        except (KeyError, TypeError, ValueError):
            return float("inf")
        dx = (mlon - lon) * 111.32 * math.cos(math.radians(lat))
        dy = (mlat - lat) * 110.57
        return math.hypot(dx, dy)

    best = min(municipios, key=dist)
    return {"id": best["id"][2:], "nombre": best.get("nombre"), "km": round(dist(best), 1)}


# ---------------------------------------------------------------- salida normalizada

def write_rows(rows, now_utc):
    if not rows:
        return None
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{now_utc.astimezone(TZ).date().isoformat()}.csv"
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        if new:
            w.writeheader()
        w.writerows(rows)
    return path


def to_rows(source, station, loc, issued, values, now_utc, raw_rel, sha):
    today = now_utc.astimezone(TZ).date()
    return [
        {
            "captured_at_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"), "issued_at": issued, "source": source,
            "station_code": station, "location_id": loc, "target_date": d.isoformat(),
            "horizon_days": (d - today).days, "variable": var, "value": v, "raw_file": raw_rel, "raw_sha256": sha,
        }
        for d, var, v in values
    ]


def _last_manifest_row():
    return store.read_manifest()[-1]


def save(product, station, tag, url, body, ext, now):
    store.save_raw(product, station, tag, url, body, now=now, ext=ext)
    r = _last_manifest_row()
    return r["file"], r["sha256_response"]


# ---------------------------------------------------------------- orquestacion

def load_config():
    with open(CONFIG, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


STATUS_FIELDS = ["captured_at_utc", "run_tag", "source", "station_code", "status", "detail"]
STATUS_FILE = OUT_DIR / "estado.csv"
# ok: datos validos. sin_prevision: la fuente respondio bien pero sin datos (SIAR desde el 24-11-2026).
# pendiente_config: falta configurar la estacion. error: fallo real (hace fallar el workflow y avisa por correo).
FAILING = {"error"}


def write_status(entries):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    new = not STATUS_FILE.exists()
    with open(STATUS_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=STATUS_FIELDS)
        if new:
            w.writeheader()
        w.writerows(entries)


def day_summary(day_local):
    """Recuento de estados por fuente en un dia local (a partir de estado.csv)."""
    counts = {}
    if not STATUS_FILE.exists():
        return counts
    with open(STATUS_FILE, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            d = datetime.strptime(r["captured_at_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if d.astimezone(TZ).date() == day_local:
                k = (r["source"], r["status"])
                counts[k] = counts.get(k, 0) + 1
    return counts


def run(mode, only=None):
    http = Http()
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    tag = now.astimezone(TZ).strftime("%Y-%m-%d_%H%M")
    names = {s.code: s.name for s in load_stations()}
    key = os.environ.get("AEMET_API_KEY", "").strip()
    cfg = load_config()
    if mode == "prueba":
        cfg = [r for r in cfg if r["station_code"] == "IB04"]
    if only:
        cfg = [r for r in cfg if r["station_code"] in only]
    rows, status, report = [], [], {}

    def note(source, code, st, detail=""):
        status.append({"captured_at_utc": stamp, "run_tag": tag, "source": source, "station_code": code,
                       "status": st, "detail": detail[:300]})
        print(f"{'+' if st == 'ok' else '!'} {source.upper()} {code}: {st} {detail[:300]}")

    retry = []

    def aemet_one(code, muni, final):
        """Captura AEMET de una estacion. Con final=False, un fallo reintentable se deja para la segunda pasada."""
        nonlocal rows
        path = f"/prediccion/especifica/municipio/diaria/{muni}"
        try:
            wrapper, payload, charset = aemet_get(http, path, key)
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if not final and re.search(r"HTTP (429|5\d\d)|URLError|Timeout|OSError", msg):
                return False
            hint = " (clave caducada o no valida?)" if "401" in msg or "403" in msg else ""
            note("aemet", code, "error", f"{msg}{hint}")
            return True
        save(AEMET_WRAPPER, code, tag, AEMET_BASE + path, wrapper, "json", now)
        rel, sha = save(AEMET_PRODUCT, code, tag, AEMET_BASE + path + " (datos)", payload, "json", now)
        try:
            issued, vals = parse_aemet_diaria(payload, charset)
        except (ValueError, KeyError, IndexError) as e:
            note("aemet", code, "error", f"crudo guardado pero no se pudo leer: {e}")
            return True
        days = len({v[0] for v in vals})
        rows += to_rows("aemet", code, muni, issued, vals, now, rel, sha)
        note("aemet", code, "ok" if days >= 6 else "error", f"{muni} elaborado {issued}, {days} dias")
        return True

    if mode == "prueba":
        report["exploracion"] = explore(http, key)

    for r in cfg:
        code = r["station_code"]
        if not r["siar_station_form_id"] or not r["siar_id_comarca"]:
            note("siar", code, "pendiente_config", "falta formulario o comarca en config/forecast_oficial.csv")
        else:
            try:
                zb, cb, name, calc_text = siar_capture(http, r, names[code])
                url = f"{SIAR_BASE}/necesidadesHidricas/exportCSV idEstacion={r['siar_station_form_id']} idCultivo=6"
                save(SIAR_PRODUCT, code, tag, url, zb, "zip", now)
                rel, sha = save(SIAR_PRODUCT, code, tag, url + f" csv={name}", cb, "csv", now)
                try:
                    vals = parse_siar_csv(cb)
                    if vals:
                        rows += to_rows("siar", code, r["siar_station_form_id"], "", vals, now, rel, sha)
                        note("siar", code, "ok", f"{len({v[0] for v in vals})} dias")
                    else:
                        if mode == "prueba":
                            report.setdefault("siar_sin_filas", {})[code] = calc_text[:4000]
                        note("siar", code, "sin_prevision", f"CSV solo con cabecera ({len(cb)} bytes)")
                except ValueError as e:
                    note("siar", code, "error", f"crudo guardado pero no se pudo leer: {e}")
            except Exception as e:  # noqa: BLE001 - cada estacion es independiente
                note("siar", code, "error", str(e))
            time.sleep(1)

        muni = r["aemet_municipio_id"]
        if not key:
            note("aemet", code, "error", "falta el secret AEMET_API_KEY (o ha caducado y se borro)")
        elif not muni:
            note("aemet", code, "pendiente_config", "municipio sin configurar")
        elif not aemet_one(code, muni, final=False):
            retry.append((code, muni))
        time.sleep(AEMET_PAUSE)

    # Segunda pasada para las que AEMET corto por limite de peticiones o fallo de red.
    if retry:
        print(f"= reintento AEMET en 60 s: {[c for c, _m in retry]}")
        time.sleep(60)
        for code, muni in retry:
            aemet_one(code, muni, final=True)
            time.sleep(AEMET_PAUSE)

    out = write_rows(rows, now)
    if out:
        print(f"= extracto: {out.name} (+{len(rows)} filas)")
    write_status(status)
    if report:
        dpath = REPO_ROOT / "data" / "raw" / "exploracion_oficial" / f"{tag}.json"
        dpath.parent.mkdir(parents=True, exist_ok=True)
        dpath.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"= exploracion: {dpath.relative_to(REPO_ROOT)}")
    write_summary(now, status)
    return 1 if any(e["status"] in FAILING for e in status) else 0


def write_summary(now, status):
    """Resumen en la pagina de la ejecucion de GitHub (si existe GITHUB_STEP_SUMMARY) y en el registro."""
    day = now.astimezone(TZ).date()
    lines = [f"### Captura oficial {now.astimezone(TZ):%Y-%m-%d %H:%M} (hora peninsular)", "",
             "| Fuente | Estacion | Estado | Detalle |", "|---|---|---|---|"]
    lines += [f"| {e['source']} | {e['station_code']} | {e['status']} | {e['detail']} |" for e in status]
    lines += ["", f"**Acumulado del dia {day}:** " + ", ".join(
        f"{src} {st}: {n}" for (src, st), n in sorted(day_summary(day).items()))]
    text = "\n".join(lines) + "\n"
    print(text)
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a", encoding="utf-8") as f:
            f.write(text)


def explore(http, key):
    """Datos para completar config/forecast_oficial.csv: desplegables de SIAR y municipio AEMET mas cercano."""
    rep = {}
    try:
        page, _u = siar_start(http)
        rep["siar_selects"] = page.selects
        rep["siar_inputs"] = page.inputs
        rep["siar_scripts"] = page.scripts
    except Exception as e:  # noqa: BLE001
        rep["siar_error"] = str(e)
    if key:
        try:
            munis = aemet_municipios(http, key)
            rep["aemet_propuesta"] = {s.code: nearest_municipio(s.latitude, s.longitude, munis) for s in load_stations()}
        except Exception as e:  # noqa: BLE001
            rep["aemet_error"] = str(e)
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["prueba", "completo"], default="completo")
    ap.add_argument("--stations", nargs="*", default=None)
    a = ap.parse_args(argv)
    return run(a.mode, a.stations)


if __name__ == "__main__":
    sys.exit(main())
