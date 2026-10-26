# WalkSim Mobility 3.3 · Senderos compartidos · Fase 5

Esta entrega incorpora peatones y bicicletas en senderos pavimentados, con PLOS
por sentido, BLOS condicionado a datos de demora, microsimulación mixta y comparación
de alternativas. La Fase 4 (ampliación de escaleras) permanece pendiente por decisión
del proyecto. Los métodos de escaleras ya existentes siguen en sus módulos anteriores.

## Uso

1. Complete Proyecto, ubicación, nombre del analista y notas.
2. Abra **Sendero compartido** y elija ambos análisis, Sólo PLOS o Sólo BLOS.
3. Indique longitud y ancho útil total del sendero.
4. Capture flujos por modo y dirección, o conteos críticos de 15 min.
5. Introduzca velocidades representativas. Para BLOS, revise sus desviaciones estándar.
6. Para BLOS, documente la probabilidad de rebase demorado por sentido: con una muestra
   de intentos y demorados de campo, o una probabilidad sustentada directamente.
7. Pulse **Calcular nivel de servicio**. Sin probabilidad válida se muestran los eventos
   y la causa de BLOS N/A; no se infiere una probabilidad cero.
8. Configure llegadas, semilla y periodos; pulse **Simular mis datos** para ejecutar
   peatones y bicicletas reales dentro del mismo escenario SUMO.
9. Revise resultados, comparación, gráficas y método. Duplique el caso para alternativas.
10. Exporte comparación, grupos, series o gráficas. Guarde `.wksim` y exporte `.tex`
    desde Archivo; conserve la carpeta de figuras junto al informe.

La acción del menú **Simular mis datos · Sendero compartido** ejecuta el caso actual.
F5 mantiene la acción Walkway. **Simular ejemplo** añade un corredor Walkway de muestra.

## Demanda y unidades

Las velocidades se introducen en m/s, dimensiones en m y periodos en s. Las demandas
horarias se dividen entre PHF una vez, independientemente por cada modo y sentido.
Las cuatro columnas son peatones AB/BA y bicicletas AB/BA.

Con conteos de 15 min se multiplica cada conteo por cuatro. En Sólo PLOS no se pide
PHF para conteos; en BLOS se conserva porque corrige el término DPm del procedimiento,
no porque se vuelva a ajustar la demanda. Consulte la ecuación de DPm más adelante.
Los flujos por sentido evitan asumir una distribución 50/50; el analista debe medirlos
cuando sea posible. Una tasa cero representa ausencia de ese grupo.

## PLOS peatonal

Se aplican HCM 7, capítulo 24, Ecuaciones 24-5 a 24-7 y Exhibit 24-4. Para un peatón
representativo en cada sentido:

- Fp = qb,s (1 − Sp/Sb): bicicletas que lo rebasan por hora de caminata.
- Fm = qb,o (1 + Sp/Sb): bicicletas opuestas que encuentra por hora de caminata.
- F = Fp + 0.5 Fm: tasa ponderada por peatón·h.

qb,s y qb,o son flujos ciclistas de diseño del mismo sentido y el contrario. El
cociente de velocidades admite m/s porque ambas usan la misma unidad. El procedimiento
supone velocidad ciclista mayor que la peatonal y desprecia encuentros peatón–peatón.

| PLOS | Tasa ponderada F (eventos por peatón·h) |
|---|---:|
| A | F ≤ 38 |
| B | 38 < F ≤ 60 |
| C | 60 < F ≤ 103 |
| D | 103 < F ≤ 144 |
| E | 144 < F ≤ 180 |
| F | F > 180 |

Sin peatones en un sentido se informan tasas teóricas de referencia pero PLOS N/A.
No se elimina automáticamente el término de encuentros al aumentar el ancho: en
esta entrega no se presupone operación como dos instalaciones unidireccionales.
El límite E/F expresa experiencia deteriorada; no es capacidad física del sendero.

## BLOS ciclista: variante con probabilidad documentada

**Alcance explícito:** WalkSim calcula los eventos de los pasos 2–3, la tasa de
rebases demorados y la regresión/clasificación de los pasos 6–8 del HCM. La probabilidad
empírica introducida sustituye la estimación automática de bloqueo por carriles de
los pasos 4–5. Esta versión no debe presentarse como cálculo automático completo
de la probabilidad de bloqueo multimodal del HCM.

Se consideran únicamente peatones y bicicletas. Corredores, patinadores y bicicletas
infantiles se suponen ausentes; no se trasladan sus flujos a otra categoría. El
procedimiento se restringe a sendero pavimentado compartido, sin separación por modo,
y ancho de 8 a 20 ft (2.4384–6.096 m). Fuera de ese dominio BLOS es N/A.

### Eventos analíticos

