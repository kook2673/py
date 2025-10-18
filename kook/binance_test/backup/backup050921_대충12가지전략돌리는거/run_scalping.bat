@echo off
chcp 65001 > nul
echo 🚀 스켈핑 최적화 도구 실행
echo ========================================

:menu
echo.
echo 실행 모드를 선택하세요:
echo 1. 백테스트 실행 (파라미터 최적화)
echo 2. 실시간 모니터링
echo 3. 빠른 테스트
echo 4. 종료
echo.
set /p choice="선택 (1-4): "

if "%choice%"=="1" (
    echo.
    echo 🔍 백테스트 실행 중...
    python run_scalping_optimizer.py backtest
    pause
    goto menu
)

if "%choice%"=="2" (
    echo.
    echo 📊 실시간 모니터링 시작...
    echo Ctrl+C로 중지할 수 있습니다.
    python run_scalping_optimizer.py monitor
    pause
    goto menu
)

if "%choice%"=="3" (
    echo.
    echo ⚡ 빠른 테스트 실행 중...
    python run_scalping_optimizer.py quick
    pause
    goto menu
)

if "%choice%"=="4" (
    echo.
    echo 👋 프로그램을 종료합니다.
    exit
)

echo.
echo 잘못된 선택입니다. 다시 선택해주세요.
goto menu
