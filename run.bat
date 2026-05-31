@echo off
REM Econometric Wiki Compiler - Windows run script
REM Usage: double-click this file or run it from cmd

cd /d "%~dp0"

echo Checking Python dependencies...
python -c "import PyQt6" 2>nul || pip install PyQt6
python -c "import fitz" 2>nul || pip install PyMuPDF
python -c "import openai" 2>nul || pip install openai
python -c "import yaml" 2>nul || pip install pyyaml

echo Starting Econometric Wiki Compiler...
python main.py
pause
