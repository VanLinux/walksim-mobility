# WalkSim Mobility

**WalkSim Mobility** es una herramienta ligera para la simulación y el análisis de movilidad peatonal. Su objetivo es permitir que el usuario describa un problema mediante parámetros de ingeniería sencillos mientras **Eclipse SUMO** funciona como motor de microsimulación en segundo plano.

El usuario no necesita editar archivos XML, utilizar NetEdit ni programar escenarios de SUMO.

## Versión 2.0.0

El análisis se concentra en un problema:

**Corredor peatonal bidireccional.**

El usuario define:

- longitud y ancho útil del corredor;
- flujo peatonal A → B;
- flujo peatonal B → A;
- velocidad peatonal de referencia;
- periodo de análisis;
- semilla de simulación.

WalkSim Mobility construye automáticamente el escenario, ejecuta SUMO con el modelo peatonal **striping** y procesa la salida para presentar indicadores interpretables.

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

## Resultados actuales

- peatones que completaron el recorrido;
- tiempo medio de recorrido;
- velocidad media efectiva;
- tiempo medio perdido;
- distancia media recorrida;
- resultados separados por sentido A → B y B → A.

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

La versión 2.0.0 no incluye todavía cruces peatonales, interacción vehículo-peatón, semáforos ni edición libre de redes.

## Autor

Héctor Alonso Benítez García

## Licencia

GNU General Public License v3.0.

