#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
크론탭 스케줄러
정해진 시간에 파워셸을 호출해 다른 Python 스크립트들을 실행
"""

import schedule
import time
import subprocess
import logging
import os
import sys
import json
import re
import hashlib
from datetime import datetime
from pathlib import Path
from datetime import timedelta
import gc

# logs 폴더 생성
logs_dir = Path(__file__).parent / "logs"
logs_dir.mkdir(exist_ok=True)

# 로깅 설정 - 일자별로 로그 파일 분리
class DailyRotatingFileHandler(logging.FileHandler):
    """날짜가 바뀔 때마다 로그 파일을 자동으로 변경하는 핸들러"""
    
    def __init__(self, logs_dir):
        self.logs_dir = logs_dir
        self.current_date = None
        self.current_handler = None
        super().__init__(self._get_log_file(), encoding='utf-8')
    
    def _get_log_file(self):
        """현재 날짜에 맞는 로그 파일 경로 반환"""
        today = datetime.now().strftime("%Y%m%d")
        return self.logs_dir / f"crontab_{today}.log"
    
    def emit(self, record):
        """로그 레코드 출력 시 날짜 확인 후 필요시 파일 변경"""
        current_date = datetime.now().strftime("%Y%m%d")
        
        # 날짜가 바뀌었으면 새 파일로 변경
        if self.current_date != current_date:
            self.current_date = current_date
            new_log_file = self._get_log_file()
            
            # 기존 핸들러 닫기
            if self.current_handler:
                self.current_handler.close()
            
            # 새 핸들러 생성
            self.current_handler = logging.FileHandler(new_log_file, encoding='utf-8')
            self.current_handler.setFormatter(self.formatter)
            
            # 로거에 새 핸들러 추가하고 기존 핸들러 제거
            logger = logging.getLogger(__name__)
            for handler in logger.handlers[:]:
                if isinstance(handler, DailyRotatingFileHandler):
                    logger.removeHandler(handler)
            logger.addHandler(self.current_handler)
        
        # 현재 핸들러로 로그 출력
        if self.current_handler:
            self.current_handler.emit(record)

def setup_logging():
    """날짜별 로그 파일 설정"""
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # 파일 핸들러 (날짜별 자동 회전)
    file_handler = DailyRotatingFileHandler(logs_dir)
    file_handler.setFormatter(formatter)
    
    # 콘솔 출력 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # 로거 설정
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # 기존 핸들러 제거
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 새 핸들러 추가
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# 로거 초기화
logger = setup_logging()

class CrontabScheduler:
    def __init__(self):
        self.script_dir = Path(__file__).parent
        self.python_exe = sys.executable
        self.config_path = self.script_dir / "crontab_config.json"
        self.config = self.load_config()
        self.startup_time = datetime.now().replace(second=0, microsecond=0)
        self.state_path = self.script_dir / "crontab_state.json"
        self.state = self.load_state()
        
    def load_config(self):
        """설정 파일 로드"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.warning(f"설정 파일을 찾을 수 없음: {self.config_path}")
                return {}
        except Exception as e:
            logger.error(f"설정 파일 로드 중 오류: {e}")
            return {}
        
    def run_powershell_command(self, command):
        """파워셸 명령어 실행"""
        try:
            # 파워셸 실행
            ps_command = f'powershell.exe -Command "{command}"'
            logger.info(f"파워셸 명령어 실행: {ps_command}")
            
            result = subprocess.run(
                ps_command,
                shell=True,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            if result.returncode == 0:
                logger.info(f"명령어 실행 성공: {command}")
                if result.stdout:
                    logger.info(f"출력: {result.stdout.strip()}")
            else:
                logger.error(f"명령어 실행 실패: {command}")
                if result.stderr:
                    logger.error(f"에러: {result.stderr.strip()}")
                    
        except Exception as e:
            logger.error(f"파워셸 명령어 실행 중 오류: {e}")
    
    def execute_scheduled_tasks(self):
        """스케줄된 작업들을 실행"""
        try:
            # logger.info("스케줄 작업 실행 시작")  # 중복 로그 제거
            
            # 모든 스케줄 확인
            schedules = self.config.get("schedules", [])
            
            for schedule_item in schedules:
                if not schedule_item.get("enabled", True):
                    continue
                    
                cron_expression = schedule_item.get("cron", "")
                reason_to_run = None
                if cron_expression and self.is_cron_time(cron_expression):
                    reason_to_run = "scheduled"
                else:
                    # 보장 실행(캐치업) 판단
                    if cron_expression and self.should_run_catchup(schedule_item, cron_expression):
                        reason_to_run = "catchup"

                if reason_to_run:
                    logger.info(f"크론 표현식 {cron_expression}에 맞는 작업 실행({reason_to_run}): {schedule_item.get('description', '')}")
                    # 작업 목록 실행
                    tasks = schedule_item.get("tasks", [])
                    for task in tasks:
                        if not task.get("enabled", True):
                            continue
                        self.execute_task(task)
                    # 상태 저장: 마지막 실행 시각 업데이트
                    self.mark_schedule_ran(schedule_item)
                        
        except Exception as e:
            logger.error(f"스케줄 작업 실행 중 오류: {e}")
    
    def is_cron_time(self, cron_expression):
        """크론 표현식이 현재 시간과 일치하는지 확인"""
        try:
            # 크론 표현식 파싱: 분 시 일 월 요일
            parts = cron_expression.split()
            if len(parts) != 5:
                logger.warning(f"잘못된 크론 표현식: {cron_expression}")
                return False
            
            minute, hour, day, month, weekday = parts
            now = datetime.now()
            
            # 분 확인
            if not self.matches_cron_field(minute, now.minute):
                return False
                
            # 시 확인
            if not self.matches_cron_field(hour, now.hour):
                return False
                
            # 일 확인
            if not self.matches_cron_field(day, now.day):
                return False
                
            # 월 확인
            if not self.matches_cron_field(month, now.month):
                return False
                
            # 요일 확인 (0=일요일, 1=월요일, ..., 6=토요일)
            if not self.matches_cron_field(weekday, now.weekday() + 1):
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"크론 표현식 파싱 중 오류: {e}")
            return False

    def is_cron_time_at(self, cron_expression, dt):
        """주어진 시각 dt가 크론 표현식과 일치하는지 확인"""
        try:
            parts = cron_expression.split()
            if len(parts) != 5:
                return False
            minute, hour, day, month, weekday = parts
            # 기존 요일 로직과 동일하게 유지 (0=일요일, 1=월요일, ..., 6=토요일) 주석과 다소 상이하나 호환성 유지
            weekday_value = dt.weekday() + 1

            if not self.matches_cron_field(minute, dt.minute):
                return False
            if not self.matches_cron_field(hour, dt.hour):
                return False
            if not self.matches_cron_field(day, dt.day):
                return False
            if not self.matches_cron_field(month, dt.month):
                return False
            if not self.matches_cron_field(weekday, weekday_value):
                return False
            return True
        except Exception:
            return False
    
    def matches_cron_field(self, field, value):
        """크론 필드가 값과 일치하는지 확인"""
        try:
            # * (모든 값)
            if field == "*":
                return True
                
            # 숫자 (정확한 값)
            if field.isdigit():
                return int(field) == value
                
            # */n (n마다)
            if field.startswith("*/"):
                n = int(field[2:])
                return value % n == 0
                
            # 범위 (예: 1-5)
            if "-" in field:
                start, end = map(int, field.split("-"))
                return start <= value <= end
                
            # 리스트 (예: 1,3,5)
            if "," in field:
                values = [int(x) for x in field.split(",")]
                return value in values
                
            return False
            
        except Exception as e:
            logger.error(f"크론 필드 매칭 중 오류: {field}, {value}, {e}")
            return False

    def parse_guarantee_config(self, schedule_item):
        """보장 실행 옵션 파싱: {enabled: bool, window_minutes: int} 형식 반환
        - window_minutes 또는 window_days를 허용하며, 둘 다 있으면 큰 값을 사용
        - 안전 상한: 최대 365일
        - run_on_startup 기본값: False (부팅 직후 캐치업 금지)
        """
        default = {"enabled": False, "window_minutes": 0, "run_on_startup": False}
        g = schedule_item.get("guarantee", None)
        if g is True:
            return {"enabled": True, "window_minutes": 180, "run_on_startup": False}
        if g is False or g is None:
            return default
        # dict 케이스
        try:
            enabled = bool(g.get("enabled", True))
            window = int(g.get("window_minutes", 0) or 0)
            window_days = g.get("window_days")
            run_on_startup = bool(g.get("run_on_startup", False))
            if window_days is not None:
                try:
                    window = max(window, int(window_days) * 1440)
                except Exception:
                    pass
            # 기본값 보정
            if window <= 0:
                window = 180
            # 안전 차단: 과도한 범위 방지 (최대 365일)
            window = max(0, min(window, 365 * 24 * 60))
            return {"enabled": enabled, "window_minutes": window, "run_on_startup": run_on_startup}
        except Exception:
            return default

    def should_run_catchup(self, schedule_item, cron_expression):
        """보장 실행이 필요한지 판단"""
        g = self.parse_guarantee_config(schedule_item)
        if not g.get("enabled", False):
            return False
        window = g.get("window_minutes", 0)
        if window <= 0:
            return False

        now = datetime.now()
        last_sched = self.find_last_scheduled_time(cron_expression, now, window)
        if last_sched is None:
            return False

        last_run = self.get_last_run_time(schedule_item)
        # 부팅 직후 캐치업 금지 옵션: 마지막 실행 기록이 없고 시작 직후라면 캐치업 생략
        if last_run is None and not g.get("run_on_startup", True):
            # 단, 이미 시작 이후의 슬롯을 놓친 경우만 고려하려면 아래와 같이 시작 시간과 비교 가능
            # if last_sched >= self.startup_time:
            #     return True
            return False
        if last_run is None or last_run < last_sched:
            return True
        return False

    def find_last_scheduled_time(self, cron_expression, now_dt, search_minutes):
        """과거 search_minutes 분 내 가장 최근 스케줄 시각 반환 (없으면 None)
        - 분/시가 고정 숫자일 경우 일 단위로 최적 탐색하여 성능 개선
        - 그 외에는 분 단위 역방향 탐색
        """
        try:
            parts = cron_expression.split()
            if len(parts) != 5:
                return None
            minute, hour, day, month, weekday = parts

            # 일 단위 최적 탐색: 분, 시가 모두 숫자일 때
            if minute.isdigit() and hour.isdigit():
                fixed_minute = int(minute)
                fixed_hour = int(hour)
                base = now_dt.replace(second=0, microsecond=0)
                max_days = int(search_minutes // 1440) + 1
                for i in range(0, max_days + 1):
                    candidate = (base.replace(hour=fixed_hour, minute=fixed_minute) - timedelta(days=i))
                    if candidate > now_dt:
                        continue
                    if self.is_cron_time_at(cron_expression, candidate):
                        return candidate
                return None

            # 일반 케이스: 분 단위 탐색
            for i in range(0, search_minutes + 1):
                candidate = now_dt - timedelta(minutes=i)
                if self.is_cron_time_at(cron_expression, candidate):
                    return candidate.replace(second=0, microsecond=0)
            return None
        except Exception:
            return None

    # ------------------- 상태 저장/복구 -------------------
    def load_state(self):
        try:
            if self.state_path.exists():
                with open(self.state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"상태 파일 로드 중 오류: {e}")
        return {"schedules": {}}

    def save_state(self):
        try:
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"상태 파일 저장 중 오류: {e}")

    def compute_schedule_id(self, schedule_item):
        try:
            key_src = json.dumps({
                "cron": schedule_item.get("cron"),
                "description": schedule_item.get("description"),
                "tasks": schedule_item.get("tasks"),
            }, ensure_ascii=False, sort_keys=True)
            return hashlib.sha1(key_src.encode("utf-8")).hexdigest()[:12]
        except Exception:
            # 폴백: 설명 또는 크론 사용
            return (schedule_item.get("cron") or schedule_item.get("description") or "unknown")

    def get_last_run_time(self, schedule_item):
        try:
            sid = self.compute_schedule_id(schedule_item)
            iso = self.state.get("schedules", {}).get(sid, {}).get("last_run_at")
            if not iso:
                return None
            return datetime.fromisoformat(iso)
        except Exception:
            return None

    def mark_schedule_ran(self, schedule_item):
        try:
            sid = self.compute_schedule_id(schedule_item)
            self.state.setdefault("schedules", {}).setdefault(sid, {})["last_run_at"] = datetime.now().replace(second=0, microsecond=0).isoformat()
            self.save_state()
        except Exception as e:
            logger.error(f"상태 업데이트 중 오류: {e}")
    
    def execute_task(self, task):
        """개별 작업 실행"""
        try:
            task_type = task.get("type", "")
            description = task.get("description", "작업")
            
            logger.info(f"작업 실행: {description} ({task_type})")
            
            if task_type == "python_script":
                script_name = task.get("script", "")
                self.run_python_script(script_name)
                
            elif task_type == "powershell_command":
                command = task.get("command", "")
                self.run_powershell_command(command)
                
            elif task_type == "batch_file":
                batch_file = task.get("file", "")
                self.run_batch_file(batch_file)
                
            else:
                logger.warning(f"알 수 없는 작업 타입: {task_type}")
                
            logger.info(f"작업 완료: {description}")
            
        except Exception as e:
            logger.error(f"작업 실행 중 오류: {e}")
    
    def run_batch_file(self, batch_file):
        """배치 파일 실행"""
        try:
            batch_path = self.script_dir / batch_file
            if batch_path.exists():
                logger.info(f"배치 파일 직접 실행: {batch_file}")
                
                # 배치 파일을 직접 실행
                result = subprocess.run(
                    [str(batch_path)],
                    cwd=self.script_dir,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    shell=True
                )
                
                if result.returncode == 0:
                    logger.info(f"배치 파일 실행 성공: {batch_file}")
                    if result.stdout:
                        logger.info(f"출력: {result.stdout.strip()}")
                else:
                    logger.error(f"배치 파일 실행 실패: {batch_file}")
                    if result.stderr:
                        logger.error(f"에러: {result.stderr.strip()}")
            else:
                logger.error(f"배치 파일을 찾을 수 없음: {batch_path}")
        except Exception as e:
            logger.error(f"배치 파일 실행 중 오류: {e}")
    
    def cleanup_logs(self):
        """로그 정리"""
        try:
            logger.info("로그 정리 시작")
            # 오래된 로그 파일 정리
            # 로그 파일 크기 제한 등
            logger.info("로그 정리 완료")
        except Exception as e:
            logger.error(f"로그 정리 중 오류: {e}")
    
    def cleanup_temp_files(self):
        """임시 파일 정리"""
        try:
            logger.info("임시 파일 정리 시작")
            # 임시 파일, 캐시 파일 정리
            logger.info("임시 파일 정리 완료")
        except Exception as e:
            logger.error(f"임시 파일 정리 중 오류: {e}")
    
    def generate_weekly_report(self):
        """주간 리포트 생성"""
        try:
            logger.info("주간 리포트 생성 시작")
            # 주간 통계, 성과 분석 등
            logger.info("주간 리포트 생성 완료")
        except Exception as e:
            logger.error(f"주간 리포트 생성 중 오류: {e}")
    
    def analyze_weekly_data(self):
        """주간 데이터 분석"""
        try:
            logger.info("주간 데이터 분석 시작")
            # 데이터 트렌드 분석, 패턴 찾기 등
            logger.info("주간 데이터 분석 완료")
        except Exception as e:
            logger.error(f"주간 데이터 분석 중 오류: {e}")
    
    def optimize_performance(self):
        """성능 최적화"""
        try:
            logger.info("성능 최적화 시작")
            # 데이터베이스 최적화, 캐시 정리 등
            logger.info("성능 최적화 완료")
        except Exception as e:
            logger.error(f"성능 최적화 중 오류: {e}")
    
    def archive_monthly_data(self):
        """월간 데이터 아카이브"""
        try:
            logger.info("월간 데이터 아카이브 시작")
            # 오래된 데이터 압축, 백업 등
            logger.info("월간 데이터 아카이브 완료")
        except Exception as e:
            logger.error(f"월간 데이터 아카이브 중 오류: {e}")
    
    def generate_monthly_report(self):
        """월간 리포트 생성"""
        try:
            logger.info("월간 리포트 생성 시작")
            # 월간 종합 리포트, KPI 분석 등
            logger.info("월간 리포트 생성 완료")
        except Exception as e:
            logger.error(f"월간 리포트 생성 중 오류: {e}")
    
    def system_cleanup(self):
        """시스템 정리"""
        try:
            logger.info("시스템 정리 시작")
            # 시스템 최적화, 정리 등
            logger.info("시스템 정리 완료")
        except Exception as e:
            logger.error(f"시스템 정리 중 오류: {e}")
    
    def run_python_script(self, script_name):
        """Python 스크립트 실행"""
        try:
            script_path = self.script_dir / script_name
            if script_path.exists():
                logger.info(f"Python 스크립트 직접 실행: {script_name}")
                
                # Python 스크립트를 직접 실행
                env = os.environ.copy()
                # 자식 파이썬 프로세스의 표준 입출력 인코딩을 강제로 UTF-8로 고정
                env['PYTHONIOENCODING'] = 'utf-8'
                env['PYTHONUTF8'] = '1'

                # 자식 프로세스 출력을 파일로 바로 스트리밍하여 메모리 점유 최소화
                scripts_log_dir = logs_dir / "scripts"
                scripts_log_dir.mkdir(exist_ok=True)
                # 현재 날짜로 로그 파일명 생성 (실행 시점 기준)
                log_file = scripts_log_dir / f"{script_path.stem}_{datetime.now().strftime('%Y%m%d')}.log"

                # 실행 전 메모리 사용량 기록 (가능 시)
                before_mb = None
                try:
                    import psutil  # type: ignore
                    before_mb = int(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024))
                except Exception:
                    pass

                with open(log_file, "a", encoding="utf-8", errors="replace") as lf:
                    lf.write(f"\n==== [{datetime.now().isoformat(sep=' ', timespec='seconds')}] Run: {script_path.name} ===="\
                             f"\nCWD: {self.script_dir}\nPython: {self.python_exe}\n")
                    result = subprocess.run(
                        [self.python_exe, str(script_path)],
                        cwd=self.script_dir,
                        stdout=lf,
                        stderr=lf,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        env=env
                    )
                    lf.write(f"\n==== Exit code: {result.returncode} ===="\
                             f"\n==== End of run ===\n")

                # 실행 후 메모리 사용량 기록 및 정리
                try:
                    import psutil  # type: ignore
                    after_mb = int(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024))
                    if before_mb is not None:
                        delta = after_mb - before_mb
                        logger.info(f"Python 스크립트 실행 성공: {script_name} | 메모리(MB) before={before_mb}, after={after_mb}, delta={delta}")
                    else:
                        logger.info(f"Python 스크립트 실행 성공: {script_name}")
                except Exception:
                    logger.info(f"Python 스크립트 실행 성공: {script_name}")

                # 가비지 컬렉션으로 메모리 회수 유도
                try:
                    gc.collect()
                except Exception:
                    pass
            else:
                logger.error(f"스크립트를 찾을 수 없음: {script_path}")
        except Exception as e:
            logger.error(f"Python 스크립트 실행 중 오류: {e}")
    
    def run_scheduled_tasks(self):
        """스케줄된 작업 실행"""
        # logger.info("스케줄된 작업 실행 시작")  # 중복 로그 제거
        self.execute_scheduled_tasks()
    
    def setup_schedule(self):
        """스케줄 설정"""
        logger.info("크론탭 스케줄러 시작")
        
        # 설정 파일에서 스케줄 로드
        schedules = self.config.get("schedules", [])
        
        # 모든 스케줄을 1분마다 체크하도록 설정
        schedule.every().minute.do(self.run_scheduled_tasks)
        
        # 등록된 스케줄 출력
        logger.info(f"총 {len(schedules)}개의 크론 스케줄 로드됨:")
        for schedule_item in schedules:
            if schedule_item.get("enabled", True):
                cron = schedule_item.get("cron", "")
                description = schedule_item.get("description", "")
                logger.info(f"  - {cron} : {description}")
        
        logger.info("스케줄 설정 완료")
    
    def run_scheduler(self):
        """스케줄러 실행"""
        try:
            self.setup_schedule()
            last_config_time = self.config_path.stat().st_mtime if self.config_path.exists() else 0
            
            while True:
                # 설정 파일 변경 감지
                if self.config_path.exists():
                    current_config_time = self.config_path.stat().st_mtime
                    if current_config_time > last_config_time:
                        logger.info("설정 파일이 변경되었습니다. 스케줄을 다시 로드합니다.")
                        self.config = self.load_config()
                        schedule.clear()  # 기존 스케줄 클리어
                        self.setup_schedule()  # 새 스케줄 설정
                        last_config_time = current_config_time
                
                schedule.run_pending()
                time.sleep(60)  # 1분마다 체크
                
        except KeyboardInterrupt:
            logger.info("크론탭 스케줄러 종료")
        except Exception as e:
            logger.error(f"스케줄러 실행 중 오류: {e}")
            raise

