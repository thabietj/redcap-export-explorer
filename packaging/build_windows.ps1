$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$Python = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }
if (-not $env:PYINSTALLER_CONFIG_DIR) { $env:PYINSTALLER_CONFIG_DIR = Join-Path (Get-Location) "build\pyinstaller-config" }
New-Item -ItemType Directory -Force -Path $env:PYINSTALLER_CONFIG_DIR | Out-Null
& $Python -m PyInstaller --noconfirm --clean redcap_export_explorer.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }
$ISCC = if ($env:ISCC) { $env:ISCC } else { "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" }
if (-not (Test-Path $ISCC)) { throw "Install Inno Setup 6 or set ISCC to ISCC.exe" }
& $ISCC "packaging\windows_installer.iss"
if ($LASTEXITCODE -ne 0) { throw "Windows installer build failed" }
