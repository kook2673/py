#!/usr/bin/env python3
#-*-coding:utf-8 -*-

import os
import sys
import pandas as pd
from datetime import datetime

def main():
    print("Test script started")
    print("Current directory:", os.getcwd())
    
    # 데이터 파일 확인
    data_file = "data/BTCUSDT/1h/BTCUSDT_1h_2024.csv"
    if os.path.exists(data_file):
        print(f"Data file exists: {data_file}")
        try:
            df = pd.read_csv(data_file)
            print(f"Data loaded successfully: {len(df)} rows")
            print(f"Columns: {df.columns.tolist()}")
            print(f"First few rows:")
            print(df.head())
        except Exception as e:
            print(f"Error loading data: {e}")
    else:
        print(f"Data file not found: {data_file}")
        print("Available files in data directory:")
        if os.path.exists("data"):
            for root, dirs, files in os.walk("data"):
                for file in files:
                    print(f"  {os.path.join(root, file)}")

if __name__ == "__main__":
    main()
