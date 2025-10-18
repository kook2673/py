@echo off
echo ========================================
echo 스켈핑 라이브 전략 시스템 시작
echo ========================================
echo.

cd /d "%~dp0"

echo Python 환경 확인 중...
python --version
echo.

echo 스켈핑 라이브 전략 실행 중...
python scalping_live_strategy.py

echo.
echo ========================================
echo 스켈핑 라이브 전략 시스템 종료
echo ========================================
pause
