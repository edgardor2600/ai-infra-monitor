@echo off
title AI Infra Monitor - Apagar Sistema
echo ===================================================
echo   Deteniendo todos los servicios de AI Infra Monitor
echo ===================================================
echo.

echo Cerrando procesos de Uvicorn (Backend)...
taskkill /FI "WINDOWTITLE eq Backend API (Uvicorn)*" /F /T >nul 2>&1

echo Cerrando Agente de Monitoreo...
taskkill /FI "WINDOWTITLE eq Agente Python*" /F /T >nul 2>&1

echo Cerrando Web Dashboard (React)...
taskkill /FI "WINDOWTITLE eq Dashboard React*" /F /T >nul 2>&1

:: Forzar cierre de procesos de desarrollo si quedaron huérfanos
taskkill /IM node.exe /F >nul 2>&1

echo.
echo ===================================================
echo  Todos los servicios han sido detenidos con éxito.
echo ===================================================
pause
