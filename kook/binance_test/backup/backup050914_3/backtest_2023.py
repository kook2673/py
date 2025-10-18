#-*-coding:utf-8 -*-
'''
2023년 전체 기간 백테스트
========================

=== 사용법 ===
python backtest_2023.py

=== 기능 ===
1. 2023년 전체 기간 다중 전략 백테스트
2. 분기별 성과 분석
3. 월별 성과 분석
4. 전략별 상세 성과 분석
'''

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime

# Windows에서 이모지 출력을 위한 인코딩 설정
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

from multi_strategy_portfolio_manager import MultiStrategyPortfolioManager

def load_2023_data():
    """2023년 데이터 로드"""
    print("📊 2023년 데이터 로드 중...")
    
    data_path = "data/BTCUSDT/1h/BTCUSDT_1h_2023.csv"
    
    if not os.path.exists(data_path):
        print(f"❌ 데이터 파일을 찾을 수 없습니다: {data_path}")
        return None
    
    try:
        # 데이터 로드
        data = pd.read_csv(data_path)
        print(f"✅ 데이터 로드 성공: {len(data)}개 행")
        
        # 데이터 전처리
        data['timestamp'] = pd.to_datetime(data['timestamp'])
        data.set_index('timestamp', inplace=True)
        
        # 2023년 전체 데이터
        full_data = data[(data.index >= '2023-01-01') & (data.index <= '2023-12-31')]
        print(f"📅 2023년 데이터: {len(full_data)}개 행")
        print(f"💰 가격 범위: ${full_data['close'].min():.2f} ~ ${full_data['close'].max():.2f}")
        print(f"📈 기간: {full_data.index[0].strftime('%Y-%m-%d')} ~ {full_data.index[-1].strftime('%Y-%m-%d')}")
        
        return full_data
        
    except Exception as e:
        print(f"❌ 데이터 로드 실패: {e}")
        return None

def run_2023_backtest():
    """2023년 백테스트 실행"""
    print("🚀 2023년 다중 전략 백테스트 시작")
    print("=" * 60)
    
    # 2023년 데이터 로드
    data = load_2023_data()
    if data is None:
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
    
    print(f"\n📊 2023년 전체 성과:")
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
    
    return strategy_performance, portfolio_returns, data

def analyze_quarterly_performance(data, portfolio_returns):
    """분기별 성과 분석"""
    print(f"\n📅 분기별 성과 분석:")
    print("-" * 50)
    
    quarters = {
        'Q1 (1-3월)': (1, 3),
        'Q2 (4-6월)': (4, 6),
        'Q3 (7-9월)': (7, 9),
        'Q4 (10-12월)': (10, 12)
    }
    
    quarterly_performance = []
    
    for quarter_name, (start_month, end_month) in quarters.items():
        # 분기 데이터 필터링
        quarter_data = data[(data.index.month >= start_month) & (data.index.month <= end_month)]
        if len(quarter_data) > 0:
            quarter_returns = portfolio_returns[(portfolio_returns.index.month >= start_month) & (portfolio_returns.index.month <= end_month)]
            if len(quarter_returns) > 0:
                quarter_return = quarter_returns.sum() * 100
                quarter_winrate = (quarter_returns > 0).mean() * 100
                quarter_volatility = quarter_returns.std() * 100
                quarterly_performance.append((quarter_name, quarter_return, quarter_winrate, quarter_volatility))
                print(f"  {quarter_name:<15}: 수익률 {quarter_return:6.2f}%, 승률 {quarter_winrate:5.1f}%, 변동성 {quarter_volatility:5.2f}%")
    
    # 분기별 성과 순위
    quarterly_performance.sort(key=lambda x: x[1], reverse=True)
    print(f"\n🏆 분기별 성과 순위:")
    for i, (quarter_name, quarter_return, quarter_winrate, quarter_volatility) in enumerate(quarterly_performance):
        print(f"  {i+1}. {quarter_name}: {quarter_return:6.2f}% (승률: {quarter_winrate:.1f}%)")

