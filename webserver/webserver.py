from flask import Flask, request, jsonify, send_from_directory, abort, redirect, url_for, make_response, session
from pathlib import Path
from queue import Queue
from threading import Thread
from functools import wraps
import re
import os
import sys
import json
import subprocess
import datetime
import time
import traceback

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent  # C:\work\GitHub\py\webserver
USER_ID_PATTERN = re.compile(r'^[A-Za-z0-9_-]+$')

# 중앙 명령 큐 (단일 프로세스). 필요 시 Redis/Celery로 교체
command_queue: "Queue[dict]" = Queue()

# 세션/보안 설정
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "dev-secret-change-this"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


def get_admin_password() -> str:
    # 우선순위: 환경변수 -> 파일(.admin_password) -> 기본값(경고)
    pwd = os.environ.get("xlskfm79")
    if pwd:
        return pwd
    pw_file = BASE_DIR / ".admin_password"
    if pw_file.exists():
        try:
            return pw_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return "change-me"


def admin_required(fn):
    # 임시로 관리자 인증을 비활성화하여 모두 접근 가능
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper


# def get_windows_scheduler():
#     """Windows Task Scheduler 연결 (더 이상 사용되지 않음 - schtasks 명령어로 대체)"""
#     try:
#         import win32com.client
#         scheduler = win32com.client.Dispatch("Schedule.Service")
#         scheduler.Connect()
#         return scheduler
#     except ImportError:
#         print("win32com 모듈이 설치되지 않았습니다. 'pip install pywin32'로 설치하세요.")
#         return None
#     except Exception as e:
#         print(f"Windows Scheduler 연결 실패: {e}")
#         import traceback
#         traceback.print_exc()
#         error_msg = str(e).lower()
#         if "access denied" in error_msg or "permission" in error_msg:
#             print("권한 부족으로 인한 연결 실패. 관리자 권한으로 실행하세요.")
#         elif "service" in error_msg or "scheduler" in error_msg:
#             print("Task Scheduler 서비스가 실행되지 않았습니다. 서비스 관리자에서 확인하세요.")
#         elif "com" in error_msg or "interface" in error_msg:
#             print("COM+ 서비스 문제일 수 있습니다. 시스템을 재부팅하거나 COM+ 서비스를 재시작하세요.")
#         return None


