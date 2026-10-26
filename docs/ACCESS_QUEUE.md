# WalkSim Mobility 3.1 · Accesos y colas

Fase 2: capacidad de puertas, torniquetes y filtros, atención en fila común,
patrones de llegada y plantilla de Metro. Se mantienen Walkway y los análisis
complementarios. Los valores iniciales son ejemplos; el analista debe introducir
capacidades sustentadas para la instalación estudiada.

## Uso

1. Complete Proyecto, ubicación, analista y notas.
2. Abra **Accesos y colas**. Seleccione acceso individual, Metro entrada o Metro descarga.
3. Elija dispositivo y patrón de llegada. Sólo aparecen los datos pertinentes.
4. Configure la cantidad de dispositivos y el tiempo medio **o** la tasa de servicio.
5. Defina recorridos, ancho, velocidad y dimensiones del área de espera.
6. En Metro, indique recorrido intermedio, número y capacidad de escaleras y área de andén.
7. **Calcular capacidad** obtiene demanda nominal, capacidad y demanda/capacidad.
8. **Simular mis datos** ejecuta el escenario seleccionado. No crea un ejemplo ni sustituye sus datos.
9. Revise Resultados, Comparar, Gráficas y Método y datos.
10. Duplique el caso, modifique los dispositivos y simule la alternativa. Comparar calcula
    las capacidades de todos; cada microsimulación se ejecuta en su escenario seleccionado.
11. Guarde `.wksim`. Exporte comparación, series CSV o gráficas. Archivo exporta el reporte `.tex`.

**Simulación → Simular mis datos · Accesos y colas** ejecuta el caso seleccionado.
La acción **Simular ejemplo** conserva su función de crear un corredor Walkway de ejemplo.
F5 ejecuta el caso seleccionado de Walkway, según su etiqueta en el menú.

## Patrones

| Patrón | Entrada | Generación |
|---|---|---|
| Uniforme | Demanda peat/h | Separación constante, primera llegada a media separación |
| Aleatoria | Demanda peat/h | Proceso Poisson con intervalos exponenciales |
| Intermitente | Demanda media, ciclo y duración de pico | Llegadas Poisson comprimidas al inicio de cada ciclo |
| Descarga masiva | Pasajeros por descarga, ciclo y duración | Exactamente P pasajeros uniformemente repartidos en cada descarga completa |

Los ciclos comienzan en tiempo cero y continúan durante calentamiento y observación.
Una descarga que cruza el final de generación se corta en ese instante. El promedio
nominal de patrones cíclicos se refiere a ciclos completos; los conteos realizados
pueden diferir en una ventana parcial. No hay nuevas llegadas en el despeje.
La semilla controla los patrones aleatorios y el servicio exponencial.

## Plantilla Metro

- **Entrada:** aproximación → torniquetes/puertas → vestíbulo/pasillo → capacidad
  equivalente de escaleras → recorrido final al andén.
- **Descarga:** aproximación desde el tren → capacidad equivalente de escaleras →
  vestíbulo/pasillo → torniquetes/puertas → recorrido final a salida.
- **Acceso libre:** elimina el servicio de puerta; en Metro se conserva la escalera
  y el recorrido intermedio. En acceso individual sólo se simulan aproximación y salida.

El área de espera de puertas se calcula como largo × ancho; el área de la escalera
se introduce por separado. No se dibuja una estación ni se edita XML.

## Modelo híbrido y alcance

SUMO `striping` calcula cada recorrido plano a partir de las llegadas o liberaciones
reales del tramo anterior. WalkSim toma los instantes de llegada de `personinfo`
y resuelve cada atención mediante eventos discretos con una fila FCFS común y c
servidores idénticos. El siguiente tramo de SUMO recibe los instantes de finalización
de servicio. Se registran la versión real del motor y la semilla.

Las escaleras se representan como dispositivos de capacidad equivalente, en peat/h
por escalera. Esta fase no modela la geometría vertical ni calcula un LOS de escalera.
No atribuya una capacidad normativa a los valores iniciales de ejemplo.

La cola tiene almacenamiento ilimitado, sin abandono, prioridades ni bloqueo por
falta de espacio. Los recorridos son simulaciones separadas y no realimentan
espacialmente las colas anteriores. La densidad equivalente divide acumulación
entre área; **no es un mapa local ni una evaluación de seguridad o evacuación**.
La acumulación del sistema incluye toda demanda generada y aún no salida, incluida
la que espera inserción en un tramo. La acumulación de una estación sólo incluye
quienes ya llegaron a ese servicio y aún no terminaron de atenderse.

## Cálculos

Con s segundos de servicio por persona, μ = 3600/s peat/h por dispositivo;
C = c μ. Para estaciones en serie se informa min(Cj). La razón λ/C es carga
nominal; la fracción efectiva de tiempo ocupado se mide de la simulación.

Para P pasajeros cada H segundos, λ = 3600P/H. La reserva nominal por ciclo es
CH/3600 − P, que puede ser negativa. La cota P/C × 3600 es sólo tiempo de atención
ideal de una descarga aislada; no incluye recorridos, variabilidad ni otras colas.

