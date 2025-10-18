#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Advanced MA ML Bot 테스트 스크립트
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime

# 현재 디렉토리를 파이썬 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from advanced_ma_ml_bot import AdvancedMAMLBot

def load_binance_data(filepath: str) -> pd.DataFrame:
    """바이낸스 데이터 로드"""
    try:
        print(f"데이터 로딩 중: {filepath}")
        df = pd.read_csv(filepath)
        
        # 컬럼명 확인
        print(f"컬럼: {df.columns.tolist()}")
        
        # 타임스탬프 처리
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
        elif 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
        
        # 필수 컬럼 확인
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in required_columns:
            if col not in df.columns:
                print(f"경고: '{col}' 컬럼이 없습니다.")
                return None
        
        print(f"데이터 로드 완료: {len(df)}개 행")
        print(f"기간: {df.index[0]} ~ {df.index[-1]}")
        
        return df
        
    except Exception as e:
        print(f"데이터 로드 실패: {e}")
        import traceback
        traceback.print_exc()
        return None

def simple_backtest():
    """간단한 백테스트"""
    print("\n" + "="*60)
    print("Advanced MA ML Bot - 간단한 백테스트")
    print("="*60 + "\n")
    
    # 봇 생성
    bot = AdvancedMAMLBot(initial_balance=10000, leverage=20)
    
    # 간단한 파라미터 설정
    bot.params['ma_short'] = 5
    bot.params['ma_long'] = 20
    bot.params['stop_loss_pct'] = 0.01
    bot.params['take_profit_pct'] = 0.03
    
    # 데이터 로드 시도 (여러 경로 시도)
    data_paths = [
        r'c:\work\GitHub\py\kook\binance_test\data\BTCUSDT_1h_2024-01.csv',
        r'c:\work\GitHub\py\kook\binance_test\data\BTCUSDT_1h.csv',
        r'c:\work\GitHub\py\kook\binance\data\BTC_USDT\1h\2024-01.csv',
        r'c:\work\GitHub\py\kook\binance\data\BTC_USDT\1m\2024-01.csv',
    ]
    
    df = None
    for path in data_paths:
        if os.path.exists(path):
            print(f"파일 발견: {path}")
            df = load_binance_data(path)
            if df is not None:
                break
    
    if df is None:
        print("\n경고: 데이터 파일을 찾을 수 없습니다.")
        print("샘플 데이터를 생성합니다...\n")
        df = generate_sample_data()
    
    # 백테스트 실행
    print("\n백테스트 실행 중...\n")
    try:
        results = bot.run_backtest(
            df, 
            start_date=df.index[0].strftime('%Y-%m-%d'),
            end_date=df.index[-1].strftime('%Y-%m-%d')
        )
        
        if 'error' in results:
            print(f"백테스트 오류: {results['error']}")
            return
        
        # 결과 출력
        print("\n" + "="*60)
        print("백테스트 결과")
        print("="*60)
        print(f"초기 자본: {results['initial_balance']:,.0f} USDT")
        print(f"최종 자본: {results['final_balance']:,.0f} USDT")
        print(f"총 수익: {results['total_pnl']:,.2f} USDT")
        print(f"총 수익률: {results['total_return']:.2f}%")
        print(f"최대 낙폭: {results['max_drawdown']:.2f}%")
        print(f"샤프 비율: {results['sharpe_ratio']:.2f}")
        print(f"\n총 거래 횟수: {results['total_trades']}회")
        print(f"승리 거래: {results['winning_trades']}회")
        print(f"손실 거래: {results['losing_trades']}회")
        print(f"승률: {results['win_rate']:.2f}%")
        print(f"평균 수익: {results['avg_win']:.2f} USDT")
        print(f"평균 손실: {results['avg_loss']:.2f} USDT")
        print(f"수익 팩터: {results['profit_factor']:.2f}")
        print("="*60)
        
        # 거래 내역 일부 출력
        if results['trades']:
            print(f"\n최근 5개 거래:")
            for trade in results['trades'][-5:]:
                print(f"  {trade['side']:4s} | 진입: {trade['entry_price']:.2f} | "
                      f"청산: {trade['exit_price']:.2f} | "
                      f"손익: {trade['pnl']:+.2f} USDT | 사유: {trade['reason']}")
        
    except Exception as e:
        print(f"백테스트 실행 오류: {e}")
        import traceback
        traceback.print_exc()

