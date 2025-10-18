#-*-coding:utf-8 -*-
'''
장기 백테스트 스크립트
=====================

=== 사용법 ===
python long_term_backtest.py

=== 기능 ===
1. 2024년 전체 기간 백테스트
2. 분기별 성과 분석
3. 월별 성과 분석
4. 전략별 상세 성과 분석
'''

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Windows에서 이모지 출력을 위한 인코딩 설정
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

from multi_strategy_portfolio_manager import MultiStrategyPortfolioManager

def load_real_data(symbol: str = 'BTCUSDT', timeframe: str = '1h', 
                   start_date: str = '2024-01-01', end_date: str = '2024-12-31') -> pd.DataFrame:
    """실제 데이터 로드"""
    print(f"📊 실제 데이터 로드 중... ({symbol}, {timeframe})")
    print(f"📅 기간: {start_date} ~ {end_date}")
    
    # 데이터 파일 경로
    data_path = f"data/{symbol}/{timeframe}/{symbol}_{timeframe}_2024.csv"
    
    if not os.path.exists(data_path):
        print(f"❌ 데이터 파일을 찾을 수 없습니다: {data_path}")
        return None
    
    try:
        # 데이터 로드
        data = pd.read_csv(data_path)
        print(f"✅ 데이터 로드 성공: {len(data)}개 행")
        
        # 컬럼 확인
        required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            print(f"❌ 누락된 컬럼: {missing_columns}")
            return None
        
        # 데이터 전처리
        data['timestamp'] = pd.to_datetime(data['timestamp'])
        data.set_index('timestamp', inplace=True)
        
        # 날짜 필터링
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        filtered_data = data[(data.index >= start_dt) & (data.index <= end_dt)]
        
        if len(filtered_data) == 0:
            print(f"❌ 필터링된 데이터가 없습니다. 원본 데이터 기간: {data.index[0]} ~ {data.index[-1]}")
            return data  # 원본 데이터 반환
        
        print(f"📅 필터링된 데이터: {len(filtered_data)}개 행")
        print(f"💰 가격 범위: ${filtered_data['close'].min():.2f} ~ ${filtered_data['close'].max():.2f}")
        print(f"📈 기간: {filtered_data.index[0].strftime('%Y-%m-%d')} ~ {filtered_data.index[-1].strftime('%Y-%m-%d')}")
        
        return filtered_data
        
    except Exception as e:
        print(f"❌ 데이터 로드 실패: {e}")
        return None

def run_long_term_backtest():
    """장기 백테스트 실행"""
    print("🚀 장기 백테스트 시작 (2024년 전체)")
    print("=" * 60)
    
    # 2024년 전체 데이터 로드
    data = load_real_data('BTCUSDT', '1h', '2024-01-01', '2024-12-31')
    
    if data is None:
        print("❌ 데이터를 로드할 수 없습니다.")
        return
    
    # 포트폴리오 관리자 생성
    portfolio_manager = MultiStrategyPortfolioManager(initial_capital=100000)
    
    # 신호 계산
    print("\n📊 전략 신호 계산 중...")
    signals = portfolio_manager.calculate_strategy_signals(data)
    
    # 포트폴리오 성과 계산
    print("📈 포트폴리오 성과 계산 중...")
    portfolio_returns = portfolio_manager.calculate_portfolio_performance(data, signals)
    
    # 전체 성과 통계
    total_return = portfolio_returns.sum() * 100
    win_rate = (portfolio_returns > 0).mean() * 100
    volatility = portfolio_returns.std() * 100
    sharpe_ratio = portfolio_returns.mean() / portfolio_returns.std() * np.sqrt(252) if portfolio_returns.std() > 0 else 0
    
    # 최대 낙폭 계산
    cumulative_returns = (1 + portfolio_returns).cumprod()
    running_max = cumulative_returns.expanding().max()
    drawdown = (cumulative_returns - running_max) / running_max
    max_drawdown = drawdown.min() * 100
    
    print(f"\n📊 2024년 전체 성과:")
    print(f"  기간: {data.index[0].strftime('%Y-%m-%d')} ~ {data.index[-1].strftime('%Y-%m-%d')}")
    print(f"  총 수익률: {total_return:6.2f}%")
    print(f"  승률:      {win_rate:6.1f}%")
    print(f"  변동성:    {volatility:6.2f}%")
    print(f"  샤프비율:  {sharpe_ratio:6.2f}")
    print(f"  최대낙폭:  {max_drawdown:6.2f}%")
    
    # 전략별 성과
    print(f"\n📋 전략별 성과:")
    strategy_performance = {}
    for name, strategy in portfolio_manager.strategies.items():
        if name in signals:
            performance = strategy.calculate_performance(data, signals[name])
            strategy_performance[name] = performance
            print(f"  {strategy.name:<15}: 수익률 {performance['total_return']:6.2f}%, 승률 {performance['win_rate']:5.1f}%, 샤프 {performance['sharpe_ratio']:5.2f}")
    
    # 최고 성과 전략 찾기
    if strategy_performance:
        best_return = max(strategy_performance.keys(), key=lambda x: strategy_performance[x]['total_return'])
        best_sharpe = max(strategy_performance.keys(), key=lambda x: strategy_performance[x]['sharpe_ratio'])
        best_winrate = max(strategy_performance.keys(), key=lambda x: strategy_performance[x]['win_rate'])
        
        print(f"\n🏆 최고 성과 전략:")
        print(f"  최고 수익률: {best_return} ({strategy_performance[best_return]['total_return']:.2f}%)")
        print(f"  최고 샤프비율: {best_sharpe} ({strategy_performance[best_sharpe]['sharpe_ratio']:.2f})")
        print(f"  최고 승률: {best_winrate} ({strategy_performance[best_winrate]['win_rate']:.1f}%)")
    
    # 분기별 성과 분석
    print(f"\n📅 분기별 성과 분석:")
    quarters = {
        'Q1': ('2024-01-01', '2024-03-31'),
        'Q2': ('2024-04-01', '2024-06-30'),
        'Q3': ('2024-07-01', '2024-09-30'),
        'Q4': ('2024-10-01', '2024-12-31')
    }
    
    for quarter, (start, end) in quarters.items():
        quarter_data = data[(data.index >= start) & (data.index <= end)]
        if len(quarter_data) > 0:
            quarter_returns = portfolio_returns[(portfolio_returns.index >= start) & (portfolio_returns.index <= end)]
            if len(quarter_returns) > 0:
                quarter_return = quarter_returns.sum() * 100
                quarter_winrate = (quarter_returns > 0).mean() * 100
                print(f"  {quarter}: 수익률 {quarter_return:6.2f}%, 승률 {quarter_winrate:5.1f}%")
    
    # 월별 성과 분석 (상위 5개월)
    print(f"\n📅 월별 성과 분석 (상위 5개월):")
    monthly_returns = []
    for month in range(1, 13):
        month_data = data[data.index.month == month]
        if len(month_data) > 0:
            month_returns = portfolio_returns[portfolio_returns.index.month == month]
            if len(month_returns) > 0:
                month_return = month_returns.sum() * 100
                monthly_returns.append((month, month_return))
    
    # 수익률 기준으로 정렬
    monthly_returns.sort(key=lambda x: x[1], reverse=True)
    
    for i, (month, month_return) in enumerate(monthly_returns[:5]):
        month_name = f"{month}월"
        print(f"  {month_name}: {month_return:6.2f}%")
    
    print("\n✅ 장기 백테스트 완료!")

