# WalkSim Mobility 3.0 — Walkway, primera entrega

## Alcance de esta entrega

La versión 3.0 incorpora el núcleo Walkway acordado: operación, diseño inverso,
alternativas, comparación analítica con microsimulación y gráficas. Conserva los
siete análisis de la versión 2.1 en **Complementarios**, así como el corredor
libre y sus resultados. Accesos y colas de servicio, plazas con OD, mapas de
calor locales, ampliación de escaleras, senderos compartidos e intersecciones
son fases posteriores: no se presentan como implementados.

## Interfaz y secuencia

1. En **Proyecto**, indique nombre, ubicación, analista y notas.
2. En **Walkway**, elija la pregunta: evaluar operación, diseñar ancho o calcular
   demanda admisible para un LOS objetivo.
3. Introduzca geometría, velocidad y demanda. El formulario muestra los datos
   correspondientes a la tarea y al tipo de flujo.
4. Pulse **Calcular escenario**. Revise LOS, ancho efectivo, demanda/capacidad,
   tiempo libre, desarrollo metodológico y advertencias.
5. Use **Duplicar escenario** para crear alternativas. La nueva alternativa
   conserva los datos, pero debe calcularse y simularse por separado.
6. En **Comparar**, calcule todas las alternativas y exporte la tabla a CSV.
7. Despliegue **Opciones de microsimulación** y pulse **Ejecutar microsimulación**
   (también Simulación → Ejecutar escenario Walkway, F5).
8. Revise la comparación, gráficas y procedencia de datos. Puede exportar las
   gráficas a PNG/PDF y las series a CSV.
9. En **Archivo**, guarde `.wksim` o exporte el informe `.tex` con el analista.

**Simular ejemplo** añade un escenario didáctico independiente y lo ejecuta;
no sustituye las alternativas existentes. Las operaciones Nuevo/Abrir/Guardar/
Exportar están únicamente en Archivo, sin barra redundante. Ayuda incluye guía,
metodología y Acerca de. Se conservan los modos claro y oscuro y el desplazamiento
para pantallas pequeñas; las acciones de escenario se apilan en ventanas estrechas.

## Demanda: dos bases alternativas

### Demanda horaria con PHF

Flujos direccionales horarios `Qh_AB`, `Qh_BA` y factor `PHF`:

`Qd_AB = Qh_AB/PHF`, `Qd_BA = Qh_BA/PHF`.

`Qd` es una tasa horaria equivalente del periodo crítico, no una nueva demanda
horaria observada. El PHF de 15 min se usa solo para flujo aleatorio. Un PHF
válido está entre 0 y 1; el programa admite 0.01–1 para evitar entradas extremas
por error de captura.

### Conteo directo

`Qd_AB = 60 N_AB/T` y `Qd_BA = 60 N_BA/T`, con `T` en minutos:

- flujo aleatorio: conteo de los **15 min** más cargados;
- pelotones: conteo de **5 min**, con la tabla específica del HCM.

Los campos inactivos permanecen en el borrador, pero no participan en el cálculo
ni bloquean una tarea distinta. No se vuelve a aplicar PHF al conteo. Para pelotones, el formulario selecciona
esta base automáticamente. Las series de microsimulación no son un archivo de
entrada de demanda variable: en esta entrega se parametrizan llegadas aleatorias
o descargas periódicas.

## Cálculo operacional en SI

Se conserva el criterio HCM 7, capítulo 24, Exhibits 24-1 y 24-2 y ecuaciones
24-1 a 24-4, ya contrastados en la versión 2.1:

- `WE = WT − WO − WB` (m).
- `Qd = Qd_AB + Qd_BA` (peat/h).
- `q = Qd/(60 WE)` (peat/min/m).
- `D = q/(60 S)` (peat/m²), para `S` en m/s.
- `M = 1/D` (m²/peatón).
- `X = Qd/(60 c WE)`.
- `t_libre_nominal = L/S`.

Capacidad específica de referencia: `c = 23/0.3048` peat/min/m para flujo aleatorio,
y `18/0.3048` para pelotones. Los límites espaciales se convierten exactamente desde
ft²/peatón multiplicando por `0.09290304`. El LOS por espacio utiliza los límites
inferiores estrictos; si la demanda supera la capacidad se informa además LOS
operativo F y se advierte que el flujo estacionario supuesto no es sostenible.