def enable_windows_task(task_name, enabled=True):
    """Windows Scheduler 작업 활성화/비활성화"""
    try:
        # schtasks를 사용하여 활성화/비활성화 (더 안정적)
        if enabled:
            cmd = ["cmd", "/c", "schtasks", "/Change", "/TN", task_name, "/ENABLE"]
            message = f'작업 "{task_name}"이 활성화되었습니다.'
        else:
            cmd = ["cmd", "/c", "schtasks", "/Change", "/TN", task_name, "/DISABLE"]
            message = f'작업 "{task_name}"이 비활성화되었습니다.'
        
        print(f"작업 상태 변경 명령어: {cmd}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            if result.returncode != 0:
                error_msg = f'schtasks 오류 (코드: {result.returncode}): {result.stderr}'
                print(error_msg)
                return {'success': False, 'message': error_msg}
            
            print(f"작업 {task_name} 상태 변경 성공: {result.stdout}")
            return {'success': True, 'message': message}
            
        except Exception as e:
            return {'success': False, 'message': f'schtasks 실행 실패: {e}'}
            
    except Exception as e:
        return {'success': False, 'message': f'작업 상태 변경 실패: {str(e)}'}


def list_windows_tasks():
    """Windows Scheduler의 모든 작업 목록 가져오기 (schtasks 사용)"""
    try:
        # Windows Task Scheduler에서 모든 작업 조회
        cmd = ["cmd", "/c", "schtasks", "/Query", "/FO", "CSV", "/V"]
        print(f"작업 목록 조회 명령어: {cmd}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        if result.returncode != 0:
            print(f"작업 목록 조회 실패: {result.stderr}")
            return []
        
        # CSV 출력 파싱
        lines = result.stdout.strip().split('\n')
        print(f"총 {len(lines)}줄의 출력")
        
        if len(lines) < 2:  # 헤더 + 데이터가 최소 2줄 필요
            print("작업 목록이 비어있거나 형식이 잘못됨")
            return []
        
        # 헤더 출력
        print(f"헤더: {lines[0]}")
        
        # 헤더 제거하고 데이터만 처리
        data_lines = lines[1:]
        task_list = []
        
        for i, line in enumerate(data_lines):
            if line.strip():
                try:
                    # CSV 파싱 (쉼표로 구분, 따옴표 처리)
                    parts = []
                    current_part = ""
                    in_quotes = False
                    
                    for char in line:
                        if char == '"':
                            in_quotes = not in_quotes
                        elif char == ',' and not in_quotes:
                            parts.append(current_part.strip())
                            current_part = ""
                        else:
                            current_part += char
                    
                    parts.append(current_part.strip())
                    
                    if len(parts) >= 12:  # "예약된 작업 상태" 컬럼을 위해 최소 12개 필요
                        task_name = parts[1].strip('"').lstrip('\\')  # "작업 이름" 컬럼 (인덱스 1)
                        
                        task_enabled_raw = parts[11].strip('"')  # "예약된 작업 상태" 컬럼 (인덱스 11)
                        task_enabled = '사용' in task_enabled_raw  # 한국어 "사용" (Enabled) 확인
                        task_state = parts[3].strip('"')  # "상태" 컬럼 (인덱스 3)
                        
                        print(f"작업 발견: {task_name}, 활성화상태: {task_enabled_raw} -> {task_enabled}, 상태: {task_state}")
                        
                        # 비활성화된 작업이 있다면 자동으로 활성화 시도
                        if not task_enabled:
                            print(f"비활성화된 작업 {task_name} 활성화 시도...")
                            try:
                                enable_cmd = ["cmd", "/c", "schtasks", "/Change", "/TN", task_name, "/ENABLE"]
                                print(f"활성화 명령어: {enable_cmd}")
                                enable_result = subprocess.run(enable_cmd, capture_output=True, text=True, shell=True)
                                print(f"활성화 결과: {enable_result.returncode}, {enable_result.stdout}, {enable_result.stderr}")
                                
                                if enable_result.returncode == 0:
                                    print(f"작업 {task_name} 활성화 완료")
                                    task_enabled = True
                                    task_state = "Ready"
                                else:
                                    print(f"작업 {task_name} 활성화 실패: {enable_result.stderr}")
                            except Exception as e:
                                print(f"작업 {task_name} 활성화 중 오류: {e}")
                        
                        task_info = {
                            'name': task_name,
                            'enabled': task_enabled,
                            'state': task_state,
                            'last_run_time': parts[5].strip('"') if len(parts) > 5 and parts[5].strip('"') else '실행된 적 없음',
                            'next_run_time': parts[2].strip('"') if len(parts) > 2 and parts[2].strip('"') else '예약된 실행 없음',
                            'last_run_result': parts[6].strip('"') if len(parts) > 6 and parts[6].strip('"') else 'N/A',
                            'number_of_missed_runs': 'N/A'  # schtasks /V 출력에서는 직접 사용할 수 없음
                        }
                        task_list.append(task_info)
                        print(f"작업 정보 추가: {task_info}")
                        
                except Exception as e:
                    print(f"작업 정보 파싱 실패 (라인 {i+1}: {line}): {e}")
                    continue
        
        print(f"총 {len(task_list)}개 작업 조회 완료")
        for task in task_list:
            print(f"  - {task['name']}: 활성화={task['enabled']}, 상태={task['state']}")
        
        return task_list
        
    except Exception as e:
        print(f"Windows 작업 목록 가져오기 실패: {e}")
        import traceback
        traceback.print_exc()
        return []


# ---------------- Windows Scheduler: create/update/delete via schtasks ---------------- #
def _weekday_num_to_str(weekday_num: int) -> str:
    mapping = {
        1: "SUN",
        2: "MON",
        3: "TUE",
        4: "WED",
        5: "THU",
        6: "FRI",
        7: "SAT",
    }
    try:
        return mapping.get(int(weekday_num), "MON")
    except Exception:
        return "MON"


def _month_num_to_str(month_num: int) -> str:
    mapping = {
        1: "JAN", 2: "FEB", 3: "MAR", 4: "APR", 5: "MAY", 6: "JUN",
        7: "JUL", 8: "AUG", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC"
    }
    try:
        return mapping.get(int(month_num), "JAN")
    except Exception:
        return "JAN"


def _build_tr_command(executable_path: str, script_path: str) -> str:
    # Windows Task Scheduler용 명령어 형식
    # 작업 디렉토리를 포함한 명령어 생성
    exe = str(executable_path).replace('"', '')
    scr = str(script_path).replace('"', '')
    
    # 경로에 공백이 있으면 따옴표로 감싸기
    if ' ' in exe:
        exe = f'"{exe}"'
    if ' ' in scr:
        scr = f'"{scr}"'
    
    # 작업 디렉토리를 포함한 명령어 생성
    script_dir = str(Path(script_path).parent.absolute()).replace('/', '\\')
    return f'cd /d "{script_dir}" && {exe} {scr}'


def create_or_update_task_with_schtasks(task_name: str, executable_path: str, script_path: str,
                                        schedule_type: str, schedule_time: str | None,
                                        extra: dict | None, force: bool = False) -> dict:
    try:
        schedule_type = (schedule_type or "daily").lower()
        schedule_time = schedule_time or "09:00"
        tr_cmd = _build_tr_command(executable_path, script_path)

        base_cmd = [
            "cmd", "/c", "schtasks", "/Create",
            "/TN", task_name,
            "/TR", tr_cmd,
            "/ST", schedule_time,
            # /ENABLE 옵션은 /CREATE에서 사용할 수 없음 - 작업 생성 후 별도로 활성화
        ]
        
        # /SD 옵션 제거 - 작업 디렉토리는 /TR 명령어에 포함됨
        
        # 현재 사용자로 실행 (권한 문제 해결)
        try:
            import getpass
            username = getpass.getuser()
            base_cmd.extend(["/RU", username])
        except Exception:
            pass  # 사용자명 가져오기 실패 시 무시
        
        if force:
            base_cmd += ["/F"]

        if schedule_type == "daily":
            base_cmd += ["/SC", "DAILY"]
        elif schedule_type == "weekly":
            weekday = _weekday_num_to_str((extra or {}).get("weekday", 1))
            base_cmd += ["/SC", "WEEKLY", "/D", weekday]
        elif schedule_type == "monthly":
            day = str((extra or {}).get("day", 1))
            base_cmd += ["/SC", "MONTHLY", "/D", day]
        elif schedule_type == "yearly":
            month = _month_num_to_str((extra or {}).get("month", 1))
            day = str((extra or {}).get("day", 1))
            base_cmd += ["/SC", "MONTHLY", "/M", month, "/D", day]
        elif schedule_type == "cron":
            # 크론 표현식 파싱 및 Windows 스케줄로 변환
            cron_expression = (extra or {}).get("cron_expression", "0 * * * *")
            cron_parts = cron_expression.split()
            
            if len(cron_parts) >= 5:
                minute, hour, day, month, weekday = cron_parts[:5]
                
                # 1시간마다 실행 (매시간)
                if hour == "*" and minute != "*":
                    # 특정 분에 매시간 실행
                    base_cmd += ["/SC", "HOURLY"]
                    if minute != "0":
                        base_cmd.extend(["/MO", minute])
                elif hour == "*" and minute == "*":
                    # 매분마다 실행 (1분마다)
                    base_cmd += ["/SC", "MINUTE"]
                    base_cmd.extend(["/MO", "1"])
                elif hour != "*" and minute == "*":
                    # 특정 시간에 매분 실행
                    base_cmd += ["/SC", "MINUTE"]
                    base_cmd.extend(["/MO", "1"])
                    # 시작 시간 설정
                    if hour.isdigit():
                        start_time = f"{hour.zfill(2)}:00"
                        base_cmd[base_cmd.index("/ST") + 1] = start_time
                elif hour != "*" and minute != "*":
                    # 특정 시간에 실행 (매일)
                    base_cmd += ["/SC", "DAILY"]
                    # 시간:분 설정
                    if hour.isdigit() and minute.isdigit():
                        schedule_time = f"{hour.zfill(2)}:{minute.zfill(2)}"
                        base_cmd[base_cmd.index("/ST") + 1] = schedule_time
                else:
                    # 기본값: 매일
                    base_cmd += ["/SC", "DAILY"]
            else:
                # 크론 표현식이 올바르지 않으면 기본값 사용
                base_cmd += ["/SC", "DAILY"]
        else:
            return {"success": False, "message": f"지원되지 않는 스케줄 타입: {schedule_type}"}

        # 디버깅을 위한 명령어 출력
        print(f"실행할 schtasks 명령어: {base_cmd}")
        
        try:
            # creationflags 제거하여 더 안정적인 실행
            result = subprocess.run(base_cmd, capture_output=True, text=True, shell=True)
            
            if result.returncode != 0:
                error_msg = f"schtasks 오류 (코드: {result.returncode}): {result.stderr}"
                print(error_msg)
                return {"success": False, "message": error_msg}
            
            print(f"schtasks 성공: {result.stdout}")
            
            # 작업 생성 후 활성화
            try:
                print(f"작업 {task_name} 활성화 중...")
                enable_cmd = ["cmd", "/c", "schtasks", "/Change", "/TN", task_name, "/ENABLE"]
                enable_result = subprocess.run(enable_cmd, capture_output=True, text=True, shell=True)
                
                if enable_result.returncode == 0:
                    print(f"작업 {task_name} 활성화 완료")
                else:
                    print(f"작업 {task_name} 활성화 실패: {enable_result.stderr}")
                    # 활성화 실패는 치명적이지 않음, 작업은 생성됨
                    
            except Exception as e:
                print(f"작업 활성화 실패: {e}")
                # 활성화 실패는 치명적이지 않음
                
        except Exception as e:
            return {"success": False, "message": f"schtasks 실행 실패: {e}"}



        return {"success": True, "message": f'작업 "{task_name}" 등록 완료'}
    except Exception as e:
        return {"success": False, "message": f"작업 생성 실패: {e}"}


def delete_task_with_schtasks(task_name: str) -> dict:
    try:
        cmd = ["cmd", "/c", "schtasks", "/Delete", "/TN", task_name, "/F"]
        print(f"작업 삭제 명령어: {cmd}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            if result.returncode != 0:
                # 작업이 존재하지 않는 경우는 성공으로 간주
                if "ERROR: The system cannot find the file specified" in result.stderr:
                    print(f"작업 {task_name}이 이미 존재하지 않음")
                    return {"success": True, "message": f'작업 "{task_name}"이 이미 존재하지 않습니다'}
                else:
                    error_msg = f"삭제 실패(schtasks): {result.stderr}"
                    print(error_msg)
                    return {"success": False, "message": error_msg}
            
            print(f"작업 {task_name} 삭제 성공: {result.stdout}")
            
        except Exception as e:
            return {"success": False, "message": f"삭제 실행 실패: {e}"}



        return {"success": True, "message": f'작업 "{task_name}" 삭제 완료'}
    except Exception as e:
        return {"success": False, "message": f"삭제 실패: {e}"}


def run_windows_task(task_name):
    """Windows Scheduler 작업 즉시 실행 (schtasks 사용)"""
    try:
        cmd = ["cmd", "/c", "schtasks", "/Run", "/TN", task_name]
        print(f"작업 실행 명령어: {cmd}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        if result.returncode != 0:
            error_msg = f"작업 실행 실패: {result.stderr}"
            print(error_msg)
            return {'success': False, 'message': error_msg}
        
        print(f"작업 {task_name} 실행 성공: {result.stdout}")
        return {'success': True, 'message': f'작업 "{task_name}"이 실행되었습니다.'}
        
    except Exception as e:
        error_msg = f'작업 실행 실패: {str(e)}'
        print(error_msg)
        return {'success': False, 'message': error_msg}


def is_valid_user(user_id: str) -> bool:
    return USER_ID_PATTERN.fullmatch(user_id) is not None


def get_user_dir(user_id: str) -> Path:
    # kook는 이제 webserver/kook 폴더에서 서빙
    if user_id == "kook":
        return (BASE_DIR / "kook").resolve()
    return BASE_DIR / user_id


@app.get("/")
def root():
    # 간단 안내 페이지
    return (
        "<h3>Webserver is running</h3>"
        "<p>Try: /kook/index.html or /wildrose/index.html</p>"
    )


@app.get('/<user_id>/index.html')
def serve_user_index(user_id: str):
    if not is_valid_user(user_id):
        abort(400, 'invalid user id')
    directory = get_user_dir(user_id)
    index_path = directory / 'index.html'
    if not index_path.exists():
        abort(404, 'index.html not found')
    # 관리자 인증 임시 해제: 누구나 접근 가능
    return send_from_directory(directory, 'index.html')


# 사용자 폴더 내 기타 정적 리소스 (js, css, images 등)
@app.get('/<user_id>/<path:filename>')
def serve_user_static(user_id: str, filename: str):
    if not is_valid_user(user_id):
        abort(400, 'invalid user id')
    # 관리자 인증 임시 해제: 누구나 접근 가능
    directory = get_user_dir(user_id)
    file_path = directory / filename
    if not file_path.exists():
        abort(404)
    return send_from_directory(directory, filename)


# 중앙 명령 처리 엔드포인트 (사용자 경로에 귀속)
@app.post('/<user_id>/api/command')
def receive_command(user_id: str):
    if not is_valid_user(user_id):
        abort(400, 'invalid user id')
    data = request.get_json(silent=True) or {}
    job = {
        "user": user_id,
        "command": data.get("command"),
        "payload": data.get("payload"),
    }
    command_queue.put(job)
    return jsonify({"status": "queued", "user": user_id})


def worker_loop():
    while True:
        job = command_queue.get()
        try:
            # TODO: 중앙 처리 로직 연결
            # 예: user에 따라 모듈 라우팅 또는 공용 핸들러 호출
            # if job["user"] == "kook": run_kook_command(job)
            # else: run_wildrose_command(job)
            print("Processing job:", job)
        except Exception as e:
            print("Error:", e)
        finally:
            command_queue.task_done()


Thread(target=worker_loop, daemon=True).start()


# ---- 관리자 로그인/로그아웃 (임시 비활성화: 바로 대시보드로 리다이렉트) ----
@app.get("/kook/login")
def kook_login():
    return redirect("/kook/index.html")


@app.post("/kook/login")
def kook_login_post():
    return redirect("/kook/index.html")


@app.post("/kook/logout")
def kook_logout():
    return redirect(url_for("root"))


# ---- API 구현 (관리자 전용) ----
def _now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _kis_dir() -> Path:
    # kook/kis 폴더 경로 (프로젝트 루트 기준)
    return (BASE_DIR.parent / "kook" / "kis").resolve()





def _safe_load_json(file_path: Path, default_value):
    try:
        if file_path.exists():
            return json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default_value


@app.get("/api/status")
@admin_required
def api_status():
    processes = {
        "Kosdaqpi_Bot": {"running": False, "pid": None, "memory": 0.0, "cpu_percent": 0.0},
        "MA_Strategy_KR_Bot_v3": {"running": False, "pid": None, "memory": 0.0, "cpu_percent": 0.0},
        "MA_Kosdaqpi100_Bot_v1": {"running": False, "pid": None, "memory": 0.0, "cpu_percent": 0.0},
        "scheduler": {"running": False, "pid": None, "memory": 0.0, "cpu_percent": 0.0},
        "web_server": {"running": True, "pid": os.getpid(), "memory": 0.0, "cpu_percent": 0.0},
    }
    return jsonify({"success": True, "status": {"processes": processes}})


@app.get("/api/portfolio")
@admin_required
def api_portfolio():
    kis_dir = _kis_dir()
    cfg = _safe_load_json(kis_dir / "portfolio_config.json", {})
    daily = _safe_load_json(kis_dir / "portfolio_daily_profit_summary.json", {})

    performance = daily.get("performance", {})
    bots_cfg = cfg.get("bots", {}) or {}

    bots = {}
    for bot_name in [
        "Kosdaqpi_Bot",
        "MA_Strategy_KR_Bot_v3",
        "MA_Kosdaqpi100_Bot_v1",
    ]:
        c = bots_cfg.get(bot_name, {}) or {}
        bots[bot_name] = {
            "initial_allocation": c.get("initial_allocation", 0),
            "current_allocation": c.get("current_allocation", 0),
            "total_holding_value": c.get("total_holding_value", 0),
            "holdings": c.get("holdings", []),
        }

    portfolio = {
        "initial_investment": cfg.get("initial_investment", 0),
        "dividend_income": cfg.get("dividend_income", 0),
        "investment_date": cfg.get("investment_date", ""),
        "performance": {
            "total_value": performance.get("total_value", 0),
            "total_profit": performance.get("total_profit", 0),
            "total_profit_rate": performance.get("total_profit_rate", 0.0),
        },
        "bots": bots,
        "bot_profits": daily.get("bot_profits", {}),
    }
    return jsonify({"success": True, "portfolio": portfolio})


@app.get("/api/portfolio_overview")
@admin_required
def api_portfolio_overview():
    kis_dir = _kis_dir()
    cfg = _safe_load_json(kis_dir / "portfolio_config.json", {})
    daily = _safe_load_json(kis_dir / "portfolio_daily_profit_summary.json", {})

    def _num(x):
        try:
            return float(x)
        except Exception:
            return 0.0

    initial_investment = _num(cfg.get("initial_investment", 0))
    performance = daily.get("performance", {})
    current_value = _num(performance.get("total_value", 0))
    total_profit = _num(performance.get("total_profit", 0))
    total_profit_rate = _num(performance.get("total_profit_rate", 0))
    periods = performance.get("periods", {}) or {}
    daily_bots = daily.get("bots", {}) or {}
    cfg_bots = (cfg.get("bots") or {})

    bots_overview = {}
    total_sold_profit_total = 0.0
    all_bot_names = set(list(daily_bots.keys()) + list(cfg_bots.keys()))
    for bot_name in all_bot_names:
        cfg_bot = cfg_bots.get(bot_name, {}) or {}
        bot_initial_alloc = _num(cfg_bot.get("initial_allocation", 0))
        bot_total_sold = _num(cfg_bot.get("cumulative_profit_if_sold", 0))
        total_sold_profit_total += bot_total_sold
        periods_src = (daily_bots.get(bot_name, {}).get("periods") or {})
        bots_overview[bot_name] = {
            "total_sold_profit": bot_total_sold,
            "periods": {
                "daily": {
                    "profit": _num(periods_src.get("daily", {}).get("profit", 0)),
                    "profit_rate": _num(periods_src.get("daily", {}).get("profit_rate", 0)),
                },
                "weekly": {
                    "profit": _num(periods_src.get("weekly", {}).get("profit", 0)),
                    "profit_rate": _num(periods_src.get("weekly", {}).get("profit_rate", 0)),
                },
                "monthly": {
                    "profit": _num(periods_src.get("monthly", {}).get("profit", 0)),
                    "profit_rate": _num(periods_src.get("monthly", {}).get("profit_rate", 0)),
                },
                "yearly": {
                    "profit": _num(periods_src.get("yearly", {}).get("profit", 0)),
                    "profit_rate": _num(periods_src.get("yearly", {}).get("profit_rate", 0)),
                },
                "total": {
                    "profit": bot_total_sold,
                    "profit_rate": (bot_total_sold / bot_initial_alloc * 100.0) if bot_initial_alloc else 0.0,
                },
            },
        }

    overview = {
        "initial_investment": initial_investment,
        "current_value": current_value,
        "total_profit": total_profit,
        "total_profit_rate": total_profit_rate,
        "investment_date": cfg.get("investment_date", ""),
        "dividend_income": _num(cfg.get("dividend_income", 0)),
        "total_sold_profit_total": total_sold_profit_total,
        "periods": {
            "daily": {
                "profit": _num(periods.get("daily", {}).get("profit", 0)),
                "profit_rate": _num(periods.get("daily", {}).get("profit_rate", 0)),
            },
            "weekly": {
                "profit": _num(periods.get("weekly", {}).get("profit", 0)),
                "profit_rate": _num(periods.get("weekly", {}).get("profit_rate", 0)),
            },
            "monthly": {
                "profit": _num(periods.get("monthly", {}).get("profit", 0)),
                "profit_rate": _num(periods.get("monthly", {}).get("profit_rate", 0)),
            },
            "yearly": {
                "profit": _num(periods.get("yearly", {}).get("profit", 0)),
                "profit_rate": _num(periods.get("yearly", {}).get("profit_rate", 0)),
            },
            "total": {
                "profit": total_sold_profit_total,
                "profit_rate": (total_sold_profit_total / initial_investment * 100.0) if initial_investment else 0.0,
            },
        },
        "bots": bots_overview,
    }
    return jsonify({"success": True, "overview": overview})


@app.get("/api/kospi_check")
@admin_required
def api_kospi_check():
    """KOSPI 체크 정보를 반환하는 API"""
    try:
        # kospi_check.json 파일 경로 (kook/kis 디렉토리에 있음)
        kospi_file = BASE_DIR.parent / "kook" / "kis" / "kospi_check.json"
        
        if not kospi_file.exists():
            return jsonify({
                "success": False,
                "message": "KOSPI 체크 파일이 존재하지 않습니다."
            })
        
        # JSON 파일 읽기
        with open(kospi_file, 'r', encoding='utf-8') as f:
            kospi_data = json.load(f)
        
        return jsonify({
            "success": True,
            "kospi_data": kospi_data
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"KOSPI 정보 로드 실패: {str(e)}"
        })


@app.get("/api/bot_holdings")
@admin_required
def api_bot_holdings():
    return jsonify({
        "success": True,
        "bot_holdings": {
            "Kosdaqpi_Bot": {"holdings": []},
            "MA_Strategy_KR_Bot_v3": {"holdings": []},
            "MA_Kosdaqpi100_Bot_v1": {"holdings": []},
        }
    })


@app.get("/api/python_processes")
@admin_required
def api_python_processes():
    def _extract_script_from_cmdline(cmdline: list) -> str:
        try:
            # psutil returns list[str]; find first .py
            for token in (cmdline or []):
                t = str(token)
                if t.lower().endswith(".py"):
                    try:
                        return os.path.basename(t)
                    except Exception:
                        return t
            # handle -m module
            if "-m" in (cmdline or []):
                i = (cmdline or []).index("-m")
                if i + 1 < len(cmdline):
                    return f"-m {cmdline[i+1]}"
            # handle -c
            if "-c" in (cmdline or []):
                return "-c"
        except Exception:
            pass
        return ""

    processes = []
    try:
        import psutil  # type: ignore
        for p in psutil.process_iter(["pid", "name", "memory_info", "cpu_percent", "cmdline"]):
            name = (p.info.get("name") or "").lower()
            if "python" in name:
                mem = 0.0
                try:
                    mem = (p.info.get("memory_info").rss or 0) / (1024 * 1024)
                except Exception:
                    pass
                cmdline = p.info.get("cmdline") or []
                script = _extract_script_from_cmdline(cmdline)
                processes.append({
                    "pid": p.info.get("pid"),
                    "name": p.info.get("name"),
                    "memory": round(mem, 1),
                    "cpu": float(p.info.get("cpu_percent") or 0.0),
                    "cmd": script,
                })
    except Exception:
        # psutil이 없으면 WMIC로 commandline 포함 정보를 수집 (가능 시)
        try:
            out = subprocess.check_output(
                ["cmd", "/c", "wmic process where \"name='python.exe'\" get ProcessId,Name,CommandLine /format:csv"],
                creationflags=0x08000000,
            )
            text = out.decode(errors="ignore")
            # CSV 헤더: Node,CommandLine,Name,ProcessId
            for line in text.splitlines():
                if not line or line.lower().startswith("node,"):
                    continue
                parts = line.split(",", 3)
                if len(parts) < 4:
                    continue
                _, cmdline, name, pid_str = parts
                try:
                    pid = int(pid_str)
                except Exception:
                    continue
                script = ""
                try:
                    for token in (cmdline or "").split():
                        if token.lower().endswith(".py"):
                            script = os.path.basename(token)
                            break
                except Exception:
                    pass
                processes.append({
                    "pid": pid,
                    "name": name or "python.exe",
                    "memory": 0.0,
                    "cpu": 0.0,
                    "cmd": script,
                })
        except Exception as e:
            print(f"WMIC failed: {e}")
            # WMIC 실패 시 tasklist로 fallback
            # 마지막 대안: tasklist (commandline 없음)
            try:
                out = subprocess.check_output(["cmd", "/c", "tasklist | findstr /I python"], creationflags=0x08000000)
                lines = out.decode(errors="ignore").splitlines()
                for ln in lines:
                    parts = ln.split()
                    if len(parts) >= 2:
                        name = parts[0]
                        pid = int(parts[1]) if parts[1].isdigit() else None
                        if pid:
                            processes.append({"pid": pid, "name": name, "memory": 0.0, "cpu": 0.0, "cmd": ""})
            except Exception:
                pass
    return jsonify({"success": True, "processes": processes})


@app.post("/api/kill/<int:pid>")
@admin_required
def api_kill(pid: int):
    try:
        subprocess.check_call(["cmd", "/c", f"taskkill /PID {pid} /F"], creationflags=0x08000000)
        return jsonify({"success": True, "message": f"PID {pid} 종료됨"})
    except subprocess.CalledProcessError as e:
        return jsonify({"success": False, "message": f"종료 실패: {e}"}), 400


@app.get("/api/start/<process_name>")
@admin_required
def api_start(process_name: str):
    command_queue.put({"user": "kook", "command": "start", "payload": {"name": process_name}})
    return jsonify({"success": True, "message": f"{process_name} 시작 요청"})


@app.get("/api/stop/<process_name>")
@admin_required
def api_stop(process_name: str):
    command_queue.put({"user": "kook", "command": "stop", "payload": {"name": process_name}})
    return jsonify({"success": True, "message": f"{process_name} 중지 요청"})


@app.get("/api/send_daily_report")
@admin_required
def api_send_daily_report():
    return jsonify({"success": True, "message": "일일 보고서 전송 요청 완료"})


@app.get("/api/send_monthly_report")
@admin_required
def api_send_monthly_report():
    return jsonify({"success": True, "message": "월간 보고서 전송 요청 완료"})


@app.get("/api/bot_log/<bot_name>")
@admin_required
def api_bot_log(bot_name: str):
    lines = int(request.args.get("lines", "500") or 500)
    # 실제 로그 파일 연동 전까지 빈 로그 제공
    log_text = f"[{_now_iso()}] {bot_name} 로그가 아직 연결되지 않았습니다. (최근 {lines}줄)"
    return jsonify({"success": True, "log": log_text})


@app.get("/api/python_executable")
@admin_required
def api_python_executable():
    return jsonify({"success": True, "python_path": sys.executable})


CONFIG_FILE = (_kis_dir() / "portfolio_config.json")


@app.get("/api/portfolio_config")
@admin_required
def api_portfolio_config_get():
    if CONFIG_FILE.exists():
        try:
            return jsonify(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    # 기본값
    return jsonify({
        "success": True,
        "portfolio": {
            "initial_investment": 0,
            "initial_investment_old": None,
            "dividend_income": 0,
            "investment_date": "",
        },
        "bots": {}
    })


@app.post("/api/portfolio_config")
@admin_required
def api_portfolio_config_post():
    data = request.get_json(silent=True) or {}
    if CONFIG_FILE.exists():
        try:
            current = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            current = {"success": True}
    else:
        current = {"success": True}
    # merge 얕게 처리
    for k, v in data.items():
        current[k] = v
    CONFIG_FILE.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return jsonify({"success": True})


# Windows Scheduler 관련 (실제 Windows Task Scheduler 상태 확인)
@app.get("/api/windows_tasks")
@admin_required
def api_windows_tasks_list():
    """Windows Scheduler의 모든 작업 목록 가져오기"""
    try:
        print("=== /api/windows_tasks API 호출됨 ===")
        tasks = list_windows_tasks()
        print(f"=== list_windows_tasks 결과: {len(tasks)}개 작업 ===")
        for task in tasks:
            print(f"  - {task['name']}: 활성화={task['enabled']}, 상태={task['state']}")
        
        return jsonify({
            'success': True,
            'tasks': tasks
        })
    except Exception as e:
        print(f"=== /api/windows_tasks 오류: {e} ===")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'작업 목록 가져오기 실패: {str(e)}'
        })


@app.post("/api/windows_tasks")
@admin_required
def api_windows_tasks_create():
    try:
        data = request.get_json(silent=True) or {}
        task_name = data.get("task_name") or data.get("name")
        executable_path = data.get("executable_path") or sys.executable
        script_path = data.get("script_path")
        schedule_type = data.get("schedule_type") or "daily"
        schedule_time = data.get("schedule_time") or data.get("time")
        description = data.get("description", "")

        if not task_name or not script_path:
            return jsonify({"success": False, "message": "task_name, script_path는 필수입니다."}), 400

        extra = {
            "description": description,
        }
        for key in ("weekday", "day", "month", "cron_expression"):
            if key in data:
                extra[key] = data[key]

        result = create_or_update_task_with_schtasks(
            task_name=task_name,
            executable_path=executable_path,
            script_path=script_path,
            schedule_type=schedule_type,
            schedule_time=schedule_time,
            extra=extra,
            force=True,
        )
        status = 200 if result.get("success") else 400
        return jsonify(result), status
    except Exception as e:
        return jsonify({"success": False, "message": f"작업 등록 실패: {e}"}), 500


@app.get("/api/windows_tasks/<task_name>")
@admin_required
def api_windows_task_get(task_name: str):
    # 기본값 반환 (user_tasks.json 파일 없이)
    return jsonify({
        "success": True,
        "task": {
            "name": task_name,
            "schedule_type": "daily",
            "schedule_time": "09:00",
            "script_path": str(_kis_dir() / f"{task_name}.py"),
            "description": "",
            "executable_path": sys.executable,
            "schedule_config": {}
        }
    })


@app.put("/api/windows_tasks/<task_name>")
@admin_required
def api_windows_task_update(task_name: str):
    try:
        data = request.get_json(silent=True) or {}
        executable_path = data.get("executable_path") or sys.executable
        script_path = data.get("script_path")
        schedule_type = data.get("schedule_type") or "daily"
        schedule_time = data.get("schedule_time") or data.get("time")
        description = data.get("description", "")

        if not script_path:
            return jsonify({"success": False, "message": "script_path는 필수입니다."}), 400

        extra = {"description": description}
        for key in ("weekday", "day", "month", "cron_expression"):
            if key in data:
                extra[key] = data[key]

        _ = delete_task_with_schtasks(task_name)
        result = create_or_update_task_with_schtasks(
            task_name=task_name,
            executable_path=executable_path,
            script_path=script_path,
            schedule_type=schedule_type,
            schedule_time=schedule_time,
            extra=extra,
            force=True,
        )
        status = 200 if result.get("success") else 400
        return jsonify(result), status
    except Exception as e:
        return jsonify({"success": False, "message": f"작업 수정 실패: {e}"}), 500


@app.delete("/api/windows_tasks/<task_name>")
@admin_required
def api_windows_task_delete(task_name: str):
    try:
        result = delete_task_with_schtasks(task_name)
        status = 200 if result.get("success") else 400
        return jsonify(result), status
    except Exception as e:
        return jsonify({"success": False, "message": f"작업 삭제 실패: {e}"}), 500


@app.post("/api/windows_tasks/<task_name>/run")
@admin_required
def api_windows_task_run(task_name: str):
    try:
        result = run_windows_task(task_name)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'작업 실행 실패: {str(e)}'
        })


@app.post("/api/windows_tasks/<task_name>/enable")
@admin_required
def api_windows_task_enable(task_name: str):
    try:
        data = request.get_json(silent=True) or {}
        enabled = data.get('enabled', True)
        
        result = enable_windows_task(task_name, enabled)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'작업 상태 변경 실패: {str(e)}'
        })


