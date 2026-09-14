Write-Host "========================================="
Write-Host " TokenTotals PyInstaller Build Script    "
Write-Host "========================================="

Write-Host "
[1/3] Installing PyInstaller..."
pip install pyinstaller

$pluginDir = "C:\Users\Command Center\.gemini\config\plugins\token-cost-estimator\scripts"

Write-Host "
[2/3] Compiling Application Engine..."
pyinstaller --noconfirm --windowed --name "TokenTotals" --paths "$pluginDir" --hidden-import "uvicorn.logging" --hidden-import "uvicorn.loops" --hidden-import "uvicorn.loops.auto" --hidden-import "uvicorn.protocols" --hidden-import "uvicorn.protocols.http" --hidden-import "uvicorn.protocols.http.auto" --hidden-import "uvicorn.protocols.websockets" --hidden-import "uvicorn.protocols.websockets.auto" --hidden-import "uvicorn.lifespan" --hidden-import "uvicorn.lifespan.on" app_gui.py

Write-Host "
[3/3] Build Complete!"
Write-Host "Your standalone TokenTotals.exe app is located in the dist\TokenTotals folder."
