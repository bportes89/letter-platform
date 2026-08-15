@echo off
cd /d "%~dp0backend"
if not exist .venv (
  py -3.12 -m venv .venv
  call .venv\Scripts\activate
  python -m pip install -r requirements.txt
) else (
  call .venv\Scripts\activate
)
if not exist .env copy .env.example .env >nul
python -m alembic upgrade head
python -m app.seed
python -m uvicorn app.main:app --reload --port 8000
