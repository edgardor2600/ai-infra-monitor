# AI Infra Monitor Backend - Development Server Script
# This script starts the FastAPI backend in development mode with auto-reload

Write-Host "Starting AI Infra Monitor Backend in development mode..." -ForegroundColor Green
Write-Host ""

# Check if uvicorn is installed
try {
    $uvicornVersion = python -m uvicorn --version 2>&1
    Write-Host "Uvicorn found: $uvicornVersion" -ForegroundColor Cyan
} catch {
    Write-Host "Error: uvicorn not found. Please install dependencies first:" -ForegroundColor Red
    Write-Host "  pip install -e backend/" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Starting server at http://localhost:8000" -ForegroundColor Cyan
Write-Host "API docs available at http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Start uvicorn with auto-reload
python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
