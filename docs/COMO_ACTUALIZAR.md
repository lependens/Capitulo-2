# Cómo se actualiza el repo cuando hay avances

Regla general: **cada avance entra por un PR**, y el PR que cierra un estudio deja al día los tres sitios que se leen primero. Los chats de ejecución siguen esta guía (está enlazada en todos los `PROMPT_CHAT.md`).

## Qué se toca y cuándo

| Momento | README del estudio | README principal | `docs/IDEAS_Y_MEJORAS.md` |
|---|---|---|---|
| Se crea un estudio (plan) | Plan completo y estado PLAN | Fila en «Qué hay aquí» y en la hoja de ruta, estado «Plan» | Línea afectada → «plan»; registro de cambios |
| Se congelan criterios | Estado | Estado de la fila | — |
| Resultados intermedios (una sesión de Kaggle) | Estado de la ejecución | — | — |
| **Se cierra el estudio** | Resultados, hipótesis, regla aplicada, salvedades | Fila: resultado clave en una frase y estado «Ejecutado (PR #n)»; «Lectura rápida» si cambia el rumbo | «Lo que sabemos hoy» (añadir o corregir puntos), estado de las líneas, ideas nuevas, preguntas abiertas resueltas, registro de cambios |
| Cambia el rumbo o una licencia | — | «Rumbo actual» o «Licencias» | Sección 4 y registro de cambios |

## Reglas

- **Los resultados se escriben una vez y donde nacen:** en el README del estudio. El README principal y las ideas solo los resumen (una frase o una cifra) y enlazan.
- **«Lo que sabemos hoy» es la verdad actual**, no un historial: si un estudio corrige un punto, se reescribe el punto. El historial va al registro de cambios.
- **Fecha y estudio en cada cambio** del registro.
- **Nada de resultados nuevos en un PR de criterios**, ni criterios en un PR de resultados.
- Un PR que cierra un estudio no se fusiona sin las tres actualizaciones; la plantilla de PR lo recuerda.

## Varios chats a la vez

Cada chat trabaja en su rama y solo toca su carpeta, salvo al cerrar. Si dos cierres chocan en el README o en las ideas, se resuelve el conflicto conservando las dos filas o los dos puntos (se hizo así con el 03.2 y el 05). Antes de abrir el PR de cierre: `git fetch && git merge origin/main`.
