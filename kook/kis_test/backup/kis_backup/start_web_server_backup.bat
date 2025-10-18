@echo on
chcp 65001 >nul
echo ========================================
echo    스케줄러 웹 관리 시스템 시작
echo ========================================
echo.

REM 현재 디렉토리를 스크립트가 있는 디렉토리로 변경
cd /d "%~dp0"

echo 현재 디렉토리: %CD%
echo.

REM 기존 텔레그램 봇(telegram_bot.py) 프로세스 종료
echo 기존 텔레그램 봇 프로세스를 종료합니다...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance -ClassName Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'telegram_bot.py' } | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {} }"
timeout /t 2 >nul
echo 텔레그램 봇 종료 완료(없으면 무시).
echo.

REM 포트 5000이 사용 중인지 확인
netstat -an | findstr :5000 > nul
if %errorlevel% == 0 (
    echo [경고] 포트 5000이 이미 사용 중입니다.
    echo 기존 프로세스를 자동으로 종료합니다...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5000') do (
        if not "%%a"=="0" taskkill /F /PID %%a >nul 2>&1
    )
    timeout /t 2 >nul
    echo 기존 프로세스 종료 완료.
)

echo 웹 서버를 시작합니다...
echo.

REM Python이 설치되어 있는지 확인
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [오류] Python이 설치되어 있지 않거나 PATH에 등록되지 않았습니다.
    echo Python을 설치하고 PATH에 추가한 후 다시 시도하세요.
    pause
    exit /b 1
)

REM 필요한 패키지가 설치되어 있는지 확인 (실패 시에만 설치)
echo 필요한 패키지를 확인합니다... (flask, psutil, schedule, win32com)
python -c "import flask, psutil, schedule, win32com.client" >nul 2>&1 && (
    echo 필요한 패키지가 모두 설치되어 있습니다.
) || (
    echo [경고] 필요한 패키지가 설치되지 않았습니다. (flask, psutil, schedule, pywin32)
    echo 패키지를 설치합니다...
    python -m pip install --quiet --disable-pip-version-check flask psutil schedule pywin32
    if %errorlevel% neq 0 (
        echo [오류] 패키지 설치에 실패했습니다.
        pause
        exit /b 1
    )
    echo 패키지 설치가 완료되었습니다.
    echo.
)

echo 웹 서버를 시작합니다...
echo 웹 서버가 준비될 때까지 기다립니다...
echo.

REM 웹 서버를 백그라운드에서 시작
start /B python web_server.py

REM 웹 서버가 준비될 때까지 대기 (최대 30초)
echo 웹 서버 준비 상태를 확인하고 있습니다...
set /a attempts=0
:wait_for_server
timeout /t 1 >nul
set /a attempts+=1

REM 포트 5000이 열렸는지 확인
netstat -an | findstr :5000 >nul
if %errorlevel% neq 0 (
    if %attempts% lss 30 (
        echo 웹 서버 시작 대기 중... (%attempts%/30)
        goto wait_for_server
    ) else (
        echo [경고] 웹 서버 시작 시간 초과. 브라우저를 수동으로 열어주세요.
        goto start_browser
    )
)

REM HTTP 응답 확인 (웹 서버가 실제로 응답하는지 테스트)
echo 웹 서버 응답을 확인하고 있습니다...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:5000/api/status' -TimeoutSec 5; if ($response.StatusCode -eq 200) { Write-Host 'SUCCESS' } else { Write-Host 'FAILED' } } catch { Write-Host 'FAILED' }" > temp_response.txt
findstr "SUCCESS" temp_response.txt >nul
if %errorlevel% neq 0 (
    if %attempts% lss 30 (
        echo 웹 서버 응답 대기 중... (%attempts%/30)
        del temp_response.txt >nul 2>&1
        goto wait_for_server
    ) else (
        echo [경고] 웹 서버 응답 시간 초과. 브라우저를 수동으로 열어주세요.
        del temp_response.txt >nul 2>&1
        goto start_browser
    )
)

del temp_response.txt >nul 2>&1
echo 웹 서버가 준비되었습니다!
echo.

:start_browser
echo 브라우저를 열고 있습니다...
start "" "http://localhost:5000"

echo.
echo 웹 서버가 백그라운드에서 실행 중입니다.
echo 웹 서버를 중지하려면 작업 관리자에서 python.exe 프로세스를 종료하거나
echo 다음 명령어를 실행하세요: taskkill /F /IM python.exe
echo.
echo 웹 서버 로그를 보려면 별도의 명령 프롬프트에서 다음을 실행하세요:
echo python web_server.py
echo.