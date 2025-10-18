#-*-coding:utf-8 -*-
'''
다중 전략 포트폴리오 실행 스크립트
=====================================

=== 사용법 ===
python run_multi_strategy.py --start 2024-01-01 --end 2024-12-31 --capital 100000

=== 주요 기능 ===
1. 10개 전략 동시 실행
2. 자산 100등분 및 동적 배분
3. 승률 기반 전략 활성화/비활성화
4. 실시간 성과 모니터링
5. 자동 리밸런싱
'''

import os
import sys
import argparse
from datetime import datetime
import json

# Windows에서 이모지 출력을 위한 인코딩 설정
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

# 표준 출력 인코딩 강제 설정
if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

from multi_strategy_portfolio_manager import MultiStrategyPortfolioManager

def print_banner():
    """배너 출력"""
    print("=" * 80)
    print("🚀 다중 전략 포트폴리오 관리 시스템")
    print("=" * 80)
    print("📊 10개 전략 동시 실행")
    print("💰 자산 100등분 및 동적 배분")
    print("🎯 승률 기반 전략 활성화/비활성화")
    print("🔄 실시간 성과 모니터링 및 리밸런싱")
    print("=" * 80)

def print_strategy_info():
    """전략 정보 출력"""
    print("\n📋 지원 전략 목록:")
    print("-" * 50)
    
    strategies = [
        ("1. 변동성돌파", "변동성 기반 돌파 전략", "1h"),
        ("2. 모멘텀", "가격 모멘텀 추종 전략", "1h"),
        ("3. 스윙", "스윙 고점/저점 돌파 전략", "4h"),
        ("4. 브레이크아웃", "저항선/지지선 돌파 전략", "1h"),
        ("5. 스캘핑", "단기 이동평균 교차 전략", "1m"),
        ("6. RSI", "RSI 과매수/과매도 전략", "1h"),
        ("7. MACD", "MACD 신호선 교차 전략", "1h"),
        ("8. 볼린저밴드", "볼린저밴드 이탈 전략", "1h"),
        ("9. 이동평균", "이동평균 교차 전략", "1h"),
        ("10. 스토캐스틱", "스토캐스틱 과매수/과매도 전략", "1h")
    ]
    
    for strategy, description, timeframe in strategies:
        print(f"{strategy:<15} | {description:<25} | {timeframe}")
    
    print("-" * 50)

def print_allocation_info():
    """자본 배분 정보 출력"""
    print("\n💰 자본 배분 전략:")
    print("-" * 50)
    print("• 초기: 10개 전략에 균등 배분 (각 10%)")
    print("• 동적 배분: 성과에 따라 1% ~ 20% 범위에서 조정")
    print("• 비활성화: 성과가 -50% 이하 또는 승률 30% 이하")
    print("• 재활성화: 성과가 양수이고 승률 50% 이상")
    print("• 리밸런싱: 주간 단위로 자동 실행")
    print("-" * 50)

def run_backtest(args):
    """백테스트 실행"""
    print(f"\n🚀 백테스트 시작!")
    print(f"📅 기간: {args.start} ~ {args.end}")
    print(f"💰 초기 자본: {args.capital:,} USDT")
    print(f"📊 심볼: {args.symbol}")
    print(f"⏰ 시간프레임: {args.timeframe}")
    print(f"🔄 리밸런싱 주기: {args.rebalance}시간")
    
    # 포트폴리오 관리자 생성
    portfolio_manager = MultiStrategyPortfolioManager(
        initial_capital=args.capital,
        rebalance_frequency=args.rebalance
    )
    
    # 백테스트 실행
    start_time = datetime.now()
    portfolio_manager.run_backtest(
        symbol=args.symbol,
        timeframe=args.timeframe,
        start_date=args.start,
        end_date=args.end
    )
    end_time = datetime.now()
    
    # 실행 시간 계산
    execution_time = end_time - start_time
    
    print(f"\n⏱️ 실행 시간: {execution_time}")
    
    # 성과 차트 생성
    portfolio_manager.create_performance_chart()
    
    return portfolio_manager

