param(
    [Parameter(Mandatory=$true)][string]$Installer,
    [Parameter(Mandatory=$true)][string]$ExpectedVersion
)
$ErrorActionPreference = 'Stop'
$Installer = (Resolve-Path $Installer).Path
$testRoot = Join-Path $env:RUNNER_TEMP 'Prueba Héctor México'
$installDir = Join-Path $testRoot 'WalkSim Mobility'
$reportDir = Join-Path $env:GITHUB_WORKSPACE 'installation-results'
$env:PYTHONUTF8 = '1'
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$installLog = Join-Path $reportDir 'instalacion.log'
$process = Start-Process $Installer -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/DIR=`"$installDir`"", "/LOG=`"$installLog`"") -Wait -PassThru
if ($process.ExitCode -ne 0) { throw "Instalación fallida: $($process.ExitCode)" }
$exe = Join-Path $installDir 'WalkSim.exe'
if (-not (Test-Path $exe)) { throw 'No se instaló WalkSim.exe' }
if ((Get-Item $exe).VersionInfo.ProductVersion -ne $ExpectedVersion) {
    throw "El ejecutable no corresponde a WalkSim $ExpectedVersion"
}
$shortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) 'WalkSim Mobility.lnk'
if (-not (Test-Path $shortcut)) { throw 'No se creó el acceso directo' }
# Sin acceso a los Python/SUMO que pudiera tener la imagen de GitHub.
$env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
$env:SUMO_HOME = Join-Path $testRoot 'SUMO externo inexistente'
$env:PYTHONHOME = Join-Path $testRoot 'Python externo inexistente'
$env:PYTHONPATH = ''
Remove-Item Env:QT_PLUGIN_PATH -ErrorAction SilentlyContinue
Remove-Item Env:QT_QPA_PLATFORM_PLUGIN_PATH -ErrorAction SilentlyContinue
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
$env:HTTP_PROXY = 'http://127.0.0.1:9'
$env:HTTPS_PROXY = 'http://127.0.0.1:9'
$env:ALL_PROXY = 'http://127.0.0.1:9'
$env:NO_PROXY = ''
$report = Join-Path $reportDir 'comprobacion.json'
$process = Start-Process $exe -ArgumentList @('--self-test', "`"$report`"") -PassThru
if (-not $process.WaitForExit(300000)) {
    $process.Kill()
    throw 'La prueba del ejecutable excedió cinco minutos'
}
if (-not (Test-Path $report)) { throw "El ejecutable no produjo diagnóstico (código $($process.ExitCode))" }
$result = Get-Content $report -Raw | ConvertFrom-Json
Write-Output (Get-Content $report -Raw)
if (-not $result.ok) { throw $result.error }
if ($result.version -ne $ExpectedVersion) { throw 'La versión interna no corresponde al instalador' }
$required = @('bundled_sumo_and_netconvert', 'gui_tabs_fonts_and_themes',
    'bundled_examples', 'corridor_simulation', 'walkway_simulation', 'access_simulation',
    'plaza_simulation', 'shared_simulation', 'crossing_simulation',
    'save_and_reopen_wksim', 'latex_reports_and_pdf_figures_without_tex', 'gui_with_saved_results')
foreach ($check in $required) {
    if ($result.checks -notcontains $check) { throw "Falta comprobación: $check" }
}
if ($process.ExitCode -ne 0) { throw "El ejecutable terminó con código $($process.ExitCode)" }
if ($result.corridor_completed -le 0) { throw 'El corredor no completó recorridos' }
# El desinstalador debe conservar los trabajos fuera de la instalación.
$uninstall = Join-Path $installDir 'unins000.exe'
$process = Start-Process $uninstall -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART') -Wait -PassThru
if ($process.ExitCode -ne 0) { throw 'Falló la desinstalación' }
if (Test-Path $exe) { throw 'El ejecutable sigue instalado' }
if (-not (Test-Path (Join-Path $reportDir 'Práctica México.wksim'))) { throw 'Se perdió el ejercicio del usuario' }
if (Test-Path $shortcut) { throw 'El acceso directo no se retiró' }



