$ErrorActionPreference = "Stop"

Write-Host "========================================="
Write-Host " TokenTotals Hermes Windows Build        "
Write-Host "========================================="

Write-Host "`n[1/3] Installing pinned build dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt

Write-Host "`n[2/3] Building TokenTotals..."
python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "TokenTotals" `
    --add-data "pricing;pricing" `
    --add-data "icon.png;." `
    --add-data "icon_green.png;." `
    --add-data "icon_yellow.png;." `
    --add-data "icon_red.png;." `
    --collect-data "litellm" `
    --collect-submodules "google.auth" `
    --hidden-import "google.auth.credentials" `
    --hidden-import "tiktoken_ext" `
    --hidden-import "tiktoken_ext.openai_public" `
    --hidden-import "hermes_evidence_store" `
    --hidden-import "hermes_turn_ingest" `
    --hidden-import "hermes_turn_api" `
    --hidden-import "turn_receipt_terminal" `
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
    app_gui_hermes.py

$exe = Join-Path $PSScriptRoot "dist\TokenTotals\TokenTotals.exe"
if (-not (Test-Path $exe)) {
    throw "Build completed without expected executable: $exe"
}

$trace = Join-Path $PSScriptRoot "packaging-smoke-trace.txt"
Remove-Item $trace -Force -ErrorAction SilentlyContinue

function Write-SmokeTrace {
    if (Test-Path $trace) {
        Write-Host "--- packaged smoke trace ---"
        Get-Content $trace | ForEach-Object { Write-Host $_ }
        Write-Host "--- end packaged smoke trace ---"
    } else {
        Write-Host "Packaged smoke trace file was not created."
    }
}

Write-Host "`n[3/3] Running packaged smoke test..."
$smoke = Start-Process -FilePath $exe -ArgumentList "--smoke-test" -WorkingDirectory $PSScriptRoot -PassThru
if (-not $smoke.WaitForExit(90000)) {
    Stop-Process -Id $smoke.Id -Force -ErrorAction SilentlyContinue
    Write-SmokeTrace
    throw "Packaged smoke test timed out after 90 seconds"
}
$smoke.Refresh()
Write-SmokeTrace
if ($smoke.ExitCode -ne 0) {
    throw "Packaged smoke test failed with exit code $($smoke.ExitCode)"
}

Write-Host "`nBuild complete and smoke-tested."
Write-Host "Output: dist\TokenTotals\TokenTotals.exe"
