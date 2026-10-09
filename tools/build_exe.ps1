$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

$py = "$root\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "venv missing: run tools/setup_env.ps1 first" }

& $py -m unittest discover -s tests
if (-not $?) { throw "tests must pass before packaging" }

# --windowed: no console; startup errors go to stderr when run from a terminal.
& $py tools\make_icon.py
if (-not $?) { throw "icon build failed" }

& $py -m PyInstaller --onefile --name MaderPacker --windowed --clean --icon "assets/logo.ico" --add-data "maderpacker/fonts;maderpacker/fonts" --add-data "maderpacker/icons;maderpacker/icons" --add-data "assets/logo.svg;assets" --add-data "assets/logo.png;assets" --add-data "fixtures/shubidx;fixtures" maderpacker/app.py
if (-not $?) { throw "pyinstaller build failed" }

Copy-Item "$root\dist\MaderPacker.exe" "$root\MaderPacker.exe" -Force
Write-Output "built: $root\MaderPacker.exe"
