$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Frontend = Join-Path $Root "frontend"

Write-Host "`n====================================" -ForegroundColor Cyan
Write-Host "       RAGFORGE STARTUP MANAGER" -ForegroundColor Cyan
Write-Host "====================================`n" -ForegroundColor Cyan

# Validate environment
if (!(Test-Path $Python)) {
    throw "Python virtual environment not found: $Python"
}

if (!(Test-Path $Frontend)) {
    throw "Frontend directory not found."
}

# Check PostgreSQL
Write-Host "[1/6] Checking PostgreSQL..." -ForegroundColor Yellow

$pg = Get-Service -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -match "postgresql"
    }

if ($pg -and ($pg | Where-Object Status -eq "Running")) {
    Write-Host "PostgreSQL is running." -ForegroundColor Green
}
else {
    Write-Warning "PostgreSQL service not detected as running. Verify your database."
}

# Check Ollama without restarting it
Write-Host "[2/6] Checking Ollama..." -ForegroundColor Yellow

try {
    $ollama = Invoke-RestMethod `
        -Uri "http://127.0.0.1:11434/api/tags" `
        -TimeoutSec 3

    Write-Host "Ollama is responding." -ForegroundColor Green
}
catch {
    Write-Warning "Ollama is unavailable. Check that it is already running."
}

# Start backend
Write-Host "[3/6] Starting FastAPI..." -ForegroundColor Yellow

$backend = Start-Process powershell.exe -PassThru -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$Root'; & '$Python' -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000"
)

# Wait for backend readiness
Write-Host "[4/6] Waiting for API..." -ForegroundColor Yellow

$ready = $false

for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 2

    try {
        $response = Invoke-WebRequest `
            -Uri "http://127.0.0.1:8000/docs" `
            -UseBasicParsing `
            -TimeoutSec 2

        if ($response.StatusCode -eq 200) {
            $ready = $true
            break
        }
    }
    catch {}
}

if (!$ready) {
    throw "FastAPI did not become ready. Check the backend terminal."
}

Write-Host "FastAPI is healthy." -ForegroundColor Green

# Start ingestion worker
Write-Host "[5/6] Starting ingestion worker..." -ForegroundColor Yellow

$worker = Start-Process powershell.exe -PassThru -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$Root'; & '$Python' -m backend.worker"
)

Write-Host "Worker process launched." -ForegroundColor Green

# Start frontend
Write-Host "[6/6] Starting Next.js..." -ForegroundColor Yellow

$frontendProcess = Start-Process powershell.exe -PassThru -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$Frontend'; npm run dev"
)

Write-Host "`n====================================" -ForegroundColor Green
Write-Host "          RAGFORGE STARTED" -ForegroundColor Green
Write-Host "====================================" -ForegroundColor Green

Write-Host "`nFrontend: http://localhost:3000"
Write-Host "Backend:  http://127.0.0.1:8000"
Write-Host "API Docs: http://127.0.0.1:8000/docs"

Write-Host "`nKeep the service terminals open."
Write-Host "Close their windows to stop the respective services."

