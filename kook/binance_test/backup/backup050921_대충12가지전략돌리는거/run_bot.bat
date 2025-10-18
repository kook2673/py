@echo off
chcp 65001
echo 🚀 고도화된 MA+ML 자동매매봇 실행
echo =====================================

echo.
echo 1. 빠른 테스트 (기본 설정)
echo 2. 2018-2024년 연속 백테스트 (간단)
echo 3. 2018-2024년 연속 백테스트 (상세)
echo 4. 슬라이딩 윈도우 백테스트
echo 5. 파라미터 튜닝 백테스트
echo 6. 사용자 정의 백테스트
echo.

set /p choice="선택하세요 (1-6): "

if "%choice%"=="1" (
    echo 빠른 테스트 실행 중...
    python quick_test.py
) else if "%choice%"=="2" (
    echo 2018-2024년 연속 백테스트 실행 중...
    python run_2018_2024.py
) else if "%choice%"=="3" (
    echo 2018-2024년 연속 백테스트 (상세) 실행 중...
    python run_yearly_backtest.py --start-year 2018 --end-year 2024
) else if "%choice%"=="4" (
    echo 슬라이딩 윈도우 백테스트 실행 중...
    python run_advanced_bot.py --data data/BTCUSDT/5m/BTCUSDT_5m_2024.csv --sliding-window --start-date 2024-01-01 --end-date 2024-03-31
) else if "%choice%"=="5" (
    echo 파라미터 튜닝 백테스트 실행 중...
    python run_advanced_bot.py --data data/BTCUSDT/5m/BTCUSDT_5m_2024.csv --auto-tune --tune-trials 100 --start-date 2024-01-01 --end-date 2024-01-31
) else if "%choice%"=="6" (
    echo 사용자 정의 백테스트...
    set /p data_file="데이터 파일 경로: "
    set /p start_date="시작 날짜 (YYYY-MM-DD): "
    set /p end_date="종료 날짜 (YYYY-MM-DD): "
    set /p balance="초기 자본: "
    set /p leverage="레버리지: "
    python run_advanced_bot.py --data "%data_file%" --start-date "%start_date%" --end-date "%end_date%" --balance %balance% --leverage %leverage%
) else (
    echo 잘못된 선택입니다.
)

echo.
echo 실행 완료!
pause
