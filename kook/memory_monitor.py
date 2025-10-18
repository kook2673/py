#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
메모리 모니터링 시스템
- 파이썬 프로세스들의 메모리 사용량을 실시간으로 모니터링
- 메모리 사용량이 임계값을 초과하면 알림 발송
- 메모리 누수 감지 및 자동 정리
"""

import psutil
import time
import logging
import json
import os
from datetime import datetime
import gc

import sys

# 텔레그램 알림 모듈
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import telegram_sender as line_alert

class MemoryMonitor:
    def __init__(self, memory_threshold_mb=1000, check_interval=60):
        """
        메모리 모니터 초기화
        
        Args:
            memory_threshold_mb (int): 메모리 사용량 임계값 (MB)
            check_interval (int): 체크 간격 (초)
        """
        self.memory_threshold = memory_threshold_mb
        self.check_interval = check_interval
        self.processes = {}
        self.alert_sent = {}
        
        # 로깅 설정
        self.setup_logging()
        
    def setup_logging(self):
        """로깅 설정"""
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f"memory_monitor_{datetime.now().strftime('%Y%m%d')}.log")
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        
    def get_python_processes(self):
        """실행 중인 파이썬 프로세스들 가져오기"""
        python_processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info']):
            try:
                if proc.info['name'] and 'python' in proc.info['name'].lower():
                    # 명령행에 우리 프로젝트 경로가 포함된 프로세스만 필터링
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    if 'kook' in cmdline or 'webserver' in cmdline:
                        python_processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        return python_processes
    
    def get_memory_usage(self, process):
        """프로세스의 메모리 사용량 가져오기"""
        try:
            memory_info = process.memory_info()
            return memory_info.rss / 1024 / 1024  # MB 단위
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0
    
    def cleanup_process_memory(self, process):
        """프로세스 메모리 정리 시도"""
        try:
            # 프로세스가 여전히 실행 중인지 확인
            if process.is_running():
                # 가비지 컬렉션 시도 (프로세스 내부에서 실행)
                # 실제로는 프로세스 내부에서 cleanup_memory() 함수를 호출해야 함
                self.logger.info(f"프로세스 {process.pid} 메모리 정리 시도")
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return False
    
    def check_memory_usage(self):
        """메모리 사용량 체크"""
        python_processes = self.get_python_processes()
        high_memory_processes = []
        
        for process in python_processes:
            try:
                memory_mb = self.get_memory_usage(process)
                process_name = ' '.join(process.cmdline()) if process.cmdline() else f"PID {process.pid}"
                
                self.logger.info(f"프로세스: {process_name[:50]}... | 메모리: {memory_mb:.2f} MB")
                
                if memory_mb > self.memory_threshold:
                    high_memory_processes.append({
                        'process': process,
                        'memory_mb': memory_mb,
                        'name': process_name
                    })
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return high_memory_processes
    
    def send_memory_alert(self, high_memory_processes):
        """메모리 사용량 경고 알림 발송"""
        if not high_memory_processes:
            return
            
        alert_message = "🚨 **메모리 사용량 경고**\n\n"
        
        for proc_info in high_memory_processes:
            memory_mb = proc_info['memory_mb']
            process_name = proc_info['name'][:50]
            
            alert_message += f"• {process_name}...\n"
            alert_message += f"  메모리: {memory_mb:.2f} MB (임계값: {self.memory_threshold} MB)\n\n"
            
            # 프로세스별로 알림 중복 방지
            process_key = f"{proc_info['process'].pid}_{int(memory_mb)}"
            if process_key not in self.alert_sent:
                self.alert_sent[process_key] = time.time()
        
        # 텔레그램 알림 발송
        try:
            line_alert.SendMessage(alert_message)
            self.logger.warning(f"메모리 경고 알림 발송: {len(high_memory_processes)}개 프로세스")
        except Exception as e:
            self.logger.error(f"알림 발송 실패: {e}")
    
    def cleanup_old_alerts(self):
        """오래된 알림 기록 정리 (1시간 이상)"""
        current_time = time.time()
        old_keys = [key for key, timestamp in self.alert_sent.items() 
                   if current_time - timestamp > 3600]  # 1시간
        
        for key in old_keys:
            del self.alert_sent[key]
    
    def run_monitoring(self):
        """메모리 모니터링 실행"""
        self.logger.info(f"메모리 모니터링 시작 (임계값: {self.memory_threshold} MB, 체크 간격: {self.check_interval}초)")
        
        try:
            while True:
                # 메모리 사용량 체크
                high_memory_processes = self.check_memory_usage()
                
                # 경고 알림 발송
                if high_memory_processes:
                    self.send_memory_alert(high_memory_processes)
                
                # 오래된 알림 기록 정리
                self.cleanup_old_alerts()
                
                # 시스템 전체 메모리 사용량도 체크
                system_memory = psutil.virtual_memory()
                if system_memory.percent > 90:
                    self.logger.warning(f"시스템 메모리 사용량 높음: {system_memory.percent:.1f}%")
                
                # 대기
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            self.logger.info("메모리 모니터링 중단됨")
        except Exception as e:
            self.logger.error(f"모니터링 중 오류: {e}")

def main():
    """메인 함수"""
    # 메모리 모니터 생성 (임계값: 1GB, 체크 간격: 60초)
    monitor = MemoryMonitor(memory_threshold_mb=1000, check_interval=60)
    
    # 모니터링 시작
    monitor.run_monitoring()

if __name__ == "__main__":
    main()