La velocidad es una hipótesis representativa, no una predicción ni una calibración.
Las pendientes admitidas son −5 % a +5 %; se documentan con la velocidad introducida.
No se aplica una corrección biomecánica ni se crea una pendiente tridimensional en
la microsimulación. Los descuentos de obstáculos se representan mediante ancho
útil uniforme; no se generan obstáculos puntuales.

## Diseño inverso

Se elige objetivo **LOS A, B, C, D o E, o mejor**, y un margen positivo `m`
(predeterminado 1 %, admisible 0.01–25 %).

### Ancho propuesto

Para un límite inferior de espacio `Mobj`:

`WE_espacio = Qd Mobj/(3600 S)`.

Se toma al menos el mayor entre `WE_espacio(1+m)`, el ancho de capacidad
`Qd/(60c)` y 0.5 m. Se suman los descuentos y se redondea el ancho total hacia
arriba a centímetros. Se vuelve a evaluar el ancho resultante para comprobar el
LOS y la relación demanda/capacidad. El margen evita la igualdad del límite.

### Demanda admisible

`Qd_max = min(3600 S WE/[Mobj(1+m)], 60cWE)`.

Es una demanda máxima de diseño **con margen**, no el supremo matemático sin margen.
En base horaria se informa `Qh_max = Qd_max PHF`; en base de conteo se informa el
conteo entero admisible redondeado hacia abajo. Para preparar la simulación se usa
el reparto A → B introducido y su complemento B → A.

Estos resultados son condicionales a velocidad, geometría y metodología. El ancho
calculado no sustituye mínimos normativos ni requisitos de accesibilidad.

## Referencias numéricas de aceptación

1. Ancho total 3 m; obstáculos 0.2 m; bordes 0.3 m; velocidad 1.2 m/s;
   demanda 900 + 600 peat/h y PHF 0.5:
   `WE=2.5`, `Qd=3000`, `q=20`, `D=0.2777778`, `M=3.6`, **LOS C**.
   Conteos 450 + 300 en 15 min deben producir los mismos resultados cualquiera
   que sea el valor de PHF conservado en el borrador.
2. Demanda de diseño 3600 peat/h; velocidad 1.2 m/s; objetivo C;
   descuentos 0.5 m y margen 1 %: límite espacial de ancho útil
   `1.8580608 m`; ancho total propuesto **2.38 m**, ancho útil **1.88 m**,
   espacio **2.256 m²/peatón**, **LOS C**.
3. Cambiar la semilla repite las entradas del escenario, pero cambia la realización
   de llegadas. Repetir semilla, configuración y versión del motor debe reproducir
   los mismos resultados numéricos dentro de la precisión de salida.

## Microsimulación y mediciones

El motor es Eclipse SUMO, modelo peatonal `striping`. La versión 3 define
explícitamente el tipo peatonal con la velocidad de referencia, factor 1 y
sin dispersión de ese factor. El comportamiento y la interacción del modelo
pueden reducir la velocidad efectiva. Los resultados de la versión 2.1 se
conservan con su versión y parámetros originales; no se equiparan automáticamente
con una ejecución nueva.

Las llegadas aleatorias siguen un proceso Poisson, reproducible con la semilla.
En pelotones se concentran esas llegadas en ventanas de descarga con un intervalo
y duración configurables. El aforo de 5 min fija la tasa media; el patrón temporal
es una hipótesis de simulación explícita, no una deducción única del HCM.
Los recuentos generados varían respecto a la demanda media esperada.

### Periodos

- **Calentamiento:** se genera demanda para llenar el corredor. No forma parte
  de la ventana de observación. Se advierte si es menor que `L/S`.
- **Observación:** ventana de cálculo de acumulación, densidad, flujo y cohorte.
- **Despeje:** se deja de generar demanda y se permite terminar recorridos. Se
  usa el margen del corredor (`max(300 s, 3 L/S)`).

La ocupación se integra exactamente desde las salidas y llegadas de los peatones,
incluidos los inconclusos. La densidad es la presencia acumulada dividida por
área global y tiempo observado. No se promete densidad local máxima ni heatmap.
La población de la cohorte son los peatones que entran durante la observación;
sus estadísticas de recorrido incluyen los que terminan durante el despeje.
Se informa censura cuando quedan recorridos de esa cohorte pendientes.

