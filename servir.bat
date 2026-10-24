@echo off
rem Serve o site local em http://localhost:8000 (Ctrl+C para parar). Porta opcional: servir.bat 8080
cd /d "%~dp0"
set PORTA=%1
if "%PORTA%"=="" set PORTA=8000
start "" "http://localhost:%PORTA%/"
python -m http.server %PORTA% -d site
