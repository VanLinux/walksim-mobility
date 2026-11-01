# Instalador completo para Windows 11 x64

El archivo **WalkSim-Mobility-3.4.2-Windows-x64-Setup.exe** instala WalkSim
con Python, Qt/PySide6, Matplotlib, NumPy, las fuentes Latin Modern, datos horarios
y Eclipse SUMO 1.28.0 incluidos. Instala accesos en el escritorio y el menú Inicio
y un desinstalador. No requiere privilegios de administrador, conexión a Internet,
Python, SUMO ni cambios en PATH en el equipo del estudiante.

No incluye un compilador LaTeX. El usuario sube a Overleaf el reporte .tex y
su carpeta de figuras PDF, cuando se genera. Los estudios se guardan como .wksim.

## Construcción

La configuración se adapta del instalador de MacroNet Transport.

El flujo `.github/workflows/windows-installer.yml` compila en Windows Server 2022
x64 con Python 3.12 y PyInstaller, y crea el instalador mediante Inno Setup 6.
Se ejecuta al cambiar código o empaquetado en `main` o `build/windows-*`.
Puede ejecutarse manualmente desde Actions.

Los componentes Python se fijan en `packaging/windows/requirements-build.txt`.
La distribución oficial de SUMO se descarga durante la construcción y se verifica
contra un SHA256 fijo en `prepare.py`. No se descarga durante la instalación.
El motor se conserva completo con sus DLL, datos y licencias originales.

Los comandos de construcción en una máquina Windows con Python 3.12 x64,
Git e Inno Setup 6 son:

```powershell
python -m pip install -r packaging/windows/requirements-build.txt
python -m pip install -e ".[dev]"
python packaging/windows/prepare.py
python -m PyInstaller --clean --noconfirm packaging/windows/walksim.spec
python packaging/windows/prepare.py --stage
$version = (Get-Content build/windows/build-info.json -Raw | ConvertFrom-Json).version
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" "/DAppVersion=$version" packaging/windows/installer.iss
```

La salida está en `dist/installer/`. Los trabajos del estudiante se guardan en
sus carpetas personales, fuera de la instalación.

## Pruebas del paquete

Un segundo runner instala el .exe en una carpeta con espacios y acentos,
elimina Python y SUMO externos de PATH, asigna SUMO_HOME y PYTHONHOME inválidos
y configura los proxies para impedir que SUMO dependa de descargas de esquemas.

El ejecutable instalado se inicia con `--self-test ruta.json` y comprueba:

- interfaz Qt, todas las pestañas, temas y fuentes incluidas;
- lectura de los estudios de ejemplo;
- SUMO y netconvert incluidos, con la versión esperada;
- cálculo y simulación de Corredor libre, Walkway, Accesos, Plaza, Sendero y Cruce;
- conservación de usuarios, guardado y recuperación .wksim;
- reportes .tex de cada módulo y figuras PDF sin invocar LaTeX;
- presentación de resultados en la interfaz y captura PNG;
- desinstalación y conservación del estudio fuera de la carpeta instalada.

El motor privado se selecciona junto al ejecutable: nunca se mezcla con un
SUMO externo. Los procesos nativos se aíslan de las DLL de Python/Qt.
En rutas Windows con caracteres no ASCII se usan copias locales relativas
de los esquemas XSD, como en MacroNet.

La publicación sólo se crea si pasan la construcción y las pruebas instaladas.
Incluye SHA256SUMS.txt. Se conserva el código fuente exacto y las licencias dentro
de la instalación. No se reemplaza una publicación de la misma versión con
un árbol de código distinto.

Estas pruebas automatizadas usan Windows Server 2022. La revisión manual
en los equipos Windows 11 del docente es adicional. El instalador no está firmado
digitalmente.

