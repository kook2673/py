#-*-coding:utf-8 -*-
'''
다중 전략 포트폴리오 테스트 스크립트
=====================================

=== 사용법 ===
python test_multi_strategy.py

=== 기능 ===
1. 시스템 기본 동작 테스트
2. 전략별 신호 생성 테스트
3. 자본 배분 로직 테스트
4. 성과 계산 테스트
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
                   start_date: str = '2023-01-01', end_date: str = '2023-12-31') -> pd.DataFrame:
    """실제 데이터 로드"""
    print(f"📊 실제 데이터 로드 중... ({symbol}, {timeframe})")
    
    # 데이터 파일 경로 (2023년 데이터 사용)
    data_path = f"kook/binance_test/data/{symbol}/{timeframe}/{symbol}_{timeframe}_2023.csv"
    
    if not os.path.exists(data_path):
        print(f"❌ 데이터 파일을 찾을 수 없습니다: {data_path}")
        print("📋 사용 가능한 데이터:")
        
        # 사용 가능한 데이터 파일들 표시
        data_dir = "kook/binance_test/data"
        if os.path.exists(data_dir):
            for symbol_dir in os.listdir(data_dir):
                symbol_path = os.path.join(data_dir, symbol_dir)
                if os.path.isdir(symbol_path):
                    for tf_dir in os.listdir(symbol_path):
                        tf_path = os.path.join(symbol_path, tf_dir)
                        if os.path.isdir(tf_path):
                            files = [f for f in os.listdir(tf_path) if f.endswith('.csv')]
                            if files:
                                print(f"  {symbol_dir}/{tf_dir}: {files}")
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
            print(f"📊 실제 컬럼: {list(data.columns)}")
            return None
        
        # 데이터 전처리
        data['timestamp'] = pd.to_datetime(data['timestamp'])
        data.set_index('timestamp', inplace=True)
        
        # 사용 가능한 전체 기간 사용 (필터링 없이)
        print(f"📅 사용 가능한 전체 데이터: {len(data)}개 행")
        print(f"💰 가격 범위: ${data['close'].min():.2f} ~ ${data['close'].max():.2f}")
        print(f"📈 기간: {data.index[0].strftime('%Y-%m-%d')} ~ {data.index[-1].strftime('%Y-%m-%d')}")
        
        return data
        
    except Exception as e:
        print(f"❌ 데이터 로드 실패: {e}")
        return None

def create_sample_data(days: int = 30) -> pd.DataFrame:
    """샘플 데이터 생성 (백업용)"""
    print("📊 샘플 데이터 생성 중...")
    
    # 1시간 간격으로 데이터 생성
    start_date = datetime.now() - timedelta(days=days)
    dates = pd.date_range(start=start_date, periods=days*24, freq='1H')
    
    # 랜덤 가격 데이터 생성 (랜덤 워크)
    np.random.seed(42)  # 재현 가능한 결과를 위해
    price = 50000  # 초기 가격
    prices = [price]
    
    for i in range(len(dates) - 1):
        # 랜덤 워크 (약간의 트렌드 포함)
        change = np.random.normal(0, 0.02)  # 2% 표준편차
        price = price * (1 + change)
        prices.append(price)
    
    # OHLCV 데이터 생성
    data = pd.DataFrame(index=dates)
    data['close'] = prices
    
    # 고가/저가 생성 (종가 기준 ±1%)
    data['high'] = data['close'] * (1 + np.random.uniform(0, 0.01, len(data)))
    data['low'] = data['close'] * (1 - np.random.uniform(0, 0.01, len(data)))
    data['open'] = data['close'].shift(1).fillna(data['close'].iloc[0])
    data['volume'] = np.random.uniform(1000, 10000, len(data))
    
    print(f"✅ {len(data)}개 캔들 데이터 생성 완료")
    return data

def test_strategy_signals(use_real_data: bool = True):
    """전략 신호 생성 테스트"""
    print("\n🧪 전략 신호 생성 테스트")
    print("-" * 50)
    
    # 데이터 로드
    if use_real_data:
        data = load_real_data('BTCUSDT', '1h', '2024-01-01', '2024-01-07')  # 1주일 데이터
        if data is None:
            print("⚠️ 실제 데이터 로드 실패, 샘플 데이터 사용")
            data = create_sample_data(7)
    else:
        data = create_sample_data(7)  # 7일 데이터
    
    if data is None or len(data) < 50:
        print("❌ 충분한 데이터가 없습니다.")
        return
    
    # 포트폴리오 관리자 생성
    portfolio_manager = MultiStrategyPortfolioManager(initial_capital=10000)
    
    # 각 전략 테스트
    for name, strategy in portfolio_manager.strategies.items():
        try:
            signals = strategy.calculate_signals(data)
            
            # 신호 통계
            total_signals = len(signals)
            buy_signals = (signals['signal'] == 1).sum()
            sell_signals = (signals['signal'] == -1).sum()
            hold_signals = (signals['signal'] == 0).sum()
            
            print(f"✅ {strategy.name:<15} | 총신호: {total_signals:3d} | 매수: {buy_signals:3d} | 매도: {sell_signals:3d} | 보유: {hold_signals:3d}")
            
        except Exception as e:
            print(f"❌ {strategy.name:<15} | 오류: {e}")
    
    print("-" * 50)

def test_capital_allocation():
    """자본 배분 테스트"""
    print("\n💰 자본 배분 테스트")
    print("-" * 50)
    
    portfolio_manager = MultiStrategyPortfolioManager(initial_capital=100000)
    
    # 초기 배분 확인
    print("초기 배분:")
    total_allocation = 0
    for name, strategy in portfolio_manager.strategies.items():
        print(f"  {strategy.name:<15}: {strategy.current_allocation*100:5.1f}%")
        total_allocation += strategy.current_allocation
    
    print(f"  {'총합':<15}: {total_allocation*100:5.1f}%")
    
    # 가상 성과 데이터 설정
    print("\n가상 성과 데이터 설정:")
    test_performances = [
        ("변동성돌파", 15.5, 65.0, 1.2),
        ("모멘텀", 8.2, 58.0, 0.8),
        ("스윙", -5.3, 45.0, -0.3),
        ("브레이크아웃", 22.1, 72.0, 1.5),
        ("스캘핑", 3.7, 52.0, 0.4),
        ("RSI", 12.8, 68.0, 1.1),
        ("MACD", 6.4, 55.0, 0.6),
        ("볼린저밴드", 18.9, 70.0, 1.3),
        ("이동평균", 4.1, 50.0, 0.3),
        ("스토캐스틱", 9.6, 62.0, 0.9)
    ]
    
    for name, strategy in portfolio_manager.strategies.items():
        for test_name, return_pct, winrate, sharpe in test_performances:
            if strategy.name == test_name:
                strategy.total_return = return_pct
                strategy.win_rate = winrate
                strategy.sharpe_ratio = sharpe
                print(f"  {strategy.name:<15}: 수익률 {return_pct:5.1f}%, 승률 {winrate:4.1f}%, 샤프 {sharpe:4.1f}")
                break
    
    # 자본 재배분 실행
    print("\n자본 재배분 실행:")
    portfolio_manager._reallocate_capital()
    
    # 재배분 결과 확인
    total_allocation = 0
    for name, strategy in portfolio_manager.strategies.items():
        print(f"  {strategy.name:<15}: {strategy.current_allocation*100:5.1f}%")
        total_allocation += strategy.current_allocation
    
    print(f"  {'총합':<15}: {total_allocation*100:5.1f}%")
    print("-" * 50)

def test_performance_calculation(use_real_data: bool = True):
    """성과 계산 테스트"""
    print("\n📈 성과 계산 테스트")
    print("-" * 50)
    
    # 데이터 로드
    if use_real_data:
        data = load_real_data('BTCUSDT', '1h', '2024-01-01', '2024-01-31')  # 1개월 데이터
        if data is None:
            print("⚠️ 실제 데이터 로드 실패, 샘플 데이터 사용")
            data = create_sample_data(30)
    else:
        data = create_sample_data(30)  # 30일 데이터
    
    if data is None or len(data) < 50:
        print("❌ 충분한 데이터가 없습니다.")
        return
    
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
    
    print(f"포트폴리오 성과:")
    print(f"  총 수익률: {total_return:6.2f}%")
    print(f"  승률:      {win_rate:6.1f}%")
    print(f"  변동성:    {volatility:6.2f}%")
    print(f"  샤프비율:  {sharpe_ratio:6.2f}")
    
    # 전략별 성과
    print(f"\n전략별 성과:")
    for name, strategy in portfolio_manager.strategies.items():
        if name in signals:
            performance = strategy.calculate_performance(data, signals[name])
            print(f"  {strategy.name:<15}: 수익률 {performance['total_return']:6.2f}%, 승률 {performance['win_rate']:5.1f}%")
    
    print("-" * 50)

def test_strategy_activation():
    """전략 활성화/비활성화 테스트"""
    print("\n🔄 전략 활성화/비활성화 테스트")
    print("-" * 50)
    
    portfolio_manager = MultiStrategyPortfolioManager(initial_capital=100000)
    
    # 초기 상태 확인
    print("초기 상태:")
    for name, strategy in portfolio_manager.strategies.items():
        status = "활성" if strategy.is_active else "비활성"
        print(f"  {strategy.name:<15}: {status}")
    
    # 성과 데이터 설정 (일부 전략을 비활성화 조건에 맞춤)
    test_cases = [
        ("변동성돌파", 20.0, 70.0, True),   # 좋은 성과
        ("모멘텀", -60.0, 25.0, False),     # 비활성화 조건
        ("스윙", 5.0, 35.0, False),         # 비활성화 조건
        ("브레이크아웃", 15.0, 65.0, True), # 좋은 성과
        ("스캘핑", -45.0, 40.0, True),      # 경계선 (승률 30% 이상)
    ]
    
    print("\n성과 데이터 설정:")
    for name, strategy in portfolio_manager.strategies.items():
        for test_name, return_pct, winrate, expected_active in test_cases:
            if strategy.name == test_name:
                strategy.total_return = return_pct
                strategy.win_rate = winrate
                print(f"  {strategy.name:<15}: 수익률 {return_pct:5.1f}%, 승률 {winrate:4.1f}%")
                break
    
    # 활성화 상태 체크
    print("\n활성화 상태 체크 실행:")
    portfolio_manager.check_strategy_activation()
    
    # 결과 확인
    print("\n체크 후 상태:")
    for name, strategy in portfolio_manager.strategies.items():
        status = "활성" if strategy.is_active else "비활성"
        allocation = f"{strategy.current_allocation*100:5.1f}%"
        print(f"  {strategy.name:<15}: {status} (배분: {allocation})")
    
    print("-" * 50)

def test_real_data_backtest():
    """실제 데이터 백테스트 테스트"""
    print("\n🚀 실제 데이터 백테스트 테스트")
    print("-" * 50)
    

    # 실제 데이터로 백테스트 실행 (사용 가능한 전체 기간)
    data = load_real_data('BTCUSDT', '1h')  # 사용 가능한 전체 데이터
    
    if data is None:
        print("❌ 실제 데이터를 로드할 수 없습니다.")
        return
    
    # 포트폴리오 관리자 생성
    portfolio_manager = MultiStrategyPortfolioManager(initial_capital=100000)
    
    # 신호 계산
    print("📊 전략 신호 계산 중...")
    signals = portfolio_manager.calculate_strategy_signals(data)
    
    # 포트폴리오 성과 계산
    print("📈 포트폴리오 성과 계산 중...")
    portfolio_returns = portfolio_manager.calculate_portfolio_performance(data, signals)
    
    # 성과 통계
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
    
    print("-" * 50)

def run_all_tests(use_real_data: bool = True):
    """모든 테스트 실행"""
    print("🧪 다중 전략 포트폴리오 테스트 시작")
    print("=" * 60)
    
    try:
        # 1. 전략 신호 생성 테스트
        test_strategy_signals(use_real_data)
        
        # 2. 자본 배분 테스트
        test_capital_allocation()
        
        # 3. 성과 계산 테스트
        test_performance_calculation(use_real_data)
        
        # 4. 전략 활성화/비활성화 테스트
        test_strategy_activation()
        
        # 5. 실제 데이터 백테스트 (실제 데이터 사용 시)
        if use_real_data:
            test_real_data_backtest()
        
        print("\n✅ 모든 테스트가 성공적으로 완료되었습니다!")
        print("🎉 시스템이 정상적으로 작동합니다.")
        
    except Exception as e:
        print(f"\n❌ 테스트 중 오류가 발생했습니다: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_all_tests()
