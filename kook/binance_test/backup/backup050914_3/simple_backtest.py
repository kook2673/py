#-*-coding:utf-8 -*-
'''
간단한 백테스트 테스트
'''

import pandas as pd
import numpy as np
import os
from datetime import datetime

def test_data_loading():
    """데이터 로딩 테스트"""
    print("📊 데이터 로딩 테스트")
    print("-" * 50)
    
    # BTCUSDT 1시간 데이터 로드
    data_path = "data/BTCUSDT/1h/BTCUSDT_1h_2024.csv"
    
    if not os.path.exists(data_path):
        print(f"❌ 데이터 파일을 찾을 수 없습니다: {data_path}")
        return None
    
    try:
        data = pd.read_csv(data_path)
        print(f"✅ 데이터 로드 성공: {len(data)}개 행")
        print(f"📅 기간: {data['timestamp'].iloc[0]} ~ {data['timestamp'].iloc[-1]}")
        print(f"📊 컬럼: {list(data.columns)}")
        
        # 필요한 컬럼 확인
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            print(f"❌ 누락된 컬럼: {missing_columns}")
            return None
        
        # 데이터 전처리
        data['timestamp'] = pd.to_datetime(data['timestamp'])
        data.set_index('timestamp', inplace=True)
        
        # 2024년 1월-6월 데이터 필터링
        start_date = '2024-01-01'
        end_date = '2024-06-30'
        filtered_data = data[(data.index >= start_date) & (data.index <= end_date)]
        
        print(f"📅 필터링된 데이터: {len(filtered_data)}개 행")
        print(f"💰 가격 범위: ${filtered_data['close'].min():.2f} ~ ${filtered_data['close'].max():.2f}")
        
        return filtered_data
        
    except Exception as e:
        print(f"❌ 데이터 로드 실패: {e}")
        return None

def test_simple_strategy(data):
    """간단한 전략 테스트"""
    print("\n🧪 간단한 전략 테스트")
    print("-" * 50)
    
    if data is None or len(data) < 50:
        print("❌ 충분한 데이터가 없습니다.")
        return
    
    # 간단한 이동평균 전략
    short_ma = data['close'].rolling(window=10).mean()
    long_ma = data['close'].rolling(window=30).mean()
    
    # 매매 신호 생성
    signals = pd.DataFrame(index=data.index)
    signals['signal'] = 0
    signals.loc[short_ma > long_ma, 'signal'] = 1  # 매수
    signals.loc[short_ma < long_ma, 'signal'] = -1  # 매도
    
    # 신호 통계
    total_signals = len(signals)
    buy_signals = (signals['signal'] == 1).sum()
    sell_signals = (signals['signal'] == -1).sum()
    hold_signals = (signals['signal'] == 0).sum()
    
    print(f"📊 신호 통계:")
    print(f"  총 신호: {total_signals}")
    print(f"  매수 신호: {buy_signals} ({buy_signals/total_signals*100:.1f}%)")
    print(f"  매도 신호: {sell_signals} ({sell_signals/total_signals*100:.1f}%)")
    print(f"  보유 신호: {hold_signals} ({hold_signals/total_signals*100:.1f}%)")
    
    # 수익률 계산
    returns = data['close'].pct_change()
    signal_returns = returns * signals['signal'].shift(1)
    signal_returns = signal_returns.dropna()
    
    if len(signal_returns) > 0:
        total_return = signal_returns.sum() * 100
        win_rate = (signal_returns > 0).mean() * 100
        avg_return = signal_returns.mean() * 100
        volatility = signal_returns.std() * 100
        
        print(f"\n📈 성과 분석:")
        print(f"  총 수익률: {total_return:.2f}%")
        print(f"  승률: {win_rate:.1f}%")
        print(f"  평균 수익률: {avg_return:.4f}%")
        print(f"  변동성: {volatility:.2f}%")
        
        # 최대 낙폭 계산
        cumulative_returns = (1 + signal_returns).cumprod()
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / running_max
        max_drawdown = drawdown.min() * 100
        
        print(f"  최대 낙폭: {max_drawdown:.2f}%")
        
        # 샤프 비율
        if volatility > 0:
            sharpe_ratio = avg_return / volatility * np.sqrt(252)
            print(f"  샤프 비율: {sharpe_ratio:.2f}")
        
        return {
            'total_return': total_return,
            'win_rate': win_rate,
            'max_drawdown': max_drawdown,
            'volatility': volatility,
            'sharpe_ratio': avg_return / volatility * np.sqrt(252) if volatility > 0 else 0
        }
    else:
        print("❌ 유효한 신호가 없습니다.")
        return None

def test_multiple_strategies(data):
    """여러 전략 테스트"""
    print("\n🎯 여러 전략 테스트")
    print("-" * 50)
    
    if data is None or len(data) < 50:
        print("❌ 충분한 데이터가 없습니다.")
        return
    
    strategies = {
        'MA_5_20': (5, 20),
        'MA_10_30': (10, 30),
        'MA_20_50': (20, 50),
        'MA_50_100': (50, 100)
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
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        signals.loc[short_ma > long_ma, 'signal'] = 1
        signals.loc[short_ma < long_ma, 'signal'] = -1
        
        # 성과 계산
        returns = data['close'].pct_change()
        signal_returns = returns * signals['signal'].shift(1)
        signal_returns = signal_returns.dropna()
        
        if len(signal_returns) > 0:
            total_return = signal_returns.sum() * 100
            win_rate = (signal_returns > 0).mean() * 100
            volatility = signal_returns.std() * 100
            sharpe_ratio = signal_returns.mean() / signal_returns.std() * np.sqrt(252) if signal_returns.std() > 0 else 0
            
            results[name] = {
                'total_return': total_return,
                'win_rate': win_rate,
                'volatility': volatility,
                'sharpe_ratio': sharpe_ratio
            }
            
            print(f"✅ {name:<10}: 수익률 {total_return:6.2f}%, 승률 {win_rate:5.1f}%, 샤프 {sharpe_ratio:5.2f}")
        else:
            print(f"❌ {name}: 유효한 신호 없음")
    
    # 최고 성과 전략 찾기
    if results:
        best_return = max(results.keys(), key=lambda x: results[x]['total_return'])
        best_sharpe = max(results.keys(), key=lambda x: results[x]['sharpe_ratio'])
        
        print(f"\n🏆 최고 수익률: {best_return} ({results[best_return]['total_return']:.2f}%)")
        print(f"📊 최고 샤프비율: {best_sharpe} ({results[best_sharpe]['sharpe_ratio']:.2f})")
    
    return results

def main():
    """메인 함수"""
    print("🚀 간단한 백테스트 테스트 시작")
    print("=" * 60)
    
    # 1. 데이터 로딩 테스트
    data = test_data_loading()
    
    if data is not None:
        # 2. 간단한 전략 테스트
        simple_result = test_simple_strategy(data)
        
        # 3. 여러 전략 테스트
        multi_results = test_multiple_strategies(data)
        
        print(f"\n✅ 테스트 완료!")
        print(f"📊 데이터 기간: {data.index[0].strftime('%Y-%m-%d')} ~ {data.index[-1].strftime('%Y-%m-%d')}")
        print(f"📈 총 {len(data)}개 캔들 데이터로 테스트")

if __name__ == "__main__":
    main()