def analyze_monthly_performance(data, portfolio_returns):
    """월별 성과 분석"""
    print(f"\n📅 월별 성과 분석:")
    print("-" * 50)
    
    monthly_performance = []
    
    for month in range(1, 13):
        month_data = data[data.index.month == month]
        if len(month_data) > 0:
            month_returns = portfolio_returns[portfolio_returns.index.month == month]
            if len(month_returns) > 0:
                month_return = month_returns.sum() * 100
                month_winrate = (month_returns > 0).mean() * 100
                month_volatility = month_returns.std() * 100
                monthly_performance.append((month, month_return, month_winrate, month_volatility))
                print(f"  {month:2d}월: 수익률 {month_return:6.2f}%, 승률 {month_winrate:5.1f}%, 변동성 {month_volatility:5.2f}%")
    
    # 월별 성과 순위 (상위 5개월)
    monthly_performance.sort(key=lambda x: x[1], reverse=True)
    print(f"\n🏆 월별 성과 순위 (상위 5개월):")
    for i, (month, month_return, month_winrate, month_volatility) in enumerate(monthly_performance[:5]):
        print(f"  {i+1}. {month:2d}월: {month_return:6.2f}% (승률: {month_winrate:.1f}%)")

def analyze_risk_metrics(portfolio_returns):
    """리스크 지표 분석"""
    print(f"\n⚠️ 리스크 분석:")
    print("-" * 50)
    
    # 변동성 분석
    daily_volatility = portfolio_returns.std() * 100
    annualized_volatility = daily_volatility * np.sqrt(252)
    
    print(f"  일일 변동성: {daily_volatility:.2f}%")
    print(f"  연간 변동성: {annualized_volatility:.2f}%")
    
    # VaR (Value at Risk) 계산
    var_95 = np.percentile(portfolio_returns, 5) * 100
    var_99 = np.percentile(portfolio_returns, 1) * 100
    
    print(f"  VaR 95%: {var_95:.2f}%")
    print(f"  VaR 99%: {var_99:.2f}%")
    
    # 최대 연속 손실일
    consecutive_losses = 0
    max_consecutive_losses = 0
    for ret in portfolio_returns:
        if ret < 0:
            consecutive_losses += 1
            max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
        else:
            consecutive_losses = 0
    
    print(f"  최대 연속 손실: {max_consecutive_losses}일")
    
    # 최대 연속 수익일
    consecutive_gains = 0
    max_consecutive_gains = 0
    for ret in portfolio_returns:
        if ret > 0:
            consecutive_gains += 1
            max_consecutive_gains = max(max_consecutive_gains, consecutive_gains)
        else:
            consecutive_gains = 0
    
    print(f"  최대 연속 수익: {max_consecutive_gains}일")

def analyze_strategy_ranking(strategy_performance):
    """전략 순위 분석"""
    print(f"\n🏆 전략 순위 분석:")
    print("-" * 50)
    
    # 수익률 기준 정렬
    sorted_by_return = sorted(strategy_performance.items(), key=lambda x: x[1]['total_return'], reverse=True)
    print(f"  수익률 기준 순위:")
    for i, (name, performance) in enumerate(sorted_by_return):
        print(f"    {i+1:2d}. {name:<15}: {performance['total_return']:6.2f}%")
    
    # 샤프비율 기준 정렬
    sorted_by_sharpe = sorted(strategy_performance.items(), key=lambda x: x[1]['sharpe_ratio'], reverse=True)
    print(f"\n  샤프비율 기준 순위:")
    for i, (name, performance) in enumerate(sorted_by_sharpe):
        print(f"    {i+1:2d}. {name:<15}: {performance['sharpe_ratio']:6.2f}")
    
    # 승률 기준 정렬
    sorted_by_winrate = sorted(strategy_performance.items(), key=lambda x: x[1]['win_rate'], reverse=True)
    print(f"\n  승률 기준 순위:")
    for i, (name, performance) in enumerate(sorted_by_winrate):
        print(f"    {i+1:2d}. {name:<15}: {performance['win_rate']:5.1f}%")

def main():
    """메인 함수"""
    print("🚀 2023년 전체 기간 백테스트 시스템")
    print("=" * 60)
    
    try:
        # 1. 2023년 백테스트 실행
        strategy_performance, portfolio_returns, data = run_2023_backtest()
        
        if strategy_performance is None:
            print("❌ 백테스트 실행 실패")
            return
        
        # 2. 분기별 성과 분석
        analyze_quarterly_performance(data, portfolio_returns)
        
        # 3. 월별 성과 분석
        analyze_monthly_performance(data, portfolio_returns)
        
        # 4. 리스크 분석
        analyze_risk_metrics(portfolio_returns)
        
        # 5. 전략 순위 분석
        analyze_strategy_ranking(strategy_performance)
        
        print(f"\n🎉 2023년 백테스트 분석이 완료되었습니다!")
        print(f"📊 총 {len(data)}개 캔들 데이터로 분석 완료")
        
    except Exception as e:
        print(f"\n❌ 오류가 발생했습니다: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
