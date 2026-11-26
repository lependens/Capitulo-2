# Estudio 02: Open-Meteo + ajuste tipo AHC frente a V2

Criterios fijados antes de ejecutar: `config/thresholds_v2.json`. Ejecutar: `python studies/02_openmeteo_ahc/run.py`.

**Protocolo (igual que V2):** coeficiente `a = Σ(x·PM)/Σ(x²)` por estación y granularidad (anual, estacional, mensual), con x = ET0 de Open-Meteo (archive), ajustado solo con DESARROLLO (2004–2019, 48.445 pares) y evaluado en TEST 2020–2025 sobre la cohorte común de V2 (n=19.251, mismas claves). No se elige granularidad mirando TEST.

## Resultado global (RMSE mm/día, referencia PM_FAO56_V1)

| | Open-Meteo crudo | OM + AHC anual | OM + AHC estacional | OM + AHC mensual |
|---|---|---|---|---|
| RMSE | 0,752 | 0,534 | 0,454 | 0,427 |
| Sesgo | +0,542 | +0,103 | +0,016 | −0,005 |
| R² | 0,806 | 0,902 | 0,929 | 0,938 |

Tabla completa contra cada fórmula/AHC/ML/ANN de V2 y granularidad: `results/comparison.md`. Métricas globales y por estación: `results/metrics_*.csv`; coeficientes: `results/coefficients.csv`; predicciones: `results/predictions_openmeteo_2020_2025.csv`.

## Qué significan anual / estacional / mensual para ML y ANN (misma información de calendario)
Según la metodología V2 de Capitulo-1 (`et0_methodology_review_v2.md`, `ET0_V2_MEMORIA_CIENTIFICA.md`): en anual, ML/ANN usan solo las entradas base de la familia; en estacional se añaden 4 indicadores de temporada (DJF/MAM/JJA/SON); en mensual, 12 indicadores de mes; AHC usa 1, 4 o 12 coeficientes con la misma partición. Por eso **todas las comparaciones de este estudio emparejan la misma granularidad**: Open-Meteo + AHC anual con las ANN anuales, el mensual con las mensuales, etc. (las columnas `*_ANN_A` de cada CSV de `data/v2` ya corresponden a su resolución). El día del año (seno/coseno) queda fuera de V2.

### Diferencias pareadas con intervalo de confianza (`paired_ci.py`, `results/paired_ci.csv`)
ΔRMSE = RMSE(ANN A de V2) − RMSE(Open-Meteo + AHC) en la misma cohorte; negativo gana la ANN. IC 95 % por bootstrap de bloques estación-año (54 bloques).

| Granularidad | HS-Ra ANN | HG-Rs ANN | Valiantzas ANN |
|---|---|---|---|
| Anual | −0,001 [−0,035, +0,035] empate | −0,166 [−0,198, −0,134] gana ANN | −0,113 [−0,148, −0,082] gana ANN |
| Estacional | +0,069 [+0,043, +0,096] gana OM+AHC | −0,117 [−0,139, −0,096] gana ANN | −0,038 [−0,063, −0,017] gana ANN |
| Mensual | +0,108 [+0,085, +0,132] gana OM+AHC | −0,099 [−0,119, −0,080] gana ANN | −0,004 [−0,027, +0,017] empate |

Los ML hacen lo mismo con diferencias algo menores a favor de OM+AHC. Lectura: Valiantzas (Tmin, Tmax, HRmedia, Ra) **empata** con Open-Meteo + AHC solo en mensual y le gana de forma significativa en anual y estacional; HG-Rs (con Rs medida) gana siempre; HS-Ra (solo temperaturas) pierde en estacional y mensual. El IC no incluye la incertidumbre de entrenamiento (un solo ajuste por celda) ni es un test leave-one-station-out.

## Gráficos
![RMSE global](figures/01_rmse_global.png)
![RMSE por mes](figures/02_rmse_por_mes.png)
![RMSE por estación](figures/03_rmse_por_estacion.png)
![Variantes más justas](figures/04_variantes_justas.png)
![Coeficientes mensuales](figures/05_coeficientes_mensuales.png)
![Sesgo por año](figures/06_sesgo_por_anio.png)

Tablas completas (por método, estación, mes, año, coeficientes y variantes): `results/tablas_ampliadas.md`. Las figuras se regeneran con `python studies/02_openmeteo_ahc/make_figures.py`.

## Lectura
- **A (OM+AHC frente a fórmulas V2):** mejora a las tres fórmulas sin ajustar en las tres granularidades, y al AHC de HS-Ra en todas y al de Valiantzas en estacional y mensual. No mejora al AHC de HG-Rs (RMSE 0,395–0,413) ni, en anual, al AHC de Valiantzas (0,512).
- **B (ML/ANN frente a OM+AHC):** ML y ANN de HG-Rs ganan en todas las granularidades y en las 9 estaciones (ANN 0,328–0,368); en Valiantzas ganan en anual y estacional y quedan prácticamente empatados en mensual (0,423–0,441 frente a 0,427); los de HS-Ra (solo Tmin/Tmax/Ra) no superan a OM+AHC estacional ni mensual.
- **La diferencia depende de la época del año.** De octubre a febrero Open-Meteo + AHC mensual iguala a la ANN de Valiantzas (0,25–0,32) y se acerca a la de HG-Rs; de abril a septiembre se queda en 0,44–0,61 frente a 0,25–0,31 de la ANN de HG-Rs. Es justo la temporada de más demanda de riego, así que es la que más pesa en la práctica.
- **Open-Meteo sobreestima mucho más en invierno:** el coeficiente AHC medio pasa de ≈0,60 (dic–ene) a ≈0,95 (jun–jul). Un coeficiente anual único corrige mal esa forma, por eso la granularidad mensual mejora tanto (0,534 → 0,427).
- **Variantes más justas (`fair_variants.py`, mismo AHC):** con el viento de Open-Meteo sustituido por 2 m/s fijos la PM propia con AHC mensual da 0,465 frente a 0,446 con su viento: tras calibrar, el viento aporta poco (la calibración ya absorbe el sesgo). Hargreaves-Samani con las T de Open-Meteo (0,988) es mucho peor que con las T de SIAR (0,620): las T de la rejilla tienen un rango diurno 5 °C demasiado pequeño, lo que rompe la fórmula basada en Tmax−Tmin. Es decir, lo que sirve de Open-Meteo es su radiación y su humedad; sus temperaturas no son sustituto del sensor para modelos de pocos inputs.
- Mejor V2 (HG-Rs ANN) 0,328 frente a mejor OM+AHC 0,427.
- **Deriva:** el sesgo anual de OM+AHC es +0,06…+0,18 según el año (2024 el peor, +0,18 en anual y +0,05 en mensual). Los coeficientes de 2004–2019 se mantienen razonablemente en 2020–2025, sobre todo con ajuste mensual.

## Salvedades
Open-Meteo usa todas las entradas y las fórmulas V2 pocas; el coeficiente ajustado sobre reanálisis puede no transferirse a la previsión; el catálogo derivado V2 sigue en DRAFT; el filtrado de DESARROLLO (PM no vacío, `evaluated_PM`) es criterio propio; no hay intervalos de confianza (diferencias de ≈0,01 mm/día, como Valiantzas ANN frente a OM+AHC mensual, no son concluyentes); `fair_variants.py` solo cubre HS-Ra de forma exacta (reproduce V2 a 4e-6), no Valiantzas ni HG-Rs porque no se han reimplementado esas fórmulas.
