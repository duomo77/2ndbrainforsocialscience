#!/bin/bash
# Econometric Wiki Compiler 실행 스크립트
# 사용법: bash run.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 의존성 확인 및 설치
echo "📦 의존성 확인 중..."
python3 -c "import PyQt6" 2>/dev/null || pip3 install PyQt6
python3 -c "import fitz" 2>/dev/null || pip3 install PyMuPDF
python3 -c "import openai" 2>/dev/null || pip3 install openai
python3 -c "import yaml" 2>/dev/null || pip3 install pyyaml

echo "🚀 Econometric Wiki Compiler 시작..."
python3 main.py