@app.post("/api/windows_tasks/enable_all")
@admin_required
def api_windows_tasks_enable_all():
    """모든 Windows Scheduler 작업을 활성화"""
    try:
        # Windows Task Scheduler에서 모든 작업을 가져와서 활성화
        all_tasks = list_windows_tasks()
        enabled_count = 0
        failed_count = 0
        failed_tasks = []
        
        print(f"총 {len(all_tasks)}개 작업 활성화 시작...")
        
        for task in all_tasks:
            task_name = task.get("name")
            if task_name:
                try:
                    print(f"작업 {task_name} 활성화 중...")
                    result = enable_windows_task(task_name, True)
                    if result.get("success"):
                        enabled_count += 1
                        print(f"작업 {task_name} 활성화 성공")
                    else:
                        failed_count += 1
                        failed_tasks.append(f"{task_name}: {result.get('message', '알 수 없는 오류')}")
                        print(f"작업 {task_name} 활성화 실패: {result.get('message', '알 수 없는 오류')}")
                except Exception as e:
                    failed_count += 1
                    failed_tasks.append(f"{task_name}: {str(e)}")
                    print(f"작업 {task_name} 활성화 중 예외 발생: {e}")
        
        message = f"총 {len(all_tasks)}개 작업 중 {enabled_count}개 활성화 완료"
        if failed_count > 0:
            message += f", {failed_count}개 실패"
            message += f"\n실패한 작업: {', '.join(failed_tasks)}"
        
        print(f"활성화 완료: {enabled_count}개 성공, {failed_count}개 실패")
        
        return jsonify({
            "success": True,
            "message": message,
            "enabled_count": enabled_count,
            "failed_count": failed_count,
            "failed_tasks": failed_tasks
        })
        
    except Exception as e:
        error_msg = f"일괄 활성화 실패: {str(e)}"
        print(error_msg)
        return jsonify({
            "success": False,
            "message": error_msg
        })


