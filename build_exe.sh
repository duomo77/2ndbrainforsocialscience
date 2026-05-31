#!/bin/bash
echo "============================================"
echo " Research Operating System - App Builder"
echo "============================================"
echo ""

# Python 확인
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3가 설치되어 있지 않습니다."
    exit 1
fi

# 의존성 설치
echo "[1/3] 의존성 설치 중..."
pip3 install -r requirements.txt -q
pip3 install pyinstaller -q
echo "    완료."

# 이전 빌드 정리
echo "[2/3] 이전 빌드 정리 중..."
rm -rf build dist/__pycache__

# 빌드
echo "[3/3] 앱 빌드 중... (2-5분 소요)"
pyinstaller ROS.spec --clean --noconfirm

if [ -f "dist/ROS" ]; then
    echo ""
    echo "============================================"
    echo " [SUCCESS] 빌드 완료!"
    echo " 파일 위치: dist/ROS"
    echo "============================================"
    chmod +x dist/ROS
else
    echo "[ERROR] 빌드 실패."
    exit 1
fi
