# Métodos peatonales de WalkSim Mobility 2.1

## Fuentes y alcance

La versión 2.1 integra los temas del documento aportado «Análisis y Metodología
Peatonal según el HCM 7ma Edición». Las tablas de aceras, pelotones y escaleras
se contrastaron con el **HCM 7.ª edición, versión 7.0**, capítulo 24, página 24-4,
Exhibits 24-1, 24-2 y 24-3. No se redistribuye el manual.

El documento es una síntesis de procedimientos: no contiene todas las ecuaciones
ni los datos necesarios para ejecutar los procedimientos completos del HCM de
calles urbanas e intersecciones. El programa identifica el criterio de cada caso.

| Análisis | Cálculo y criterio implementados | Fuente |
| --- | --- | --- |
| Acera / sendero | Ancho efectivo, flujo por ancho, densidad, espacio, capacidad, demanda/capacidad y LOS por espacio | HCM 7, cap. 24, ecs. 24-1 a 24-4 y Exhibit 24-1 |
| Ocupación observada | Área útil, densidad y espacio del máximo número simultáneo observado, LOS | HCM 7, cap. 24, paso 3 y Exhibit 24-1 |
| Pelotones | Conteo promedio de 5 min, velocidad, espacio equivalente y LOS con tabla propia | HCM 7, Exhibit 24-2 |
| Área de espera | Área útil por persona detenida, densidad y LOS espacial | FHWA-RD-98-107, sección 3, tabla 21, basada en Fruin |
| Cruce semaforizado | Demora uniforme, categoría por demora del documento, tiempo cinemático de recorrido y margen de despeje opcionales | Documento aportado, sección 4.3 |
| Cruce sin semáforo | Brecha crítica individual, probabilidad de brecha suficiente y demora sin cesión de paso | HCM 7, ecs. 20-76 y 20-82, caso restringido |
| Escalera | Flujo ascendente, ancho útil, reserva por contraflujo menor, densidad, espacio, capacidad y LOS | HCM 7, Exhibit 24-3 y pp. 24-11 a 24-14 |

El LOS por espacio no es el índice PLOS de enlace o segmento urbano. La demora
simple de un cruce tampoco es el procedimiento completo de PLOS de intersección
HCM 7. El cruce sin semáforo no recibe un LOS por convertir directamente su demora
en una letra: el HCM 7 evalúa satisfacción en su procedimiento completo.

## Relaciones y unidades

- `W_E = W − W_obstáculos − W_bordes − W_contraflujo`, en m.
- `q = N / (T W_E)`, en peat/min/m si `T` está en min.
- `D = q / (60 S)`, en peat/m² si `S` está en m/s.
- `M = 1/D = 60 S/q`, en m²/peatón.
- Para observación espacial: `D = N/(L W_E)` y `M = L W_E/N`.
- Para espera: `A_u = A − A_excluida`, `D = N/A_u`, `M = A_u/N`.
- `1 ft = 0.3048 m`, `1 ft² = 0.09290304 m²`, conversiones exactas.
- Ocupación o aforo cero: densidad cero, espacio sin valor finito y LOS A.
  Se guarda `null` para ese espacio; no se escribe `Infinity` en JSON.

Las entradas de flujo utilizan conteos, no volúmenes horarios confundidos con
densidades. Para el análisis HCM se recomienda el conteo de los 15 min de mayor
actividad. Los pelotones emplean un conteo de 5 min. Otro intervalo se identifica
como tal en los supuestos; no se declara que represente el pico HCM.

## Tablas espaciales

Los cinco límites originales A/B, B/C, C/D, D/E y E/F son:

| Instalación | Límites originales (ft²/peatón) |
| --- | --- |
| Acera / sendero | 60, 40, 24, 15, 8 |
| Acera con pelotones, promedio 5 min | 530, 90, 40, 23, 11 |
| Escalera | 20, 17, 12, 8, 5 |
| Espera (FHWA, tabla 21) | 13, 10, 7, 3, 2 |

Se multiplican por `0.09290304` antes de clasificar. No se redondean los límites
para decidir la letra. A exige un espacio estrictamente mayor que su límite;
los límites superiores de B–E son inclusivos y los inferiores estrictos.
F incluye la igualdad del límite E/F. Se adopta la misma convención conservadora
para los rangos de la tabla de espera.