@app.post("/api/windows_tasks/recreate_all")
@admin_required
def api_windows_tasks_recreate_all():
    """모든 Windows Scheduler 작업을 재생성 (오류 수정용)"""
    try:
        # Windows Task Scheduler에서 모든 작업을 가져와서 재생성
        all_tasks = list_windows_tasks()
        recreated_count = 0
        failed_count = 0
        
        for task in all_tasks:
            task_name = task.get("name")
            if task_name:
                try:
                    # 기존 작업 삭제
                    delete_task_with_schtasks(task_name)
                    
                    # 새로 생성 (기본값 사용)
                    result = create_or_update_task_with_schtasks(
                        task_name=task_name,
                        executable_path=sys.executable,
                        script_path=str(_kis_dir() / f"{task_name}.py"),
                        schedule_type="daily",
                        schedule_time="09:00",
                        extra={},
                        force=True,
                    )
                    
                    if result.get("success"):
                        recreated_count += 1
                    else:
                        failed_count += 1
                        
                except Exception as e:
                    print(f"작업 {task_name} 재생성 실패: {e}")
                    failed_count += 1
        
        message = f"총 {len(all_tasks)}개 작업 중 {recreated_count}개 재생성 완료"
        if failed_count > 0:
            message += f", {failed_count}개 실패"
        
        return jsonify({
            "success": True,
            "message": message,
            "recreated_count": recreated_count,
            "failed_count": failed_count
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"일괄 재생성 실패: {str(e)}"
        })


