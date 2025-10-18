#-*-coding:utf-8 -*-
'''
1분봉 데이터를 1시간봉으로 변환하는 스크립트
2024년 1분봉 데이터를 읽어서 1시간봉으로 변환하여 저장

=== 변환 로직 ===
1. 1분봉 데이터 로드 (월별 파일들)
2. 1시간 단위로 OHLCV 데이터 집계
3. 년도별로 파일 저장 (예: BTCUSDT_1h_2024.csv)

=== OHLCV 집계 규칙 ===
- Open: 시간대 첫 번째 1분봉의 시가
- High: 시간대 내 최고가
- Low: 시간대 내 최저가  
- Close: 시간대 마지막 1분봉의 종가
- Volume: 시간대 내 거래량 합계
'''

import pandas as pd
import numpy as np
import os
import glob
from datetime import datetime, timedelta

def resample_1m_to_1h(df_1m):
    """1분봉 데이터를 1시간봉으로 변환"""
    # 시간대별로 그룹화하여 OHLCV 집계
    df_1h = df_1m.resample('1H').agg({
        'open': 'first',      # 첫 번째 시가
        'high': 'max',        # 최고가
        'low': 'min',         # 최저가
        'close': 'last',      # 마지막 종가
        'volume': 'sum'       # 거래량 합계
    })
    
    # NaN 값 제거 (거래가 없는 시간대)
    df_1h = df_1h.dropna()
    
    return df_1h

def convert_monthly_files_to_1h():
    """월별 1분봉 파일들을 1시간봉으로 변환"""
    print("🔄 1분봉 → 1시간봉 변환 시작!")
    
    # 스크립트 디렉토리
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_1m_dir = os.path.join(script_dir, 'data', 'BTC_USDT', '1m')
    data_1h_dir = os.path.join(script_dir, 'data', 'BTCUSDT', '1h')
    
    # 1시간봉 저장 디렉토리 생성
    if not os.path.exists(data_1h_dir):
        os.makedirs(data_1h_dir)
        print(f"📁 1시간봉 저장 디렉토리 생성: {data_1h_dir}")
    
    # 2024년 + 2025년 월별 1분봉 파일들 찾기
    csv_pattern = '202[45]-*.csv'  # 2024년과 2025년 모두 포함
    csv_files = glob.glob(os.path.join(data_1m_dir, csv_pattern))
    
    if not csv_files:
        print(f"❌ {csv_pattern} 패턴의 파일을 찾을 수 없습니다.")
        print(f"📁 데이터 디렉토리: {data_1m_dir}")
        print("2024년과 2025년 월별 1분봉 데이터 파일이 필요합니다.")
        return
    
    print(f"📊 발견된 2024-2025년 1분봉 파일 수: {len(csv_files)}개")
    
    # 년도별로 데이터 수집
    yearly_data = {}
    total_1m_candles = 0
    
    for csv_file in sorted(csv_files):
        try:
            file_name = os.path.basename(csv_file)
            print(f"📖 {file_name} 읽는 중...")
            
            # CSV 파일 읽기
            df = pd.read_csv(csv_file, index_col='timestamp', parse_dates=True)
            
            print(f"   - 1분봉 수: {len(df):,}개")
            print(f"   - 기간: {df.index[0]} ~ {df.index[-1]}")
            
            # 년도 추출
            year = df.index[0].year
            
            if year not in yearly_data:
                yearly_data[year] = []
            
            yearly_data[year].append(df)
            total_1m_candles += len(df)
            
        except Exception as e:
            print(f"   ❌ 파일 읽기 실패: {e}")
            continue
    
    if not yearly_data:
        print("❌ 읽을 수 있는 데이터가 없습니다.")
        return
    
    # 년도별로 1시간봉 변환 및 저장
    for year, dataframes in yearly_data.items():
        print(f"\n{'='*60}")
        print(f"🎯 {year}년 1시간봉 변환 중...")
        
        # 해당 년도 데이터 병합
        df_year = pd.concat(dataframes, axis=0, ignore_index=False)
        
        # 중복 제거 및 정렬
        df_year = df_year[~df_year.index.duplicated(keep='last')]
        df_year = df_year.sort_index()
        
        print(f"📊 {year}년 1분봉 데이터: {len(df_year):,}개")
        print(f"기간: {df_year.index[0]} ~ {df_year.index[-1]}")
        
        # 1시간봉으로 변환
        print("🔄 1시간봉으로 변환 중...")
        df_1h = resample_1m_to_1h(df_year)
        
        print(f"✅ 1시간봉 변환 완료: {len(df_1h):,}개")
        print(f"기간: {df_1h.index[0]} ~ {df_1h.index[-1]}")
        
        # 파일 저장
        filename = f'BTCUSDT_1h_{year}.csv'
        filepath = os.path.join(data_1h_dir, filename)
        
        df_1h.to_csv(filepath)
        print(f"💾 {year}년 1시간봉 저장 완료: {filepath}")
        
        # 샘플 데이터 출력
        print(f"\n📋 {year}년 1시간봉 샘플:")
        print(df_1h.head())
        print(f"\n📋 {year}년 1시간봉 마지막:")
        print(df_1h.tail())
    
    print(f"\n{'='*60}")
    print("🎉 모든 년도 1시간봉 변환 완료!")
    print(f"📊 총 처리된 1분봉: {total_1m_candles:,}개")
    print(f"📁 저장 위치: {data_1h_dir}")

def verify_1h_data():
    """1시간봉 데이터 검증"""
    print("\n🔍 1시간봉 데이터 검증 중...")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_1h_dir = os.path.join(script_dir, 'data', 'BTCUSDT', '1h')
    
    if not os.path.exists(data_1h_dir):
        print("❌ 1시간봉 디렉토리가 존재하지 않습니다.")
        return
    
    # 1시간봉 파일들 확인
    csv_files = glob.glob(os.path.join(data_1h_dir, '*.csv'))
    
    if not csv_files:
        print("❌ 1시간봉 파일이 없습니다.")
        return
    
    print(f"📁 발견된 1시간봉 파일: {len(csv_files)}개")
    
    for csv_file in sorted(csv_files):
        try:
            file_name = os.path.basename(csv_file)
            df = pd.read_csv(csv_file, index_col='timestamp', parse_dates=True)
            
            print(f"\n📊 {file_name}:")
            print(f"   - 캔들 수: {len(df):,}개")
            print(f"   - 기간: {df.index[0]} ~ {df.index[-1]}")
            print(f"   - 컬럼: {list(df.columns)}")
            
            # 데이터 품질 확인
            print(f"   - NaN 값: {df.isnull().sum().sum()}")
            print(f"   - 중복: {df.index.duplicated().sum()}")
            
        except Exception as e:
            print(f"   ❌ 파일 검증 실패: {e}")

if __name__ == "__main__":
    # 1분봉 → 1시간봉 변환
    convert_monthly_files_to_1h()
    
    # 변환된 데이터 검증
    verify_1h_data()
    
    print("\n✨ 1시간봉 변환 작업 완료!")
