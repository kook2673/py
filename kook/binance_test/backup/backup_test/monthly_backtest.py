#-*-coding:utf-8 -*-
'''
2024년 2월부터 12월까지 월별 백테스트 자동 실행 스크립트
'''

import os
import sys
import importlib.util

def run_monthly_backtest():
    """월별 백테스트 실행"""
    
    # 백테스트할 월들
    months = [
        "2024_02", "2024_03", "2024_04", "2024_05", "2024_06",
        "2024_07", "2024_08", "2024_09", "2024_10", "2024_11", "2024_12"
    ]
    
    print("=" * 80)
    print("2024년 2월부터 12월까지 월별 백테스트 시작!")
    print("=" * 80)
    
    # MA_Trend_1h_Backtest.py 모듈 로드
    spec = importlib.util.spec_from_file_location("backtest_module", "MA_Trend_1h_Backtest.py")
    backtest_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backtest_module)
    
    results = {}
    
    for month in months:
        print(f"\n{'='*60}")
        print(f"🎯 {month}월 백테스트 실행 중...")
        print(f"{'='*60}")
        
        try:
            # 해당 월의 파라미터와 데이터로 백테스트 실행
            params, month_used = backtest_module.load_optimized_parameters('MA_Trend_Optimizer_1h.json', month)
            
            if not params:
                print(f"❌ {month}월 파라미터를 찾을 수 없습니다. 건너뜁니다.")
                continue
            
            # 해당 월의 데이터 로드
            script_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(script_dir, 'data', 'BTCUSDT', '1h')
            
            df_1h = backtest_module.load_1h_data(data_dir, month)
            if df_1h is None:
                print(f"❌ {month}월 데이터를 로드할 수 없습니다. 건너뜁니다.")
                continue
            
            # 백테스트 실행
            backtest_result = backtest_module.backtest_ma_strategy(df_1h, params, 10000, 7)
            
            if backtest_result:
                # 결과 저장
                results[month] = {
                    'ma1': backtest_result['ma1'],
                    'ma2': backtest_result['ma2'],
                    'total_return': backtest_result['total_return'],
                    'final_equity': backtest_result['final_equity'],
                    'trade_count': backtest_result['trade_count'],
                    'win_rate': backtest_result['win_trades'] / backtest_result['trade_count'] * 100 if backtest_result['trade_count'] > 0 else 0,
                    'mdd': backtest_result['mdd']
                }
                
                print(f"✅ {month}월 백테스트 완료!")
                print(f"   MA 설정: MA{backtest_result['ma1']} / MA{backtest_result['ma2']}")
                print(f"   수익률: {backtest_result['total_return']:.2f}%")
                print(f"   최종 자본: {backtest_result['final_equity']:,.0f} USDT")
                print(f"   거래 횟수: {backtest_result['trade_count']}회")
                print(f"   승률: {results[month]['win_rate']:.1f}%")
                print(f"   MDD: {backtest_result['mdd']:.2f}%")
                
            else:
                print(f"❌ {month}월 백테스트 실패")
                
        except Exception as e:
            print(f"❌ {month}월 백테스트 중 오류 발생: {e}")
            continue
    
    # 전체 결과 요약
    print(f"\n{'='*80}")
    print("📊 월별 백테스트 전체 결과 요약")
    print(f"{'='*80}")
    
    if results:
        print(f"{'월':<8} {'MA설정':<12} {'수익률':<8} {'최종자본':<12} {'거래횟수':<8} {'승률':<6} {'MDD':<6}")
        print("-" * 80)
        
        total_return_sum = 0
        total_trades = 0
        total_wins = 0
        
        for month, result in results.items():
            print(f"{month:<8} MA{result['ma1']}/{result['ma2']:<12} {result['total_return']:>6.2f}% {result['final_equity']:>10,.0f} {result['trade_count']:>6}회 {result['win_rate']:>5.1f}% {result['mdd']:>5.1f}%")
            total_return_sum += result['total_return']
            total_trades += result['trade_count']
            total_wins += result['trade_count'] * result['win_rate'] / 100
        
        avg_return = total_return_sum / len(results)
        avg_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
        
        print("-" * 80)
        print(f"평균 수익률: {avg_return:.2f}%")
        print(f"총 거래 횟수: {total_trades}회")
        print(f"평균 승률: {avg_win_rate:.1f}%")
        print(f"성공한 월: {len([r for r in results.values() if r['total_return'] > 0])}개")
        print(f"실패한 월: {len([r for r in results.values() if r['total_return'] <= 0])}개")
        
        # 최고 성과 월
        best_month = max(results.items(), key=lambda x: x[1]['total_return'])
        print(f"최고 성과: {best_month[0]}월 ({best_month[1]['total_return']:.2f}%)")
        
        # 최저 성과 월
        worst_month = min(results.items(), key=lambda x: x[1]['total_return'])
        print(f"최저 성과: {worst_month[0]}월 ({worst_month[1]['total_return']:.2f}%)")
        
    else:
        print("❌ 성공한 백테스트가 없습니다.")
    
    print(f"\n{'='*80}")
    print("월별 백테스트 완료!")
    print(f"{'='*80}")

if __name__ == "__main__":
    run_monthly_backtest()