@app.get("/api/trade_logs")
@admin_required
def api_trade_logs():
    return jsonify({"success": True, "logs": [], "total_count": 0})


# 사용자 작업 조회 (스케줄러 등록 시 참조)
@app.get("/api/user_tasks/<task_name>")
@admin_required
def api_user_task(task_name: str):
    # 기본값 반환 (user_tasks.json 파일 없이)
    return jsonify({
        "success": True,
        "task": {
            "name": task_name,
            "executable_path": sys.executable,
            "script_path": str(_kis_dir() / f"{task_name}.py"),
            "schedule_type": "daily",
            "schedule_time": "09:00",
            "description": ""
        }
    })

@app.get("/api/upbit_status")
@admin_required
def api_upbit_status():
    """업비트 투자현황 정보 조회"""
    try:
        # 업비트 JSON 파일 경로 (프로젝트 루트의 kook/upbit 폴더)
        upbit_file_path = BASE_DIR.parent / "kook" / "upbit" / "Ma_Double_Upbit_1d4h_Bot.json"
        
        if not upbit_file_path.exists():
            return jsonify({
                "success": False,
                "message": "업비트 정보 파일을 찾을 수 없습니다."
            })
        
        # JSON 파일 읽기
        with open(upbit_file_path, 'r', encoding='utf-8') as f:
            upbit_data = json.load(f)
        
        return jsonify({
            "success": True,
            "upbit_data": upbit_data
        })
        
    except FileNotFoundError:
        return jsonify({
            "success": False,
            "message": "업비트 정보 파일이 존재하지 않습니다."
        })
    except json.JSONDecodeError as e:
        return jsonify({
            "success": False,
            "message": f"JSON 파일 형식 오류: {str(e)}"
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"업비트 정보 조회 실패: {str(e)}"
        })

