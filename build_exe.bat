@echo off
chcp 65001 > nul
echo ============================================
echo  Research Operating System - EXE Builder
echo ============================================
echo.

:: Python 확인
python --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python이 설치되어 있지 않습니다.
    echo https://www.python.org/downloads/ 에서 설치하세요.
    pause
    exit /b 1
)

:: 의존성 설치
echo [1/3] 의존성 설치 중...
pip install -r requirements.txt -q
pip install pyinstaller -q
echo     완료.

:: 이전 빌드 정리
echo [2/3] 이전 빌드 정리 중...
if exist dist\ROS.exe del /f /q dist\ROS.exe
if exist build rmdir /s /q build

:: EXE 빌드
echo [3/3] EXE 빌드 중... (2-5분 소요)
pyinstaller ROS.spec --clean --noconfirm

if exist dist\ROS.exe (
    echo.
    echo ============================================
    echo  [SUCCESS] 빌드 완료!
    echo  파일 위치: dist\ROS.exe
    echo ============================================
    echo.
    echo 지금 실행하시겠습니까? (Y/N)
    set /p choice=
    if /i "%choice%"=="Y" start dist\ROS.exe
) else (
    echo.
    echo [ERROR] 빌드 실패. 위 오류 메시지를 확인하세요.
)
pause