def run_quarterly_backtest():
    """분기별 백테스트 실행"""
    print("\n📊 분기별 상세 백테스트")
    print("=" * 60)
    
    quarters = {
        'Q1 (1-3월)': ('2024-01-01', '2024-03-31'),
        'Q2 (4-6월)': ('2024-04-01', '2024-06-30'),
        'Q3 (7-9월)': ('2024-07-01', '2024-09-30'),
        'Q4 (10-12월)': ('2024-10-01', '2024-12-31')
    }
    
    for quarter_name, (start_date, end_date) in quarters.items():
        print(f"\n🔍 {quarter_name} 분석:")
        print("-" * 40)
        
        # 분기 데이터 로드
        data = load_real_data('BTCUSDT', '1h', start_date, end_date)
        
        if data is None or len(data) < 50:
            print(f"❌ {quarter_name} 데이터 부족")
            continue
        
        # 포트폴리오 관리자 생성
        portfolio_manager = MultiStrategyPortfolioManager(initial_capital=100000)
        
        # 신호 계산
        signals = portfolio_manager.calculate_strategy_signals(data)
        
        # 포트폴리오 성과 계산
        portfolio_returns = portfolio_manager.calculate_portfolio_performance(data, signals)
        
        # 성과 통계
        total_return = portfolio_returns.sum() * 100
        win_rate = (portfolio_returns > 0).mean() * 100
        volatility = portfolio_returns.std() * 100
        sharpe_ratio = portfolio_returns.mean() / portfolio_returns.std() * np.sqrt(252) if portfolio_returns.std() > 0 else 0
        
        print(f"  총 수익률: {total_return:6.2f}%")
        print(f"  승률:      {win_rate:6.1f}%")
        print(f"  변동성:    {volatility:6.2f}%")
        print(f"  샤프비율:  {sharpe_ratio:6.2f}")
        
        # 최고 성과 전략
        best_strategy = None
        best_return = -999
        for name, strategy in portfolio_manager.strategies.items():
            if name in signals:
                performance = strategy.calculate_performance(data, signals[name])
                if performance['total_return'] > best_return:
                    best_return = performance['total_return']
                    best_strategy = strategy.name
        
        if best_strategy:
            print(f"  최고 전략: {best_strategy} ({best_return:.2f}%)")

def main():
    """메인 함수"""
    print("🚀 장기 백테스트 시스템")
    print("=" * 60)
    
    try:
        # 1. 전체 기간 백테스트
        run_long_term_backtest()
        
        # 2. 분기별 상세 분석
        run_quarterly_backtest()
        
        print(f"\n🎉 모든 분석이 완료되었습니다!")
        
    except Exception as e:
        print(f"\n❌ 오류가 발생했습니다: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
