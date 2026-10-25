# Historial de cambios

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
