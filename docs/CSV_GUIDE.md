# Guía de CSV y plantillas

En **Análisis peatonal**, seleccione el método y pulse **Descargar plantilla CSV**. En **Microsimulación**, use **Descargar plantilla del corredor**.

Cada plantilla contiene una fila de ejemplo editable. Conserve los encabezados; el CSV analítico admite hasta 1000 filas del mismo método. El CSV de microsimulación admite un escenario y lo carga sin ejecutarlo automáticamente.

Use UTF-8 (se acepta BOM), coma como separador y punto decimal. También se acepta punto y coma como separador con coma decimal. No use separadores de miles. No escriba unidades dentro de las celdas numéricas.

`analysis` identifica el método y `name` identifica el caso. Campos obligatorios vacíos, columnas repetidas o desconocidas, números no finitos y filas inválidas rechazan el archivo completo sin cambiar los resultados anteriores.


## `walkway` — Acera / sendero — aforo y velocidad

Flujo aleatorio. Use el conteo de los 15 min más cargados y velocidad medida; M = 60 S / q. Aplicable a pendientes de hasta 5 %. No es el índice PLOS de calle urbana.

| Columna | Dato | Unidad | Ejemplo | Obligatorio |
| --- | --- | --- | --- | --- |
| `width_m` | Ancho total | m | `3` | Sí |
| `obstacles_m` | Descuento por obstáculos | m | `0.2` | Sí |
| `edges_m` | Descuento total por bordes | m | `0.3` | Sí |
| `count` | Peatones contados (ambos sentidos) | peat | `250` | Sí |
| `period_min` | Intervalo del conteo | min | `15` | Sí |
| `speed_mps` | Velocidad media medida | m/s | `1.2` | Sí |

## `occupancy` — Acera / sendero — ocupación observada

M = área útil / ocupación simultánea. Use una zona representativa del cuello de botella; la medición es espacial y no equivale a un conteo de paso.

| Columna | Dato | Unidad | Ejemplo | Obligatorio |
| --- | --- | --- | --- | --- |
| `width_m` | Ancho total | m | `3` | Sí |
| `obstacles_m` | Descuento por obstáculos | m | `0.2` | Sí |
| `edges_m` | Descuento total por bordes | m | `0.3` | Sí |
| `length_m` | Longitud del área observada | m | `10` | Sí |
| `occupants` | Máxima ocupación simultánea observada | peat | `5` | Sí |

## `platoon` — Acera con pelotones — promedio de 5 min

Tabla específica de flujo en pelotones del HCM, Exhibit 24-2. El aforo y el espacio corresponden al promedio de 5 min, no al espacio instantáneo dentro de un grupo. Use ocupación observada para diagnosticar un grupo local.

| Columna | Dato | Unidad | Ejemplo | Obligatorio |
| --- | --- | --- | --- | --- |
| `width_m` | Ancho total | m | `3` | Sí |
| `obstacles_m` | Descuento por obstáculos | m | `0.2` | Sí |
| `edges_m` | Descuento total por bordes | m | `0.3` | Sí |
| `count` | Peatones contados en 5 min | peat | `100` | Sí |
| `speed_mps` | Velocidad media medida | m/s | `1.0` | Sí |

## `queue` — Área de espera / andén — ocupación

Personas detenidas: M = área útil / ocupación, D = 1/M. Criterios de espera de FHWA/Fruin, diferentes de los de circulación.

| Columna | Dato | Unidad | Ejemplo | Obligatorio |
| --- | --- | --- | --- | --- |
| `area_m2` | Área total | m² | `30` | Sí |
| `excluded_area_m2` | Área no utilizable | m² | `3` | Sí |
| `occupants` | Ocupación simultánea de diseño | peat | `35` | Sí |

## `signal` — Cruce semaforizado — demora y tiempo de cruce

Demora media con llegadas uniformes y cumplimiento de la señal: d = (C − g)² / (2C). La categoría A–F por demora es la del documento aportado; no es el PLOS completo de una intersección HCM 7. El despeje se revisa aparte del WALK.

| Columna | Dato | Unidad | Ejemplo | Obligatorio |
| --- | --- | --- | --- | --- |
| `cycle_s` | Ciclo semafórico C | s | `90` | Sí |
| `green_s` | WALK efectivo g (admisión) | s | `25` | Sí |
| `crossing_m` | Distancia de cruce (opcional) | m | `` | No |
| `speed_mps` | Velocidad de cruce (opcional) | m/s | `` | No |
| `clearance_s` | Despeje disponible (opcional) | s | `` | No |

## `unsignal` — Cruce sin semáforo — aceptación de brechas

Peatón individual, cruce en una etapa, vehículos con llegadas Poisson y sin cesión de paso. tc = L/S + ts; d = (exp(v tc) − v tc − 1)/v. Se calcula demora por brechas; no el PLOS HCM 7 por satisfacción.

| Columna | Dato | Unidad | Ejemplo | Obligatorio |
| --- | --- | --- | --- | --- |
| `crossing_m` | Distancia de cruce de una etapa | m | `8` | Sí |
| `speed_mps` | Velocidad de cruce | m/s | `1.1` | Sí |
| `startup_s` | Arranque y margen final | s | `3` | Sí |
| `vehicles_pph` | Flujo vehicular conflictivo total | veh/h | `600` | Sí |

## `stairs` — Escalera — flujo ascendente

HCM 7, Exhibit 24-3. Analice el flujo ascendente; el contraflujo menor ocupa 0.762 m adicionales. La velocidad es su componente horizontal, no la velocidad sobre la pendiente. Capacidad de referencia: 15 peat/min/ft.

| Columna | Dato | Unidad | Ejemplo | Obligatorio |
| --- | --- | --- | --- | --- |
| `width_m` | Ancho total | m | `3` | Sí |
| `obstacles_m` | Descuento por obstáculos | m | `0.2` | Sí |
| `edges_m` | Descuento total por bordes | m | `0.3` | Sí |
| `reverse_flow` | ¿Existe contraflujo menor? (0=no, 1=sí) | — | `0` | Sí |
| `count` | Peatones ascendentes contados | peat | `150` | Sí |
| `period_min` | Intervalo del conteo ascendente | min | `15` | Sí |
| `speed_mps` | Velocidad horizontal media en escalera | m/s | `0.5` | Sí |

## `simulation` — corredor bidireccional

| Columna | Significado y unidad |
| --- | --- |
| `length_m` | Longitud, m (5–2000) |
| `width_m` | Ancho útil, m (0.5–20) |
| `flow_ab_pph` | Flujo A → B, peat/h (0–20000) |
| `flow_ba_pph` | Flujo B → A, peat/h (0–20000) |
| `walking_speed_mps` | Velocidad de referencia, m/s (0.2–3) |
| `analysis_time_s` | Duración de la demanda, **segundos** (60–28800) |
| `seed` | Semilla entera, 0–2147483647 |

La interfaz muestra el periodo en minutos; el CSV y el proyecto lo guardan en segundos. La suma de los dos flujos debe ser positiva.
