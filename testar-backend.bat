@echo off
cd /d "%~dp0backend"
if not exist .venv (
  echo Ambiente virtual nao encontrado. Execute iniciar-backend.bat uma vez antes.
  exit /b 1
)
call .venv\Scripts\activate
python -m pytest %*
