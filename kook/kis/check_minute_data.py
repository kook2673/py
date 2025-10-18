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

# KIS API 모드 설정
Common.SetChangeMode("REAL")

def check_minute_data():
    """1분만에 3% 이상 오르는 종목의 수익률 분석"""
    
    print("=== 1분만에 3% 이상 오르는 종목 수익률 분석 ===")
    print(f"분석 시간: {datetime.now(timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')}")
    print("조건: 1분봉에서 3% 이상 상승한 종목")
    print()
    
    # 상승률 상위 종목들 조회
    try:
        from DantaBot import fetch_rising_stocks
        all_stocks = fetch_rising_stocks(50, "J", "2")  # J: KRX, 2: 시가대비상승율
        print(f"상승률 상위 {len(all_stocks)}개 종목 조회 완료")
        print()
    except Exception as e:
        print(f"종목 조회 실패: {e}")
        return
    
    # 1분만에 5% 이상 오른 종목들 찾기
    spike_stocks = []
    
    for stock in all_stocks:
        code = stock['code']
        name = stock['name']
        current_price = stock['price']
        
        try:
            # 1분봉 데이터 가져오기
            df = GetOhlcvMinute(code, '1T', 100)
            
            if df is not None and not df.empty:
                # 9시 이후 데이터만 필터링
                df['datetime'] = pd.to_datetime(df.index, format='%H%M%S')
                df = df[df['datetime'].dt.hour >= 9].copy()
                df = df.sort_values('datetime')
                
                if len(df) >= 2:
                    # 시가 조회
                    try:
                        from DantaBot import get_stock_open_price
                        open_price = get_stock_open_price(code)
                        if open_price <= 0:
                            open_price = df.iloc[0]['open']
                    except:
                        open_price = df.iloc[0]['open']
                    
                    # 1분봉에서 5% 이상 상승한 구간 찾기
                    for i in range(1, len(df)):
                        prev_price = df.iloc[i-1]['close']
                        curr_price = df.iloc[i]['close']
                        minute_change = ((curr_price - prev_price) / prev_price) * 100
                        
                        if minute_change >= 3.0:  # 3% 이상 상승
                            spike_time = df.iloc[i]['datetime'].strftime('%H:%M')
                            
                            # 구매 시뮬레이션 (3% 상승 직후 구매)
                            buy_price = curr_price
                            buy_time = spike_time
                            
                            # 매도 시뮬레이션 (다양한 전략)
                            sell_results = simulate_sell_strategy(df, i, buy_price)
                            
                            spike_stocks.append({
                                'code': code,
                                'name': name,
                                'current_price': current_price,
                                'open_price': open_price,
                                'spike_time': spike_time,
                                'spike_change': minute_change,
                                'buy_price': buy_price,
                                'buy_time': buy_time,
                                'sell_results': sell_results
                            })
                            
                            print(f"✅ {name}({code}) - {spike_time}에 {minute_change:.2f}% 상승 발견!")
                            break  # 첫 번째 3% 상승만 기록
                            
        except Exception as e:
            print(f"❌ {name}({code}) - 분석 실패: {e}")
            continue
        
        time.sleep(0.1)  # API 호출 간격 조절
    
    # 결과 분석
    if spike_stocks:
        print(f"\n=== 1분만에 3% 이상 상승한 종목: {len(spike_stocks)}개 ===")
        analyze_spike_results(spike_stocks)
    else:
        print("\n❌ 1분만에 3% 이상 상승한 종목이 없습니다.")

