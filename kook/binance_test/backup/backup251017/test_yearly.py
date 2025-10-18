# -*- coding: utf-8 -*-
"""
연도별 테스트 - 간단한 버전
"""

import pandas as pd
import numpy as np
import os

def test_yearly():
    print("=== 연도별 테스트 시작 ===")
    
    # 데이터 파일 확인
    years = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
    
    for year in years:
        file_path = f"data/BTCUSDT/5m/BTCUSDT_5m_{year}.csv"
        if os.path.exists(file_path):
            print(f"{year}년 데이터 파일 존재: {file_path}")
        else:
            print(f"{year}년 데이터 파일 없음")
    
    print("=== 테스트 완료 ===")

if __name__ == "__main__":
    test_yearly()
