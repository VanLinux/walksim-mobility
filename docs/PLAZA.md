# WalkSim Mobility 3.2 · Plaza y flujos cruzados

Fase 3 del desarrollo: un recinto peatonal con varios accesos, matriz origen–destino
local y mapas derivados de la microsimulación. Los valores iniciales y los estudios
incluidos son sintéticos. El analista debe sustituirlos por datos del sitio.

## Flujo de trabajo

1. Indique proyecto, ubicación, analista y notas en Proyecto.
2. Abra **Plaza y flujos cruzados**. Seleccione plaza, vestíbulo, cruce + o cruce T.
3. Defina dimensiones Este–Oeste y Norte–Sur, accesos, anchos y velocidad.
4. Capture las tasas OD en peat/h: filas son orígenes, columnas destinos.
5. Pulse **Calcular geometría y demanda** para revisar área, demanda y flujos por acceso.
6. Ajuste observación, calentamiento, despeje, semilla, intervalo de serie y celda.
7. Pulse **Simular mis datos**. Se ejecuta la matriz y geometría del escenario seleccionado.
8. Revise Resultados, Resultados OD y Gráficas. El selector cambia entre cuatro mapas.
9. Duplique el escenario, cambie geometría o demanda, calcule y simule la alternativa.
10. Compare resultados o exporte comparación, OD, celdas y series CSV; guarde mapas PNG/PDF.
11. Guarde el proyecto `.wksim` y exporte el reporte `.tex` desde Archivo.

Simulación → **Simular mis datos · Plaza y flujos cruzados** ejecuta este módulo.
F5 conserva su acción Walkway. **Simular ejemplo** añade un corredor Walkway de
muestra; no ejecuta los datos de Plaza.

## Plantillas y accesos

- Plaza rectangular y vestíbulo: área rectangular abierta, con dos accesos Este/Oeste,
  tres Sur/Este/Oeste o cuatro Norte/Sur/Este/Oeste.
- Cruce +: cuatro brazos de ancho común conectados al área central rectangular.
- Cruce T: brazos Sur/Este/Oeste, con el mismo criterio de conexión central.
- Cada acceso exterior tiene longitud y ancho propios (longitud común, ancho por lado).
- El ancho de los accesos debe caber en el lado del recinto; en cruces debe caber en el brazo.
- El área del mapa incluye recinto o brazos interiores. Excluye los accesos exteriores.
- Las celdas OD de accesos inactivos se deshabilitan y se ignoran en el cálculo; sus
  textos se conservan en el borrador para recuperarlos al volver a otra plantilla.

Las plantillas no requieren dibujar ni editar XML. Un vestíbulo y una plaza rectangular
comparten el procedimiento geométrico: la denominación describe la aplicación del estudio.
No se incluyen obstáculos interiores, columnas, giros de accesos ni geometría urbana completa.

## OD local y reparto de destinos

La matriz fija cuatro códigos: **N**, **S**, **E**, **W**. Cada celda qij es una tasa
absoluta en peat/h. La diagonal debe ser cero. La suma de fila Qi es la demanda del
origen y qij/Qi es su proporción de destinos. Una fila cero representa un origen sin
entradas; una columna cero representa un acceso sin salidas en el periodo modelado.

Se puede representar, por ejemplo, dos accesos con demanda de entrada y varias
salidas usando filas nulas en los lados que sólo reciben peatones. No se generan
viajes externos a la instalación ni se estima la matriz mediante un modelo urbano.

**Uniforme** genera separación constante por OD, con primera llegada a media separación.
**Aleatoria** genera intervalos exponenciales Poisson por OD con semillas derivadas
reproducibles. Las llegadas continúan durante calentamiento y observación y cesan
al terminar esta última. Las tasas nominales y los conteos realizados pueden diferir.

## Matriz CSV

**Matriz guía CSV** descarga un archivo UTF-8 con esta estructura:

```csv
origin,N,S,E,W
N,0,1200,200,0
S,1200,0,0,200
E,200,0,0,1200
W,0,200,1200,0
```

La guía contiene ejemplos y deja en cero los accesos inactivos de la plantilla actual.
Use exactamente esos códigos y orden, con cuatro filas.
**Importar matriz CSV** reemplaza sólo la matriz del caso seleccionado, tras validar
el archivo completo. **Exportar matriz CSV** guarda la demanda activa de ese caso.
Se admite coma y punto decimal, o punto y coma con coma decimal.

**Plantilla de escenarios** usa formato largo: una fila por cada uno de los doce pares
OD no diagonales, incluyendo ceros. La columna `name` agrupa filas en un escenario.
Las columnas de geometría y periodos se repiten en cada fila del grupo y deben coincidir.
No se admiten pares repetidos, grupos incompletos ni demanda positiva en accesos inactivos.
La plantilla contiene sólo los campos que requiere la tarea seleccionada. Los códigos
son `rectangle`, `hall`, `cross`, `tee`; accesos `2`, `3`, `4`; llegada `uniform` o `random`.

Las plantillas están en `examples/csv/plaza_*.csv`. No confunda la matriz cuadrada
con la plantilla de escenarios completa: tienen botones de importación separados.

## Motor y red