def simulate_sell_strategy(df, buy_idx, buy_price):
    """매도 전략 시뮬레이션"""
    try:
        # 구매 후 30분간 데이터 확인
        end_idx = min(buy_idx + 30, len(df))
        post_buy_data = df.iloc[buy_idx:end_idx]
        
        if post_buy_data.empty:
            return {
                'max_profit': 0,
                'max_loss': 0,
                'final_profit': 0,
                'sell_time': '데이터없음',
                'sell_price': buy_price,
                'sell_reason': '데이터부족'
            }
        
        max_profit = 0
        max_loss = 0
        final_profit = 0
        sell_time = post_buy_data.iloc[-1]['datetime'].strftime('%H:%M')
        sell_price = post_buy_data.iloc[-1]['close']
        sell_reason = '시간만료'
        
        # DantaBot 부분매도 전략: 2%→10%, 3%→20%, 4%→30%, 5%→50%
        remaining_qty = 100  # 100주로 가정
        total_profit = 0
        sold_2pct = False
        sold_3pct = False
        sold_4pct = False
        sold_5pct = False
        
        for i, (idx, row) in enumerate(post_buy_data.iterrows()):
            current_price = row['close']
            profit_pct = ((current_price - buy_price) / buy_price) * 100
            
            # 최대 수익/손실 추적
            if profit_pct > max_profit:
                max_profit = profit_pct
            if profit_pct < max_loss:
                max_loss = profit_pct
            
            # 2%에서 10% 매도 (남은 수량의 10%)
            if profit_pct >= 2.0 and not sold_2pct and remaining_qty > 0:
                sell_qty = int(remaining_qty * 0.1)
                if sell_qty >= 1:
                    remaining_qty -= sell_qty
                    profit = (current_price - buy_price) * sell_qty
                    total_profit += profit
                    sold_2pct = True
                    sell_reason = '2%에서10%매도'
            
            # 3%에서 20% 매도 (남은 수량의 20%)
            elif profit_pct >= 3.0 and not sold_3pct and remaining_qty > 0:
                sell_qty = int(remaining_qty * 0.2)
                if sell_qty >= 1:
                    remaining_qty -= sell_qty
                    profit = (current_price - buy_price) * sell_qty
                    total_profit += profit
                    sold_3pct = True
                    sell_reason = '3%에서20%매도'
            
            # 4%에서 30% 매도 (남은 수량의 30%)
            elif profit_pct >= 4.0 and not sold_4pct and remaining_qty > 0:
                sell_qty = int(remaining_qty * 0.3)
                if sell_qty >= 1:
                    remaining_qty -= sell_qty
                    profit = (current_price - buy_price) * sell_qty
                    total_profit += profit
                    sold_4pct = True
                    sell_reason = '4%에서30%매도'
            
            # 5%에서 50% 매도 (남은 수량의 50%)
            elif profit_pct >= 5.0 and not sold_5pct and remaining_qty > 0:
                sell_qty = int(remaining_qty * 0.5)
                if sell_qty >= 1:
                    remaining_qty -= sell_qty
                    profit = (current_price - buy_price) * sell_qty
                    total_profit += profit
                    sold_5pct = True
                    sell_reason = '5%에서50%매도'
                    sell_time = row['datetime'].strftime('%H:%M')
                    sell_price = current_price
                    break
            
            # 1% 손절
            elif profit_pct <= -1.0:
                sell_qty = remaining_qty
                remaining_qty = 0
                profit = (current_price - buy_price) * sell_qty
                total_profit += profit
                sell_reason = '1%손절'
                sell_time = row['datetime'].strftime('%H:%M')
                sell_price = current_price
                break
        
        # 최종 수익률 계산
        final_profit = (total_profit / (buy_price * 100)) * 100
        
        return {
            'max_profit': max_profit,
            'max_loss': max_loss,
            'final_profit': final_profit,
            'sell_time': sell_time,
            'sell_price': sell_price,
            'sell_reason': sell_reason
        }
        
    except Exception as e:
        return {
            'max_profit': 0,
            'max_loss': 0,
            'final_profit': 0,
            'sell_time': '오류',
            'sell_price': buy_price,
            'sell_reason': f'오류: {e}'
        }

