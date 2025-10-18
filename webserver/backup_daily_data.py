#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
일일 데이터 백업 스크립트
크론탭에서 호출되어 실행됨
"""

import os
import shutil
import json
from datetime import datetime
from pathlib import Path

def backup_data():
    """데이터 백업 실행"""
    try:
        print(f"[{datetime.now()}] 일일 데이터 백업 시작")
        
        # 백업 디렉토리 생성
        backup_dir = Path("backups") / "daily" / datetime.now().strftime("%Y-%m-%d")
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 백업할 데이터 목록
        data_sources = [
            "data/portfolio_config.json",
            "data/portfolio_daily_profit_summary.json",
            "crontab.log"
        ]
        
        # 파일 백업
        for source in data_sources:
            source_path = Path(source)
            if source_path.exists():
                dest_path = backup_dir / source_path.name
                shutil.copy2(source_path, dest_path)
                print(f"백업 완료: {source} -> {dest_path}")
            else:
                print(f"백업 대상 파일 없음: {source}")
        
        # 백업 정보 저장
        backup_info = {
            "backup_time": datetime.now().isoformat(),
            "backup_type": "daily",
            "files_backed_up": len([s for s in data_sources if Path(s).exists()]),
            "backup_directory": str(backup_dir)
        }
        
        with open(backup_dir / "backup_info.json", "w", encoding="utf-8") as f:
            json.dump(backup_info, f, indent=2, ensure_ascii=False)
        
        print(f"[{datetime.now()}] 일일 데이터 백업 완료: {backup_dir}")
        return True
        
    except Exception as e:
        print(f"[{datetime.now()}] 백업 중 오류 발생: {e}")
        return False

if __name__ == "__main__":
    backup_data()
