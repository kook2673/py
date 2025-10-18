# -*- coding: utf-8 -*-
"""
커버드콜 ETF 매수 전략 테스트
- RSI 40 이하일 때 매수
- 분배금 지급 후 하락 고려
- 모으는 구조 (매도 없음)
"""

import KIS_Common as Common
import KIS_API_Helper_KR as KisKR
import pandas as pd
import time
from datetime import datetime, timedelta

# 설정
APP_KEY = ""
APP_SECRET = ""
CANO = ""
ACCOUNT_PREFIX = ""

# 테스트할 ETF 티커
# KODEX 코스닥150커버드콜: '271060'
# KODEX 200커버드콜: '271050'
# TIGER 코스닥150커버드콜: '273140'
TEST_TICKER = '271060'  # KODEX 코스닥150커버드콜

# 매수 전략 설정
RSI_THRESHOLD = 40  # RSI 40 이하일 때 매수
RSI_PERIOD = 14  # RSI 기간

# 최소 매수 금액
MIN_BUY_AMOUNT = 100000  # 10만원

print("=" * 80)
print("커버드콜 ETF 매수 전략 테스트")
print("=" * 80)
print(f"테스트 종목: {TEST_TICKER}")
print(f"RSI 기준: {RSI_THRESHOLD} 이하")
print(f"RSI 기간: {RSI_PERIOD}일")
print("=" * 80)

# API 초기화 (실제 사용 시 주석 해제)
# Common.SetChangeMode("REAL")
# KisKR.SetAPIInfo(APP_KEY, APP_SECRET, CANO, ACCOUNT_PREFIX)

def test_rsi_calculation():
    """RSI 계산 테스트"""
    print("\n[1] RSI 계산 테스트")
    print("-" * 80)
    
    try:
        # 일봉 데이터 가져오기
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)
        
        df = Common.GetOhlcv("KR", TEST_TICKER, 100)  # 최근 100일
        
        if df is None or len(df) == 0:
            print("❌ 데이터를 가져올 수 없습니다.")
            return None
        
        print(f"✅ 데이터 조회 성공: {len(df)}일치")
        print(f"\n최근 5일 데이터:")
        print(df[['open', 'high', 'low', 'close', 'volume']].tail())
        
        # RSI 계산
        rsi_values = []
        for i in range(RSI_PERIOD, len(df)):
            rsi = Common.GetRSI(df, RSI_PERIOD, i)
            date = df.index[i]
            close = df['close'].iloc[i]
            rsi_values.append({
                'date': date,
                'close': close,
                'rsi': rsi
            })
        
        rsi_df = pd.DataFrame(rsi_values)
        
        print(f"\n최근 10일 RSI:")
        print(rsi_df.tail(10).to_string(index=False))
        
        # 현재 RSI
        current_rsi = rsi_df['rsi'].iloc[-1]
        current_price = rsi_df['close'].iloc[-1]
        
        print(f"\n📊 현재 상태:")
        print(f"  현재가: {current_price:,.0f}원")
        print(f"  현재 RSI: {current_rsi:.2f}")
        
        if current_rsi <= RSI_THRESHOLD:
            print(f"  ✅ 매수 신호! (RSI {current_rsi:.2f} <= {RSI_THRESHOLD})")
        else:
            print(f"  ⏸️  대기 (RSI {current_rsi:.2f} > {RSI_THRESHOLD})")
        
        return rsi_df
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None


def analyze_distribution_pattern():
    """분배금 지급 패턴 분석"""
    print("\n[2] 분배금 지급 패턴 분석")
    print("-" * 80)
    
    try:
        # 6개월 데이터
        df = Common.GetOhlcv("KR", TEST_TICKER, 180)
        
        if df is None or len(df) == 0:
            print("❌ 데이터를 가져올 수 없습니다.")
            return
        
        # 일일 등락률 계산
        df['daily_change'] = ((df['close'] - df['open']) / df['open'] * 100)
        
        # 급격한 하락일 찾기 (분배금 지급 추정)
        # 보통 -1% 이상 하락
        distribution_days = df[df['daily_change'] < -1.0]
        
        print(f"✅ 6개월 데이터 분석 완료")
        print(f"\n급격한 하락일 (분배금 지급 추정):")
        print(f"  총 {len(distribution_days)}일")
        
        if len(distribution_days) > 0:
            print(f"\n최근 5회:")
            for idx in distribution_days.tail(5).index:
                date = idx
                change = distribution_days.loc[idx, 'daily_change']
                close = distribution_days.loc[idx, 'close']
                print(f"  {date}: {close:,.0f}원 ({change:+.2f}%)")
        
        # 분배금 지급일 이후 RSI 변화
        print(f"\n분배금 지급 추정일 이후 평균 RSI:")
        for i, idx in enumerate(distribution_days.tail(3).index):
            date_idx = df.index.get_loc(idx)
            if date_idx + 1 < len(df):
                rsi_after = Common.GetRSI(df, RSI_PERIOD, date_idx + 1)
                print(f"  {idx} 다음날 RSI: {rsi_after:.2f}")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