def analyze_spike_results(spike_stocks):
    """급등 종목 결과 분석"""
    print("\n=== 급등 종목 상세 결과 ===")
    
    for i, stock in enumerate(spike_stocks, 1):
        print(f"\n{i}. {stock['name']} ({stock['code']})")
        print(f"   시가: {stock['open_price']:,}원")
        print(f"   현재가: {stock['current_price']:,}원")
        print(f"   급등 시간: {stock['spike_time']} ({stock['spike_change']:.2f}% 상승)")
        print(f"   구매 가격: {stock['buy_price']:,}원")
        
        results = stock['sell_results']
        print(f"   최대 수익률: {results['max_profit']:+.2f}%")
        print(f"   최대 손실률: {results['max_loss']:+.2f}%")
        print(f"   최종 수익률: {results['final_profit']:+.2f}%")
        print(f"   매도 시간: {results['sell_time']} ({results['sell_price']:,}원)")
        print(f"   매도 사유: {results['sell_reason']}")
    
    # 통계 분석
    print("\n=== 통계 분석 ===")
    final_profits = [s['sell_results']['final_profit'] for s in spike_stocks]
    max_profits = [s['sell_results']['max_profit'] for s in spike_stocks]
    max_losses = [s['sell_results']['max_loss'] for s in spike_stocks]
    
    print(f"평균 최종 수익률: {sum(final_profits)/len(final_profits):+.2f}%")
    print(f"평균 최대 수익률: {sum(max_profits)/len(max_profits):+.2f}%")
    print(f"평균 최대 손실률: {sum(max_losses)/len(max_losses):+.2f}%")
    
    profitable = len([p for p in final_profits if p > 0])
    print(f"수익 종목: {profitable}개 ({profitable/len(spike_stocks)*100:.1f}%)")
    print(f"손실 종목: {len(spike_stocks)-profitable}개 ({(len(spike_stocks)-profitable)/len(spike_stocks)*100:.1f}%)")
    
    # 매도 전략별 분석
    sell_reasons = [s['sell_results']['sell_reason'] for s in spike_stocks]
    reason_counts = {}
    for reason in sell_reasons:
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    
    print("\n=== 매도 전략별 분석 ===")
    for reason, count in reason_counts.items():
        print(f"{reason}: {count}개")
        
        # 해당 전략의 평균 수익률
        strategy_profits = [s['sell_results']['final_profit'] for s in spike_stocks if s['sell_results']['sell_reason'] == reason]
        if strategy_profits:
            avg_profit = sum(strategy_profits) / len(strategy_profits)
            print(f"  평균 수익률: {avg_profit:+.2f}%")

