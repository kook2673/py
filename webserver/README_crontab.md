# 크론탭 스케줄러 사용법

## 개요
`crontab.py`는 정해진 시간에 파워셸을 호출해 다른 Python 스크립트들을 실행하는 스케줄러입니다.

## 설치 및 실행

### 1. 필요한 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. 스케줄러 실행
```bash
# 스케줄러 모드로 실행 (백그라운드에서 계속 실행)
python crontab.py

# 또는 배치 파일 사용
start_crontab.bat
```

### 3. 즉시 실행 (테스트용)
```bash
# 웹서버 즉시 실행
python crontab.py webserver

# 텔레그램 봇 즉시 실행
python crontab.py telegram_bot

# 스케줄된 작업 즉시 실행
python crontab.py tasks

# 크론 표현식 테스트
python crontab.py test
```

## 설정 파일 (crontab_config.json)

### 크론 표현식 스케줄 설정
```json
{
  "schedules": [
    {
      "cron": "0 9 * * *",
      "description": "매일 오전 9시 데이터 백업 및 리포트 생성",
      "enabled": true,
      "tasks": [
        {
          "type": "python_script",
          "script": "backup_daily_data.py",
          "description": "일일 데이터 백업",
          "enabled": true
        },

      ]
    },
    {
      "cron": "*/30 * * * *",
      "description": "30분마다 시스템 상태 체크",
      "enabled": false,
      "tasks": [
        {
          "type": "python_script",
          "script": "check_system_status.py",
          "description": "시스템 상태 확인",
          "enabled": true
        }
      ]
    }
  ]
}
```

### 크론 표현식 형식
```
* * * * *
│ │ │ │ │
│ │ │ │ └── 요일 (0-7, 0과 7은 일요일)
│ │ │ └──── 월 (1-12)
│ │ └────── 일 (1-31)
│ └──────── 시 (0-23)
└────────── 분 (0-59)
```

### 크론 표현식 예시
- **`0 9 * * *`**: 매일 오전 9시
- **`0 18 * * *`**: 매일 오후 6시
- **`0 10 * * 1`**: 매주 월요일 오전 10시
- **`0 1 1 * *`**: 매월 1일 새벽 1시
- **`*/30 * * * *`**: 30분마다
- **`0 */2 * * *`**: 2시간마다
- **`0 9-18 * * 1-5`**: 평일 오전 9시-오후 6시
- **`0 9,18 * * *`**: 매일 오전 9시와 오후 6시

### 작업 타입
- **`python_script`**: Python 스크립트 실행
- **`powershell_command`**: PowerShell 명령어 실행  
- **`batch_file`**: 배치 파일 실행
- **`external_program`**: 외부 프로그램 실행

## 백그라운드 실행

### Windows 서비스로 등록
1. `nssm` (Non-Sucking Service Manager) 설치
2. 서비스 등록:
```bash
nssm install CrontabScheduler "C:\Python\python.exe" "C:\path\to\crontab.py"
nssm start CrontabScheduler
```

### 작업 스케줄러 사용
1. Windows 작업 스케줄러 열기
2. "기본 작업 만들기" 선택
3. 트리거: 컴퓨터 시작 시
4. 동작: 프로그램 시작
5. 프로그램: `python.exe`
6. 인수: `crontab.py`

## 로그 확인
- 로그 파일: `crontab.log`
- 실시간 로그: 콘솔 출력

## 문제 해결

### 파워셸 실행 정책 오류
```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope CurrentUser
```

### 권한 문제
- 관리자 권한으로 실행
- 스크립트 경로에 한글이나 특수문자 없도록 설정

### 스케줄이 실행되지 않는 경우
1. 로그 파일 확인
2. 시간대 설정 확인
3. 설정 파일의 `enabled` 값 확인

## 예시 사용 사례

### 매일 오전 9시에 웹서버 재시작
```json
{
  "daily": [
    {
      "time": "09:00",
      "description": "웹서버 재시작",
      "enabled": true
    }
  ]
}
```

### 매주 월요일 오전 10시에 주간 리포트 생성
```json
{
  "weekly": [
    {
      "day": "monday",
      "time": "10:00",
      "description": "주간 리포트 생성",
      "enabled": true
    }
  ]
}
```

### 매월 1일 새벽 1시에 월간 정리 작업
```json
{
  "monthly": [
    {
      "day": 1,
      "time": "01:00",
      "description": "월간 정리 작업",
      "enabled": true
    }
  ]
}
```
