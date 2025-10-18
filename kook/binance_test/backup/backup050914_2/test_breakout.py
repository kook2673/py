#!/usr/bin/env python3
#-*-coding:utf-8 -*-

print("Test script started")

try:
    from breakout_strategy_backtest import BreakoutStrategyBacktester
    print("Import successful")
    
    backtester = BreakoutStrategyBacktester(initial_capital=10000, leverage=10)
    print("Backtester created")
    
    # 데이터 로드
    print("Loading data...")
    data_dir = "data"
    df = backtester.load_data(data_dir, '2018-01-01', '2024-12-31', '1h')
    print(f"Data loaded: {len(df)} rows")
    
    # 기술적 지표 계산
    print("Calculating indicators...")
    df = backtester.calculate_indicators(df)
    print("Indicators calculated")
    
    # 신호 생성
    print("Generating signals...")
    df = backtester.generate_signals(df)
    print("Signals generated")
    
    # 백테스트 실행
    print("Running backtest...")
    result = backtester.run_backtest(df)
    print("Backtest completed")
    
    # 결과 출력
    print(f"Final capital: {result['final_capital']:.2f}")
    print(f"Total return: {result['total_return']:.2f}%")
    print(f"Total trades: {result['total_trades']}")
    print(f"Win rate: {result['win_rate']:.1f}%")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("Test script finished")
