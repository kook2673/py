"""
5분 데이터를 10분 데이터로 변환하는 스크립트
"""

import pandas as pd
import os
from datetime import datetime

def convert_5m_to_10m():
    """5분 데이터를 10분 데이터로 변환"""
    
    # 5분 데이터 디렉토리
    input_dir = "data/BTCUSDT/5m"
    output_dir = "data/BTCUSDT/10m"
    
    # 출력 디렉토리 생성
    os.makedirs(output_dir, exist_ok=True)
    
    years = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
    
    for year in years:
        input_file = f"{input_dir}/BTCUSDT_5m_{year}.csv"
        output_file = f"{output_dir}/BTCUSDT_10m_{year}.csv"
        
        if os.path.exists(input_file):
            print(f"{year}년 5분 데이터 변환 중...")
            
            # 5분 데이터 로드
            df = pd.read_csv(input_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            
            # 10분 데이터로 리샘플링
            # OHLC 데이터는 각각 적절한 집계 함수 사용
            df_10m = df.resample('10T').agg({
                'open': 'first',      # 첫 번째 값
                'high': 'max',        # 최고가
                'low': 'min',         # 최저가
                'close': 'last',      # 마지막 값
                'volume': 'sum'       # 거래량 합계
            }).dropna()
            
            # 인덱스를 다시 컬럼으로 변환
            df_10m.reset_index(inplace=True)
            
            # 컬럼 순서 정리
            df_10m = df_10m[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
            # CSV로 저장
            df_10m.to_csv(output_file, index=False)
            
            print(f"  완료: {len(df_10m)}개 캔들 -> {output_file}")
            print(f"  기간: {df_10m['timestamp'].min()} ~ {df_10m['timestamp'].max()}")
        else:
            print(f"{year}년 5분 데이터 파일이 없습니다: {input_file}")
    
    print("\n=== 10분 데이터 변환 완료 ===")

if __name__ == "__main__":
    convert_5m_to_10m()