El ciclista representativo tiene velocidad constante U, igual a la media ciclista.
La velocidad modal Vi se considera normal con media μi y desviación σi.
La probabilidad de rebasar un usuario situado x metros adelante es
P(Vi < U(1 − x/L)). Se integra de 0 a L por trapecios, en divisiones no mayores que
0.01 mi (16.09344 m). Multiplicando por densidad modal y dividiendo por tiempo de
recorrido se obtiene Ai, en rebases activos por ciclista·min. AT suma los modos.

Los encuentros incluyen M1 = (U/60) suma(qo,i/μi), más la contribución de usuarios
opuestos que todavía no habían entrado al tramo, integrando P(Vi > UX/L) para X
entre 0 y L. El cociente q/μ se implementa con unidades consistentes. Con desviación
cero se usa la distribución determinista para evitar divisiones por cero.

Los valores iniciales de media/desviación proceden del Exhibit 24-6 convertidos a SI:
peatones 3.4/0.6 mi/h, bicicletas 12.8/3.4 mi/h. Son valores por defecto, no datos del sitio.
Una normal con desviación grande puede tener cola negativa; se avisa al analista.

### Probabilidad y rebases demorados

- **Conteos:** PT = número de rebases demorados / intentos observados, por sentido.
- **Probabilidad documentada:** introduzca PT entre 0 y 1 y registre fuente, muestra
  o supuesto en las notas del proyecto.
- Cero intentos no demuestra PT = 0: en ese caso BLOS queda N/A.
- Cero demorados en una muestra positiva permite PT = 0.
- Un dato vacío conserva los demás cálculos, con BLOS N/A en ese sentido.

DPm = AT × PT × PHF, en rebases demorados por ciclista·min. El PHF corrige la
calibración histórica de este término a condiciones horarias, incluso cuando la
entrada de demanda son conteos de 15 min. DP = min(0.5 DPm, 1.5).

E = MT + 10 AT; RW = 0.3048 / ancho_m; CL = 1 con línea central, 0 sin ella.

**Score = 5.446 − 0.00809 E − 15.86 RW − 0.287 CL − DP.**

| BLOS sin ajuste | Score |
|---|---:|
| A | > 4.0 |
| B | > 3.5 a 4.0 |
| C | > 3.0 a 3.5 |
| D | > 2.5 a 3.0 |
| E | > 2.0 a 2.5 |
| F | ≤ 2.0 |

Se usa la convención de igualdad del HCM 7 aportado. Para bajo volumen: E ≤ 5
asigna A; 5 < E ≤ 10 asigna B, salvo que el score ya produzca A. Se conservan score,
clasificación sin ajuste y clasificación final, para que la decisión sea trazable.
Sin ciclistas de un sentido no se asigna BLOS a ese sentido.

**Alternativas:** si cambia ancho, demanda o mezcla, revise PT. Mantenerla constante
produce una comparación condicional que aísla el efecto de otros términos; no
predice cómo cambiaría la probabilidad de demora en la instalación modificada.
Los datos de campo o una probabilidad sustentada deben permitir justificar esa hipótesis.

## Microsimulación mixta con SUMO

Las bicicletas son vehículos `vClass=bicycle` con seguimiento IDM y movimiento
lateral de subcarriles. Los peatones son personas `striping`. Cada dirección ocupa
una mitad del ancho total, compartida por ambos modos; las mitades se declaran
adyacentes para que el motor pueda permitir rebases en la contraria. No se sustituye
la bicicleta por un peatón rápido.

La simulación existe aunque BLOS sea N/A. La línea central afecta la regresión
analítica; el motor conserva dos mitades direccionales tanto con línea como sin ella.
No se simula una prohibición de rebase por el simple hecho de marcar CL.

Las velocidades individuales deseadas se muestrean de normales recortadas a
0.2–15 m/s con semilla reproducible. En Sólo PLOS se usan las velocidades constantes
introducidas. No se afirma calibración de perfiles ni un modelo ciclista validado. Se adoptan
buffers de modelo de 0.3 m de separación lateral ciclista y 0.5 m entre peatón y
vehículo, como supuestos explícitos de simulación, no mínimos de diseño.
Se desactivan teletransportes de vehículos y se extiende el umbral de resolución
forzada de atascos peatonales para que los pendientes permanezcan como tales.
Las colisiones del motor no provocan teletransporte; si se registran se informa
su número como advertencia para revisar el escenario y la aproximación del modelo.

### Eventos observados

La salida FCD se lee cada 0.5 s. Se identifica un evento cuando dos usuarios que
están presentes en muestras consecutivas invierten su orden longitudinal:

- sentidos opuestos: encuentro peatón–bicicleta o bicicleta–bicicleta;
- mismo sentido: bicicleta que rebasa peatón o bicicleta que rebasa bicicleta.

