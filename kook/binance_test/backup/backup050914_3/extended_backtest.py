#-*-coding:utf-8 -*-
'''
확장된 백테스트 스크립트
======================

=== 사용법 ===
python extended_backtest.py

=== 기능 ===
1. 사용 가능한 전체 기간 백테스트
2. 전략별 상세 성과 분석
3. 월별 성과 분석
4. 리스크 분석
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

def load_available_data():
    """사용 가능한 데이터 로드"""
    print("📊 사용 가능한 데이터 로드 중...")
    
    data_path = "data/BTCUSDT/1h/BTCUSDT_1h_2024.csv"
    
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
        
        print(f"📅 전체 기간: {data.index[0].strftime('%Y-%m-%d')} ~ {data.index[-1].strftime('%Y-%m-%d')}")
        print(f"💰 가격 범위: ${data['close'].min():.2f} ~ ${data['close'].max():.2f}")
        
        return data
        
    except Exception as e:
        print(f"❌ 데이터 로드 실패: {e}")
        return None

def run_multi_strategy_backtest(data):
    """다중 전략 백테스트 실행"""
    print("\n🚀 다중 전략 백테스트 실행")
    print("=" * 60)
    
    # 포트폴리오 관리자 생성
    portfolio_manager = MultiStrategyPortfolioManager(initial_capital=100000)
    
    # 신호 계산
    print("📊 전략 신호 계산 중...")
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
    
    print(f"\n📊 포트폴리오 전체 성과:")
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
    
    return strategy_performance, portfolio_returns

def analyze_monthly_performance(data, portfolio_returns):
    """월별 성과 분석"""
    print(f"\n📅 월별 성과 분석:")
    print("-" * 40)
    
    monthly_returns = []
    for month in range(1, 13):
        month_data = data[data.index.month == month]
        if len(month_data) > 0:
            month_returns = portfolio_returns[portfolio_returns.index.month == month]
            if len(month_returns) > 0:
                month_return = month_returns.sum() * 100
                month_winrate = (month_returns > 0).mean() * 100
                monthly_returns.append((month, month_return, month_winrate))
                print(f"  {month:2d}월: 수익률 {month_return:6.2f}%, 승률 {month_winrate:5.1f}%")
    
    # 수익률 기준으로 정렬
    monthly_returns.sort(key=lambda x: x[1], reverse=True)
    
    print(f"\n🏆 월별 성과 순위:")
    for i, (month, month_return, month_winrate) in enumerate(monthly_returns[:5]):
        print(f"  {i+1}. {month:2d}월: {month_return:6.2f}% (승률: {month_winrate:.1f}%)")

def analyze_risk_metrics(portfolio_returns):
    """리스크 지표 분석"""
    print(f"\n⚠️ 리스크 분석:")
    print("-" * 40)
    
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

def analyze_strategy_correlation(strategy_performance):
    """전략 간 상관관계 분석"""
    print(f"\n🔗 전략 상관관계 분석:")
    print("-" * 40)
    
    # 전략별 수익률 데이터 수집 (간단한 예시)
    strategy_returns = {}
    for name, performance in strategy_performance.items():
        # 실제로는 각 전략의 일별 수익률이 필요하지만, 여기서는 간단히 표시
        strategy_returns[name] = performance['total_return']
    
    # 상위 3개 전략 표시
    sorted_strategies = sorted(strategy_returns.items(), key=lambda x: x[1], reverse=True)
    print(f"  상위 3개 전략:")
    for i, (name, return_pct) in enumerate(sorted_strategies[:3]):
        print(f"    {i+1}. {name}: {return_pct:.2f}%")

def main():
    """메인 함수"""
    print("🚀 확장된 백테스트 시스템")
    print("=" * 60)
    
    try:
        # 1. 데이터 로드
        data = load_available_data()
        if data is None:
            return
        
        # 2. 다중 전략 백테스트
        strategy_performance, portfolio_returns = run_multi_strategy_backtest(data)
        
        # 3. 월별 성과 분석
        analyze_monthly_performance(data, portfolio_returns)
        
        # 4. 리스크 분석
        analyze_risk_metrics(portfolio_returns)
        
        # 5. 전략 상관관계 분석
        analyze_strategy_correlation(strategy_performance)
        
        print(f"\n🎉 모든 분석이 완료되었습니다!")
        print(f"📊 총 {len(data)}개 캔들 데이터로 분석 완료")
        
    except Exception as e:
        print(f"\n❌ 오류가 발생했습니다: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
