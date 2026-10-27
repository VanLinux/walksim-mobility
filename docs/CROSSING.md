# Cruce peatonal semaforizado — WalkSim 3.4.0

La Fase 6 responde una pregunta concreta: **¿cuánto esperan los peatones, cuántos se acumulan y cuántos completan un cruce semaforizado aislado?** Admite un caso base y una alternativa. La Fase 4 (ampliación de escaleras) sigue pendiente.

## Uso

1. Abra **Análisis → Cruce semaforizado**.
2. Capture longitud entre aceras y ancho del paso en metros, demanda por sentido en peat/h y velocidad peatonal en m/s. A es la acera superior del esquema; B la inferior.
3. Indique ciclo, verde para iniciar y despeje peatonal, todos en segundos enteros. El programa obtiene el verde vehicular como `C − verde peatonal − despeje − 3`; debe quedar al menos 5 s. Los 3 s corresponden al amarillo vehicular supuesto de la plantilla.
4. Capture el flujo vehicular total en veh/h. Se divide por igual entre los dos sentidos. Puede ser cero.
5. **Calcular referencia L/v** obtiene el recorrido libre de referencia; **Simular mis datos** ejecuta el escenario introducido con SUMO. No son resultados de ejemplo.
6. Para comparar, duplique el escenario y cambie, por ejemplo, el verde peatonal. Simule cada alternativa. La pestaña Comparar reúne sus resultados y permite exportar CSV.

**Opciones de simulación** se despliega cuando hace falta cambiar duración (600 s por defecto) o semilla (42). Las llegadas terminan al acabar la duración; el modelo continúa dos ciclos adicionales sin nuevas llegadas. Parte vacío, sin calentamiento: se evalúa un episodio finito y no un régimen estacionario.

## Cuatro resultados principales

- **Recorrido de referencia:** `t₀ = L/v` en segundos. Excluye espera, área de aproximación e interacciones. No es el tiempo real de viaje de SUMO.
- **Espera media:** detención acumulada a velocidad menor que 0.1 m/s antes de entrar al enlace del cruce. La media se refiere a las personas que ya iniciaron antes de cerrar la simulación. Incluye a quien sigue cruzando; excluye a quien aún espera. Se muestra el tamaño de muestra.
- **Cola máxima A/B:** máximos por acera del número de personas detenidas antes del cruce, muestreados cada 0.5 s. Incluye las aproximaciones saturadas; no incluye demanda que no logró insertarse.
- **Completados/programados:** completa quien abandona el enlace de cruce hacia el área de salida, aunque aún camine por el acceso final. Se muestran porcentaje, pendientes por sentido y personas aún no insertadas, aún esperando y aún cruzando.

No se asume que quien inició también completó, ni que toda demanda se insertó. La espera de los que siguen esperando está censurada: no se mezcla con una media de esperas completas y puede hacer que la media presentada parezca favorable cuando la demanda es muy alta. Revise siempre pendientes y muestra.

## Señalización y geometría

Una vía recta, un carril equivalente por sentido, un paso peatonal y dos accesos. No hay giros, refugios, semáforos actuados, otros cruces, estacionamiento ni rutas alternativas. Longitud entre 5 y 20 m; ancho entre 2 y 10 m. Cada carril equivalente tiene ancho `L/2` para que la longitud geométrica del paso coincida con la entrada; **no representa una propuesta de sección vial ni de número real de carriles**. El esquema de interfaz es orientativo, no está a escala.

`netconvert` genera las áreas peatonales y un cruce de longitud explícita L. Se comprueba que hay exactamente un enlace de cruce, que coincide con L y que la señal controla su entrada. El ciclo empieza con verde vehicular y se repite:

1. Verde vehicular, peatones en rojo.
2. Amarillo vehicular de 3 s, peatones en rojo.
3. Verde peatonal para iniciar, vehículos en rojo.
4. Despeje con todos en rojo: quienes entraron pueden terminar, no se habilitan nuevas entradas.

Se avisa si el despeje es menor que L/v. Es una comprobación de coherencia **orientativa**, no certifica tiempos de señalización contra una norma. Velocidad deseada vehicular 30 km/h, modelo Krauss; peatones striping con velocidad deseada constante. El caudal vehicular aporta contexto e interacción básica: no se evalúan capacidad ni LOS vehicular, conflictos o riesgo.

