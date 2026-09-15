Write-Host "========================================="
Write-Host " TokenTotals PyInstaller Build Script    "
Write-Host "========================================="

Write-Host "`n[1/3] Installing build/runtime dependencies..."
python -m pip install -r requirements.txt pyinstaller
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n[2/3] Compiling Application Engine..."
pyinstaller --noconfirm --windowed --name "TokenTotals" `
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
