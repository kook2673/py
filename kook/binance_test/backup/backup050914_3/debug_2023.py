#-*-coding:utf-8 -*-
'''
2023년 디버깅 테스트
'''

import pandas as pd
import os

def test_2023_data():
    """2023년 데이터 테스트"""
    print("📊 2023년 데이터 테스트")
    
    data_path = "data/BTCUSDT/1h/BTCUSDT_1h_2023.csv"
    
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
        
        # 2023년 전체 데이터
        full_data = data[(data.index >= '2023-01-01') & (data.index <= '2023-12-31')]
        print(f"📅 2023년 데이터: {len(full_data)}개 행")
        print(f"💰 가격 범위: ${full_data['close'].min():.2f} ~ ${full_data['close'].max():.2f}")
        
        return full_data
        
    except Exception as e:
        print(f"❌ 오류: {e}")
        return None

def test_simple_strategy_2023(data):
    """2023년 간단한 전략 테스트"""
    print("\n🧪 2023년 간단한 전략 테스트")
    
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
        
        print(f"📈 2023년 성과:")
        print(f"  총 수익률: {total_return:.2f}%")
        print(f"  승률: {win_rate:.1f}%")
        print(f"  거래 수: {len(signal_returns)}")
        
        # 분기별 성과
        print(f"\n📅 분기별 성과:")
        quarters = {
            'Q1 (1-3월)': (1, 3),
            'Q2 (4-6월)': (4, 6),
            'Q3 (7-9월)': (7, 9),
            'Q4 (10-12월)': (10, 12)
        }
        
        for quarter_name, (start_month, end_month) in quarters.items():
            quarter_returns = signal_returns[(signal_returns.index.month >= start_month) & (signal_returns.index.month <= end_month)]
            if len(quarter_returns) > 0:
                quarter_return = quarter_returns.sum() * 100
                quarter_winrate = (quarter_returns > 0).mean() * 100
                print(f"  {quarter_name}: 수익률 {quarter_return:6.2f}%, 승률 {quarter_winrate:5.1f}%")
        
        # 월별 성과 (상위 5개월)
        print(f"\n📅 월별 성과 (상위 5개월):")
        monthly_returns = []
        for month in range(1, 13):
            month_returns = signal_returns[signal_returns.index.month == month]
            if len(month_returns) > 0:
                month_return = month_returns.sum() * 100
                monthly_returns.append((month, month_return))
        
        monthly_returns.sort(key=lambda x: x[1], reverse=True)
        for i, (month, month_return) in enumerate(monthly_returns[:5]):
            print(f"  {i+1}. {month:2d}월: {month_return:6.2f}%")

if __name__ == "__main__":
    print("🚀 2023년 디버깅 테스트 시작")
    print("=" * 50)
    
    # 데이터 로드
    data = test_2023_data()
    
    # 간단한 전략 테스트
    test_simple_strategy_2023(data)
    
    print("\n✅ 테스트 완료!")