La referencia longitudinal de la bicicleta se corrige del frente al centro,
considerando su longitud 1.6 m. Cada par se cuenta una sola vez por ejecución.
Se excluyen encuentros peatón–peatón y eventos fuera de observación. Pueden omitirse
eventos junto a entradas/salidas o más breves que el muestreo. La detección no evalúa
distancia lateral, maniobras peligrosas ni colisiones.

La exposición de cada grupo integra usuarios presentes × tiempo durante observación.
La tasa peatonal observada convierte eventos a hora de peatón; la ciclista a minuto
de ciclista. Las gráficas comparan esas tasas con las analíticas como descriptores:
no se recalcula PLOS/BLOS a partir de FCD y no se sustituye PT con estos eventos.
Una reducción de eventos completados por congestión no implica mejor nivel de servicio.

## Cohortes y resultados

Generados, iniciados, completados y pendientes incluyen calentamiento. Los tiempos
se refieren a quienes se generaron durante observación y completaron al límite de
despeje. Se informan muestra, tiempo medio, P95, velocidad espacial y tiempo perdido
por modo y sentido. Tiempo total incluye espera de inserción; tiempo perdido procede
del motor y puede usar otra referencia. La velocidad espacial es suma de distancias
reales / suma de tiempos totales. Los pendientes pueden sesgar la muestra completada.

Después de observación no se generan usuarios nuevos; el despeje continúa hasta su
límite. El tiempo de despeje completo es N/A cuando quedan pendientes.

## CSV, guardado y reportes

**Plantilla CSV** contiene sólo columnas pertinentes al análisis, modalidad de demanda
y fuente de demora. Una fila es un escenario. Use UTF-8, coma con punto decimal o
punto y coma con coma decimal. Códigos: `both`, `ped`, `bike`; `hourly`, `count`;
`uniform`, `random`; `yes`, `no`; `counts`, `probability`. Campos de probabilidad o
muestra pueden quedar vacíos, con BLOS N/A. Se valida todo el lote antes de importar.

Exportes: comparación, series, resultados y exposición por grupo, gráficas PNG/PDF.
El proyecto `.wksim` esquema 6 incluye senderos y lee esquemas 1, 3, 4 y 5. Al convertir
un original 3.2 conserva copia `.v3.2-backup.wksim`; los respaldos anteriores continúan.
Puede guardar borradores incompletos y recuperar el caso seleccionado. Editar entradas
marca resultados como desactualizados sin modificar sus snapshots originales.

El reporte carta incluye analista, datos activos y procedencia, ecuaciones, tablas LOS,
condiciones BLOS, muestras de demora, resultados por sentido, cohortes y gráficas.
Conserve `nombre_figuras` junto al `.tex` al trasladarlo.

Límites: 30 casos por módulo, 5000 usuarios por ejecución, 2 millones de usuario·s
potenciales y 8 MiB por proyecto. El control de tamaño es conservador para uso ligero.
La simulación admite 1.6–10 m de ancho; el dominio de BLOS sigue siendo 2.4384–6.096 m.

Abra **examples/Sendero_Compartido_Comparacion.wksim** para comparar dos anchos con
la misma demanda, semilla y PT. Las muestras de 100 intentos y 20 demorados son
sintéticas, no datos reales. Los dos casos contienen microsimulaciones ejecutadas.
Las plantillas están en `examples/csv/sendero_*.csv`.

## CROW y alcance de diseño

CROW se mantiene como referencia cualitativa para discutir convivencia, separación
y alternativas. Esta entrega no asigna mínimos de ancho CROW, índices de seguridad
ni decisiones automáticas de separación. La comparación necesita observaciones,
condiciones del sitio y una revisión de la metodología de diseño que se adopte.

## Referencias

- HCM 7, capítulo 24 aportado por el usuario: Exhibits 24-4, 24-5 y 24-6; ecuaciones
  24-5 a 24-16 y 24-34 a 24-35; ajuste de bajo volumen en página 24-26.
- [FHWA-HRT-05-137](https://www.fhwa.dot.gov/publications/research/safety/pedbike/05137/).
- [FHWA-HRT-05-138](https://www.fhwa.dot.gov/publications/research/safety/pedbike/05138/).
- [SUMO Bicycles](https://sumo.dlr.de/docs/Simulation/Bicycles.html).
- [SUMO Pedestrians](https://sumo.dlr.de/docs/Simulation/Pedestrians.html).
- [SUMO Sublane](https://sumo.dlr.de/docs/Simulation/SublaneModel.html).
- [SUMO Opposite Direction Driving](https://sumo.dlr.de/docs/Simulation/OppositeDirectionDriving.html).
