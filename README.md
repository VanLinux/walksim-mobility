# WalkSim Mobility

**WalkSim Mobility** es una herramienta ligera para la simulación y el análisis de movilidad peatonal. Su objetivo es permitir que el usuario describa un problema mediante parámetros de ingeniería sencillos mientras **Eclipse SUMO** funciona como motor de microsimulación en segundo plano.

El usuario no necesita editar archivos XML, utilizar NetEdit ni programar escenarios de SUMO.

## Versión 2.1.0

La familia 2 incorpora un estudio con casos analíticos seleccionables y microsimulación
peatonal de corredor. La interfaz permite introducir los datos manualmente o importar CSV.

## Guardar y recuperar avances

- **Archivo → Guardar .wksim** (`Ctrl+S`) y **Guardar como** (`Ctrl+Shift+S`).
- **Abrir .wksim** (`Ctrl+O`) recupera identificación, borradores, casos y resultados.
- **Nuevo estudio** (`Ctrl+N`) pregunta por cambios pendientes, igual que abrir y cerrar.
- El proyecto es JSON UTF-8 validado, portable y versionado; se escribe de forma atómica.
  No incluye ejecutables ni necesita los archivos temporales originales para consultar resultados.
- Se puede guardar una captura analítica incompleta. Los resultados conservan las entradas
  usadas para calcularlos; editar un formulario no cambia retroactivamente un caso calculado.

## Análisis disponibles

1. Acera / sendero por aforo y velocidad.
2. Acera / sendero por ocupación observada.
3. Acera con pelotones, promedio de 5 min.
4. Área de espera / andén por ocupación.
5. Cruce semaforizado: demora y revisión cinemática de cruce opcional.
6. Cruce sin semáforo: demora por aceptación de brechas sin cesión de paso.
7. Escalera: flujo ascendente y reserva por contraflujo menor.

Seleccione el método en **Análisis peatonal**: se muestran solo sus datos. Pulse
**Calcular y añadir al estudio** para conservar un caso. Puede acumular casos y
eliminar uno seleccionado. La clasificación por espacio de circulación se contrastó
con el HCM 7, capítulo 24; las fuentes y límites de cada método aparecen con sus resultados.
Las categorías por demora del documento no se presentan como el PLOS completo HCM 7.

Para simular un caso de acera o pelotones con aforo, seleccione su resultado y pulse
**Preparar microsimulación del caso seleccionado**. Indique longitud y distribución
A → B; el programa transfiere ancho efectivo, demanda, velocidad y periodo al corredor.
Después pulse **Simular corredor**. SUMO conserva el cálculo microscópico con `striping`.

## Datos CSV

**Descargar plantilla CSV** exporta el ejemplo del método seleccionado. **Importar
casos CSV** valida todo el lote antes de incorporarlo. Las plantillas se incluyen
también en [examples/csv](examples/csv). Consulte [la guía de columnas](docs/CSV_GUIDE.md).
El corredor tiene su plantilla independiente; se carga un escenario y se ejecuta a petición.

Puede abrir [el estudio didáctico](examples/estudio_ejemplo.wksim) desde Archivo → Abrir.
Sus datos son ejemplos sintéticos y su analista es «Analista de ejemplo».

## Reporte completo LaTeX

**Archivo → Exportar reporte .tex** solicita el nombre del analista si aún no se
ha indicado. Incluye identificación, notas, todos los casos calculados, entradas,
ecuaciones, desarrollo, resultados, límites LOS, hipótesis y referencias. También
incluye las microsimulaciones con parámetros propios, semilla y versión exacta del motor.
Se excluyen borradores no calculados. El documento es autónomo, en tamaño carta,
sin archivos auxiliares de datos ni bibliografía externa.

Para compilar (opcional, la exportación no necesita LaTeX):

```bash
pdflatex informe_walksim.tex
pdflatex informe_walksim.tex
```

Se necesitan los paquetes LaTeX habituales (amsmath, longtable, booktabs, lmodern,
xcolor, fancyhdr e hyperref). Si está disponible, se usa babel en español;
con una instalación mínima se conserva el texto español y se usa babel en inglés.

## Interfaz de la versión 2

- Menú **Apariencia → Modo claro / Modo oscuro**; la elección se conserva al cerrar.
- Ventana inicial ajustada al espacio disponible de la pantalla.
- Parámetros y esquema en columnas para ventanas amplias y apilados en ventanas estrechas.
- Pestañas desplazables y contenido con desplazamiento para pantallas pequeñas.
- Tarjetas de resultados distribuidas en cuatro, dos o una columna según el ancho.
- Tabla de resultados con columnas ajustables y desplazamiento horizontal.
- La interfaz presenta el análisis peatonal sin avisos sobre el motor interno.

Eclipse SUMO sigue siendo una dependencia de ejecución. Si una simulación falla,
la interfaz presenta un aviso general; la terminal conserva el detalle técnico
para diagnóstico. Los requisitos de instalación se describen más abajo.

## Resultados de microsimulación

- peatones que completaron el recorrido;
- tiempo medio de recorrido;
- velocidad media efectiva;
- tiempo medio perdido;
- distancia media recorrida;
- resultados separados por sentido A → B y B → A;
- agentes iniciados e inconclusos, ocupación media y máxima global;
- densidad temporal y espacio equivalente global durante la demanda;
- LOS indicativo del espacio global, con límites de interpretación explícitos.

La simulación se ejecuta en un hilo de trabajo y tiene un límite de 180 s por subproceso.
Los casos analíticos usan ecuaciones en Python; sus resultados no se atribuyen a una
microsimulación de geometrías no implementadas. [Metodología y fuentes](docs/METHODOLOGY.md).

## Arquitectura

```text
Interfaz PySide6
      ↓
Modelo de escenario
      ↓
Generador SUMO
      ↓
netconvert + sumo
      ↓
personinfo.xml
      ↓
Procesador de resultados
      ↓
Indicadores WalkSim Mobility
```

Los XML se generan internamente y no forman parte del flujo de trabajo normal del usuario.

## Requisitos

- Python 3.11 o superior.
- Eclipse SUMO instalado y con los ejecutables `sumo` y `netconvert` disponibles en `PATH`.

Documentación oficial de peatones en SUMO:
https://eclipse.dev/sumo/docs/Simulation/Pedestrians.html

## Instalación de desarrollo

```bash
git clone https://github.com/VanLinux/walksim-mobility.git
cd walksim-mobility

python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Ejecución

```bash
walksim
```

También puede iniciarse con:

```bash
python -m walksim
```

## Alcance

WalkSim Mobility no pretende sustituir a SUMO, NetEdit o SUMO-GUI. Es una capa de abstracción orientada a problemas específicos de movilidad peatonal, con escenarios parametrizados y resultados de ingeniería.

La microsimulación representa un corredor sin vehículos ni semáforos. Los módulos analíticos de espera, escaleras y cruces aplican los métodos documentados en [Metodología](docs/METHODOLOGY.md).

## Autor

Héctor Alonso Benítez García

## Licencia

GNU General Public License v3.0.

