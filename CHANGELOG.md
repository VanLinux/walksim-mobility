# Historial de cambios

## 3.3.0 — 25 de octubre de 2026 · Fase 5: Senderos compartidos

- Nuevo módulo con PLOS y BLOS por sentido, selección de análisis y demanda horaria o conteos de 15 min.
- PLOS HCM 7 por encuentros/rebases ponderados; BLOS por eventos, ancho, línea central y demora documentada.
- Probabilidad calculada de intentos y demorados de campo, o valor sustentado; BLOS N/A cuando falta ese dato.
- BLOS condicionado: no se automatiza el modelo completo de bloqueo por carriles del HCM.
- Integración normal de velocidades, factor DP, corrección PHF y ajustes por bajo volumen trazables.
- Bicicletas-vehículo y peatones en ejecución SUMO con IDM, striping y subcarriles, sin teletransporte vehicular.
- Eventos geométricos FCD de 0.5 s, exposición por modo/sentido, cohortes, tiempos, P95 y pendientes.
- Alternativas, plantillas e importación CSV, exportes de grupos/series/comparación y gráficas PNG/PDF.
- Formato .wksim esquema 6; lectura anterior y respaldo automático al convertir archivos 3.2.
- Reporte técnico con analista, datos, método, restricciones, resultados y gráficas.
- Ejemplo sintético de dos anchos, ambos simulados; guía SHARED_PATH.md.
- La Fase 4 de ampliación de escaleras permanece pendiente por solicitud del usuario.

## 3.2.0 — 25 de octubre de 2026 · Fase 3: Plaza y flujos cruzados

- Plantillas de plaza/vestíbulo rectangular, cruce + y T, con 2–4 accesos.
- Matriz OD local editable en peat/h, sumas por origen y destino, guía y CSV completos.
- Ejecución SUMO striping compartida, con walkingArea explícita y brazos en cruces.
- Posiciones FCD por segundo, integración espacial y celdas recortadas por el polígono.
- Cuatro mapas: densidad media/máxima, ocupación acumulada y permanencia por visitante.
- Conteos, tiempos, P95, velocidad espacial y tiempo perdido por OD, con cohortes y pendientes.
- Alternativas, zonas críticas, exportes de OD, celdas, series y mapas PNG/PDF.
- Proyecto esquema 5; lee 1/3/4 y conserva respaldo al convertir un original 3.1.
- Reporte LaTeX con matriz, ecuaciones, trazabilidad, resultados y cuatro mapas por caso.
- Interfaz en claro/oscuro adaptable, acciones de simulación explícitas y guía integrada.
- Estudio sintético de comparación de plazas ejecutado y plantillas por geometría.
- Límites de cálculo documentados; sin índices de seguridad ni PLOS de plaza inferidos.

## 3.1.0 — 26 de octubre de 2026 · Fase 2: Accesos y colas

- Nueva pestaña adaptable en claro/oscuro: accesos individuales y Metro entrada/descarga.
- Puertas, torniquetes, filtros y acceso libre; datos activos según tarea.
- Servicio por tasa o tiempo medio, constante o exponencial, con varios dispositivos FCFS.
- Llegadas uniformes, Poisson, intermitentes y descargas masivas reproducibles.
- Recorridos SUMO enlazados por atención de eventos; escaleras por capacidad equivalente.
- Colas, acumulación, densidad global de área, utilización, esperas, P95, despeje y censura.
- Capacidad nominal, reserva entre descargas y referencia Erlang C sólo cuando aplica.
- Alternativas, CSV por tarea, gráficas PNG/PDF, comparación y series exportables.
- Esquema .wksim 4, lectura 1/3, borradores y snapshots; respaldo al convertir originales.
- Reporte LaTeX ampliado con entradas, procedencia, ecuaciones, motor, límites y figuras.
- Ejemplo Metro ejecutado de dos y cuatro torniquetes y guía ACCESS_QUEUE.md.
- Aclarados los nombres de las acciones que ejecutan datos del usuario.
- El modelo de cola es equivalente y no impone bloqueo espacial; no representa peldaños.

## 3.0.0 — 25 de octubre de 2026 · Walkway, primera entrega

