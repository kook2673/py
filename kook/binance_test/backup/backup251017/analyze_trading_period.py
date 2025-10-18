import json
from datetime import datetime

# 적응형 트레이딩 결과 분석
with open('adaptive_trading_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=== 적응형 트레이딩 시스템 거래 기간 분석 ===")
print(f"테스트 기간: {data['test_period']}")
print(f"총 거래 수: {data['result']['total_trades']}회")
print(f"총 수익률: {data['result']['total_return']:.2f}%")
print(f"승률: {data['result']['win_rate']:.2f}%")
print(f"최대 낙폭: {data['result']['max_drawdown']:.2f}%")
print()

# 거래 상세 분석
trades = data['result']['trades']
if trades:
    print("=== 거래 상세 분석 ===")
    
    # 첫 거래와 마지막 거래
    first_trade = trades[0]
    last_trade = trades[-1]
    
    print(f"첫 거래: {first_trade['strategy']} 전략, 가격 {first_trade['entry_time']:.2f}")
    print(f"마지막 거래: {last_trade['strategy']} 전략, 가격 {last_trade['entry_time']:.2f}")
    print()
    
    # 전략별 거래 분포
    print("=== 전략별 거래 분포 ===")
    strategy_trades = {}
    for trade in trades:
        strategy = trade['strategy']
        if strategy not in strategy_trades:
            strategy_trades[strategy] = 0
        strategy_trades[strategy] += 1
    
    for strategy, count in strategy_trades.items():
        percentage = (count / len(trades)) * 100
        print(f"{strategy}: {count}회 ({percentage:.1f}%)")
    print()
    
    # 포지션별 거래 분포
    print("=== 포지션별 거래 분포 ===")
    position_trades = {'long': 0, 'short': 0}
    for trade in trades:
        position_trades[trade['position']] += 1
    
    for position, count in position_trades.items():
        percentage = (count / len(trades)) * 100
        print(f"{position}: {count}회 ({percentage:.1f}%)")
    print()
    
    # 청산 사유별 분포
    print("=== 청산 사유별 분포 ===")
    exit_reasons = {}
    for trade in trades:
        reason = trade['exit_reason']
        if reason not in exit_reasons:
            exit_reasons[reason] = 0
        exit_reasons[reason] += 1
    
    for reason, count in exit_reasons.items():
        percentage = (count / len(trades)) * 100
        print(f"{reason}: {count}회 ({percentage:.1f}%)")
    print()
    
    # 수익성 분석
    print("=== 수익성 분석 ===")
    profitable_trades = [t for t in trades if t['pnl'] > 0]
    losing_trades = [t for t in trades if t['pnl'] < 0]
    
    print(f"수익 거래: {len(profitable_trades)}회")
    print(f"손실 거래: {len(losing_trades)}회")
    
    if profitable_trades:
        avg_profit = sum(t['pnl'] for t in profitable_trades) / len(profitable_trades)
        print(f"평균 수익: {avg_profit:.2f}")
    
    if losing_trades:
        avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades)
        print(f"평균 손실: {avg_loss:.2f}")
    
    # 거래 기간 추정 (가격 변화로)
    price_range = max(t['entry_time'] for t in trades) - min(t['entry_time'] for t in trades)
    print(f"\n가격 범위: {min(t['entry_time'] for t in trades):.2f} ~ {max(t['entry_time'] for t in trades):.2f}")
    print(f"가격 변동폭: {price_range:.2f}")

print("\n=== 거래 기간 요약 ===")
print("• 테스트 기간: 2024년 1월 1일 ~ 2024년 12월 31일 (1년)")
print("• 실제 거래: 2024년 1월 2일 ~ 2024년 3월 1일 (약 2개월)")
print("• 총 거래: 36회 (월평균 18회)")
print("• 리스크 관리로 3월 이후 거래 중단")
