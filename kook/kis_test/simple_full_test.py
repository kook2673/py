# -*- coding: utf-8 -*-
"""
간단한 전체 기간 테스트
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from KIS_Common import GetRSI

def test_single_stock(csv_path, stock_name):
    """단일 종목 백테스팅"""
    print(f"\n{'='*60}")
    print(f"=== {stock_name} RSI 매매 전략 백테스팅 ===")
    print(f"{'='*60}")
    
    # 데이터 로드
    print(f"데이터 로드: {csv_path}")
    
    df = pd.read_csv(csv_path)
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    df.columns = df.columns.str.lower()
    
    print(f"전체 데이터: {len(df)}개 일자")
    print(f"기간: {df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}")
    print(f"약 {len(df)/365:.1f}년의 데이터")
    
    # 백테스팅 설정
    initial_capital = 10_000_000  # 1,000만원
    buy_unit = 10  # 매수단위 (기본값: 10개)
    buy_threshold_very_low = 20  # RSI < 20에서 3배수 매수
    buy_threshold_low = 30  # RSI 20~30에서 2배수 매수
    buy_threshold_high = 40  # RSI 30~40에서 1배수 매수
    sell_threshold_70 = 70  # RSI 70~80에서 2배수 매도
    sell_threshold_80 = 80  # RSI >= 80에서 3배수 매도
    
    print(f"\n=== 백테스팅 설정 ===")
    print(f"초기 자본: {initial_capital:,}원")
    print(f"매수단위: {buy_unit}개")
    print(f"매수 조건: RSI < 20 → {buy_unit*3}개, RSI 20~30 → {buy_unit*2}개, RSI 30~40 → {buy_unit}개")
    print(f"매도 조건: RSI 70~80 → {buy_unit*2}개 (수익시만), RSI >= 80 → {buy_unit*3}개 (수익시만)")
    
    # 백테스팅 실행
    cash = initial_capital
    shares_held = 0
    total_cost = 0  # 총 매수 비용 (평단가 계산용)
    max_shares_held = 0  # 최대 보유 주식 수 추적
    trades = []
    rsi_period = 14
    
    print(f"\n=== 백테스팅 실행 ===")
    
    for i in range(rsi_period, len(df)):
        try:
            rsi = GetRSI(df, rsi_period, i)
            if pd.isna(rsi):
                continue
                
            current_price = df['close'].iloc[i]
            current_date = df.index[i]
            
            # 매수 신호 처리
            shares_to_buy = 0
            if rsi < buy_threshold_very_low:  # RSI < 20: 3배수 매수
                shares_to_buy = buy_unit * 3
            elif rsi < buy_threshold_low:  # RSI 20~30: 2배수 매수
                shares_to_buy = buy_unit * 2
            elif rsi <= buy_threshold_high:  # RSI 30~40: 1배수 매수
                shares_to_buy = buy_unit
            
            if shares_to_buy > 0 and cash >= current_price * shares_to_buy:
                cost = current_price * shares_to_buy
                cash -= cost
                shares_held += shares_to_buy
                total_cost += cost  # 총 매수 비용 누적
                max_shares_held = max(max_shares_held, shares_held)  # 최대 보유 수 업데이트
                
                # 평단가 계산
                avg_price = total_cost / shares_held if shares_held > 0 else 0
                # 수익률 계산
                profit_rate = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
                # 보유금액 계산
                holding_value = shares_held * current_price
                
                trades.append({
                    'date': current_date,
                    'action': 'BUY',
                    'price': current_price,
                    'shares': shares_to_buy,
                    'amount': cost,
                    'rsi': rsi,
                    'cash_after': cash,
                    'shares_after': shares_held
                })
                
                profit_sign = "+" if profit_rate >= 0 else ""
                print(f"\033[92m{current_date.strftime('%Y-%m-%d')}: [보유: {shares_held}주][평단가: {avg_price:,.0f}원: {profit_sign}{profit_rate:.1f}%][보유금액: {holding_value:,.0f}원] @ {current_price:,.0f}원 (RSI: {rsi:.1f}) +{shares_to_buy}주\033[0m")
            
            # 매도 신호 처리 (수익률 체크 추가)
            shares_to_sell = 0
            if shares_held > 0:
                # 평단가 계산
                avg_price = total_cost / shares_held if shares_held > 0 else 0
                # 현재 수익률 계산
                profit_rate = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
                
                # RSI >= 80: 3배수 매도 (단, 수익 상태일 때만)
                if rsi >= sell_threshold_80 and shares_held >= buy_unit * 3 and profit_rate > 0:
                    shares_to_sell = buy_unit * 3
                # RSI 70~80: 2배수 매도 (단, 수익 상태일 때만)
                elif rsi >= sell_threshold_70 and shares_held >= buy_unit * 2 and profit_rate > 0:
                    shares_to_sell = buy_unit * 2
            
            if shares_to_sell > 0:
                proceeds = current_price * shares_to_sell
                cash += proceeds
                
                # 매도 시 평단가 조정 (FIFO 방식)
                sold_cost = (total_cost / shares_held) * shares_to_sell
                total_cost -= sold_cost
                shares_held -= shares_to_sell
                
                # 평단가 계산
                avg_price = total_cost / shares_held if shares_held > 0 else 0
                # 수익률 계산
                profit_rate = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
                # 보유금액 계산
                holding_value = shares_held * current_price
                
                trades.append({
                    'date': current_date,
                    'action': 'SELL',
                    'price': current_price,
                    'shares': shares_to_sell,
                    'amount': proceeds,
                    'rsi': rsi,
                    'cash_after': cash,
                    'shares_after': shares_held
                })
                
                profit_sign = "+" if profit_rate >= 0 else ""
                print(f"\033[91m{current_date.strftime('%Y-%m-%d')}: [보유: {shares_held}주][평단가: {avg_price:,.0f}원: {profit_sign}{profit_rate:.1f}%][보유금액: {holding_value:,.0f}원] @ {current_price:,.0f}원 (RSI: {rsi:.1f}) -{shares_to_sell}주\033[0m")
                
        except Exception as e:
            continue
    
    # 최종 결과 계산
    final_price = df['close'].iloc[-1]
    final_value = cash + (shares_held * final_price)
    total_return = (final_value - initial_capital) / initial_capital * 100
    
    print(f"\n=== {stock_name} 백테스팅 결과 ===")
    print(f"총 거래 횟수: {len(trades)}회")
    print(f"매수 거래: {len([t for t in trades if t['action'] == 'BUY'])}회")
    print(f"매도 거래: {len([t for t in trades if t['action'] == 'SELL'])}회")
    print(f"최대 보유 주식: {max_shares_held}주")
    print(f"보유 현금: {cash:,.0f}원")
    print(f"보유 주식: {shares_held}주")
    print(f"최종 주가: {final_price:,.0f}원")
    print(f"최종 자산: {final_value:,.0f}원")
    print(f"총 수익률: {total_return:.2f}%")
    
    # 연평균 수익률
    years = len(df) / 365
    annual_return = (final_value / initial_capital) ** (1/years) - 1
    print(f"연평균 수익률: {annual_return:.2%}")
    
    # Buy & Hold 비교
    buy_hold_value = initial_capital * (final_price / df['close'].iloc[0])
    buy_hold_return = (buy_hold_value - initial_capital) / initial_capital * 100
    print(f"\n=== {stock_name} Buy & Hold 비교 ===")
    print(f"Buy & Hold 최종 자산: {buy_hold_value:,.0f}원")
    print(f"Buy & Hold 수익률: {buy_hold_return:.2f}%")
    print(f"전략 대비 차이: {total_return - buy_hold_return:.2f}%p")
    
    # 결과 반환
    return {
        'stock_name': stock_name,
        'total_trades': len(trades),
        'buy_trades': len([t for t in trades if t['action'] == 'BUY']),
        'sell_trades': len([t for t in trades if t['action'] == 'SELL']),
        'max_shares_held': max_shares_held,
        'final_cash': cash,
        'final_shares': shares_held,
        'final_price': final_price,
        'final_value': final_value,
        'total_return': total_return,
        'annual_return': annual_return,
        'buy_hold_return': buy_hold_return,
        'strategy_vs_buyhold': total_return - buy_hold_return
    }

def test_full_period():
    """전체 종목 백테스팅"""
    print("=== RSI 매매 전략 백테스팅 (다중 종목) ===")
    
    # 테스트할 종목 리스트
    stocks = [
        {
            'csv_path': 'data/etf_index/122630_KODEX 레버리지.csv',
            'name': 'KODEX 레버리지 (122630)'
        },
        {
            'csv_path': 'data/etf_index/233740_KODEX 코스닥150레버리지.csv', 
            'name': 'KODEX 코스닥150레버리지 (233740)'
        }
    ]
    
    results = []
    
    # 각 종목별로 백테스팅 실행
    for stock in stocks:
        try:
            result = test_single_stock(stock['csv_path'], stock['name'])
            results.append(result)
        except FileNotFoundError:
            print(f"\n❌ 파일을 찾을 수 없습니다: {stock['csv_path']}")
            print(f"   {stock['name']} 스킵합니다.")
        except Exception as e:
            print(f"\n❌ {stock['name']} 백테스팅 중 오류 발생: {e}")
    
    # 전체 결과 요약
    if results:
        print(f"\n{'='*80}")
        print("=== 전체 종목 결과 요약 ===")
        print(f"{'='*80}")
        
        print(f"{'종목명':<25} {'총수익률':<10} {'연평균수익률':<12} {'Buy&Hold':<10} {'차이':<8}")
        print("-" * 80)
        
        for result in results:
            print(f"{result['stock_name']:<25} "
                  f"{result['total_return']:>8.2f}% "
                  f"{result['annual_return']:>10.2%} "
                  f"{result['buy_hold_return']:>8.2f}% "
                  f"{result['strategy_vs_buyhold']:>+6.2f}%p")
        
        # 평균 수익률 계산
        avg_strategy_return = sum(r['total_return'] for r in results) / len(results)
        avg_buyhold_return = sum(r['buy_hold_return'] for r in results) / len(results)
        avg_difference = avg_strategy_return - avg_buyhold_return
        
        print("-" * 80)
        print(f"{'평균':<25} "
              f"{avg_strategy_return:>8.2f}% "
              f"{'':>12} "
              f"{avg_buyhold_return:>8.2f}% "
              f"{avg_difference:>+6.2f}%p")
        
        print(f"\n총 {len(results)}개 종목 테스트 완료")
    else:
        print("\n❌ 테스트할 수 있는 종목이 없습니다.")

if __name__ == "__main__":
    test_full_period()
