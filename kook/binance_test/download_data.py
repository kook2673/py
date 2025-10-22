"""
바이낸스 1분봉 데이터 다운로드 스크립트
- 비트코인, 이더리움, 도지, 솔라나, XRP
- 2024년, 2025년 1분봉 데이터
"""

import ccxt
import pandas as pd
import os
import time
from datetime import datetime, timedelta
import json

def download_coin_data(symbol, start_date, end_date, timeframe='1m'):
    """특정 코인의 데이터 다운로드"""
    print(f"\n{symbol} {timeframe} 데이터 다운로드 시작...")
    print(f"기간: {start_date} ~ {end_date}")
    
    # 바이낸스 객체 생성 (공개 API만 사용)
    exchange = ccxt.binance({
        'apiKey': '',
        'secret': '',
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',
        }
    })
    
    # 데이터 저장 디렉토리 생성
    data_dir = f"data/{symbol}/{timeframe}"
    os.makedirs(data_dir, exist_ok=True)
    
    # 시작일과 종료일을 timestamp로 변환
    start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
    end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)
    
    all_data = []
    current_ts = start_ts
    
    # 1000개씩 나누어서 다운로드 (바이낸스 제한)
    while current_ts < end_ts:
        try:
            print(f"다운로드 중... {datetime.fromtimestamp(current_ts/1000).strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 1000개 캔들 다운로드 (약 16시간 40분)
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, current_ts, 1000)
            
            if not ohlcv:
                print("더 이상 데이터가 없습니다.")
                break
                
            all_data.extend(ohlcv)
            
            # 다음 배치를 위한 타임스탬프 업데이트
            current_ts = ohlcv[-1][0] + 60000  # 1분 추가
            
            # API 제한 방지
            time.sleep(0.1)
            
        except Exception as e:
            print(f"오류 발생: {e}")
            time.sleep(1)
            continue
    
    if not all_data:
        print(f"{symbol} 데이터를 다운로드할 수 없습니다.")
        return None
    
    # DataFrame으로 변환
    df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.set_index('timestamp')
    
    # 중복 제거 및 정렬
    df = df.drop_duplicates().sort_index()
    
    # 연도별로 분할하여 저장
    for year in df.index.year.unique():
        year_data = df[df.index.year == year]
        
        if len(year_data) > 0:
            filename = f"{symbol}_{timeframe}_{year}.csv"
            filepath = os.path.join(data_dir, filename)
            
            # CSV로 저장
            year_data.to_csv(filepath)
            
            print(f"{year}년 데이터 저장 완료: {len(year_data):,}개 캔들")
            print(f"파일: {filepath}")
            print(f"기간: {year_data.index[0]} ~ {year_data.index[-1]}")
    
    # 메타데이터 저장
    meta = {
        'symbol': symbol,
        'timeframe': timeframe,
        'start_date': start_date,
        'end_date': end_date,
        'total_candles': len(df),
        'download_time': datetime.now().isoformat(),
        'data_range': {
            'start': df.index[0].isoformat(),
            'end': df.index[-1].isoformat()
        }
    }
    
    meta_file = os.path.join(data_dir, f"{symbol}_{timeframe}_meta.json")
    with open(meta_file, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    
    print(f"{symbol} 다운로드 완료! 총 {len(df):,}개 캔들")
    return df

def main():
    """메인 실행 함수"""
    print("=" * 80)
    print("바이낸스 1분봉 데이터 다운로드")
    print("=" * 80)
    
    # 다운로드할 코인 목록
    coins = ['BTCUSDT', 'ETHUSDT', 'DOGEUSDT', 'SOLUSDT', 'XRPUSDT']
    
    # 다운로드 기간
    start_date = '2024-01-01'
    end_date = datetime.now().strftime('%Y-%m-%d')  # 오늘까지
    
    print(f"다운로드 기간: {start_date} ~ {end_date}")
    print(f"다운로드 코인: {', '.join(coins)}")
    print("=" * 80)
    
    # 각 코인별로 데이터 다운로드
    for coin in coins:
        try:
            download_coin_data(coin, start_date, end_date, '1m')
            print(f"\n{coin} 다운로드 완료!")
            
        except Exception as e:
            print(f"\n{coin} 다운로드 실패: {e}")
            continue
        
        # 코인 간 대기 시간
        print("다음 코인 다운로드를 위해 5초 대기...")
        time.sleep(5)
    
    print("\n" + "=" * 80)
    print("모든 데이터 다운로드 완료!")
    print("=" * 80)

if __name__ == "__main__":
    main()