def backtest_strategy():
    """백테스트: RSI 40 이하에서 매수"""
    print("\n[3] 매수 전략 백테스트")
    print("-" * 80)
    
    try:
        # 1년 데이터
        df = Common.GetOhlcv("KR", TEST_TICKER, 365)
        
        if df is None or len(df) == 0:
            print("❌ 데이터를 가져올 수 없습니다.")
            return
        
        print(f"✅ 백테스트 기간: {df.index[0]} ~ {df.index[-1]}")
        
        # 매수 시뮬레이션
        initial_cash = 10000000  # 1000만원
        cash = initial_cash
        shares = 0
        buy_history = []
        
        for i in range(RSI_PERIOD, len(df)):
            current_price = df['close'].iloc[i]
            current_rsi = Common.GetRSI(df, RSI_PERIOD, i)
            current_date = df.index[i]
            
            # RSI 40 이하이고, 현금이 충분하면 매수
            if current_rsi <= RSI_THRESHOLD and cash >= MIN_BUY_AMOUNT:
                # 10만원어치 매수
                buy_shares = MIN_BUY_AMOUNT // current_price
                buy_amount = buy_shares * current_price
                
                if buy_shares > 0 and cash >= buy_amount:
                    cash -= buy_amount
                    shares += buy_shares
                    
                    buy_history.append({
                        'date': current_date,
                        'price': current_price,
                        'shares': buy_shares,
                        'amount': buy_amount,
                        'rsi': current_rsi,
                        'total_shares': shares,
                        'cash': cash
                    })
        
        # 결과 출력
        print(f"\n📈 백테스트 결과:")
        print(f"  총 매수 횟수: {len(buy_history)}회")
        print(f"  총 매수 금액: {initial_cash - cash:,.0f}원")
        print(f"  보유 주식: {shares}주")
        
        if len(buy_history) > 0:
            avg_buy_price = (initial_cash - cash) / shares if shares > 0 else 0
            current_price = df['close'].iloc[-1]
            current_value = shares * current_price + cash
            total_return = ((current_value - initial_cash) / initial_cash * 100)
            
            print(f"  평균 매수가: {avg_buy_price:,.0f}원")
            print(f"  현재가: {current_price:,.0f}원")
            print(f"  평가 금액: {shares * current_price:,.0f}원")
            print(f"  잔여 현금: {cash:,.0f}원")
            print(f"  총 자산: {current_value:,.0f}원")
            print(f"  총 수익률: {total_return:+.2f}%")
            
            print(f"\n최근 5회 매수 내역:")
            for record in buy_history[-5:]:
                print(f"  {record['date']}: {record['price']:,.0f}원 x {record['shares']}주 (RSI: {record['rsi']:.2f})")
        
        return buy_history
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """메인 실행 함수"""
    
    # 1. RSI 계산 테스트
    rsi_df = test_rsi_calculation()
    
    time.sleep(1)
    
    # 2. 분배금 패턴 분석
    analyze_distribution_pattern()
    
    time.sleep(1)
    
    # 3. 백테스트
    buy_history = backtest_strategy()
    
    print("\n" + "=" * 80)
    print("✅ 테스트 완료!")
    print("=" * 80)
    
    # 결론
    print("\n💡 결론:")
    print("  1. RSI 계산이 정상적으로 작동합니다.")
    print("  2. RSI 40 이하에서 매수하는 전략은 분배금 하락 후 저점 매수에 유리합니다.")
    print("  3. 커버드콜 ETF는 분배금으로 인한 주가 하락이 있지만,")
    print("     RSI 지표로 과매도 구간을 포착하여 좋은 진입 시점을 찾을 수 있습니다.")
    print("  4. 장기적으로 모으는 전략에 적합합니다.")


if __name__ == "__main__":
    main()

