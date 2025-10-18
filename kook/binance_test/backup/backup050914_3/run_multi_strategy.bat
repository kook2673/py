@echo off
chcp 65001 > nul
echo ========================================
echo 다중 전략 포트폴리오 관리 시스템 실행
echo ========================================
echo.

REM Python 경로 확인
python --version > nul 2>&1
if errorlevel 1 (
    echo ❌ Python이 설치되지 않았거나 PATH에 없습니다.
    echo Python을 설치하고 PATH에 추가해주세요.
    pause
    exit /b 1
)

REM 필요한 패키지 확인
echo 📦 필요한 패키지 확인 중...
python -c "import pandas, numpy, matplotlib, seaborn" > nul 2>&1
if errorlevel 1 (
    echo ❌ 필요한 패키지가 설치되지 않았습니다.
    echo 다음 명령어로 설치해주세요:
    echo pip install pandas numpy matplotlib seaborn
    pause
    exit /b 1
)

echo ✅ 필요한 패키지가 모두 설치되어 있습니다.
echo.

REM 메뉴 출력
echo 📋 실행 옵션을 선택하세요:
echo.
echo 1. 기본 백테스트 실행 (2024년 전체, 100,000 USDT)
echo 2. 커스텀 백테스트 실행
echo 3. 전략 정보만 보기
echo 4. 종료
echo.

set /p choice="선택 (1-4): "

if "%choice%"=="1" (
    echo.
    echo 🚀 기본 백테스트 실행 중...
    python run_multi_strategy.py --start 2024-01-01 --end 2024-12-31 --capital 100000
) else if "%choice%"=="2" (
    echo.
    set /p symbol="거래 심볼 (기본값: BTCUSDT): "
    if "%symbol%"=="" set symbol=BTCUSDT
    
    set /p timeframe="시간프레임 (기본값: 1h): "
    if "%timeframe%"=="" set timeframe=1h
    
    set /p start_date="시작 날짜 (YYYY-MM-DD, 기본값: 2024-01-01): "
    if "%start_date%"=="" set start_date=2024-01-01
    
    set /p end_date="종료 날짜 (YYYY-MM-DD, 기본값: 2024-12-31): "
    if "%end_date%"=="" set end_date=2024-12-31
    
    set /p capital="초기 자본 (기본값: 100000): "
    if "%capital%"=="" set capital=100000
    
    echo.
    echo 🚀 커스텀 백테스트 실행 중...
    python run_multi_strategy.py --symbol %symbol% --timeframe %timeframe% --start %start_date% --end %end_date% --capital %capital%
) else if "%choice%"=="3" (
    echo.
    python run_multi_strategy.py --info
) else if "%choice%"=="4" (
    echo.
    echo 👋 프로그램을 종료합니다.
    exit /b 0
) else (
    echo.
    echo ❌ 잘못된 선택입니다. 1-4 중에서 선택해주세요.
    pause
    goto :eof
)

echo.
echo ✅ 실행이 완료되었습니다.
echo 📁 결과 파일들은 'logs' 디렉토리에 저장되었습니다.
echo.
pause