def generate_sample_data(days: int = 90) -> pd.DataFrame:
    """샘플 데이터 생성 (실제 데이터가 없을 때)"""
    print("샘플 데이터 생성 중...")
    
    # 1시간봉 데이터 생성
    timestamps = pd.date_range(start='2024-01-01', periods=days*24, freq='1H')
    
    # 랜덤 워크로 가격 생성
    np.random.seed(42)
    price = 40000
    prices = []
    
    for _ in range(len(timestamps)):
        change = np.random.randn() * 500  # 변동성
        price = max(price + change, 30000)  # 최소 가격 30000
        prices.append(price)
    
    # OHLCV 데이터 생성
    data = []
    for i, ts in enumerate(timestamps):
        p = prices[i]
        high = p + abs(np.random.randn() * 200)
        low = p - abs(np.random.randn() * 200)
        open_p = prices[i-1] if i > 0 else p
        close_p = p
        volume = np.random.uniform(100, 1000)
        
        data.append({
            'open': open_p,
            'high': max(high, open_p, close_p),
            'low': min(low, open_p, close_p),
            'close': close_p,
            'volume': volume
        })
    
    df = pd.DataFrame(data, index=timestamps)
    print(f"샘플 데이터 생성 완료: {len(df)}개 행")
    
    return df

def sliding_window_test():
    """슬라이딩 윈도우 백테스트 테스트"""
    print("\n" + "="*60)
    print("Advanced MA ML Bot - 슬라이딩 윈도우 백테스트")
    print("="*60 + "\n")
    
    # 봇 생성
    bot = AdvancedMAMLBot(initial_balance=10000, leverage=20)
    
    # 샘플 데이터 생성
    df = generate_sample_data(days=90)
    
    # 슬라이딩 윈도우 백테스트
    print("\n슬라이딩 윈도우 백테스트 실행 중...\n")
    try:
        results = bot.run_sliding_window_backtest(
            df,
            train_days=15,
            test_days=15,
            start_date='2024-01-01',
            end_date='2024-03-31'
        )
        
        if 'error' in results:
            print(f"백테스트 오류: {results['error']}")
            return
        
        # 결과 출력
        print("\n" + "="*60)
        print("슬라이딩 윈도우 백테스트 결과")
        print("="*60)
        print(f"초기 자본: {results['initial_balance']:,.0f} USDT")
        print(f"최종 자본: {results['final_balance']:,.0f} USDT")
        print(f"총 수익: {results['total_pnl']:,.2f} USDT")
        print(f"총 수익률: {results['total_return']:.2f}%")
        print(f"최대 낙폭: {results['max_drawdown']:.2f}%")
        print(f"샤프 비율: {results['sharpe_ratio']:.2f}")
        print(f"\n총 거래 횟수: {results['total_trades']}회")
        print(f"승률: {results['win_rate']:.2f}%")
        print(f"수익 팩터: {results['profit_factor']:.2f}")
        print(f"테스트 기간 수: {results['num_periods']}개")
        print("="*60)
        
        # 기간별 결과
        print(f"\n기간별 결과:")
        for pr in results['period_results']:
            print(f"  기간 {pr['period']}: {pr['test_start']} ~ {pr['test_end']} | "
                  f"수익률: {pr['total_return']:+.2f}% | "
                  f"거래: {pr['total_trades']}회")
        
    except Exception as e:
        print(f"슬라이딩 윈도우 백테스트 실행 오류: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 1. 간단한 백테스트
    simple_backtest()
    
    # 2. 슬라이딩 윈도우 백테스트 (선택사항)
    # sliding_window_test()

