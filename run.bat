@echo off
REM Research Operating System web runtime

cd /d "%~dp0"

python -m pip install -r requirements.txt
npm install
npm run dev
pause
