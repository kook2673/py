#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
통합 서비스 시작 스크립트
웹서버, 텔레그램봇, 크론탭을 모두 실행
"""

import subprocess
import sys
import time
import signal
import os
from pathlib import Path
from datetime import datetime

class ServiceManager:
    def __init__(self):
        self.script_dir = Path(__file__).parent
        self.python_exe = sys.executable
        self.processes = {}
        self.running = True
        
        # 시그널 핸들러 설정
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def signal_handler(self, signum, frame):
        """시그널 처리 (Ctrl+C 등)"""
        print(f"\n[{datetime.now()}] 종료 신호 수신 ({signum})")
        self.stop_all_services()
        sys.exit(0)
        
    def start_service(self, name, script, description):
        """서비스 시작"""
        try:
            script_path = self.script_dir / script
            if not script_path.exists():
                print(f"[{datetime.now()}] 오류: {script} 파일을 찾을 수 없음")
                return False
                
            print(f"[{datetime.now()}] {description} 시작 중...")
            
            # 서비스 실행
            process = subprocess.Popen(
                [self.python_exe, str(script_path)],
                cwd=self.script_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
            )
            
            self.processes[name] = {
                'process': process,
                'script': script,
                'description': description,
                'start_time': datetime.now()
            }
            
            print(f"[{datetime.now()}] {description} 시작됨 (PID: {process.pid})")
            return True
            
        except Exception as e:
            print(f"[{datetime.now()}] {description} 시작 실패: {e}")
            return False
    
    def start_webserver(self):
        """웹서버 시작"""
        return self.start_service(
            'webserver',
            'webserver.py',
            '웹서버'
        )
    
    def start_telegram_bot(self):
        """텔레그램 봇 시작"""
        return self.start_service(
            'telegram_bot',
            'telegram_bot.py',
            '텔레그램 봇'
        )
    
    def start_crontab(self):
        """크론탭 스케줄러 시작"""
        return self.start_service(
            'crontab',
            'crontab.py',
            '크론탭 스케줄러'
        )
    
    def start_all_services(self):
        """모든 서비스 시작"""
        print(f"[{datetime.now()}] === 통합 서비스 시작 ===")
        print(f"[{datetime.now()}] Python 경로: {self.python_exe}")
        print(f"[{datetime.now()}] 작업 디렉토리: {self.script_dir}")
        print()
        
        # 필요한 패키지 설치 확인
        print(f"[{datetime.now()}] 필요한 패키지 설치 확인 중...")
        try:
            subprocess.run([self.python_exe, "-m", "pip", "install", "-r", "requirements.txt"], 
                         cwd=self.script_dir, check=True, capture_output=True)
            print(f"[{datetime.now()}] 패키지 설치 완료")
        except subprocess.CalledProcessError as e:
            print(f"[{datetime.now()}] 패키지 설치 실패: {e}")
        print()
        
        # 서비스들 순차적으로 시작
        services = [
            # ('webserver', self.start_webserver),  # 웹서버 비활성화 (나중에 사용 가능)
            ('telegram_bot', self.start_telegram_bot),
            ('crontab', self.start_crontab)
        ]
        
        started_count = 0
        for name, start_func in services:
            if start_func():
                started_count += 1
            else:
                print(f"[{datetime.now()}] {name} 시작 실패")
            
            # 서비스 간 간격
            time.sleep(2)
        
        print(f"\n[{datetime.now()}] === 서비스 시작 완료 ===")
        print(f"[{datetime.now()}] 성공적으로 시작된 서비스: {started_count}/{len(services)}")
        
        if started_count == len(services):
            print(f"[{datetime.now()}] 모든 서비스가 정상적으로 시작되었습니다.")
        else:
            print(f"[{datetime.now()}] 일부 서비스 시작에 실패했습니다.")
        
        return started_count == len(services)
    
    def check_service_status(self):
        """서비스 상태 확인"""
        print(f"\n[{datetime.now()}] === 서비스 상태 ===")
        
        for name, info in self.processes.items():
            process = info['process']
            description = info['description']
            start_time = info['start_time']
            
            # 프로세스 상태 확인
            if process.poll() is None:
                status = "실행 중"
                uptime = datetime.now() - start_time
                uptime_str = str(uptime).split('.')[0]  # 마이크로초 제거
            else:
                status = f"종료됨 (코드: {process.returncode})"
                uptime_str = "N/A"
            
            print(f"  {description}: {status}")
            print(f"    PID: {process.pid}")
            print(f"    시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"    가동 시간: {uptime_str}")
            print()
    
    def stop_service(self, name):
        """특정 서비스 종료"""
        if name in self.processes:
            info = self.processes[name]
            process = info['process']
            description = info['description']
            
            print(f"[{datetime.now()}] {description} 종료 중...")
            
            try:
                process.terminate()
                process.wait(timeout=10)
                print(f"[{datetime.now()}] {description} 정상 종료됨")
            except subprocess.TimeoutExpired:
                print(f"[{datetime.now()}] {description} 강제 종료 중...")
                process.kill()
                process.wait()
                print(f"[{datetime.now()}] {description} 강제 종료됨")
            
            del self.processes[name]
    
    def stop_all_services(self):
        """모든 서비스 종료"""
        print(f"\n[{datetime.now()}] === 모든 서비스 종료 중 ===")
        
        for name in list(self.processes.keys()):
            self.stop_service(name)
        
        print(f"[{datetime.now()}] 모든 서비스가 종료되었습니다.")
    
    def monitor_services(self):
        """서비스 모니터링"""
        print(f"[{datetime.now()}] 서비스 모니터링 시작...")
        print(f"[{datetime.now()}] 종료하려면 Ctrl+C를 누르세요.")
        print()
        
        try:
            while self.running:
                # 서비스 상태 확인
                self.check_service_status()
                
                # 30초 대기
                time.sleep(30)
                
        except KeyboardInterrupt:
            print(f"\n[{datetime.now()}] 사용자에 의한 종료 요청")
        except Exception as e:
            print(f"\n[{datetime.now()}] 모니터링 중 오류: {e}")
        finally:
            self.stop_all_services()

def main():
    """메인 함수"""
    print("=== 통합 서비스 관리자 ===")
    print("웹서버, 텔레그램봇, 크론탭을 모두 실행합니다.")
    print()
    
    # 서비스 매니저 생성
    manager = ServiceManager()
    
    try:
        # 모든 서비스 시작
        if manager.start_all_services():
            print(f"\n[{datetime.now()}] 모든 서비스가 성공적으로 시작되었습니다.")
            print(f"[{datetime.now()}] 서비스 모니터링을 시작합니다...")
            
            # 서비스 모니터링 시작
            manager.monitor_services()
        else:
            print(f"\n[{datetime.now()}] 일부 서비스 시작에 실패했습니다.")
            print(f"[{datetime.now()}] 로그를 확인하고 다시 시도해주세요.")
            
    except Exception as e:
        print(f"\n[{datetime.now()}] 치명적 오류 발생: {e}")
        manager.stop_all_services()
        sys.exit(1)

if __name__ == "__main__":
    main()
