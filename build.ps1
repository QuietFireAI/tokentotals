Write-Host "========================================="
Write-Host " TokenTotals PyInstaller Build Script    "
Write-Host "========================================="

$PythonVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if ($PythonVersion.Trim() -ne "3.12") {
  Write-Error "TokenTotals reproducible build requires Python 3.12; found Python $PythonVersion."
  exit 1
}

Write-Host "`n[1/3] Installing constrained build/runtime dependencies..."
python -m pip install -c constraints-py312.txt -r requirements.txt pyinstaller
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m pip check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n[2/3] Compiling Application Engine..."
python -m PyInstaller --noconfirm --windowed --name "TokenTotals" `
  --add-data "pricing_catalog.json;." `
  --hidden-import "uvicorn.logging" `
  --hidden-import "uvicorn.loops" `
  --hidden-import "uvicorn.loops.auto" `
  --hidden-import "uvicorn.protocols" `
  --hidden-import "uvicorn.protocols.http" `
  --hidden-import "uvicorn.protocols.http.auto" `
  --hidden-import "uvicorn.protocols.websockets" `
  --hidden-import "uvicorn.protocols.websockets.auto" `
  --hidden-import "uvicorn.lifespan" `
  --hidden-import "uvicorn.lifespan.on" `
  app_gui.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n[3/3] Build Complete!"
Write-Host "Standalone Windows app: dist\TokenTotals\TokenTotals.exe"
