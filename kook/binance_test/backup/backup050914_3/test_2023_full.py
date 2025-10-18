#-*-coding:utf-8 -*-
'''
2023년 전체 기간 백테스트 (간단 버전)
'''

import pandas as pd
import numpy as np
import os

def load_2023_data():
    """2023년 데이터 로드"""
    print("📊 2023년 데이터 로드 중...")
    
    data_path = "kook/binance_test/data/BTCUSDT/1h/BTCUSDT_1h_2023.csv"
    
    if not os.path.exists(data_path):
        print(f"❌ 파일 없음: {data_path}")
        return None
    
    try:
        data = pd.read_csv(data_path)
        print(f"✅ 데이터 로드 성공: {len(data)}개 행")
        
        # 데이터 전처리
        data['timestamp'] = pd.to_datetime(data['timestamp'])
        data.set_index('timestamp', inplace=True)
        
        print(f"📅 전체 기간: {data.index[0].strftime('%Y-%m-%d')} ~ {data.index[-1].strftime('%Y-%m-%d')}")
        print(f"💰 가격 범위: ${data['close'].min():.2f} ~ ${data['close'].max():.2f}")
        
        return data
        
    except Exception as e:
        print(f"❌ 오류: {e}")
        return None

def test_multiple_strategies(data):
    """여러 전략 테스트"""
    print("\n🧪 여러 전략 테스트")
    print("-" * 50)
    
    if data is None or len(data) < 100:
        print("❌ 데이터 부족")
        return
    
    strategies = {
        'MA_5_20': (5, 20),
        'MA_10_30': (10, 30),
        'MA_20_50': (20, 50),
        'MA_50_100': (50, 100),
        'MA_100_200': (100, 200)
    }
    
    results = {}
    
    for name, (short, long) in strategies.items():
        if len(data) < long:
            print(f"⚠️ {name}: 데이터 부족 (필요: {long}, 실제: {len(data)})")
            continue
            
        # 이동평균 계산
        short_ma = data['close'].rolling(window=short).mean()
        long_ma = data['close'].rolling(window=long).mean()
        
        # 신호 생성
        signals = pd.Series(0, index=data.index)
        signals[short_ma > long_ma] = 1
        signals[short_ma < long_ma] = -1
        
        # 성과 계산
        returns = data['close'].pct_change()
        signal_returns = returns * signals.shift(1)
        signal_returns = signal_returns.dropna()
        
        if len(signal_returns) > 0:
            total_return = signal_returns.sum() * 100
            win_rate = (signal_returns > 0).mean() * 100
            volatility = signal_returns.std() * 100
            sharpe_ratio = signal_returns.mean() / signal_returns.std() * np.sqrt(252) if signal_returns.std() > 0 else 0
            
            # 최대 낙폭 계산
            cumulative_returns = (1 + signal_returns).cumprod()
            running_max = cumulative_returns.expanding().max()
            drawdown = (cumulative_returns - running_max) / running_max
            max_drawdown = drawdown.min() * 100
            
            results[name] = {
                'total_return': total_return,
                'win_rate': win_rate,
                'volatility': volatility,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown
            }
            
            print(f"✅ {name:<10}: 수익률 {total_return:6.2f}%, 승률 {win_rate:5.1f}%, 샤프 {sharpe_ratio:5.2f}, MDD {max_drawdown:5.2f}%")
        else:
            print(f"❌ {name}: 유효한 신호 없음")
    
    # 최고 성과 전략 찾기
    if results:
        best_return = max(results.keys(), key=lambda x: results[x]['total_return'])
        best_sharpe = max(results.keys(), key=lambda x: results[x]['sharpe_ratio'])
        best_winrate = max(results.keys(), key=lambda x: results[x]['win_rate'])
        
        print(f"\n🏆 최고 성과 전략:")
        print(f"  최고 수익률: {best_return} ({results[best_return]['total_return']:.2f}%)")
        print(f"  최고 샤프비율: {best_sharpe} ({results[best_sharpe]['sharpe_ratio']:.2f})")
        print(f"  최고 승률: {best_winrate} ({results[best_winrate]['win_rate']:.1f}%)")
    
    return results

def analyze_monthly_performance(data, results):
    """월별 성과 분석"""
    print(f"\n📅 월별 성과 분석:")
    print("-" * 50)
    
    # 최고 성과 전략으로 월별 분석
    if not results:
        return
        
    best_strategy = max(results.keys(), key=lambda x: results[x]['total_return'])
    print(f"📊 {best_strategy} 전략 월별 성과:")
    
    # 해당 전략의 파라미터
    short, long = best_strategy.split('_')[1], best_strategy.split('_')[2]
    short, long = int(short), int(long)
    
    # 이동평균 계산
    short_ma = data['close'].rolling(window=short).mean()
    long_ma = data['close'].rolling(window=long).mean()
    
    # 신호 생성
    signals = pd.Series(0, index=data.index)
    signals[short_ma > long_ma] = 1
    signals[short_ma < long_ma] = -1
    
    # 수익률 계산
    returns = data['close'].pct_change()
    signal_returns = returns * signals.shift(1)
    signal_returns = signal_returns.dropna()
    
    monthly_returns = []
    for month in range(1, 13):
        month_returns = signal_returns[signal_returns.index.month == month]
        if len(month_returns) > 0:
            month_return = month_returns.sum() * 100
            month_winrate = (month_returns > 0).mean() * 100
            monthly_returns.append((month, month_return, month_winrate))
            print(f"  {month:2d}월: 수익률 {month_return:6.2f}%, 승률 {month_winrate:5.1f}%")
    
    # 월별 성과 순위
    monthly_returns.sort(key=lambda x: x[1], reverse=True)
    print(f"\n🏆 월별 성과 순위 (상위 5개월):")
    for i, (month, month_return, month_winrate) in enumerate(monthly_returns[:5]):
        print(f"  {i+1}. {month:2d}월: {month_return:6.2f}% (승률: {month_winrate:.1f}%)")

def main():
    """메인 함수"""
    print("🚀 2023년 전체 기간 백테스트")
    print("=" * 60)
    
    # 데이터 로드
    data = load_2023_data()
    
    if data is None:
        print("❌ 데이터 로드 실패")
        return
    
    # 여러 전략 테스트
    results = test_multiple_strategies(data)
    
    # 월별 성과 분석
    analyze_monthly_performance(data, results)
    
    print(f"\n✅ 백테스트 완료!")
    print(f"📊 총 {len(data)}개 캔들 데이터로 분석 완료")

if __name__ == "__main__":
    main()
