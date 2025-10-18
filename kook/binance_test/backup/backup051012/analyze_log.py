#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📊 백테스트 로그 분석기
"""

import re
from collections import defaultdict
from datetime import datetime

def parse_log_file(log_path):
    """로그 파일 파싱"""
    trades = []
    position_changes = []
    retrains = []
    
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            # 포지션 청산 로그 파싱
            if '포지션 청산:' in line:
                try:
                    # side 추출
                    side_match = re.search(r'청산: (buy|sell)', line)
                    
                    # PnL 추출
                    pnl_match = re.search(r'PnL: ([-+]?\d+\.?\d*) USDT', line)
                    
                    # 가격변동 추출
                    price_change_match = re.search(r'가격변동: ([-+]?\d+\.?\d*)%', line)
                    
                    # 청산 이유 추출
                    reason_match = re.search(r'이유: (\w+)', line)
                    
                    # 포지션 사이즈 추출
                    size_match = re.search(r'현재 포지션 사이즈: (0\.\d+)', line)
                    
                    if pnl_match and reason_match:
                        trade = {
                            'side': side_match.group(1) if side_match else 'unknown',
                            'pnl': float(pnl_match.group(1)),
                            'price_change': float(price_change_match.group(1)) if price_change_match else 0,
                            'reason': reason_match.group(1),
                            'position_size': float(size_match.group(1)) if size_match else 0
                        }
                        trades.append(trade)
                except Exception as e:
                    continue
            
            # 포지션 사이즈 변경 로그
            if '포지션 사이즈를 증가:' in line or '포지션 사이즈를 기본값으로 복원:' in line:
                try:
                    size_match = re.search(r': (0\.\d+)', line)
                    if size_match:
                        change_type = 'increase' if '증가' in line else 'reset'
                        position_changes.append({
                            'type': change_type,
                            'size': float(size_match.group(1))
                        })
                except:
                    continue
            
            # 재학습 로그
            if '월별 재학습 실행:' in line:
                try:
                    date_match = re.search(r'실행: (.+)$', line)
                    if date_match:
                        retrains.append(date_match.group(1).strip())
                except:
                    continue
    
    return trades, position_changes, retrains

def analyze_trades(trades):
    """거래 분석"""
    print("\n" + "="*70)
    print("  📊 거래 분석 결과")
    print("="*70 + "\n")
    
    if not trades:
        print("   ⚠️ 거래 내역이 없습니다.")
        return
    
    # 기본 통계
    total_trades = len(trades)
    winning_trades = [t for t in trades if t['pnl'] > 0]
    losing_trades = [t for t in trades if t['pnl'] < 0]
    
    total_pnl = sum(t['pnl'] for t in trades)
    win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
    
    print("💰 전체 통계:")
    print(f"   총 거래 횟수:     {total_trades:>6}회")
    print(f"   승리 거래:        {len(winning_trades):>6}회 ✅")
    print(f"   손실 거래:        {len(losing_trades):>6}회 ❌")
    print(f"   승률:            {win_rate:>6.2f}%")
    print(f"   총 손익:         {total_pnl:>8,.2f} USDT")
    
    # 평균 손익
    if winning_trades:
        avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades)
        print(f"   평균 수익:       {avg_win:>8,.2f} USDT")
    
    if losing_trades:
        avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades)
        print(f"   평균 손실:       {avg_loss:>8,.2f} USDT")
        
        if avg_loss != 0:
            profit_factor = abs(avg_win / avg_loss) if winning_trades else 0
            print(f"   수익 팩터:       {profit_factor:>8.2f}")
    
    # 청산 사유별 통계
    print("\n📊 청산 사유별 통계:")
    reasons = defaultdict(lambda: {'count': 0, 'pnl': 0, 'wins': 0})
    
    for trade in trades:
        reason = trade['reason']
        reasons[reason]['count'] += 1
        reasons[reason]['pnl'] += trade['pnl']
        if trade['pnl'] > 0:
            reasons[reason]['wins'] += 1
    
    reason_names = {
        'take_profit': '익절 💰',
        'stop_loss': '손절 🛑',
        'trailing_stop': '트레일링 📊'
    }
    
    print("   " + "-"*68)
    print("   사유              횟수    승률     총 손익(USDT)    평균 손익")
    print("   " + "-"*68)
    
    for reason, stats in sorted(reasons.items(), key=lambda x: x[1]['count'], reverse=True):
        reason_display = reason_names.get(reason, reason)
        winrate = (stats['wins'] / stats['count'] * 100) if stats['count'] > 0 else 0
        avg_pnl = stats['pnl'] / stats['count']
        emoji = "✅" if avg_pnl > 0 else "❌"
        
        print(f"   {reason_display:<15} {stats['count']:>4}회  {winrate:>5.1f}%  {emoji} {stats['pnl']:>10,.2f}   {avg_pnl:>9,.2f}")
    
    # 롱/숏 분석
    print("\n📈 포지션 방향별 성과:")
    print("   " + "-"*68)
    
    long_trades = [t for t in trades if t['side'] == 'buy']
    short_trades = [t for t in trades if t['side'] == 'sell']
    
    if long_trades:
        long_pnl = sum(t['pnl'] for t in long_trades)
        long_wins = sum(1 for t in long_trades if t['pnl'] > 0)
        long_winrate = (long_wins / len(long_trades)) * 100
        long_avg = long_pnl / len(long_trades)
        print(f"   롱 포지션 📈:  {len(long_trades):>4}회  |  승률: {long_winrate:>5.1f}%  |  "
              f"손익: {long_pnl:>10,.2f} USDT  |  평균: {long_avg:>8,.2f}")
    
    if short_trades:
        short_pnl = sum(t['pnl'] for t in short_trades)
        short_wins = sum(1 for t in short_trades if t['pnl'] > 0)
        short_winrate = (short_wins / len(short_trades)) * 100
        short_avg = short_pnl / len(short_trades)
        print(f"   숏 포지션 📉:  {len(short_trades):>4}회  |  승률: {short_winrate:>5.1f}%  |  "
              f"손익: {short_pnl:>10,.2f} USDT  |  평균: {short_avg:>8,.2f}")
    
    # 베스트/최악 거래
    print("\n🏆 베스트 거래 TOP 5:")
    best_trades = sorted(trades, key=lambda x: x['pnl'], reverse=True)[:5]
    for i, trade in enumerate(best_trades, 1):
        side_emoji = "📈" if trade['side'] == 'buy' else "📉"
        print(f"   {i}. {side_emoji} {trade['side'].upper():4s}  |  "
              f"수익: ${trade['pnl']:>10,.2f}  |  "
              f"가격변동: {trade['price_change']:>+6.2f}%  |  "
              f"사유: {trade['reason']}")
    
    print("\n😢 최악 거래 TOP 5:")
    worst_trades = sorted(trades, key=lambda x: x['pnl'])[:5]
    for i, trade in enumerate(worst_trades, 1):
        side_emoji = "📈" if trade['side'] == 'buy' else "📉"
        print(f"   {i}. {side_emoji} {trade['side'].upper():4s}  |  "
              f"손실: ${trade['pnl']:>10,.2f}  |  "
              f"가격변동: {trade['price_change']:>+6.2f}%  |  "
              f"사유: {trade['reason']}")
    
    # 연속 손익 분석
    print("\n🎯 연속 손익 분석:")
    max_consecutive_wins = 0
    max_consecutive_losses = 0
    current_wins = 0
    current_losses = 0
    
    for trade in trades:
        if trade['pnl'] > 0:
            current_wins += 1
            current_losses = 0
            max_consecutive_wins = max(max_consecutive_wins, current_wins)
        else:
            current_losses += 1
            current_wins = 0
            max_consecutive_losses = max(max_consecutive_losses, current_losses)
    
    print(f"   최대 연속 승리:   {max_consecutive_wins:>3}회 🔥")
    print(f"   최대 연속 손실:   {max_consecutive_losses:>3}회 ⚠️")
    
    # 포지션 사이즈별 분석
    print("\n💼 포지션 사이즈별 분석:")
    size_stats = defaultdict(lambda: {'count': 0, 'pnl': 0, 'wins': 0})
    
    for trade in trades:
        size = trade.get('position_size', 0)
        if size > 0:
            size_key = f"{size:.2f}"
            size_stats[size_key]['count'] += 1
            size_stats[size_key]['pnl'] += trade['pnl']
            if trade['pnl'] > 0:
                size_stats[size_key]['wins'] += 1
    
    print("   사이즈    횟수    승률     총 손익(USDT)")
    print("   " + "-"*45)
    for size_key, stats in sorted(size_stats.items()):
        winrate = (stats['wins'] / stats['count'] * 100) if stats['count'] > 0 else 0
        emoji = "✅" if stats['pnl'] > 0 else "❌"
        print(f"   {size_key:>6}  {stats['count']:>4}회  {winrate:>5.1f}%  {emoji} {stats['pnl']:>10,.2f}")

def analyze_retrains(retrains):
    """재학습 분석"""
    print("\n" + "="*70)
    print("  🔄 모델 재학습 분석")
    print("="*70 + "\n")
    
    if not retrains:
        print("   ⚠️ 재학습 기록이 없습니다.")
        return
    
    print(f"   총 재학습 횟수: {len(retrains)}회\n")
    print("   재학습 일시:")
    for i, retrain_time in enumerate(retrains, 1):
        print(f"   {i:>2}. {retrain_time}")

def main():
    import sys
    
    # 인코딩 설정
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    
    print("\n" + "="*70)
    print("  🤖 Advanced MA ML Bot - 로그 분석기")
    print("="*70)
    
    log_path = r'c:\work\GitHub\py\kook\binance_test\logs\advanced_ma_ml_bot.log'
    
    print(f"\n📂 로그 파일: {log_path}")
    print("🔍 분석 중...\n")
    
    # 로그 파싱
    trades, position_changes, retrains = parse_log_file(log_path)
    
    # 거래 분석
    analyze_trades(trades)
    
    # 재학습 분석
    analyze_retrains(retrains)
    
    print("\n" + "="*70)
    print("  ✅ 분석 완료!")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()

