# Historial de cambios

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
