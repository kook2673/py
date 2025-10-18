#-*-coding:utf-8 -*-
'''
빠른 테스트 스크립트
'''

import pandas as pd
import os

def test_data_loading():
    """데이터 로딩 테스트"""
    print("📊 데이터 로딩 테스트")
    
    data_path = "data/BTCUSDT/1h/BTCUSDT_1h_2024.csv"
    
    if not os.path.exists(data_path):
        print(f"❌ 파일 없음: {data_path}")
        return None
    
    try:
        data = pd.read_csv(data_path)
        print(f"✅ 데이터 로드 성공: {len(data)}개 행")
        print(f"📅 기간: {data['timestamp'].iloc[0]} ~ {data['timestamp'].iloc[-1]}")
        
        # 데이터 전처리
        data['timestamp'] = pd.to_datetime(data['timestamp'])
        data.set_index('timestamp', inplace=True)
        
        # 2024년 전체 데이터
        full_data = data[(data.index >= '2024-01-01') & (data.index <= '2024-12-31')]
        print(f"📅 2024년 데이터: {len(full_data)}개 행")
        
        return full_data
        
    except Exception as e:
        print(f"❌ 오류: {e}")
        return None

def test_simple_strategy(data):
    """간단한 전략 테스트"""
    print("\n🧪 간단한 전략 테스트")
    
    if data is None or len(data) < 100:
        print("❌ 데이터 부족")
        return
    
    # 간단한 이동평균 전략
    short_ma = data['close'].rolling(window=10).mean()
    long_ma = data['close'].rolling(window=30).mean()
    
    # 매매 신호
    signals = pd.Series(0, index=data.index)
    signals[short_ma > long_ma] = 1
    signals[short_ma < long_ma] = -1
    
    # 수익률 계산
    returns = data['close'].pct_change()
    signal_returns = returns * signals.shift(1)
    signal_returns = signal_returns.dropna()
    
    if len(signal_returns) > 0:
        total_return = signal_returns.sum() * 100
        win_rate = (signal_returns > 0).mean() * 100
        
        print(f"📈 성과:")
        print(f"  총 수익률: {total_return:.2f}%")
        print(f"  승률: {win_rate:.1f}%")
        print(f"  거래 수: {len(signal_returns)}")
        
        # 월별 성과
        print(f"\n📅 월별 성과:")
        for month in range(1, 13):
            month_returns = signal_returns[signal_returns.index.month == month]
            if len(month_returns) > 0:
                month_return = month_returns.sum() * 100
                print(f"  {month}월: {month_return:6.2f}%")

if __name__ == "__main__":
    print("🚀 빠른 테스트 시작")
    print("=" * 40)
    
    # 데이터 로드
    data = test_data_loading()
    
    # 간단한 전략 테스트
    test_simple_strategy(data)
    
    print("\n✅ 테스트 완료!")
