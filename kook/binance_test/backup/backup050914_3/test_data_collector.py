#!/usr/bin/env python3
#-*-coding:utf-8 -*-

"""
데이터 수집기 테스트 스크립트
============================

BTC만 먼저 테스트해서 1년치 데이터가 제대로 수집되는지 확인
"""

import os
import pandas as pd
import ccxt
import time
from datetime import datetime, timedelta

class TestCryptoDataCollector:
    """테스트용 암호화폐 데이터 수집기"""
    
    def __init__(self):
        self.exchange = ccxt.binance({
            'apiKey': '',  # 공개 데이터만 사용
            'secret': '',
            'sandbox': False,
            'enableRateLimit': True,
        })
        
        # 테스트용으로 BTC만
        self.symbols = ['BTC/USDT']
        self.timeframes = ['1h']
        
    def create_directories(self):
        """디렉토리 생성"""
        base_dir = os.path.join(os.path.dirname(__file__), 'data')
        
        for symbol in self.symbols:
            symbol_dir = symbol.replace('/', '')
            for timeframe in self.timeframes:
                path = os.path.join(base_dir, symbol_dir, timeframe)
                os.makedirs(path, exist_ok=True)
                print(f"📁 디렉토리 생성: {path}")
    
    def _collect_year_data(self, symbol: str, timeframe: str, year_start, year_end):
        """연도별 데이터 수집 (여러 번에 나누어서)"""
        all_ohlcv = []
        current_time = year_start
        
        while current_time < year_end:
            # 1000개씩 나누어서 수집 (1시간 데이터 기준 약 42일치)
            since = int(current_time.timestamp() * 1000)
            
            try:
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
                
                if not ohlcv:
                    break
                
                all_ohlcv.extend(ohlcv)
                
                # 마지막 캔들의 시간을 다음 시작점으로 설정
                last_timestamp = ohlcv[-1][0]
                current_time = pd.to_datetime(last_timestamp, unit='ms')
                
                # 연도가 넘어가면 중단
                if current_time.year > year_end.year:
                    break
                
                print(f"    📊 {current_time.strftime('%Y-%m-%d %H:%M')}까지 수집...")
                time.sleep(0.1)  # API 제한 방지
                
            except Exception as e:
                print(f"    ⚠️ 데이터 수집 오류: {e}")
                break
        
        if all_ohlcv:
            df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.set_index('timestamp')
            
            # 해당 연도 데이터만 필터링
            year_data = df[(df.index >= year_start) & (df.index <= year_end)]
            return year_data
        
        return pd.DataFrame()
    
    def get_historical_data(self, symbol: str, timeframe: str, start_date: str, end_date: str):
        """과거 데이터 수집 (1년치 꽉찬 데이터)"""
        print(f"📊 {symbol} {timeframe} 데이터 수집 중... ({start_date} ~ {end_date})")
        
        try:
            # 시작일과 종료일을 timestamp로 변환
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            
            # 연도별로 데이터 수집
            current_year = start_dt.year
            end_year = end_dt.year
            
            all_data = []
            
            while current_year <= end_year:
                year_start = max(start_dt, pd.to_datetime(f"{current_year}-01-01"))
                year_end = min(end_dt, pd.to_datetime(f"{current_year}-12-31 23:59:59"))
                
                print(f"  📅 {current_year}년 데이터 수집...")
                
                # 해당 연도의 데이터 수집 (여러 번에 나누어서)
                year_data = self._collect_year_data(symbol, timeframe, year_start, year_end)
                
                if not year_data.empty:
                    all_data.append(year_data)
                    print(f"    ✅ {current_year}년: {len(year_data)}개 캔들 수집")
                    print(f"    📅 기간: {year_data.index[0].strftime('%Y-%m-%d %H:%M')} ~ {year_data.index[-1].strftime('%Y-%m-%d %H:%M')}")
                else:
                    print(f"    ⚠️ {current_year}년: 데이터 없음")
                
                current_year += 1
                time.sleep(0.5)  # API 제한 방지
            
            if all_data:
                # 모든 데이터 합치기
                combined_df = pd.concat(all_data, ignore_index=False)
                combined_df = combined_df.sort_index()
                combined_df = combined_df.drop_duplicates()
                
                print(f"✅ {symbol} 총 {len(combined_df)}개 캔들 수집 완료")
                return combined_df
            else:
                print(f"❌ {symbol} 데이터 수집 실패")
                return None
                
        except Exception as e:
            print(f"❌ {symbol} 데이터 수집 오류: {e}")
            return None
    
    def save_data(self, df: pd.DataFrame, symbol: str, timeframe: str):
        """데이터 저장"""
        if df is None or df.empty:
            return
        
        symbol_dir = symbol.replace('/', '')
        base_dir = os.path.join(os.path.dirname(__file__), 'data', symbol_dir, timeframe)
        
        # 연도별로 파일 저장
        for year in df.index.year.unique():
            year_data = df[df.index.year == year]
            
            filename = f"{symbol_dir}_{timeframe}_{year}.csv"
            filepath = os.path.join(base_dir, filename)
            
            # 인덱스를 컬럼으로 변환하여 저장
            year_data_save = year_data.reset_index()
            year_data_save.to_csv(filepath, index=False)
            
            print(f"💾 {filename} 저장 완료: {len(year_data)}개 캔들")
            print(f"📅 기간: {year_data.index[0].strftime('%Y-%m-%d')} ~ {year_data.index[-1].strftime('%Y-%m-%d')}")
    
    def test_2023_data(self):
        """2023년 데이터만 테스트"""
        print("🚀 BTC 2023년 데이터 수집 테스트!")
        print("=" * 60)
        
        # 디렉토리 생성
        self.create_directories()
        
        # 2023년 데이터만 수집
        for symbol in self.symbols:
            print(f"\n🔄 {symbol} 처리 중...")
            
            for timeframe in self.timeframes:
                df = self.get_historical_data(symbol, timeframe, '2023-01-01', '2023-12-31')
                if df is not None:
                    self.save_data(df, symbol, timeframe)
            
            print(f"✅ {symbol} 완료!")
        
        print("\n🎉 테스트 완료!")

def main():
    """메인 함수"""
    collector = TestCryptoDataCollector()
    collector.test_2023_data()

if __name__ == "__main__":
    main()