Se registran generados, iniciados, completados y pendientes; ambas direcciones;
tiempo medio, mínimo, máximo, P50, P85 y P95; velocidad espacial de cohorte
(`ΣL/ΣT`), media de velocidades individuales y tiempo perdido.
Los percentiles usan interpolación lineal entre posiciones `(n−1)p`.

### Gráficas y comparación

- Acumulación y densidad: promedio temporal dentro de cada intervalo.
- Flujo de salida: completados del intervalo convertidos a peat/h.
- Velocidad: promedio de velocidades de recorridos **finalizados** en cada
  intervalo, no velocidad instantánea de todos los peatones.
- Histograma: tiempos de la cohorte completada.

La comparación usa la misma ventana y la demanda de diseño. El tiempo comparable
analítico usa `L−0.20 m`, el recorrido efectivo entre posiciones de origen y destino;
el tiempo libre nominal del formulario usa `L`. La velocidad de referencia es una
hipótesis que puede diferir de la velocidad espacial observada. Diferencias entre
estos valores no son por sí mismas error ni validación del modelo.
El LOS global simulado es indicativo; los indicadores sin equivalente son N/A.
El programa avisa si las alternativas cambian definición de demanda o periodos.

## Datos, archivos y reportes

- El origen de cada entrada puede ser predeterminado, introducido, observado o CSV.
  Cambiar un valor actualiza su origen según la selección del analista.
- Editar entradas marca los resultados como desactualizados. Se conservan los
  resultados anteriores en el proyecto, pero no se muestran como resultados
  actuales ni se usan como tales en el reporte.
- `.wksim` usa `schema_version: 3`, separado de `software_version: 3.0.0`.
  Se admiten proyectos 2.1 (`schema_version: 1`) y 3. Al sobrescribir un archivo
  con esquema 1 se conserva una copia `nombre.v2-backup.wksim`, sin reemplazar una
  copia previa. Se conservan los antiguos análisis y borradores.
- El formato guarda escenarios, procedencia, resultados, series, estadísticas y
  selección de gráfica. Se valida antes de modificar el estudio abierto.
- El límite es 30 escenarios y 8 MiB por proyecto. La simulación admite hasta
  100 000 peatones esperados, con un límite de 180 s por subproceso. Una operación
  analítica puede producir un diseño fuera del rango del corredor simulado; la
  ejecución informa el límite en vez de recortar sus parámetros.
- La plantilla CSV contiene las columnas necesarias para la tarea elegida. Use
  segundos para periodos y m/s para velocidad. Las entradas se validan por lote
  antes de incorporarlas. No se mezclan con las plantillas históricas de la 2.1.
- El reporte `.tex` incluye todos los casos actuales, procedencia, ecuaciones,
  diseño, estadísticas por sentido, comparación, advertencias y fuentes.
  Las gráficas se exportan a `nombre_reporte_figuras/` en PDF vectorial. Mantenga
  esa carpeta junto al `.tex` al copiar o compilar el reporte.

## Ejemplo incluido

Abra `examples/Walkway3_Comparacion.wksim`. Contiene tres alternativas sintéticas:
Base de 3 m, alternativa de 4 m y diseño para LOS C. La Base incluye una ejecución
real de SUMO con semilla y versión registradas. No son observaciones de campo.

## Criterios de aceptación

- Las dos bases de demanda coinciden para datos equivalentes y no duplican PHF.
- El diseño cumple el objetivo espacial estricto y capacidad, con redondeo seguro.
- El cambio de entradas invalida comparaciones y resultados visibles anteriores.
- Se conserva la población generada, iniciada, completada y pendiente.
- La integral de las series coincide con la ocupación media de la observación.
- Abrir/guardar conserva alternativas, borradores y resultados, y migra esquema 1.
- La interfaz se revisa en claro/oscuro y entre 480 × 360 y 1360 × 900.
- El reporte compila con LaTeX y sus gráficas son legibles.

## Referencias

- TRB (2022), HCM 7, capítulo 24, tablas 24-1 y 24-2; ecuaciones 24-1 a 24-4.
- Metodología histórica y conversiones: [METHODOLOGY.md](METHODOLOGY.md).
- SUMO: <https://sumo.dlr.de/docs/Simulation/Pedestrians.html> y salidas peatonales.