Los accesos colocan las llegadas 10 m antes del área de espera y las salidas 10 m después del área de salida. Los recorridos en esas áreas pueden añadir longitud y afectar espera. Las llegadas son Poisson independientes, con la semilla y desplazamientos fijos por grupo. Cambiar únicamente los tiempos de señal conserva las mismas llegadas de peatones y vehículos. Para interpretar la comparación conserve demanda, velocidad, duración y semilla. Una sola semilla no cuantifica incertidumbre estadística.

La simulación usa pasos de 0.5 s y FCD para identificar detenciones, primera entrada y primera salida del cruce. Los cambios se observan con esa resolución temporal. No se permiten teletransportes por atasco; se conserva el registro de colisiones/solapamientos del motor y se advierte si contiene eventos. Esto no convierte el escenario en una evaluación de seguridad vial ni valida el modelo con datos reales.

## CSV y archivos

**Plantilla CSV** exporta una fila con los datos actuales. Para comparar, añada una segunda fila. Máximo dos casos; importación completa y validación antes de sustituir el estudio del módulo. Si ya hay resultados se pide confirmar esa sustitución. Los demás módulos no se reemplazan.

- UTF-8, con o sin BOM.
- Separador coma y punto decimal, o punto y coma con coma decimal.
- Encabezados exactos `name,length_m,width_m,ped_ab,ped_ba,speed_mps,cycle_s,walk_s,clearance_s,vehicles_ph,duration_s,seed`.
- Las tasas son horarias directas; no se aplica PHF ni se convierten silenciosamente conteos de periodos cortos.
- Cambiar datos conserva los resultados anteriores pero los marca obsoletos y los excluye de comparación y reporte hasta recalcular/simular.

Archivo → Guardar incluye ambas alternativas, borradores, procedencia de datos, señalización, resultados y series en `.wksim` (esquema 7). Se abren esquemas anteriores. Al sobrescribir un archivo 3.3/esquema 6 se conserva una copia `.v3.3-backup.wksim`. Las versiones anteriores de la aplicación no leen el nuevo esquema.

Archivo → Exportar reporte LaTeX requiere nombre del analista en Proyecto. Incluye identificación, entradas, supuestos, referencia L/v, indicadores totales y por sentido, muestra de espera, pendientes, metadatos del motor y gráficas PDF en la carpeta acompañante `_figuras`. Mantenga esa carpeta junto al `.tex` para compilar. También se exportan comparación CSV, serie de colas a 0.5 s y gráficas PNG/PDF desde el módulo.

Ejemplos: `examples/Cruce_Semaforizado_Comparacion.wksim` y `examples/csv/cruce_semaforizado_guia.csv`. Sus datos son hipotéticos, no mediciones de campo.

## Base metodológica y límites

El HCM 7, capítulo 24, excluye los cruces de vía y remite su análisis a los capítulos de intersecciones (19–23). Por ello este módulo **no aplica tablas de senderos, no asigna A–F y no afirma implementar un LOS HCM para cruces**. La referencia L/v es cinemática; espera, cola y completados proceden del modelo de simulación descrito.

Fuentes primarias de implementación:

- [SUMO — Pedestrians](https://sumo.dlr.de/docs/Simulation/Pedestrians.html).
- [SUMO — PlainXML: cruces, áreas y control](https://sumo.dlr.de/docs/Networks/PlainXML.html).
- [SUMO — Traffic Lights](https://sumo.dlr.de/docs/Simulation/Traffic_Lights.html).
- [SUMO — FCDOutput](https://sumo.dlr.de/docs/Simulation/Output/FCDOutput.html).
- [SUMO — Tutorial de cruce peatonal](https://sumo.dlr.de/docs/Tutorials/TraCIPedCrossing.html), consultado como referencia de topología. WalkSim usa ciclo fijo, sin pulsador ni TraCI.

Fuera de alcance: intersección completa, giros, cruce sin semáforo, optimización de señales, diseño normativo, calibración automática, LOS formal, mapas de calor y evaluación de seguridad. Las condiciones locales deben contrastarse con observación de campo antes de usar resultados para decisiones de proyecto.

Para mantener una ejecución ligera se limita demanda esperada a 3000 usuarios y dos millones de usuario·s potenciales; la realización no puede superar 5000 usuarios. Son límites de rendimiento del software, no capacidades peatonales o vehiculares.