Por orden de llegada ai, el servidor más próximo queda libre en f. La atención
empieza en bi = max(ai,f), termina en ei = bi + si y espera wi = bi − ai. El tiempo
si es constante o exponencial. Cada servidor atiende una persona a la vez.

Cola Q(t) cuenta ai ≤ t < bi. Acumulación de área N(t) cuenta ai ≤ t < ei. Las medias
integran exactamente sus intervalos y los máximos agrupan eventos simultáneos.
Utilización observada integra atención ocupada y divide por c × duración observada.
Densidad media y máxima se obtienen de N(t)/área.

La referencia **M/M/c Erlang C** aparece sólo en acceso individual Poisson con
servicio exponencial y λ < C. Es estacionaria, con fila infinita. Se calcula
mediante Erlang B y su transformación a C para evitar factoriales grandes. No se
aplica a descargas, picos, servicio constante, Metro o cargas inestables. Los
recorridos de SUMO pueden cambiar la distribución de llegada al dispositivo;
la referencia no debe interpretarse como calibración del modelo híbrido.

## Periodos y estadísticas

- Calentamiento: genera y atiende demanda, pero se excluye de medias temporales.
- Observación: integra colas, acumulación y ocupación de servicio.
- Despeje: continúa los recorridos y servicios sin generar demanda adicional.
- Cohorte: personas generadas durante observación. Espera total y tiempo total se
  informan para quienes terminaron antes del límite de despeje.
- Por estación: espera de quienes llegaron durante observación e iniciaron atención
  antes del límite. Se informa muestra y número de esperas censuradas.
- Si quedan pendientes, despeje completo es N/A y se señala la posible censura.
- La cola máxima se mide dentro de observación; no incluye un máximo posterior.
- Las series guardan promedios de cada intervalo; el último puede ser más corto.
- P95 de espera usa interpolación lineal entre estadísticos de orden.
- Antes de nuevas descargas se informa demanda aún en el sistema, incluidos
  recorridos, servicios y colas de trenes anteriores. El tiempo se refiere al reloj
  global desde cero, incluido el calentamiento.

Los indicadores de personas procesadas por servicio y recorridos completados son
distintos: alguien puede haber pasado torniquetes y estar aún caminando a salida.

## CSV, proyectos y reportes

Desde WalkSim 3.2 se escribe esquema 5 para incluir Plaza; se siguen leyendo los
proyectos anteriores de Accesos y colas en esquema 4, con respaldo al convertirlos.

**Plantilla CSV** descarga columnas de la tarea seleccionada. Las opciones de texto
son códigos (`access`, `metro_entry`, `metro_exit`, `turnstile`, `free`, `uniform`,
`random`, `intermittent`, `batch`, `constant`, `exponential`, `time`, `rate`). Las
columnas numéricas y unidades son las indicadas por sus nombres y el formulario.
Use UTF-8, coma con punto decimal o punto y coma con coma decimal. Cada fila es una
alternativa; se valida el lote completo antes de incorporarlo. Máximo 30 escenarios
por módulo, 10 000 peatones generados por ejecución y 8 MiB por proyecto.

Los resultados se invalidan al editar los datos pertinentes, conservando el snapshot
original como historial hasta reemplazarlo. Un borrador incompleto se puede guardar.
Se registran datos predeterminados, introducidos, observados e importados de CSV.

El esquema `.wksim` 4 incluye Accesos y colas y lee esquemas 1 (2.1) y 3 (3.0).
Al convertir sobre el mismo archivo se conserva una copia `.v2-backup.wksim` o
`.v3.0-backup.wksim` si no existía. Las versiones antiguas del programa no deben
usarse para escribir el formato nuevo; el número del esquema lo detecta.

El informe incluye datos activos, procedencia, ecuaciones, alternativas, capacidad,
Erlang C cuando corresponde, cohortes, colas, densidades, censura, versión de motor,
semilla y gráficas vectoriales. Conserve `nombre_figuras` junto al `.tex`.

Abra `examples/AccessQueue_Metro_Comparacion.wksim` para comparar dos y cuatro
 torniquetes con datos sintéticos y resultados ya ejecutados. Las plantillas se
encuentran en `examples/csv/access_*.csv`.

## Fuentes del método

- [Eclipse SUMO: Pedestrians](https://sumo.dlr.de/docs/Simulation/Pedestrians.html).
- [Eclipse SUMO: TripInfo / personinfo](https://sumo.dlr.de/docs/Simulation/Output/TripInfo.html).
- [GNU Octave Queueing: Erlang C](https://octave.sourceforge.io/queueing/function/erlangc.html).
- [MIT 15.072J: Queues, Theory and Applications](https://ocw.mit.edu/courses/15-072j-queues-theory-and-applications-spring-2006/).

Las capacidades de escaleras y dispositivos requieren fuentes o mediciones propias
 del estudio; los valores iniciales no proceden de estas referencias.
