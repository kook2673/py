#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 2024년 BTC 1시간봉 백테스트
Advanced MA ML Bot - 실제 데이터 테스트
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime

# 현재 디렉토리를 파이썬 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from advanced_ma_ml_bot import AdvancedMAMLBot

def print_header(title):
    """헤더 출력"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70 + "\n")

def print_section(title):
    """섹션 제목 출력"""
    print(f"\n{'─'*70}")
    print(f"  {title}")
    print(f"{'─'*70}")

def load_btc_data_2024():
    """2024년 BTC 1시간봉 데이터 로드"""
    print("📂 데이터 로딩 중...")
    
    data_path = r'c:\work\GitHub\py\kook\binance_test\data\BTCUSDT\1h\BTCUSDT_1h_2024.csv'
    
    try:
        df = pd.read_csv(data_path)
        print(f"   ✅ 데이터 로드 완료: {data_path}")
        
        # 타임스탬프 처리
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')
        
        # 데이터 정보
        print(f"   📊 데이터 기간: {df.index[0]} ~ {df.index[-1]}")
        print(f"   📈 총 캔들 수: {len(df):,}개")
        print(f"   💰 시작 가격: ${df['close'].iloc[0]:,.2f}")
        print(f"   💰 종료 가격: ${df['close'].iloc[-1]:,.2f}")
        
        price_change = ((df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0]) * 100
        emoji = "📈" if price_change > 0 else "📉"
        print(f"   {emoji} BTC 변동률: {price_change:+.2f}%")
        
        return df
        
    except Exception as e:
        print(f"   ❌ 데이터 로드 실패: {e}")
        return None

def run_full_year_backtest():
    """2024년 전체 백테스트"""
    print_header("🚀 2024년 BTC 백테스트 (1시간봉)")
    
    # 데이터 로드
    df = load_btc_data_2024()
    if df is None:
        return
    
    # 봇 생성
    print("\n🤖 봇 초기화 중...")
    bot = AdvancedMAMLBot(initial_balance=10000, leverage=20)
    
    # 파라미터 설정
    bot.params['ma_short'] = 5
    bot.params['ma_long'] = 20
    bot.params['stop_loss_pct'] = 0.01
    bot.params['take_profit_pct'] = 0.03
    bot.params['trailing_stop_pct'] = 0.02
    bot.params['trailing_stop_activation_pct'] = 0.01
    bot.params['max_positions'] = 2
    print("   ✅ 봇 초기화 완료")
    
    # 백테스트 실행
    print_section("⚙️ 백테스트 실행")
    print("   🔄 머신러닝 모델 훈련 중...")
    print("   📊 기술적 지표 계산 중...")
    print("   💹 매매 시뮬레이션 중...\n")
    
    try:
        results = bot.run_backtest(
            df,
            start_date='2024-01-01',
            end_date='2024-12-31'
        )
        
        if 'error' in results:
            print(f"   ❌ 백테스트 오류: {results['error']}")
            return
        
        # 결과 출력
        print_results(results)
        
        # 월별 분석
        analyze_monthly_performance(results)
        
        # 거래 패턴 분석
        analyze_trade_patterns(results)
        
    except Exception as e:
        print(f"   ❌ 백테스트 실행 오류: {e}")
        import traceback
        traceback.print_exc()

def print_results(results):
    """결과 출력"""
    print_section("📊 백테스트 결과")
    
    # 수익성 지표
    print("\n💰 수익성 지표:")
    print(f"   초기 자본:     {results['initial_balance']:>15,.0f} USDT")
    print(f"   최종 자본:     {results['final_balance']:>15,.0f} USDT")
    print(f"   총 수익:       {results['total_pnl']:>15,.2f} USDT")
    
    return_emoji = "🚀" if results['total_return'] > 0 else "📉"
    print(f"   총 수익률:     {return_emoji} {results['total_return']:>12.2f}%")
    
    # 리스크 지표
    print("\n📉 리스크 지표:")
    print(f"   최대 낙폭(MDD): {results['max_drawdown']:>14.2f}%")
    
    sharpe_emoji = "⭐" if results['sharpe_ratio'] > 2 else "✅" if results['sharpe_ratio'] > 1 else "⚠️"
    print(f"   샤프 비율:     {sharpe_emoji} {results['sharpe_ratio']:>12.2f}")
    
    # 거래 통계
    print("\n📈 거래 통계:")
    print(f"   총 거래:       {results['total_trades']:>15,}회")
    print(f"   승리 거래:     {results['winning_trades']:>15,}회 ✅")
    print(f"   손실 거래:     {results['losing_trades']:>15,}회 ❌")
    
    winrate_emoji = "🎯" if results['win_rate'] > 60 else "✅" if results['win_rate'] > 50 else "⚠️"
    print(f"   승률:          {winrate_emoji} {results['win_rate']:>12.2f}%")
    
    # 평균 손익
    print("\n💵 평균 손익:")
    print(f"   평균 수익:     {results['avg_win']:>15,.2f} USDT")
    print(f"   평균 손실:     {results['avg_loss']:>15,.2f} USDT")
    
    pf_emoji = "🌟" if results['profit_factor'] > 2 else "✅" if results['profit_factor'] > 1.5 else "⚠️"
    print(f"   수익 팩터:     {pf_emoji} {results['profit_factor']:>12.2f}")

def analyze_monthly_performance(results):
    """월별 성과 분석"""
    print_section("📅 월별 성과 분석")
    
    if not results['trades']:
        print("   ⚠️ 거래 내역이 없습니다.")
        return
    
    # 거래를 DataFrame으로 변환
    trades_df = pd.DataFrame(results['trades'])
    trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
    trades_df['month'] = trades_df['timestamp'].dt.to_period('M')
    
    # 월별 집계
    monthly_stats = trades_df.groupby('month').agg({
        'pnl': ['sum', 'count'],
    }).round(2)
    
    print("\n   월        총 손익(USDT)    거래 횟수")
    print("   " + "-"*45)
    
    for month, row in monthly_stats.iterrows():
        pnl = row[('pnl', 'sum')]
        count = int(row[('pnl', 'count')])
        emoji = "📈" if pnl > 0 else "📉"
        print(f"   {month}    {emoji} {pnl:>12,.2f}       {count:>3}회")

def analyze_trade_patterns(results):
    """거래 패턴 분석"""
    print_section("🎯 거래 패턴 분석")
    
    if not results['trades']:
        print("   ⚠️ 거래 내역이 없습니다.")
        return
    
    trades = results['trades']
    
    # 청산 사유별 통계
    reasons = {}
    for trade in trades:
        reason = trade.get('reason', 'unknown')
        if reason not in reasons:
            reasons[reason] = {'count': 0, 'pnl': 0}
        reasons[reason]['count'] += 1
        reasons[reason]['pnl'] += trade['pnl']
    
    print("\n   청산 사유별 통계:")
    print("   " + "-"*60)
    print("   사유              횟수      총 손익(USDT)    평균 손익")
    print("   " + "-"*60)
    
    reason_names = {
        'take_profit': '익절 💰',
        'stop_loss': '손절 🛑',
        'trailing_stop': '트레일링 📊'
    }
    
    for reason, stats in sorted(reasons.items(), key=lambda x: x[1]['count'], reverse=True):
        reason_display = reason_names.get(reason, reason)
        avg_pnl = stats['pnl'] / stats['count']
        emoji = "✅" if avg_pnl > 0 else "❌"
        print(f"   {reason_display:<15} {stats['count']:>4}회  {emoji} {stats['pnl']:>12,.2f}   {avg_pnl:>10,.2f}")
    
    # 롱/숏 성과
    print("\n   포지션 방향별 성과:")
    print("   " + "-"*60)
    
    long_trades = [t for t in trades if t['side'] == 'buy']
    short_trades = [t for t in trades if t['side'] == 'sell']
    
    if long_trades:
        long_pnl = sum(t['pnl'] for t in long_trades)
        long_wins = sum(1 for t in long_trades if t['pnl'] > 0)
        long_winrate = (long_wins / len(long_trades)) * 100
        print(f"   롱 포지션 📈:  {len(long_trades):>3}회  |  손익: {long_pnl:>12,.2f} USDT  |  승률: {long_winrate:.1f}%")
    
    if short_trades:
        short_pnl = sum(t['pnl'] for t in short_trades)
        short_wins = sum(1 for t in short_trades if t['pnl'] > 0)
        short_winrate = (short_wins / len(short_trades)) * 100
        print(f"   숏 포지션 📉:  {len(short_trades):>3}회  |  손익: {short_pnl:>12,.2f} USDT  |  승률: {short_winrate:.1f}%")
    
    # 최고/최악 거래
    print("\n   🏆 베스트 거래 TOP 3:")
    best_trades = sorted(trades, key=lambda x: x['pnl'], reverse=True)[:3]
    for i, trade in enumerate(best_trades, 1):
        side_emoji = "📈" if trade['side'] == 'buy' else "📉"
        print(f"   {i}. {side_emoji} {trade['side'].upper():4s} | "
              f"진입: ${trade['entry_price']:>10,.2f} | "
              f"청산: ${trade['exit_price']:>10,.2f} | "
              f"수익: ${trade['pnl']:>10,.2f}")
    
    print("\n   😢 최악 거래 TOP 3:")
    worst_trades = sorted(trades, key=lambda x: x['pnl'])[:3]
    for i, trade in enumerate(worst_trades, 1):
        side_emoji = "📈" if trade['side'] == 'buy' else "📉"
        print(f"   {i}. {side_emoji} {trade['side'].upper():4s} | "
              f"진입: ${trade['entry_price']:>10,.2f} | "
              f"청산: ${trade['exit_price']:>10,.2f} | "
              f"손실: ${trade['pnl']:>10,.2f}")

def run_quarterly_comparison():
    """분기별 비교"""
    print_header("📊 2024년 분기별 성과 비교")
    
    df = load_btc_data_2024()
    if df is None:
        return
    
    quarters = [
        ('Q1', '2024-01-01', '2024-03-31'),
        ('Q2', '2024-04-01', '2024-06-30'),
        ('Q3', '2024-07-01', '2024-09-30'),
        ('Q4', '2024-10-01', '2024-12-31')
    ]
    
    results_list = []
    
    for quarter, start, end in quarters:
        print(f"\n{'─'*70}")
        print(f"   {quarter} ({start} ~ {end})")
        print(f"{'─'*70}")
        
        # 봇 생성
        bot = AdvancedMAMLBot(initial_balance=10000, leverage=20)
        bot.params['ma_short'] = 5
        bot.params['ma_long'] = 20
        bot.params['stop_loss_pct'] = 0.01
        bot.params['take_profit_pct'] = 0.03
        
        try:
            result = bot.run_backtest(df, start_date=start, end_date=end)
            
            if 'error' not in result:
                results_list.append({
                    'quarter': quarter,
                    'return': result['total_return'],
                    'trades': result['total_trades'],
                    'win_rate': result['win_rate'],
                    'sharpe': result['sharpe_ratio']
                })
                
                emoji = "🚀" if result['total_return'] > 0 else "📉"
                print(f"   수익률: {emoji} {result['total_return']:>8.2f}% | "
                      f"거래: {result['total_trades']:>3}회 | "
                      f"승률: {result['win_rate']:>5.1f}% | "
                      f"샤프: {result['sharpe_ratio']:>5.2f}")
        except Exception as e:
            print(f"   ❌ 오류: {e}")
    
    # 분기별 요약
    if results_list:
        print(f"\n{'='*70}")
        print("   📈 분기별 요약")
        print(f"{'='*70}")
        
        best_q = max(results_list, key=lambda x: x['return'])
        print(f"   🏆 최고 수익률: {best_q['quarter']} ({best_q['return']:+.2f}%)")
        
        avg_return = sum(r['return'] for r in results_list) / len(results_list)
        print(f"   📊 평균 수익률: {avg_return:+.2f}%")
        
        total_trades = sum(r['trades'] for r in results_list)
        print(f"   📈 총 거래 횟수: {total_trades}회")

if __name__ == "__main__":
    import sys
    
    # 인코딩 설정 (Windows)
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    
    # 메인 메뉴
    print_header("🤖 Advanced MA ML Bot - 2024 백테스트")
    print("   1️⃣  2024년 전체 백테스트")
    print("   2️⃣  분기별 성과 비교")
    print("   3️⃣  둘 다 실행")
    print()
    
    choice = input("   선택 (1/2/3): ").strip()
    
    if choice == '1':
        run_full_year_backtest()
    elif choice == '2':
        run_quarterly_comparison()
    elif choice == '3':
        run_full_year_backtest()
        run_quarterly_comparison()
    else:
        print("   ❌ 잘못된 선택입니다.")
    
    print("\n" + "="*70)
    print("   ✅ 백테스트 완료!")
    print("="*70 + "\n")

