$ErrorActionPreference = "Stop"

Write-Host "========================================="
Write-Host " TokenTotals Windows Build               "
Write-Host "========================================="

Write-Host "`n[1/3] Installing pinned build dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt

Write-Host "`n[2/3] Building TokenTotals_QuietFireAI..."
python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "TokenTotals_QuietFireAI" `
    --add-data "pricing;pricing" `
    --add-data "icon.png;." `
    --add-data "icon_green.png;." `
    --add-data "icon_yellow.png;." `
    --add-data "icon_red.png;." `
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

$exe = Join-Path $PSScriptRoot "dist\TokenTotals_QuietFireAI\TokenTotals_QuietFireAI.exe"
if (-not (Test-Path $exe)) {
    throw "Build completed without expected executable: $exe"
}

Write-Host "`n[3/3] Running packaged smoke test..."
$smoke = Start-Process -FilePath $exe -ArgumentList "--smoke-test" -Wait -PassThru
if ($smoke.ExitCode -ne 0) {
    throw "Packaged smoke test failed with exit code $($smoke.ExitCode)"
}

Write-Host "`nBuild complete and smoke-tested."
Write-Host "Output: dist\TokenTotals_QuietFireAI\"
