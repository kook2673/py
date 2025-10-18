#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from KIS_API_Helper_KR import *
import KIS_Common as Common
import pandas as pd
from datetime import datetime, timedelta
from pytz import timezone
import time
import logging

# KIS API 모드 설정
Common.SetChangeMode("REAL")

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_dropping_stocks_9am(limit=30):
    """9시 시초가 대비 하락순 종목 조회"""
    try:
        print(f"=== 9시 시초가 대비 하락순 {limit}개 종목 조회 ===")
        
        # DantaBot에서 fetch_rising_stocks 함수 import
        from DantaBot import fetch_rising_stocks
        
        # 시초가 대비 하락률 순으로 종목 조회
        stocks = fetch_rising_stocks(limit, "J", "5")  # J: KRX, 5: 시초가대비하락률순
        
        print(f"하락순 종목 {len(stocks)}개 조회 완료")
        return stocks
        
    except Exception as e:
        print(f"종목 조회 실패: {e}")
        return []

def analyze_stock_9am_pattern(code, name, target_stocks):
    """9시 패턴 분석 (시초가 상승→하락→다음분 상승)"""
    try:
        # 1분봉 데이터 조회 (9시부터 10분간)
        df = GetOhlcvMinute(code, '1T', 20)
        
        if df is None or len(df) < 5:
            return None
        
        # 9시 이후 데이터만 필터링
        df['datetime'] = pd.to_datetime(df.index, format='%H%M%S')
        df = df[df['datetime'].dt.hour >= 9].copy()
        df = df.sort_values('datetime')
        
        # 데이터가 충분한지 확인
        if len(df) < 3:
            return None
        
        # 시초가 (9시 정각)
        open_price = df.iloc[0]['open']
        
        # 9시 1분, 2분, 3분 데이터
        minute_1 = df.iloc[1] if len(df) > 1 else None
        minute_2 = df.iloc[2] if len(df) > 2 else None
        minute_3 = df.iloc[3] if len(df) > 3 else None
        
        if not all([minute_1, minute_2, minute_3]):
            return None
        
        # 패턴 분석
        pattern = {
            'code': code,
            'name': name,
            'open_price': open_price,
            'minute_1_price': minute_1['close'],
            'minute_2_price': minute_2['close'],
            'minute_3_price': minute_3['close'],
            'minute_1_change': ((minute_1['close'] - open_price) / open_price) * 100,
            'minute_2_change': ((minute_2['close'] - open_price) / open_price) * 100,
            'minute_3_change': ((minute_3['close'] - open_price) / open_price) * 100,
            'minute_1_volume': minute_1['volume'],
            'minute_2_volume': minute_2['volume'],
            'minute_3_volume': minute_3['volume'],
            'pattern_detected': False,
            'buy_signal': False,
            'sell_signal': False,
            'profit_pct': 0
        }
        
        # 패턴 조건 확인
        # 1. 9시 1분: 시초가 대비 상승
        # 2. 9시 2분: 시초가 대비 하락 (또는 상승폭 감소)
        # 3. 9시 3분: 다시 상승
        
        condition_1 = pattern['minute_1_change'] > 0  # 1분에 상승
        condition_2 = pattern['minute_2_change'] < pattern['minute_1_change']  # 2분에 하락 또는 상승폭 감소
        condition_3 = pattern['minute_3_change'] > pattern['minute_2_change']  # 3분에 다시 상승
        
        if condition_1 and condition_2 and condition_3:
            pattern['pattern_detected'] = True
            pattern['buy_signal'] = True
            
            # 매수 시뮬레이션 (9시 2분 종가에 매수)
            buy_price = minute_2['close']
            
            # 매도 시뮬레이션 (9시 3분 종가에 매도)
            sell_price = minute_3['close']
            pattern['profit_pct'] = ((sell_price - buy_price) / buy_price) * 100
            
            if pattern['profit_pct'] > 0:
                pattern['sell_signal'] = True
        
        return pattern
        
    except Exception as e:
        logging.error(f"패턴 분석 오류 {code}: {e}")
        return None