def check_single_stock():
    """단일 종목 상세 분석 (기존 기능)"""
    # 분석할 종목
    target_stock = {'code': '060900', 'name': '비올'}
    
    print("=== 335890 비올 종목 1분봉 상세 분석 ===")
    print(f"분석 시간: {datetime.now(timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"분석 종목: {target_stock['name']} ({target_stock['code']})")
    print()
    
    # 현재가 조회
    try:
        current_price = GetCurrentPrice(target_stock['code'])
        if isinstance(current_price, dict):
            current_price = float(current_price.get('price', 0))
        else:
            current_price = float(current_price)
        print(f"현재가: {current_price:,}원")
    except Exception as e:
        print(f"현재가 조회 실패: {e}")
        current_price = 0
    
    try:
        # 1분봉 데이터 가져오기 (9시부터 현재까지)
        df = GetOhlcvMinute(target_stock['code'], '1T', 200)  # 충분한 데이터 확보
        
        if df is not None and not df.empty:
            # 9시 이후 데이터만 필터링
            df['datetime'] = pd.to_datetime(df.index, format='%H%M%S')
            df = df[df['datetime'].dt.hour >= 9].copy()
            df = df.sort_values('datetime')  # 시간순 정렬
            
            if not df.empty:
                print(f"9시부터 현재까지 {len(df)}분 데이터 확인")
                print()
                
                # 시가 조회 (9시 정각 가격)
                try:
                    from DantaBot import get_stock_open_price
                    open_price = get_stock_open_price(target_stock['code'])
                    if open_price > 0:
                        print(f"시가 (9:00): {open_price:,}원")
                    else:
                        # 첫 번째 데이터를 시가로 사용
                        open_price = df.iloc[0]['open']
                        print(f"시가 (추정): {open_price:,}원")
                except:
                    open_price = df.iloc[0]['open']
                    print(f"시가 (추정): {open_price:,}원")
                
                print()
                
                # 전체 1분봉 데이터 표시 (분당 상승률 포함)
                print("=== 1분봉 데이터 (분당 상승률 포함) ===")
                print("시간    | 가격      | 시가대비  | 분당상승률 | 거래량    | 거래대금")
                print("-" * 80)
                
                prev_price = open_price
                
                for i, (idx, row) in enumerate(df.iterrows()):
                    time_str = row['datetime'].strftime('%H:%M')
                    close_price = row['close']
                    volume = row['volume']
                    amount = close_price * volume
                    
                    # 시가 대비 변동률 계산
                    if open_price > 0:
                        change_pct = ((close_price - open_price) / open_price) * 100
                    else:
                        change_pct = 0
                    
                    # 이전 분 대비 변동률 (분당 상승률)
                    if i > 0:
                        minute_change = ((close_price - prev_price) / prev_price) * 100
                    else:
                        minute_change = 0
                    
                    # 상승/하락 표시
                    if minute_change > 0:
                        change_symbol = "▲"
                    elif minute_change < 0:
                        change_symbol = "▼"
                    else:
                        change_symbol = "─"
                    
                    print(f"{time_str} | {close_price:8,.0f}원 | {change_pct:+6.2f}% | {change_symbol}{minute_change:+5.2f}% | {volume:8,.0f}주 | {amount:12,.0f}원")
                    
                    prev_price = close_price
                
                # 급등 구간 분석
                print()
                print("=== 급등 구간 분석 ===")
                
                # 연속 상승 구간 찾기
                consecutive_rises = 0
                max_consecutive = 0
                rise_start_time = ""
                current_rise_start = ""
                
                for idx in range(1, len(df)):
                    prev_price = df.iloc[idx-1]['close']
                    curr_price = df.iloc[idx]['close']
                    minute_change = ((curr_price - prev_price) / prev_price) * 100
                    
                    if minute_change > 0:
                        if consecutive_rises == 0:
                            current_rise_start = df.iloc[idx-1]['datetime'].strftime('%H:%M')
                        consecutive_rises += 1
                    else:
                        if consecutive_rises > max_consecutive:
                            max_consecutive = consecutive_rises
                            rise_start_time = current_rise_start
                        consecutive_rises = 0
                
                if consecutive_rises > max_consecutive:
                    max_consecutive = consecutive_rises
                    rise_start_time = current_rise_start
                
                print(f"최대 연속 상승: {max_consecutive}분 (시작: {rise_start_time})")
                
                # 거래량 급증 구간 찾기
                if len(df) >= 5:
                    avg_volume = df['volume'].rolling(window=5).mean()
                    volume_spike = df['volume'] > avg_volume * 2  # 평균의 2배 이상
                    spike_count = volume_spike.sum()
                    print(f"거래량 급증 분: {spike_count}분 (평균의 2배 이상)")
                
                # 최고가/최저가
                max_price = df['close'].max()
                min_price = df['close'].min()
                max_pct = ((max_price - open_price) / open_price) * 100 if open_price > 0 else 0
                min_pct = ((min_price - open_price) / open_price) * 100 if open_price > 0 else 0
                
                print(f"최고가: {max_price:,.0f}원 ({max_pct:+.2f}%)")
                print(f"최저가: {min_price:,.0f}원 ({min_pct:+.2f}%)")
                
                # 현재가 대비 시가 상승률
                if current_price > 0 and open_price > 0:
                    total_change = ((current_price - open_price) / open_price) * 100
                    print(f"현재가 대비 시가 상승률: {total_change:+.2f}%")
                
            else:
                print("9시 이후 데이터가 없습니다.")
        else:
            print("데이터를 가져올 수 없습니다.")
            
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "single":
        # 단일 종목 분석 모드
        check_single_stock()
    else:
        # 1분만에 5% 이상 오르는 종목 분석 모드 (기본)
        check_minute_data()