def main():
    """메인 함수"""
    scheduler = CrontabScheduler()
    
    # 명령행 인수가 있으면 즉시 실행
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "tasks":
            scheduler.run_scheduled_tasks()
        elif command == "test":
            # 테스트 모드: 모든 크론 표현식 테스트
            print("크론 표현식 테스트 모드")
            test_cron_expressions(scheduler)
        else:
            logger.error(f"알 수 없는 명령어: {command}")
            print("사용법: python crontab.py [tasks|test]")
            print("명령행 인수 없이 실행하면 스케줄러 모드로 실행됩니다.")
    else:
        # 스케줄러 모드로 실행
        scheduler.run_scheduler()

def test_cron_expressions(scheduler):
    """크론 표현식 테스트"""
    print("\n=== 크론 표현식 테스트 ===")
    schedules = scheduler.config.get("schedules", [])
    
    for i, schedule_item in enumerate(schedules):
        cron = schedule_item.get("cron", "")
        description = schedule_item.get("description", "")
        enabled = schedule_item.get("enabled", True)
        
        print(f"\n{i+1}. {cron} - {description} ({'활성화' if enabled else '비활성화'})")
        
        if enabled:
            is_match = scheduler.is_cron_time(cron)
            print(f"   현재 시간과 일치: {'예' if is_match else '아니오'}")
            
            # 다음 실행 시간 계산 (간단한 예시)
            print(f"   다음 실행: {get_next_run_time(cron)}")

def get_next_run_time(cron):
    """다음 실행 시간 계산 (간단한 버전)"""
    try:
        parts = cron.split()
        if len(parts) != 5:
            return "알 수 없음"
        
        minute, hour, day, month, weekday = parts
        now = datetime.now()
        
        # 간단한 다음 실행 시간 계산
        if minute != "*" and minute.isdigit():
            next_minute = int(minute)
        else:
            next_minute = now.minute
            
        if hour != "*" and hour.isdigit():
            next_hour = int(hour)
        else:
            next_hour = now.hour
            
        return f"{next_hour:02d}:{next_minute:02d}"
        
    except:
        return "알 수 없음"

if __name__ == "__main__":
    main()
