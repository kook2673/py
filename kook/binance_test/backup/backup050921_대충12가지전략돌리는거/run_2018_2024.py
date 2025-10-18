#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2018-2024년 연속 백테스트 간단 실행
"""

from advanced_ma_ml_bot_fast import AdvancedMAMLBotFast

def main():
    print("🚀 2018-2024년 연속 백테스트 시작!")
    print("=" * 60)
    
    # 봇 생성 (더 안전한 설정)
    bot = AdvancedMAMLBotFast(initial_balance=10000, leverage=5)  # 레버리지 5배로 감소
    
    # 연속 백테스트 실행
    try:
        results = bot.run_continuous_backtest(2018, 2024)
        
        if 'error' in results:
            print(f"❌ 백테스트 실패: {results['error']}")
            return
        
        print(f"\n🎯 최종 결과:")
        print(f"💰 초기 자본: ${results['initial_balance']:,.0f}")
        print(f"💰 최종 자본: ${results['final_balance']:,.0f}")
        print(f"📈 전체 수익률: {results['total_return']:.2f}%")
        print(f"📊 평균 연간 수익률: {results['avg_yearly_return']:.2f}%")
        print(f"📉 최대 낙폭: {results['max_drawdown']:.2f}%")
        print(f"📊 총 거래 횟수: {results['total_trades']:,}회")
        print(f"📊 평균 승률: {results['avg_win_rate']:.1f}%")
        
    except Exception as e:
        print(f"❌ 실행 오류: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