- Nuevo espacio de trabajo Walkway, con modos operacional, diseño de ancho y
  demanda admisible para un LOS objetivo, PHF o conteo directo sin doble ajuste.
- Escenarios Base y alternativas independientes, comparación tabular y exportación CSV.
- Diseño con límites LOS estrictos, margen explícito y redondeo de ancho hacia arriba.
- Llegadas aleatorias Poisson o pelotones parametrizados, cohorte de observación,
  calentamiento, despeje y estadísticas de recorrido por sentido y percentiles.
- Series de acumulación, densidad, flujo y velocidad de recorridos finalizados;
  histograma de tiempos y exportación de gráficas PNG/PDF y series CSV.
- Comparación analítico–simulado con definiciones y N/A; LOS espacial global indicativo.
- Procedencia de datos y control de resultados desactualizados mediante firmas de entradas.
- Formato `.wksim` esquema 3 con escenarios y gráficos; lectura de esquema 1 y copia
  de respaldo automática al convertir un archivo 2.1 sobre su ubicación original.
- Reporte LaTeX ampliado con diseño, alternativas, trazabilidad y figuras PDF vectoriales.
- Interfaz neutral en claro/oscuro, paneles adaptables, guía de uso y metodología integradas.
- Acción Simular ejemplo crea un caso independiente sin reemplazar el estudio.
- Conservados los siete métodos 2.1, sus CSV y la microsimulación libre del corredor.
- Añadidos Matplotlib y datos de zona horaria para Windows; guías de instalación y actualización.
- Esta entrega no implementa aún plazas con OD/heatmaps, accesos de servicio,
  senderos compartidos ni nuevas microsimulaciones de escaleras o intersecciones.


## 2.1.0 — 24 de octubre de 2026 (familia 2)

- Retirada la barra de accesos a Nuevo, Abrir, Guardar y Exportar; las acciones
  siguen disponibles en Archivo y mediante sus atajos.
- Retirada la opción del repositorio en Ayuda.
- Renombrada la acción del menú Simulación a «Simular ejemplo»; ejecuta el
  corredor con los parámetros actuales (los valores iniciales son un ejemplo).

- Guardado y apertura de estudios `.wksim`, incluyendo identificación, borradores
  incompletos, casos analíticos y resultados de microsimulación; escritura atómica
  y aviso de cambios sin guardar.
- Reporte LaTeX autónomo, carta, con analista obligatorio, entradas, ecuaciones,
  desarrollo, tablas LOS, hipótesis, fuentes y trazabilidad de las simulaciones.
- Siete formularios analíticos: aceras por flujo u ocupación, pelotones de 5 min,
  espera, demora semaforizada, aceptación de brechas y escaleras ascendentes.
- Criterios espaciales HCM 7 verificados y convertidos exactamente a SI;
  diferenciación de las categorías por demora y los procedimientos PLOS completos.
- Plantillas CSV por método, importación validada por lotes y plantilla de corredor.
- Transferencia de un caso de acera o pelotones a la microsimulación, solicitando
  longitud y reparto de demanda por sentido.
- Ejecución de SUMO en hilo de trabajo, registro de versión y semilla, ocupación y
  densidad globales, y distinción de recorridos completados e inconclusos.
- Guía de CSV, metodología con fuentes y estudio didáctico portable.

## 2.0.0 — 24 de octubre de 2026

- Eliminados los avisos sobre SUMO del encabezado, inicio, proyecto, corredor,
  estado de ejecución y diálogo Acerca de.
- Añadidos modos claro y oscuro con selección persistente en el menú Apariencia.
- Adaptados el texto de inicio y el esquema del corredor al tema seleccionado.
- Eliminado el mínimo de ventana de 1050 × 700; el tamaño inicial respeta la pantalla.
- Añadido desplazamiento por pestaña y reorganización del corredor y resultados
  para ventanas estrechas; tabla con columnas ajustables y desplazamiento horizontal.
- Conservado el motor de simulación; dependencia e instalación documentadas en README.

## 1.0.0 — 24 de septiembre de 2026

- Primera versión funcional para un corredor peatonal recto bidireccional.
- Parámetros de geometría, flujos, velocidad, periodo y semilla.
- Ejecución sin interfaz gráfica de SUMO y resultados totales y por sentido.