Capacidad por ancho: aceras `23/0.3048 = 75.4593` peat/min/m;
pelotones `18/0.3048 = 59.0551`; escaleras ascendentes
`15/0.3048 = 49.2126`. El valor aproximado de 56 para escaleras que menciona el
documento no es la referencia del HCM 7 utilizada aquí. El contraflujo menor en
una escalera reserva una fila de 30 pulgadas, es decir, **0.762 m**, además de
los descuentos introducidos. No duplique ese descuento en obstáculos.

Si la demanda supera la capacidad, se presenta una advertencia sobre la falta de
sostenibilidad del régimen estacionario y un LOS operativo F por exceso de demanda;
se conserva también la clasificación matemática por espacio y sus supuestos.
El modelo de aceras no incluye pendientes superiores a 5 %, cruces de flujos a
90 grados, bicicletas ni índices de percepción del entorno urbano.

## Cruces

### Semaforizado

`d = (C − g)²/(2C)`, donde `g` es el WALK efectivo de admisión. Supone llegadas
uniformes, cumplimiento de señal, tiempo fijo y ausencia de sobresaturación.
No se suma automáticamente el intervalo de despeje a `g`.

La categoría por demora del documento es: A `<10`; B `10≤d<20`;
C `20≤d<30`; D `30≤d<40`; E `40≤d≤60`; F `>60`, en s/peatón.
Se identifica como **categoría del documento**, no como PLOS HCM 7 completo.

La revisión opcional `t=L/S` compara el tiempo cinemático con el despeje disponible.
No contiene diseño completo de fases, accesibilidad ni evaluación de seguridad.
Distancia y velocidad deben proporcionarse juntas; el despeje es opcional.

### Sin semáforo

`tc = L/S + ts`; `v = V/3600`; `d = (exp(v tc) − v tc − 1)/v`.
Se usa `expm1` y una expansión para valores muy pequeños; en `V=0`, el límite es cero.
Supuestos: peatón individual, una etapa, llegadas vehiculares aleatorias Poisson,
ningún vehículo cede el paso. No incorpora refugio por etapas ni grupos cruzando.
Si `v tc > 40`, se solicita revisar la aplicabilidad del caso en vez de producir
un desbordamiento numérico. La fórmula no representa el procedimiento completo
con cesión, agrupación y satisfacción de los pasos 1–7 del capítulo 20.

## Motor de microsimulación

SUMO conserva el modelo peatonal `striping` y el corredor recto de ancho uniforme.
Los demás módulos calculan las ecuaciones en Python; no se atribuye al motor una
simulación de escaleras, zonas de espera o interacción con vehículos que no se ha
construido. La integración de estas geometrías requeriría escenarios específicos.

La simulación se ejecuta en un hilo de trabajo para mantener operativa la interfaz.
Cada subproceso tiene un límite de 180 s. El cierre, la apertura y el guardado se
bloquean hasta que termine; ante errores, el estudio anterior se conserva.

Se registra la versión exacta de SUMO, la semilla, la configuración del corredor,
los resultados totales y por sentido. El resumen de recorridos completados excluye
recorridos inconclusos. La salida incluye estos últimos para medir la ocupación:

`presencia = Σ max(0, min(arribo,T) − max(salida,0))`.

Para un recorrido todavía activo se toma `arribo=T`. La ocupación media es
`presencia/T`, la densidad global es `ocupación_media/(L W_E)` y el espacio
equivalente su inverso. También se cuenta la máxima ocupación simultánea global.
Es una media temporal sobre toda el área durante la demanda, **no una medición
local del punto crítico** ni una evaluación del interior de un pelotón.
El LOS global se identifica como indicativo. No hay un periodo de calentamiento
excluido en este escenario; el arranque vacío forma parte de la medición.

El periodo de demanda y el de despeje son distintos. Los tiempos medios de los
recorridos completados incluyen el despeje; la ocupación se integra solo durante
la demanda. Los agentes iniciados, completados durante la demanda e inconclusos
al final se informan por separado. Los promedios de velocidad son la media de
las velocidades individuales de los recorridos completados, no una velocidad
espacial que pueda sustituirse automáticamente en `q=60SD`.

## Fuentes

- TRB (2022), *Highway Capacity Manual*, 7.ª ed., capítulos 20 y 24.
- FHWA-RD-98-107, sección 3, tabla 21:
  <https://www.fhwa.dot.gov/publications/research/safety/pedbike/98107/section3.cfm>.
- Fruin (1971), *Pedestrian Planning and Design*.
- Documento de trabajo aportado por el usuario, síntesis metodológica peatonal.
- SUMO: <https://eclipse.dev/sumo/docs/Simulation/Pedestrians.html>.
