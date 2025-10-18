import json

# 적응형 트레이딩 결과 분석
with open('adaptive_trading_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=== 자동 중단 원인 분석 ===")
print()

trades = data['result']['trades']
if trades:
    # 연속 손실 분석
    consecutive_losses = 0
    max_consecutive_losses = 0
    current_consecutive = 0
    
    print("=== 연속 손실 분석 ===")
    for i, trade in enumerate(trades):
        if trade['pnl'] < 0:
            current_consecutive += 1
            max_consecutive_losses = max(max_consecutive_losses, current_consecutive)
            print(f"거래 {i+1}: {trade['strategy']} {trade['position']} - 손실 {trade['pnl']:.2f} (연속 {current_consecutive}회)")
        else:
            if current_consecutive > 0:
                print(f"  -> 연속 손실 {current_consecutive}회 후 수익 거래")
            current_consecutive = 0
    
    print(f"\n최대 연속 손실: {max_consecutive_losses}회")
    print(f"중단 조건: 5회 연속 손실")
    print(f"중단 여부: {'중단됨' if max_consecutive_losses >= 5 else '중단 안됨'}")
    print()
    
    # 최대 낙폭 분석
    print("=== 최대 낙폭 분석 ===")
    initial_capital = 10000
    current_capital = initial_capital
    max_drawdown = 0
    peak_capital = initial_capital
    
    for i, trade in enumerate(trades):
        current_capital += trade['pnl']
        
        if current_capital > peak_capital:
            peak_capital = current_capital
        
        current_drawdown = (peak_capital - current_capital) / peak_capital * 100
        max_drawdown = max(max_drawdown, current_drawdown)
        
        if i < 10 or i >= len(trades) - 5:  # 처음 10개와 마지막 5개만 출력
            print(f"거래 {i+1}: 자본 {current_capital:.2f}, 낙폭 {current_drawdown:.2f}%")
    
    print(f"\n최대 낙폭: {max_drawdown:.2f}%")
    print(f"중단 조건: 30% 이상 낙폭")
    print(f"중단 여부: {'중단됨' if max_drawdown >= 30 else '중단 안됨'}")
    print()
    
    # 마지막 거래들 분석
    print("=== 마지막 거래들 분석 ===")
    last_trades = trades[-10:]  # 마지막 10개 거래
    for i, trade in enumerate(last_trades):
        trade_num = len(trades) - 10 + i + 1
        print(f"거래 {trade_num}: {trade['strategy']} {trade['position']} - PnL {trade['pnl']:.2f}")
    
    print()
    print("=== 중단 원인 결론 ===")
    if max_consecutive_losses >= 5:
        print("• 5회 연속 손실로 인한 자동 중단")
    elif max_drawdown >= 30:
        print("• 30% 이상 낙폭으로 인한 자동 중단")
    else:
        print("• 리스크 관리 조건 미달성 - 다른 이유로 중단")
        print("• 가능한 원인: 데이터 부족, 시장 상태 변화, 또는 다른 내부 로직")
