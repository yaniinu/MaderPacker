$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

if (-not (Test-Path "$root\.venv\Scripts\python.exe")) {
    python -m venv "$root\.venv"
    if (-not $?) { throw "venv creation failed" }
}

& "$root\.venv\Scripts\python.exe" -m pip install --upgrade pip
& "$root\.venv\Scripts\python.exe" -m pip install PySide6 pycryptodome pyinstaller Pillow
if (-not $?) { throw "pip install failed" }

& "$root\.venv\Scripts\python.exe" -c "import PySide6, Crypto, PIL; print('env OK')"
