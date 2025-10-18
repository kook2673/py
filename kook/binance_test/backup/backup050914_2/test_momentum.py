#!/usr/bin/env python3
#-*-coding:utf-8 -*-

print("Test script started")

try:
    from momentum_strategy_backtest import MomentumStrategyBacktester
    print("Import successful")
    
    backtester = MomentumStrategyBacktester(initial_capital=10000, leverage=10)
    print("Backtester created")
    
    # 실제 데이터 사용
    print("Loading real data...")
    df = backtester.load_data('data', '2024-01-01', '2024-01-31', '1h')  # 1개월만 테스트
    print(f"Data loaded: {len(df)} rows")
    
    # 지표 계산 테스트
    print("Starting calculate_indicators...")
    df_with_indicators = backtester.calculate_indicators(df)
    print("Indicators calculated successfully")
    print(f"Columns: {df_with_indicators.columns.tolist()}")
    print(f"Signal exists: {'signal' in df_with_indicators.columns}")
    print(f"Signal filtered exists: {'signal_filtered' in df_with_indicators.columns}")
    
    if 'signal' in df_with_indicators.columns:
        signal_count = len(df_with_indicators[df_with_indicators['signal'] != 0])
        print(f"Signal count: {signal_count}")
    
    # 백테스트 실행
    result = backtester.run_backtest(df_with_indicators)
    print("Backtest completed")
    print(f"Final capital: {result['final_capital']:.2f}")
    print(f"Total return: {result['total_return']:.2f}%")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("Test script finished")
