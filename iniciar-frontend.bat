@echo off
cd /d "%~dp0frontend"
if not exist node_modules npm install
if not exist .env.local copy .env.example .env.local >nul
npx next dev --webpack -H 127.0.0.1 -p 3000
