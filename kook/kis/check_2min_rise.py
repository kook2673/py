#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from KIS_API_Helper_KR import *
import KIS_Common as Common
import pandas as pd
from datetime import datetime
from pytz import timezone
import time

# DantaBot에서 함수 import
from DantaBot import fetch_rising_stocks

# KIS API 모드 설정
Common.SetChangeMode("REAL")

def check_2min_rise():
    """변동률 상위 종목 중 5번 연속 상승 패턴 분석"""
    
    print("=== 변동률 상위 종목 중 5번 연속 상승 패턴 분석 ===")
    print("조건: 5번 연속 상승 + 거래대금 증가")
    print(f"분석 시간: {datetime.now(timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # 변동률 순위로 상위 30개 종목 조회
        stocks = fetch_rising_stocks(30, "J", "4")  # J: KRX, 4: 변동율순
        
        if not stocks:
            print("❌ 종목 조회 실패")
            return
        
        print(f"✅ 변동률 순위 상위 {len(stocks)}개 종목 조회 성공")
        print()
        
        consecutive_rise_stocks = []
        
        for i, stock in enumerate(stocks, 1):
            code = stock.get('code', '')
            name = stock.get('name', '')
            current_price = float(stock.get('price', 0))
            current_pct = float(stock.get('pct', 0))
            current_volume = float(stock.get('volume', 0))
            
            print(f"--- {i}/{len(stocks)}: {name} ({code}) ---")
            print(f"현재 가격: {current_price:,}원, 변동률: {current_pct:.2f}%, 거래량: {current_volume:,.0f}주")
            
            try:
                # 1분봉 데이터 가져오기
                df = GetOhlcvMinute(code, '1T', 50)  # 최근 50분 데이터
                
                if df is not None and not df.empty:
                    # 9시 이후 데이터만 필터링
                    df['datetime'] = pd.to_datetime(df.index, format='%H%M%S')
                    df = df[df['datetime'].dt.hour >= 9].copy()
                    df = df.sort_values('datetime')  # 시간순 정렬
                    
                    if len(df) >= 8:  # 최소 8분 데이터 필요 (5분 상승 + 구매 후 확인)
                        print(f"  9시부터 {len(df)}분 데이터 확인")
                        
                        # 5번 연속 상승 패턴 찾기
                        pattern = find_consecutive_rise_pattern(df, current_price, current_volume)
                        
                        if pattern:
                            print(f"  ✅ 5번 연속 상승 패턴 발견!")
                            print(f"     구매 시점: {pattern['buy_time'].strftime('%H:%M')} (가격: {pattern['buy_price']:,}원)")
                            print(f"     연속 상승률: {[f'{x:+.2f}%' for x in pattern['consecutive_changes']]}")
                            print(f"     거래대금 증가: {pattern['volume_increase']:+.1f}%")
                            print(f"     구매 후 최대 상승률: {pattern['max_profit']:+.2f}%")
                            print(f"     구매 후 최대 하락률: {pattern['max_loss']:+.2f}%")
                            print(f"     매도 시점: {pattern['sell_time'].strftime('%H:%M')} (가격: {pattern['sell_price']:,}원)")
                            print(f"     최종 수익률: {pattern['final_profit']:+.2f}%")
                            
                            consecutive_rise_stocks.append({
                                'code': code,
                                'name': name,
                                'current_price': current_price,
                                'current_pct': current_pct,
                                'pattern': pattern
                            })
                        else:
                            print(f"  ❌ 5번 연속 상승 패턴 없음")
                    else:
                        print(f"  ❌ 데이터 부족 (8분 미만)")
                else:
                    print(f"  ❌ 1분봉 데이터 없음")
                    
            except Exception as e:
                print(f"  ❌ 오류 발생: {e}")
            
            print()
            time.sleep(0.3)  # API 호출 간격 조절
        
        # 결과 요약
        print("=" * 60)
        print("=== 5번 연속 상승 패턴 요약 ===")
        print(f"총 {len(consecutive_rise_stocks)}개 종목에서 패턴 발견")
        print()
        
        if consecutive_rise_stocks:
            # 최종 수익률 기준으로 정렬
            sorted_stocks = sorted(consecutive_rise_stocks, 
                                 key=lambda x: x['pattern']['final_profit'], reverse=True)
            
            print("5번 연속 상승 패턴 순위:")
            for i, stock in enumerate(sorted_stocks, 1):
                pattern = stock['pattern']
                print(f"{i:2d}. {stock['name']} ({stock['code']})")
                print(f"    현재 변동률: {stock['current_pct']:+.2f}%")
                print(f"    구매 시점: {pattern['buy_time'].strftime('%H:%M')} (가격: {pattern['buy_price']:,}원)")
                print(f"    연속 상승률: {[f'{x:+.2f}%' for x in pattern['consecutive_changes']]}")
                print(f"    거래대금 증가: {pattern['volume_increase']:+.1f}%")
                print(f"    구매 후 최대 상승률: {pattern['max_profit']:+.2f}%")
                print(f"    구매 후 최대 하락률: {pattern['max_loss']:+.2f}%")
                print(f"    매도 시점: {pattern['sell_time'].strftime('%H:%M')} (가격: {pattern['sell_price']:,}원)")
                print(f"    최종 수익률: {pattern['final_profit']:+.2f}%")
                print()
            
            # 통계 분석
            final_profits = [s['pattern']['final_profit'] for s in consecutive_rise_stocks]
            max_profits = [s['pattern']['max_profit'] for s in consecutive_rise_stocks]
            max_losses = [s['pattern']['max_loss'] for s in consecutive_rise_stocks]
            volume_increases = [s['pattern']['volume_increase'] for s in consecutive_rise_stocks]
            
            print("=== 통계 분석 ===")
            print(f"평균 최종 수익률: {sum(final_profits)/len(final_profits):+.2f}%")
            print(f"평균 구매 후 최대 상승률: {sum(max_profits)/len(max_profits):+.2f}%")
            print(f"평균 구매 후 최대 하락률: {sum(max_losses)/len(max_losses):+.2f}%")
            print(f"평균 거래대금 증가율: {sum(volume_increases)/len(volume_increases):+.1f}%")
            
            positive_returns = [p for p in final_profits if p > 0]
            negative_returns = [p for p in final_profits if p <= 0]
            print(f"수익 종목: {len(positive_returns)}개 ({len(positive_returns)/len(final_profits)*100:.1f}%)")
            print(f"손실 종목: {len(negative_returns)}개 ({len(negative_returns)/len(final_profits)*100:.1f}%)")
            
            high_volume_increase = [v for v in volume_increases if v >= 50]  # 50% 이상 증가
            print(f"거래대금 50% 이상 증가: {len(high_volume_increase)}개")
            
            # 수익률 분포
            high_profit = [s for s in consecutive_rise_stocks if s['pattern']['final_profit'] >= 2.0]  # 2% 이상
            medium_profit = [s for s in consecutive_rise_stocks if 0 < s['pattern']['final_profit'] < 2.0]  # 0-2%
            loss = [s for s in consecutive_rise_stocks if s['pattern']['final_profit'] <= 0]  # 손실
            
            print(f"고수익 (2% 이상): {len(high_profit)}개")
            print(f"중수익 (0-2%): {len(medium_profit)}개")
            print(f"손실: {len(loss)}개")
            
            # 매도 전략별 분석
            partial_sell_1pct = [s for s in consecutive_rise_stocks if s['pattern']['sell_reason'] == 'partial_sell_1pct']
            partial_sell_2pct = [s for s in consecutive_rise_stocks if s['pattern']['sell_reason'] == 'partial_sell_2pct']
            stop_loss = [s for s in consecutive_rise_stocks if s['pattern']['sell_reason'] == 'stop_loss']
            time_out = [s for s in consecutive_rise_stocks if s['pattern']['sell_reason'] == 'time_out']
            
            print(f"\n=== 매도 전략별 분석 ===")
            print(f"1%에서 50% 매도: {len(partial_sell_1pct)}개")
            print(f"2%에서 나머지 50% 매도: {len(partial_sell_2pct)}개")
            print(f"손절매 (1% 하락): {len(stop_loss)}개")
            print(f"시간 만료 (30분): {len(time_out)}개")
            
            # 분할매도 효과 분석
            if partial_sell_1pct:
                partial_1pct_profits = [s['pattern']['final_profit'] for s in partial_sell_1pct]
                print(f"1%에서 50% 매도 평균 수익률: {sum(partial_1pct_profits)/len(partial_1pct_profits):+.2f}%")
            
            if partial_sell_2pct:
                partial_2pct_profits = [s['pattern']['final_profit'] for s in partial_sell_2pct]
                print(f"2%에서 나머지 50% 매도 평균 수익률: {sum(partial_2pct_profits)/len(partial_2pct_profits):+.2f}%")
            
        else:
            print("5번 연속 상승 패턴이 없습니다.")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

def find_consecutive_rise_pattern(df, current_price, current_volume):
    """3번 연속 상승 + 거래대금 증가 패턴 찾기"""
    
    for start_idx in range(len(df) - 5):  # 충분한 후속 데이터 확보
        # 3번 연속 상승 확인
        if start_idx + 3 >= len(df):
            continue
            
        # 첫 번째 상승
        first_price = df.iloc[start_idx]['close']
        second_price = df.iloc[start_idx + 1]['close']
        first_rise = (second_price - first_price) / first_price * 100
        
        # 두 번째 상승
        third_price = df.iloc[start_idx + 2]['close']
        second_rise = (third_price - second_price) / second_price * 100
        
        # 세 번째 상승
        fourth_price = df.iloc[start_idx + 3]['close']
        third_rise = (fourth_price - third_price) / third_price * 100
        
        # 3번 연속 상승 확인
        if first_rise > 0 and second_rise > 0 and third_rise > 0:
            # 구매 시점 (세 번째 상승 후)
            buy_time = df.iloc[start_idx + 3]['datetime']
            buy_price = fourth_price
            
            # 거래대금 증가 확인
            first_volume = df.iloc[start_idx]['volume']
            second_volume = df.iloc[start_idx + 1]['volume']
            third_volume = df.iloc[start_idx + 2]['volume']
            avg_amount_before = (first_price * first_volume + second_price * second_volume + third_price * third_volume) / 3
            current_amount = current_price * current_volume
            volume_increase = (current_amount - avg_amount_before) / avg_amount_before * 100
            
            # 거래대금 증가 조건 (20% 이상)
            if volume_increase >= 20:
                # 구매 후 매도 시뮬레이션
                sell_result = simulate_sell_strategy(df, start_idx + 3, buy_price)
                
                return {
                    'buy_time': buy_time,
                    'buy_price': buy_price,
                    'consecutive_changes': [first_rise, second_rise, third_rise],
                    'volume_increase': volume_increase,
                    'max_profit': sell_result['max_profit'],
                    'max_loss': sell_result['max_loss'],
                    'sell_time': sell_result['sell_time'],
                    'sell_price': sell_result['sell_price'],
                    'final_profit': sell_result['final_profit'],
                    'sell_reason': sell_result['sell_reason']
                }
    
    return None

def simulate_sell_strategy(df, buy_idx, buy_price):
    """구매 후 매도 전략 시뮬레이션 (1%에서 50% 매도)"""
    
    max_profit = 0
    max_loss = 0
    sell_time = None
    sell_price = buy_price
    sell_reason = 'time_out'  # 기본값: 시간 만료
    remaining_quantity = 1.0  # 전체 수량 (100%)
    sold_quantity = 0.0  # 매도한 수량
    total_profit = 0.0  # 총 수익
    
    # 구매 후 30분 동안 모니터링
    end_idx = min(buy_idx + 30, len(df))
    
    for check_idx in range(buy_idx + 1, end_idx):
        if check_idx >= len(df):
            break
            
        check_price = df.iloc[check_idx]['close']
        profit_pct = (check_price - buy_price) / buy_price * 100
        
        # 최대 수익/손실 업데이트
        if profit_pct > max_profit:
            max_profit = profit_pct
        if profit_pct < max_loss:
            max_loss = profit_pct
        
        # 매도 조건 확인
        if profit_pct >= 1.0 and sold_quantity == 0:  # 1% 도달 시 50% 매도
            sell_quantity = 0.5  # 50% 매도
            sell_time = df.iloc[check_idx]['datetime']
            sell_price = check_price
            sell_reason = 'partial_sell_1pct'
            
            # 50% 매도 수익 계산
            partial_profit = (check_price - buy_price) / buy_price * 100 * sell_quantity
            total_profit += partial_profit
            sold_quantity += sell_quantity
            remaining_quantity -= sell_quantity
            
            # 나머지 50%는 계속 보유하며 모니터링
            continue
            
        elif profit_pct >= 2.0:  # 2% 도달 시 나머지 50% 매도 (기존 방식)
            sell_quantity = remaining_quantity  # 나머지 전량 매도
            sell_time = df.iloc[check_idx]['datetime']
            sell_price = check_price
            sell_reason = 'partial_sell_2pct'
            
            # 나머지 50% 매도 수익 계산
            partial_profit = (check_price - buy_price) / buy_price * 100 * sell_quantity
            total_profit += partial_profit
            sold_quantity += sell_quantity
            remaining_quantity -= sell_quantity
            break
            
        elif profit_pct <= -1.0:  # 1% 하락 시 손절매 (전량)
            sell_time = df.iloc[check_idx]['datetime']
            sell_price = check_price
            sell_reason = 'stop_loss'
            
            # 손절매 수익 계산
            loss_profit = (check_price - buy_price) / buy_price * 100 * remaining_quantity
            total_profit += loss_profit
            break
    
    # 시간 만료 시 마지막 가격으로 매도
    if sell_reason == 'time_out':
        if end_idx < len(df):
            sell_time = df.iloc[end_idx - 1]['datetime']
            sell_price = df.iloc[end_idx - 1]['close']
        else:
            sell_time = df.iloc[-1]['datetime']
            sell_price = df.iloc[-1]['close']
        
        # 시간 만료 시 남은 수량 매도
        if remaining_quantity > 0:
            time_out_profit = (sell_price - buy_price) / buy_price * 100 * remaining_quantity
            total_profit += time_out_profit
    
    final_profit = total_profit
    
    return {
        'max_profit': max_profit,
        'max_loss': max_loss,
        'sell_time': sell_time,
        'sell_price': sell_price,
        'final_profit': final_profit,
        'sell_reason': sell_reason
    }

if __name__ == "__main__":
    check_2min_rise()
