import KIS_Common as Common
import pandas as pd
import pprint
import numpy as np
import time

# 최적화된 백테스팅 함수
def backtest_ma_combination(close_prices, ma1_values, ma2_values, fee, total_money):
    """
    최적화된 백테스팅 함수
    
    Args:
        close_prices: 종가 배열
        ma1_values: 단기 이동평균 배열
        ma2_values: 장기 이동평균 배열
        fee: 수수료
        total_money: 초기 투자금
        
    Returns:
        tuple: (최종 투자금, 매매횟수, 성공횟수, 실패횟수)
    """
    n = len(close_prices)
    is_buy = False
    buy_price = 0.0
    invest_money = total_money
    
    try_cnt = 0
    success_cnt = 0
    fail_cnt = 0
    
    for i in range(2, n):
        now_close_price = close_prices[i]
        prev_close_price = close_prices[i-1]
        
        # 매수 상태
        if is_buy:
            # 투자금의 등락률 반영
            invest_money = invest_money * (1.0 + ((now_close_price - prev_close_price) / prev_close_price))
            
            # 데드 크로스 체크
            if (ma1_values[i-1] < ma2_values[i-1] and 
                ma1_values[i-2] > ma1_values[i-1]):
                
                # 수익률 계산
                rate = (now_close_price - buy_price) / buy_price
                revenue_rate = (rate - fee) * 100.0
                
                invest_money = invest_money * (1.0 - fee)
                try_cnt += 1
                
                if revenue_rate > 0:
                    success_cnt += 1
                else:
                    fail_cnt += 1
                
                is_buy = False
        
        # 매수 전 상태
        elif not is_buy:
            # 골든 크로스 체크
            if (ma1_values[i-1] > ma2_values[i-1] and 
                ma1_values[i-2] < ma1_values[i-1]):
                
                buy_price = now_close_price
                invest_money = invest_money * (1.0 - fee)
                is_buy = True
    
    return invest_money, try_cnt, success_cnt, fail_cnt

def process_ma_combination(close_prices, ma_combo, fee, total_money):
    """
    단일 MA 조합 처리 함수
    """
    ma1, ma2 = ma_combo
    
    # 이동평균 계산
    ma1_values = pd.Series(close_prices).rolling(ma1).mean().values
    ma2_values = pd.Series(close_prices).rolling(ma2).mean().values
    
    # NaN 값 처리
    valid_start = max(ma1, ma2)
    if len(ma1_values) < valid_start:
        return None
    
    # 백테스팅 실행
    final_money, try_cnt, success_cnt, fail_cnt = backtest_ma_combination(
        close_prices[valid_start:], 
        ma1_values[valid_start:], 
        ma2_values[valid_start:], 
        fee, 
        total_money
    )
    
    if try_cnt > 0:  # 매매가 한 번이라도 있었던 경우만
        revenue_rate = ((final_money - total_money) / total_money) * 100.0
        
        return {
            'ma1': ma1,
            'ma2': ma2,
            'revenue_rate': revenue_rate,
            'try_cnt': try_cnt,
            'success_cnt': success_cnt,
            'fail_cnt': fail_cnt,
            'final_money': final_money
        }
    
    return None

def calculate_ma_combinations_optimized(stock_code, test_area="KR", get_count=700, cut_count=0, fee=0.0025, total_money=1000000):
    """
    최적화된 MA 조합 계산 (순차 처리)
    """
    print(f"\n----stock_code: {stock_code}")
    
    # 일봉 데이터 가져오기
    df = Common.GetOhlcv(test_area, stock_code, get_count)
    
    if df is None or len(df) == 0:
        print(f"데이터를 가져올 수 없습니다: {stock_code}")
        return None
    
    # 데이터 전처리
    df.dropna(inplace=True)
    df = df[:len(df)-cut_count]
    
    if len(df) < 200:  # 최소 데이터 확인
        print(f"충분한 데이터가 없습니다: {stock_code}")
        return None
    
    # 이동평균 계산을 벡터화로 최적화
    close_prices = df['close'].values
    ma_combinations = []
    
    # MA 조합 생성 (더 효율적인 범위)
    for ma1 in range(3, 16):  # 3-15일선
        for ma2 in range(max(ma1 + 5, 20), 101):  # 20-100일선 (더 효율적인 범위)
            ma_combinations.append((ma1, ma2))
    
    print(f"총 {len(ma_combinations)}개 MA 조합을 계산합니다...")
    
    # 순차 처리로 변경
    results = []
    for i, combo in enumerate(ma_combinations):
        if i % 100 == 0:  # 진행률 표시
            print(f"진행률: {i}/{len(ma_combinations)} ({i/len(ma_combinations)*100:.1f}%)")
        
        result = process_ma_combination(close_prices, combo, fee, total_money)
        if result is not None:
            results.append(result)
    
    if not results:
        print(f"{stock_code} 유효한 결과가 없습니다.")
        return None
    
    # 결과 정렬 (수익률 기준)
    results.sort(key=lambda x: x['revenue_rate'], reverse=True)
    best_result = results[0]
    
    print(f"최적의 MA 조합: small_ma={best_result['ma1']}, big_ma={best_result['ma2']}")
    print(f"수익률: {best_result['revenue_rate']:.2f}%, 매매횟수: {best_result['try_cnt']}")
    
    return {
        'stock_code': stock_code,
        'small_ma': best_result['ma1'],
        'big_ma': best_result['ma2'],
        'revenue_rate': best_result['revenue_rate'],
        'mdd': 0,  # MDD 계산은 별도로 필요시 추가
        'try_cnt': best_result['try_cnt'],
        'success_cnt': best_result['success_cnt'],
        'fail_cnt': best_result['fail_cnt']
    }

# 기존 함수와 동일한 인터페이스 유지
def FindOptimalMA(stock_code, test_area="KR", get_count=700, cut_count=0, fee=0.0025, total_money=1000000):
    """
    최적화된 MA 조합 찾기 함수 (기존 인터페이스 유지)
    """
    return calculate_ma_combinations_optimized(stock_code, test_area, get_count, cut_count, fee, total_money)

if __name__ == "__main__":
    # 테스트 실행
    result = FindOptimalMA("005930")  # 삼성전자 테스트
    if result:
        print("테스트 결과:", result) 