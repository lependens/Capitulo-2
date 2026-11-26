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

## Lectura
- **A (OM+AHC frente a fórmulas V2):** mejora a las tres fórmulas sin ajustar en las tres granularidades, y al AHC de HS-Ra en todas y al de Valiantzas en estacional y mensual. No mejora al AHC de HG-Rs (RMSE 0,395–0,413) ni, en anual, al AHC de Valiantzas (0,512).
- **B (ML/ANN frente a OM+AHC):** ML y ANN de HG-Rs ganan en todas las granularidades (0,328–0,381); en Valiantzas ganan en anual y estacional y quedan prácticamente empatados en mensual (0,423–0,441 frente a 0,427); los de HS-Ra (solo Tmin/Tmax/Ra) no superan a OM+AHC estacional ni mensual.
- Mejor V2 (HG-Rs ANN) 0,328 frente a mejor OM+AHC 0,427.

## Salvedades
Open-Meteo usa todas las entradas y las fórmulas V2 pocas; el coeficiente ajustado sobre reanálisis puede no transferirse a la previsión; el catálogo derivado V2 sigue en DRAFT; el filtrado de DESARROLLO (PM no vacío, `evaluated_PM`) es criterio propio. El sesgo anual residual (+0,10) indica que los coeficientes de 2004–2019 no se mantienen del todo en 2020–2025.
