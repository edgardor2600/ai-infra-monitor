@echo off
title AI Infra Monitor - Iniciador
echo ===================================================
echo   Iniciando AI Infrastructure Monitor + Disk Analyzer
echo ===================================================
echo.

:: 1. Ejecutar migración de base de datos
echo [1/4] Verificando migraciones de base de datos...
python backend/scripts/migrate_disk_analyzer.py

echo.
echo [2/4] Iniciando Servidor Backend API (Puerto 8000)...
start "Backend API (Uvicorn)" cmd /k "cd /d %~dp0 && python -m uvicorn backend.app.main:app --reload --port 8000"

timeout /t 3 >nul

echo [3/4] Iniciando Agente de Monitoreo...
start "Agente Python" cmd /k "cd /d %~dp0 && python -m agent run"

echo [4/4] Iniciando Web Dashboard (React)...
start "Dashboard React" cmd /k "cd /d %~dp0\dashboard && npm run dev"

echo.
echo ===================================================
echo  ¡Sistema iniciado correctamente!
echo  Abre tu navegador en: http://localhost:5173/disk-analyzer
echo ===================================================
pause