def backtest_9am_strategy():
    """9시 하락순 종목 백테스트"""
    print("=== 9시 하락순 종목 백테스트 시작 ===")
    print(f"분석 시간: {datetime.now(timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 하락순 종목 조회
    target_stocks = get_dropping_stocks_9am(30)
    
    if not target_stocks:
        print("❌ 분석할 종목이 없습니다.")
        return
    
    print(f"분석 대상: {len(target_stocks)}개 종목")
    print()
    
    # 각 종목별 패턴 분석
    results = []
    pattern_count = 0
    
    for i, stock in enumerate(target_stocks, 1):
        code = stock['code']
        name = stock['name']
        current_price = stock['price']
        
        print(f"[{i:2d}/{len(target_stocks)}] {name}({code}) 분석 중...")
        
        try:
            pattern = analyze_stock_9am_pattern(code, name, target_stocks)
            
            if pattern:
                results.append(pattern)
                
                if pattern['pattern_detected']:
                    pattern_count += 1
                    print(f"  ✅ 패턴 감지: {pattern['minute_1_change']:+.2f}% → {pattern['minute_2_change']:+.2f}% → {pattern['minute_3_change']:+.2f}%")
                    
                    if pattern['buy_signal'] and pattern['sell_signal']:
                        print(f"  💰 수익: {pattern['profit_pct']:+.2f}%")
                    else:
                        print(f"  ❌ 매매 신호 없음")
                else:
                    print(f"  ❌ 패턴 없음")
            else:
                print(f"  ❌ 데이터 없음")
                
        except Exception as e:
            print(f"  ❌ 분석 실패: {e}")
            continue
        
        time.sleep(0.5)  # API 호출 간격 조절 (초당 거래건수 초과 방지)
    
    # 결과 분석
    print(f"\n=== 백테스트 결과 ===")
    print(f"총 분석 종목: {len(results)}개")
    print(f"패턴 감지: {pattern_count}개")
    
    if pattern_count > 0:
        # 패턴 감지된 종목들
        pattern_stocks = [r for r in results if r['pattern_detected']]
        profitable_stocks = [r for r in pattern_stocks if r['profit_pct'] > 0]
        
        print(f"수익 종목: {len(profitable_stocks)}개")
        
        if profitable_stocks:
            avg_profit = sum(r['profit_pct'] for r in profitable_stocks) / len(profitable_stocks)
            max_profit = max(r['profit_pct'] for r in profitable_stocks)
            min_profit = min(r['profit_pct'] for r in profitable_stocks)
            
            print(f"평균 수익률: {avg_profit:+.2f}%")
            print(f"최대 수익률: {max_profit:+.2f}%")
            print(f"최소 수익률: {min_profit:+.2f}%")
            
            print(f"\n=== 수익 종목 상세 ===")
            for stock in sorted(profitable_stocks, key=lambda x: x['profit_pct'], reverse=True):
                print(f"{stock['name']}({stock['code']}): {stock['profit_pct']:+.2f}%")
                print(f"  시초가: {stock['open_price']:,}원")
                print(f"  1분: {stock['minute_1_price']:,}원 ({stock['minute_1_change']:+.2f}%)")
                print(f"  2분: {stock['minute_2_price']:,}원 ({stock['minute_2_change']:+.2f}%)")
                print(f"  3분: {stock['minute_3_price']:,}원 ({stock['minute_3_change']:+.2f}%)")
                print()
    else:
        print("❌ 패턴이 감지된 종목이 없습니다.")

def analyze_single_stock_9am(code, name):
    """단일 종목 9시 패턴 상세 분석"""
    print(f"=== {name}({code}) 9시 패턴 상세 분석 ===")
    print(f"분석 시간: {datetime.now(timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # 1분봉 데이터 조회
        df = GetOhlcvMinute(code, '1T', 20)
        
        if df is None or len(df) < 5:
            print("❌ 데이터를 가져올 수 없습니다.")
            return
        
        # 9시 이후 데이터만 필터링
        df['datetime'] = pd.to_datetime(df.index, format='%H%M%S')
        df = df[df['datetime'].dt.hour >= 9].copy()
        df = df.sort_values('datetime')
        
        if len(df) < 3:
            print("❌ 9시 이후 데이터가 부족합니다.")
            return
        
        # 시초가
        open_price = df.iloc[0]['open']
        print(f"시초가 (9:00): {open_price:,}원")
        print()
        
        # 9시부터 10분간 상세 분석
        print("=== 9시부터 10분간 상세 분석 ===")
        print("시간    | 가격      | 시초가대비 | 분당변화 | 거래량    | 거래대금")
        print("-" * 70)
        
        prev_price = open_price
        
        for i in range(min(10, len(df))):  # 처음 10분만
            row = df.iloc[i]
            time_str = row['datetime'].strftime('%H:%M')
            close_price = row['close']
            volume = row['volume']
            amount = close_price * volume
            
            # 시초가 대비 변동률
            change_pct = ((close_price - open_price) / open_price) * 100
            
            # 이전 분 대비 변동률
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
        
        # 패턴 분석
        print(f"\n=== 패턴 분석 ===")
        
        if len(df) >= 3:
            minute_1 = df.iloc[1]
            minute_2 = df.iloc[2]
            minute_3 = df.iloc[3]
            
            change_1 = ((minute_1['close'] - open_price) / open_price) * 100
            change_2 = ((minute_2['close'] - open_price) / open_price) * 100
            change_3 = ((minute_3['close'] - open_price) / open_price) * 100
            
            print(f"9시 1분: {minute_1['close']:,}원 ({change_1:+.2f}%)")
            print(f"9시 2분: {minute_2['close']:,}원 ({change_2:+.2f}%)")
            print(f"9시 3분: {minute_3['close']:,}원 ({change_3:+.2f}%)")
            
            # 패턴 조건 확인
            condition_1 = change_1 > 0
            condition_2 = change_2 < change_1
            condition_3 = change_3 > change_2
            
            print(f"\n패턴 조건:")
            print(f"1. 9시 1분 상승: {condition_1} ({change_1:+.2f}% > 0)")
            print(f"2. 9시 2분 하락: {condition_2} ({change_2:+.2f}% < {change_1:+.2f}%)")
            print(f"3. 9시 3분 상승: {condition_3} ({change_3:+.2f}% > {change_2:+.2f}%)")
            
            if condition_1 and condition_2 and condition_3:
                print(f"\n✅ 패턴 감지!")
                
                # 매수/매도 시뮬레이션
                buy_price = minute_2['close']
                sell_price = minute_3['close']
                profit_pct = ((sell_price - buy_price) / buy_price) * 100
                
                print(f"매수 가격 (9시 2분): {buy_price:,}원")
                print(f"매도 가격 (9시 3분): {sell_price:,}원")
                print(f"수익률: {profit_pct:+.2f}%")
            else:
                print(f"\n❌ 패턴 없음")
        
    except Exception as e:
        print(f"❌ 분석 실패: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "single":
        # 단일 종목 분석 모드
        target_code = "060900"
        target_name = "한일시멘트"
        analyze_single_stock_9am(target_code, target_name)
    else:
        # 9시 하락순 종목 백테스트 모드 (기본)
        backtest_9am_strategy()
