# WalkSim Mobility

**WalkSim Mobility** es una herramienta ligera para la simulación y el análisis de movilidad peatonal. Su objetivo es permitir que el usuario describa un problema mediante parámetros de ingeniería sencillos mientras **Eclipse SUMO** funciona como motor de microsimulación en segundo plano.

El usuario no necesita editar archivos XML, utilizar NetEdit ni programar escenarios de SUMO.

## Versión 0.1.0

La primera versión funcional se concentra deliberadamente en un solo problema:

**Corredor peatonal bidireccional.**

El usuario define:

- longitud y ancho útil del corredor;
- flujo peatonal A → B;
- flujo peatonal B → A;
- velocidad peatonal de referencia;
- periodo de análisis;
- semilla de simulación.

WalkSim Mobility construye automáticamente el escenario, ejecuta SUMO con el modelo peatonal **striping** y procesa la salida para presentar indicadores interpretables.

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

La versión 0.1.0 no incluye todavía cruces peatonales, interacción vehículo-peatón, semáforos ni edición libre de redes.

## Autor

Héctor Alonso Benítez García

## Licencia

GNU General Public License v3.0.