@app.get("/api/windows_tasks/test_status")
@admin_required
def api_windows_tasks_test_status():
    """Windows Task Scheduler 작업 상태 테스트 (디버깅용)"""
    try:
        # 1. schtasks 명령어로 전체 작업 목록 확인
        cmd = ["cmd", "/c", "schtasks", "/Query", "/FO", "CSV", "/V"]
        print(f"=== 테스트: 전체 작업 목록 조회 ===")
        print(f"명령어: {cmd}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        print(f"반환 코드: {result.returncode}")
        print(f"표준 출력: {result.stdout}")
        print(f"표준 오류: {result.stderr}")
        
        # 2. 특정 작업 상태 확인
        test_tasks = ["Kosdaqpi_Bot", "MA_Strategy_KR_Bot_v3"]
        task_statuses = {}
        
        for task_name in test_tasks:
            print(f"\n=== 테스트: 작업 {task_name} 상태 확인 ===")
            status_cmd = ["cmd", "/c", "schtasks", "/Query", "/TN", task_name, "/FO", "CSV"]
            print(f"상태 확인 명령어: {status_cmd}")
            
            status_result = subprocess.run(status_cmd, capture_output=True, text=True, shell=True)
            print(f"상태 확인 결과: {status_result.returncode}")
            print(f"상태 확인 출력: {status_result.stdout}")
            print(f"상태 확인 오류: {status_result.stderr}")
            
            task_statuses[task_name] = {
                "return_code": status_result.returncode,
                "output": status_result.stdout,
                "error": status_result.stderr
            }
        
        # 3. list_windows_tasks 함수 테스트
        print(f"\n=== 테스트: list_windows_tasks 함수 실행 ===")
        tasks = list_windows_tasks()
        print(f"반환된 작업 목록: {tasks}")
        
        return jsonify({
            "success": True,
            "message": "테스트 완료",
            "raw_output": result.stdout,
            "task_statuses": task_statuses,
            "parsed_tasks": tasks
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"테스트 실패: {str(e)}"
        })

if __name__ == '__main__':
    # 웹서버 실행 부분 주석처리 (나중에 사용 가능)
    # 텔레그램 봇을 별도 프로세스로 실행 (웹서버와 독립)
    # try:
    #     bot_path = (BASE_DIR / "telegram_bot.py").resolve()
    #     if bot_path.exists():
    #         subprocess.Popen(
    #             [sys.executable, str(bot_path)],
    #             cwd=str(BASE_DIR),
    #             stdout=subprocess.DEVNULL,
    #             stderr=subprocess.DEVNULL,
    #             creationflags=0x08000000,
    #         )
    #         print("Telegram bot process started.")
    #     else:
    #         print(f"telegram_bot.py not found at {bot_path}")
    # except Exception as e:
    #     print(f"Failed to start telegram bot: {e}")

    # # 운영 실행: 디버그/리로더 비활성화하여 중복 프로세스 방지
    # app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    
    print("웹서버가 비활성화되었습니다. 나중에 사용하려면 주석을 해제하세요.")


