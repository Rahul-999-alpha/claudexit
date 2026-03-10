# claudexit Build Pipeline
# Run from the project root: powershell -ExecutionPolicy Bypass -File scripts/build.ps1

$ErrorActionPreference = "Stop"

Write-Host "=== claudexit Build Pipeline ===" -ForegroundColor Cyan
Write-Host ""

# Step 1: Build backend
Write-Host "[1/3] Building backend (PyInstaller)..." -ForegroundColor Yellow
Push-Location backend
python -m PyInstaller claudexit-backend.spec --noconfirm
if ($LASTEXITCODE -ne 0) {
    Write-Host "Backend build failed!" -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location
Write-Host "  Backend binary: backend/dist/claudexit-backend.exe" -ForegroundColor Green

# Step 2: Build frontend
Write-Host "[2/3] Building frontend (electron-vite)..." -ForegroundColor Yellow
npx electron-vite build
if ($LASTEXITCODE -ne 0) {
    Write-Host "Frontend build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "  Frontend built to out/" -ForegroundColor Green

# Step 3: Package installer
Write-Host "[3/3] Packaging installer (electron-builder)..." -ForegroundColor Yellow
npx electron-builder --win
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installer build failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Build Complete ===" -ForegroundColor Cyan
Write-Host "  Installer: release/" -ForegroundColor Green
Get-ChildItem release/*.exe | ForEach-Object { Write-Host "    $($_.Name) ($([math]::Round($_.Length / 1MB, 1)) MB)" -ForegroundColor Green }
