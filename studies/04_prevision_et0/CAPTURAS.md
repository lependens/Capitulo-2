# Capturas de la previsión oficial (SIAR y AEMET)

Rival oficial del estudio 04. La serie «tal como se emitió» no se puede reconstruir: cada día sin captura se pierde.

## Qué se captura

| Fuente | Qué trae | Dónde | Horizonte |
|---|---|---|---|
| **SIAR**, página pública de pronóstico de necesidades netas, una por estación | CSV con `Fecha, Kc, ET0, ETc, Pe, ETc - Pe`. **La ET0 prevista la suministra AEMET** (lo dice SIAR en su documentación y al pie de la página). La ET0 no depende del cultivo (se usa Aguacate, `idCultivo=6`) | 9 estaciones IB01…IB11 | unos 6–7 días |
| **AEMET OpenData**, predicción municipal diaria | Tmáx, Tmín, HR máx y mín, viento (km/h), probabilidad de lluvia y UV. **Sin ET0 ni radiación**: para usarla como rival hay que calcular la ET0 (p. ej. Hargreaves) en el estudio, no en la captura | municipio más cercano a cada estación (`config/forecast_oficial.csv`; IB02 Inca → Costitx, a 3,1 km) | 7 días |

Hora de emisión: AEMET da `elaborado` (la de la prueba, 19:59) y la actualiza varias veces al día. SIAR no da hora de emisión, así que se usa la de captura.

## Cómo funciona

- Workflow `.github/workflows/oficial_forecast.yml`: **08:00, 14:00 y 20:00** (horario de invierno; el cron va en UTC). Script `tools/capture_oficial.py`, solo con la biblioteca estándar.
- **Crudos**: byte a byte, comprimidos, en `data/raw/siar_prevision/`, `data/raw/aemet_respuesta/` (respuesta inicial con la URL de datos) y `data/raw/aemet_municipio/`, con su SHA-256 en `data/raw/manifest.csv`. Comprimidos pesan unos 2 KB por estación y captura: unos 20 MB al año, caben en el repo.
- **Extracto normalizado**: `data/forecast_oficial/<fecha>.csv` con emisión, captura, fuente, estación, municipio, día previsto, horizonte, variable, valor, fichero crudo y hash.
- **Estado**: `data/forecast_oficial/estado.csv`, una línea por fuente, estación y captura: `ok`, `sin_prevision` (la fuente respondió sin datos), `pendiente_config` o `error`. Cada ejecución deja un resumen en su página de GitHub Actions.
- **Alerta**: el workflow falla solo con `error` (AEMET no responde, clave caducada, respuesta ilegible), y GitHub avisa por correo.
- **Clave de AEMET**: secret `AEMET_API_KEY` del repo, nunca en un fichero. Caduca; cuando pase, la captura falla con aviso de «clave caducada».

## Captura buena (criterios)

- 3 capturas al día por fuente y estación (27 por fuente y día). Se considera **buen día** el que tiene al menos una captura `ok` por estación y fuente.
- Cada crudo coincide con su hash (`store.verify`).
- AEMET: al menos 6 días previstos por captura.
- Objetivo inmediato: 15 días buenos seguidos de AEMET. SIAR cuenta aparte mientras no publique previsión.

## Incidencias

- **SIAR sin previsión desde el 24-11-2026.** La última captura con datos del servidor `iaserver` es del 23-11-2026 a las 20:00. Desde entonces SIAR responde, pero sin filas, también en su web. Se registra como `sin_prevision`; cuando SIAR vuelva, se guardará sola.
- Comarcas SIAR: Mallorca 702, Ibiza 701 (IB01 e IB11, tomada de la captura del servidor) y Menorca 703 (IB08, de `necesidadesHidricasRest/obtenerDatosEstacion` de SIAR). El servidor no capturaba IB08; aquí sí.

## Relación con el servidor (Capitulo-1)

La captura SIAR del servidor sigue funcionando en paralelo como respaldo (08:00, 14:00 y 20:00; 8 estaciones, **no captura IB08**) y no se toca. Sus crudos del 24-11 al 27-11 también están vacíos.