def print_results(portfolio_manager):
    """결과 출력"""
    print("\n" + "=" * 80)
    print("📈 백테스트 결과 요약")
    print("=" * 80)
    
    # 포트폴리오 전체 성과
    print(f"💰 초기 자본: {portfolio_manager.initial_capital:,.2f} USDT")
    print(f"💰 최종 자본: {portfolio_manager.current_capital:,.2f} USDT")
    print(f"📈 총 수익률: {portfolio_manager.total_return:.2f}%")
    print(f"📉 최대 낙폭: {portfolio_manager.max_drawdown:.2f}%")
    print(f"📊 샤프 비율: {portfolio_manager.sharpe_ratio:.2f}")
    print(f"🎯 승률: {portfolio_manager.win_rate:.1f}%")
    
    print("\n📋 전략별 성과:")
    print("-" * 80)
    print(f"{'전략명':<15} {'상태':<8} {'배분':<8} {'수익률':<10} {'승률':<8} {'거래수':<8}")
    print("-" * 80)
    
    for name, strategy in portfolio_manager.strategies.items():
        status = "활성" if strategy.is_active else "비활성"
        allocation = f"{strategy.current_allocation*100:.1f}%"
        return_pct = f"{strategy.total_return:.1f}%"
        win_rate = f"{strategy.win_rate:.1f}%"
        trades = str(strategy.total_trades)
        
        print(f"{strategy.name:<15} {status:<8} {allocation:<8} {return_pct:<10} {win_rate:<8} {trades:<8}")
    
    print("-" * 80)

def save_summary_report(portfolio_manager, args):
    """요약 보고서 저장"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 요약 데이터 생성
    summary_data = {
        'timestamp': timestamp,
        'parameters': {
            'symbol': args.symbol,
            'timeframe': args.timeframe,
            'start_date': args.start,
            'end_date': args.end,
            'initial_capital': args.capital,
            'rebalance_frequency': args.rebalance
        },
        'portfolio_performance': {
            'initial_capital': portfolio_manager.initial_capital,
            'final_capital': portfolio_manager.current_capital,
            'total_return': portfolio_manager.total_return,
            'max_drawdown': portfolio_manager.max_drawdown,
            'sharpe_ratio': portfolio_manager.sharpe_ratio,
            'win_rate': portfolio_manager.win_rate
        },
        'strategy_performance': {}
    }
    
    # 전략별 성과 추가
    for name, strategy in portfolio_manager.strategies.items():
        summary_data['strategy_performance'][name] = {
            'name': strategy.name,
            'is_active': strategy.is_active,
            'current_allocation': strategy.current_allocation,
            'total_return': strategy.total_return,
            'max_drawdown': strategy.max_drawdown,
            'win_rate': strategy.win_rate,
            'sharpe_ratio': strategy.sharpe_ratio,
            'total_trades': strategy.total_trades,
            'winning_trades': strategy.winning_trades,
            'losing_trades': strategy.losing_trades
        }
    
    # JSON 파일로 저장
    os.makedirs('logs', exist_ok=True)
    summary_file = f'logs/multi_strategy_summary_{timestamp}.json'
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n💾 요약 보고서 저장: {summary_file}")

def main():
    """메인 함수"""
    # 배너 출력
    print_banner()
    
    # 인수 파싱
    parser = argparse.ArgumentParser(description='다중 전략 포트폴리오 관리 시스템')
    parser.add_argument('--symbol', default='BTCUSDT', help='거래 심볼 (기본값: BTCUSDT)')
    parser.add_argument('--timeframe', default='1h', help='시간프레임 (기본값: 1h)')
    parser.add_argument('--start', default='2024-01-01', help='시작 날짜 (YYYY-MM-DD)')
    parser.add_argument('--end', default='2024-12-31', help='종료 날짜 (YYYY-MM-DD)')
    parser.add_argument('--capital', type=float, default=100000, help='초기 자본 (기본값: 100000)')
    parser.add_argument('--rebalance', type=int, default=24, help='리밸런싱 주기 시간 (기본값: 24)')
    parser.add_argument('--info', action='store_true', help='전략 정보만 출력하고 종료')
    
    args = parser.parse_args()
    
    # 전략 정보 출력
    if args.info:
        print_strategy_info()
        print_allocation_info()
        return
    
    # 전략 정보 출력
    print_strategy_info()
    print_allocation_info()
    
    try:
        # 백테스트 실행
        portfolio_manager = run_backtest(args)
        
        # 결과 출력
        print_results(portfolio_manager)
        
        # 요약 보고서 저장
        save_summary_report(portfolio_manager, args)
        
        print(f"\n🎉 백테스트가 성공적으로 완료되었습니다!")
        print(f"📁 결과 파일들은 'logs' 디렉토리에 저장되었습니다.")
        
    except KeyboardInterrupt:
        print(f"\n⚠️ 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 오류가 발생했습니다: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