Se utiliza Eclipse SUMO con modelo peatonal **striping**. Se genera un área común
`walkingArea` y sus caminos de acceso, con permisos peatonales. Todos los movimientos
comparten la misma ejecución y pueden interactuar.

En rectángulos se especifica la forma completa del área común. En cruces + y T se
construyen brazos interiores y un área central rectangular, evitando que una conexión
directa entre accesos recorte las esquinas de un polígono cóncavo. La forma del área
central generada se contrasta con la solicitada antes de simular.

Los mapas proceden de la salida FCD, con posición y tiempo cada segundo. Son resultados
del motor y no una implementación propia de fuerzas sociales. Striping usa franjas y
aproximaciones de trayectorias; las zonas críticas no son mediciones de campo ni una
validación del modelo. No se calculan conflictos de seguridad ni un PLOS HCM completo.

## Malla y cuatro mapas

El lado de celda solicitado se ajusta ligeramente para cubrir cada dimensión con
celdas iguales. Las celdas de borde se recortan por el polígono y se usa su área real.
Las celdas sin área de circulación no acumulan posiciones ni aparecen coloreadas.

Para una celda k, ocupación nk(t), área Ak y observación T:

- **Densidad media:** Pk/(Ak T), en peat/m².
- **Densidad máxima muestreada:** max nk(t)/Ak, en peat/m².
- **Ocupación acumulada:** Pk = suma nk(t) Δt, en peatón·s.
- **Permanencia media por visitante:** Pk/Uk, en s; Uk es el número de personas
  distintas observadas en esa celda durante el periodo.

Cada posición se mantiene hasta el siguiente segundo, integrando sólo la parte
que coincide con observación. No se interpola entre celdas. Los máximos son muestreados;
una visita muy breve puede no aparecer. Permanencia es tiempo observado por visitante
de celda, no tiempo completo de viaje. Una persona puede visitar múltiples celdas.

Las cinco celdas críticas se ordenan por densidad media. Las tres primeras se marcan
con cruces en el mapa. No corresponden a un umbral de seguridad. Cada mapa tiene su
propia escala y unidad: compare valores de la barra al contrastar alternativas.

El área media cumple Nmedia = suma Pk/T. Su densidad global es Nmedia/A. La serie
promedia esa ocupación en intervalos, con último intervalo parcial si es necesario.
Las posiciones del área central fuera del polígono se excluyen y se informan: revise
el caso si aparece ese aviso.

## Resultados OD y periodos

- Los conteos generados/completados/pendientes incluyen calentamiento.
- La cohorte se define por generación solicitada durante observación, y sólo sus
  recorridos completados antes del límite forman la muestra de tiempos y velocidades.
- El tiempo total es salida menos generación solicitada: incluye accesos y espera de
  inserción. La velocidad espacial es suma de longitudes reales / suma de esos tiempos.
- Tiempo perdido procede de `personinfo` del motor; puede excluir esperas de inserción.
- P95 usa interpolación lineal entre tiempos ordenados.
- Despeje completo es N/A si quedan pendientes. Si terminó todo, es el tiempo desde
  final de observación hasta última salida (cero si ya estaba despejado).
- Sin demanda no hay muestra de tiempos ni velocidades; se muestra N/A.
- Los pendientes pueden sesgar a la baja los tiempos de quienes terminaron.

## Guardado, límites y reporte

El esquema `.wksim` 5 guarda geometría, matriz, borradores, alternativas, resultados OD,
series y celdas. Lee esquemas 1, 3 y 4 (versiones 2.1, 3.0, 3.1). Al sobrescribir un
proyecto anterior conserva una copia `.v2-backup.wksim`, `.v3.0-backup.wksim` o
`.v3.1-backup.wksim` si no existía. Use la versión nueva para guardar ese formato.

Editar los datos pertinentes invalida los resultados visibles; el snapshot anterior
se conserva hasta reemplazarlo. Se distinguen datos predeterminados, introducidos,
observados e importados de CSV. Puede guardar celdas vacías como borrador.

Límites de esta entrega: 2–4 accesos, 30 alternativas por módulo, 2500 celdas,
10 000 peatones y 5 millones de persona·s potenciales por ejecución, proyecto máximo
8 MiB. El control de tamaño potencial es conservador y busca mantener el uso ligero.
Reduzca demanda/duración o aumente celda cuando se solicite.

El reporte carta requiere analista e incluye matriz, geometría, procedencia, ecuaciones,
cohortes, resultados por OD, celdas críticas, versión del motor, semilla, advertencias
y cuatro mapas vectoriales por caso simulado. Conserve `nombre_figuras` junto al `.tex`.

Abra **examples/Plaza_Comparacion.wksim** para revisar dos plazas con la misma demanda,
semilla y periodos. Las dimensiones cambian distancia de recorrido y área: una plaza
mayor no garantiza menor tiempo total. El estudio contiene datos sintéticos y ambos
casos ya ejecutados.

## Fuentes

- [SUMO Pedestrians](https://sumo.dlr.de/docs/Simulation/Pedestrians.html).
- [PlainXML y formas de walkingArea](https://sumo.dlr.de/docs/Networks/PlainXML.html).
- [FCDOutput](https://sumo.dlr.de/docs/Simulation/Output/FCDOutput.html).
- [TripInfo y personinfo](https://sumo.dlr.de/docs/Simulation/Output/TripInfo.html).
