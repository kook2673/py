# -*- coding: utf-8 -*-
"""
배당주식 RSI 매수 전략 백테스팅
- RSI가 낮을 때만 매수
- 매도하지 않고 장기 보유
- 배당금 수령 시뮬레이션
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys

# stock_list 모듈 import
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from stock_list import get_stock_data_and_save_csv, get_stock_name_from_api
except ImportError:
    print("❌ stock_list 모듈을 찾을 수 없습니다.")
    get_stock_data_and_save_csv = None
    get_stock_name_from_api = None

def create_sample_csv_data(csv_path, stock_code, stock_name):
    """
    샘플 주가 데이터를 생성하는 함수 (KIS API를 사용할 수 없을 때)
    
    Args:
        csv_path (str): CSV 파일 경로
        stock_code (str): 종목 코드
        stock_name (str): 종목명
        
    Returns:
        str: 생성된 CSV 파일 경로
    """
    try:
        print(f"📝 {stock_name} ({stock_code}) 샘플 데이터를 생성합니다...")
        
        # 7년간의 샘플 데이터 생성 (2018-01-01 ~ 현재)
        # 데이터 기간 설정 (ETF는 실제 상장일부터)
        if '441680' in stock_code:  # TIGER 미국나스닥100커버드콜
            start_date = pd.Timestamp('2024-01-15')  # 2024년 상장
        elif '486290' in stock_code:  # TIGER 미국나스닥100타겟데일리커버드콜
            start_date = pd.Timestamp('2024-03-01')  # 2024년 상장
        elif '0048K0' in stock_code:  # KODEX 차이나휴머노이드로봇
            start_date = pd.Timestamp('2024-06-01')  # 2024년 상장
        elif '411420' in stock_code:  # KODEX 미국나스닥AI테크액티브
            start_date = pd.Timestamp('2025-05-28')  # 2025년 5월 상장 예정
        elif '441680' in stock_code:  # KODEX 200타겟위클리커버드콜
            start_date = pd.Timestamp('2024-02-01')  # 2024년 상장
        else:
            start_date = pd.Timestamp('2018-01-01')  # 개별주식은 2018년부터
            
        end_date = pd.Timestamp.now().normalize()  # 현재 날짜까지
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        
        # 주말 제외 (월-금만)
        dates = dates[dates.weekday < 5]
        
        # 기본 주가 설정 (종목별로 다르게)
        if '한샘' in stock_name or stock_code == '009240':
            base_price = 44800  # 한샘 현재가 기준
            volatility = 0.025  # 변동성 (인테리어 업종 특성상 높음)
        elif '삼성전자우' in stock_name or stock_code == '005935':
            base_price = 65000  # 삼성전자우 현재가 기준
            volatility = 0.015
        elif '현대차우' in stock_name or stock_code == '005385':
            base_price = 200000  # 현대차우 현재가 기준
            volatility = 0.025
        elif '삼성화재우' in stock_name or stock_code == '000815':
            base_price = 120000  # 삼성화재우 현재가 기준
            volatility = 0.02
        # ETF 종목들 (실제 상장일 이후만)
        elif '441680' in stock_code:  # TIGER 미국나스닥100커버드콜 (2024년 상장)
            base_price = 15000  # ETF 가격
            volatility = 0.03
        elif '486290' in stock_code:  # TIGER 미국나스닥100타겟데일리커버드콜 (2024년 상장)
            base_price = 12000  # ETF 가격
            volatility = 0.035
        elif '0048K0' in stock_code:  # KODEX 차이나휴머노이드로봇 (2024년 상장)
            base_price = 8000   # ETF 가격
            volatility = 0.04
        elif '411420' in stock_code:  # KODEX 미국나스닥AI테크액티브 (2025년 5월 상장 예정)
            base_price = 10000  # ETF 가격
            volatility = 0.03
        elif '441680' in stock_code:  # KODEX 200타겟위클리커버드콜 (2024년 상장)
            base_price = 18000  # ETF 가격 (코스피200 기반)
            volatility = 0.025
        else:
            base_price = 50000  # 기본값
            volatility = 0.02
        
        # 랜덤 워크로 주가 생성 (현재가에서 역산)
        np.random.seed(42)  # 재현 가능한 결과를 위해
        
        # 현재가에서 시작해서 과거로 역산
        prices = [base_price]
        returns = np.random.normal(0, volatility, len(dates)-1)
        
        # 과거부터 현재까지 순차적으로 생성
        for i, ret in enumerate(returns):
            # 시간에 따른 변동성 조정 (최근일수록 더 안정적)
            time_factor = 1.0 - (i / len(returns)) * 0.3  # 최근 30% 변동성 감소
            adjusted_ret = ret * time_factor
            
            new_price = prices[-1] * (1 + adjusted_ret)
            # 최소/최대 가격 제한
            min_price = base_price * 0.3  # 현재가의 30% 이하로는 안 떨어짐
            max_price = base_price * 2.0  # 현재가의 200% 이상으로는 안 올라감
            new_price = max(min_price, min(new_price, max_price))
            prices.append(new_price)
        
        # 가격 리스트를 역순으로 정렬 (과거부터 현재까지)
        prices = prices[::-1]
        
        # OHLCV 데이터 생성
        data = []
        for i, (date, price) in enumerate(zip(dates, prices)):
            # 일일 변동률 (0.5% ~ 3%)
            daily_vol = np.random.uniform(0.005, 0.03)
            
            open_price = price * (1 + np.random.uniform(-daily_vol/2, daily_vol/2))
            high_price = max(open_price, price) * (1 + np.random.uniform(0, daily_vol/2))
            low_price = min(open_price, price) * (1 - np.random.uniform(0, daily_vol/2))
            close_price = price
            volume = int(np.random.uniform(10000, 100000))
            
            data.append({
                'date': date.strftime('%Y-%m-%d'),
                'open': round(open_price, 0),
                'high': round(high_price, 0),
                'low': round(low_price, 0),
                'close': round(close_price, 0),
                'volume': volume
            })
        
        # DataFrame 생성
        df = pd.DataFrame(data)
        
        # CSV 파일 저장
        df.to_csv(csv_path, index=False, encoding='utf-8')
        
        print(f"✅ 샘플 데이터 생성 완료: {csv_path}")
        print(f"📊 데이터 기간: {df['date'].min()} ~ {df['date'].max()}")
        print(f"📊 총 {len(df)}개 일자 데이터")
        print(f"📊 시작가: {df['close'].iloc[0]:,.0f}원, 종료가: {df['close'].iloc[-1]:,.0f}원")
        
        return csv_path
        
    except Exception as e:
        print(f"❌ 샘플 데이터 생성 실패: {e}")
        return None

def ensure_csv_file_exists(csv_path, stock_code, stock_name):
    """
    CSV 파일이 존재하지 않으면 새로 생성하는 함수
    
    Args:
        csv_path (str): CSV 파일 경로
        stock_code (str): 종목 코드
        stock_name (str): 종목명
        
    Returns:
        str: CSV 파일 경로 (생성되었거나 기존 파일)
    """
    if os.path.exists(csv_path):
        print(f"✅ 기존 CSV 파일 사용: {csv_path}")
        return csv_path
    
    print(f"❌ CSV 파일이 없습니다: {csv_path}")
    
    # data/kospi100 디렉토리 생성
    data_dir = os.path.dirname(csv_path)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        print(f"📁 디렉토리 생성: {data_dir}")
    
    # KIS API를 사용할 수 있으면 실제 데이터 가져오기 시도
    if get_stock_data_and_save_csv is not None:
        print(f"📥 {stock_name} ({stock_code}) 주가 데이터를 가져와서 CSV 파일을 생성합니다...")
        
        # 종목명이 종목코드와 같은 경우 API에서 가져오기
        if stock_name == stock_code and get_stock_name_from_api:
            actual_stock_name = get_stock_name_from_api(stock_code)
            if actual_stock_name != stock_code:
                stock_name = actual_stock_name
                print(f"📝 종목명 확인: {stock_code} -> {stock_name}")
        
        # CSV 파일 생성
        new_csv_path = get_stock_data_and_save_csv(stock_code, stock_name)
        
        if new_csv_path and os.path.exists(new_csv_path):
            print(f"✅ CSV 파일 생성 완료: {new_csv_path}")
            return new_csv_path
    
    # KIS API를 사용할 수 없거나 실패한 경우 - 가상 데이터 생성 비활성화
    print(f"❌ 실제 데이터를 가져올 수 없습니다. 가상 데이터 생성을 비활성화했습니다.")
    print(f"❌ CSV 파일을 생성할 수 없습니다: {stock_name} ({stock_code})")
    return None

def test_dividend_stock(csv_path, stock_name, dividend_rate=0.03, stock_code=None):
    """배당주식 백테스팅"""
    print(f"\n{'='*60}")
    print(f"=== {stock_name} 배당주식 RSI 매수 전략 ===")
    print(f"{'='*60}")
    
    # 데이터 로드
    print(f"데이터 로드: {csv_path}")
    
    # CSV 파일이 없으면 생성 시도
    if not os.path.exists(csv_path):
        if stock_code:
            print(f"📥 CSV 파일이 없어서 새로 생성합니다...")
            csv_path = ensure_csv_file_exists(csv_path, stock_code, stock_name)
            if csv_path is None:
                print(f"❌ CSV 파일을 생성할 수 없습니다: {stock_name} ({stock_code})")
                return None
        else:
            print(f"❌ 파일을 찾을 수 없습니다: {csv_path}")
            print(f"💡 종목 코드를 제공하면 자동으로 데이터를 가져올 수 있습니다.")
            return None
    
    df = pd.read_csv(csv_path)
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    df.columns = df.columns.str.lower()
    
    print(f"전체 데이터: {len(df)}개 일자")
    print(f"기간: {df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}")
    print(f"약 {len(df)/365:.1f}년의 데이터")
    
    # 백테스팅 설정
    initial_capital = 10_000_000  # 1,000만원
    buy_unit = 1  # 매수단위 (1주씩)
    rsi_buy_threshold = 40  # RSI < 40에서만 매수
    dividend_rate = dividend_rate  # 연간 배당률 (기본 3%)
    
    print(f"\n=== 백테스팅 설정 ===")
    print(f"초기 자본: {initial_capital:,}원")
    print(f"매수단위: {buy_unit}개")
    print(f"매수 조건: RSI < {rsi_buy_threshold}에서만 매수")
    print(f"매도 조건: 매도하지 않음 (장기 보유)")
    print(f"배당률: {dividend_rate:.1%} (연간)")
    
    # RSI 계산 (한 번만 계산)
    print("RSI 계산 중...")
    rsi_period = 14
    delta = df['close'].diff()
    up = delta.where(delta > 0, 0)
    down = -delta.where(delta < 0, 0)
    
    # RSI 계산을 위한 이동평균
    up_ma = up.ewm(com=(rsi_period - 1), min_periods=rsi_period).mean()
    down_ma = down.ewm(com=(rsi_period - 1), min_periods=rsi_period).mean()
    
    rs = up_ma / down_ma
    rsi = 100 - (100 / (1 + rs))
    
    # 백테스팅 실행
    cash = initial_capital
    shares_held = 0
    total_cost = 0  # 총 매수 비용 (평단가 계산용)
    max_shares_held = 0  # 최대 보유 주식 수 추적
    trades = []
    dividend_received = 0  # 총 배당금 수령액
    
    print(f"\n=== 백테스팅 실행 ===")
    
    for i in range(rsi_period, len(df)):
        try:
            current_rsi = rsi.iloc[i]
            if pd.isna(current_rsi):
                continue
                
            current_price = df['close'].iloc[i]
            current_date = df.index[i]
            
            # 매수 신호 처리 (RSI가 낮을 때만)
            shares_to_buy = 0
            if current_rsi < rsi_buy_threshold and cash >= current_price * buy_unit:
                shares_to_buy = buy_unit
            
            if shares_to_buy > 0:
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
                    'rsi': current_rsi,
                    'cash_after': cash,
                    'shares_after': shares_held
                })
                
                profit_sign = "+" if profit_rate >= 0 else ""
                print(f"\033[92m{current_date.strftime('%Y-%m-%d')}: [보유: {shares_held}주][평단가: {avg_price:,.0f}원: {profit_sign}{profit_rate:.1f}%][보유금액: {holding_value:,.0f}원] @ {current_price:,.0f}원 (RSI: {current_rsi:.1f}) +{shares_to_buy}주\033[0m")
            
            # 배당금 수령 시뮬레이션 (연 1회, 12월에)
            if current_date.month == 12 and current_date.day == 15 and shares_held > 0:
                # 연간 배당금 계산 (보유 주식 수 * 주가 * 배당률)
                annual_dividend = shares_held * current_price * dividend_rate
                dividend_received += annual_dividend
                cash += annual_dividend
                
                print(f"\033[94m{current_date.strftime('%Y-%m-%d')}: 배당금 수령 {annual_dividend:,.0f}원 (보유: {shares_held}주, 배당률: {dividend_rate:.1%})\033[0m")
                
        except Exception as e:
            print(f"백테스팅 중 오류 발생 (일자: {df.index[i] if i < len(df) else 'Unknown'}): {e}")
            continue
    
    # 최종 결과 계산
    final_price = df['close'].iloc[-1]
    final_value = cash + (shares_held * final_price)
    total_return = (final_value - initial_capital) / initial_capital * 100
    
    print(f"\n=== {stock_name} 백테스팅 결과 ===")
    print(f"총 매수 거래: {len(trades)}회")
    print(f"최대 보유 주식: {max_shares_held}주")
    print(f"보유 현금: {cash:,.0f}원")
    print(f"보유 주식: {shares_held}주")
    print(f"평단가: {total_cost / shares_held if shares_held > 0 else 0:,.0f}원")
    print(f"현재 주가: {final_price:,.0f}원")
    print(f"주식 평가액: {shares_held * final_price:,.0f}원")
    print(f"총 배당금 수령: {dividend_received:,.0f}원")
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
        'max_shares_held': max_shares_held,
        'final_cash': cash,
        'final_shares': shares_held,
        'avg_price': total_cost / shares_held if shares_held > 0 else 0,
        'final_price': final_price,
        'stock_value': shares_held * final_price,
        'dividend_received': dividend_received,
        'final_value': final_value,
        'total_return': total_return,
        'annual_return': annual_return,
        'buy_hold_return': buy_hold_return,
        'strategy_vs_buyhold': total_return - buy_hold_return
    }

def test_dividend_stocks():
    """배당주식들 백테스팅"""
    print("=== 배당주식 RSI 매수 전략 백테스팅 ===")
    
    # 테스트할 배당주식 리스트 (CSV 파일 경로와 배당률)
    dividend_stocks = [
        # 개별 주식 (우선주)
        {
            'csv_path': 'data/kospi100/009240_한샘.csv',
            'name': '한샘 (009240)',
            'code': '009240',
            'dividend_rate': 0.19,  # 19% (높은 배당률)
            'type': 'stock'
        },
        {
            'csv_path': 'data/kospi100/005385_현대차우.csv',
            'name': '현대차우 (005385)',
            'code': '005385',
            'dividend_rate': 0.025,  # 2.5% (우선주)
            'type': 'stock'
        },
        {
            'csv_path': 'data/kospi100/005935_삼성전자우.csv',
            'name': '삼성전자우 (005935)',
            'code': '005935',
            'dividend_rate': 0.02,  # 2% (우선주)
            'type': 'stock'
        },
        {
            'csv_path': 'data/kospi100/000815_삼성화재우.csv',
            'name': '삼성화재우 (000815)',
            'code': '000815',
            'dividend_rate': 0.03,  # 3% (우선주)
            'type': 'stock'
        },
        # ETF (배당형)
        {
            'csv_path': 'data/kospi100/441680_코스피배당.csv',
            'name': 'TIGER 미국나스닥100커버드콜 (441680)',
            'code': '441680',
            'dividend_rate': 0.08,  # 8% (ETF 배당률)
            'type': 'etf'
        },
        {
            'csv_path': 'data/kospi100/486290_코스피배당.csv',
            'name': 'TIGER 미국나스닥100타겟데일리커버드콜 (486290)',
            'code': '486290',
            'dividend_rate': 0.12,  # 12% (ETF 배당률)
            'type': 'etf'
        },
        {
            'csv_path': 'data/kospi100/0048K0_코스피배당.csv',
            'name': 'KODEX 차이나휴머노이드로봇 (0048K0)',
            'code': '0048K0',
            'dividend_rate': 0.05,  # 5% (ETF 배당률)
            'type': 'etf'
        },
        {
            'csv_path': 'data/kospi100/411420_코스피배당.csv',
            'name': 'KODEX 미국나스닥AI테크액티브 (411420)',
            'code': '411420',
            'dividend_rate': 0.06,  # 6% (ETF 배당률)
            'type': 'etf'
        },
        {
            'csv_path': 'data/kospi100/441680_코스피200타겟위클리커버드콜.csv',
            'name': 'KODEX 200타겟위클리커버드콜 (441680)',
            'code': '441680',
            'dividend_rate': 0.10,  # 10% (ETF 배당률 - 위클리 커버드콜)
            'type': 'etf'
        }
    ]
    
    results = []
    
    # 각 종목별로 백테스팅 실행
    for stock in dividend_stocks:
        try:
            print(f"\n{'='*60}")
            print(f"종목 처리 중: {stock['name']}")
            print(f"CSV 파일: {stock['csv_path']}")
            print(f"{'='*60}")
            
            result = test_dividend_stock(stock['csv_path'], stock['name'], stock['dividend_rate'], stock['code'])
            if result:
                results.append(result)
                print(f"✅ {stock['name']} 백테스팅 완료")
            else:
                print(f"❌ {stock['name']} 백테스팅 실패")
        except Exception as e:
            print(f"\n❌ {stock['name']} 백테스팅 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
    
    # 전체 결과 요약
    if results:
        print(f"\n{'='*100}")
        print("=== 전체 배당주식 결과 요약 ===")
        print(f"{'='*100}")
        
        print(f"{'종목명':<25} {'보유주식':<8} {'평단가':<10} {'현재가':<10} {'주식가치':<12} {'배당금':<10} {'총수익률':<10} {'Buy&Hold':<10} {'차이':<8}")
        print("-" * 100)
        
        for result in results:
            print(f"{result['stock_name']:<25} "
                  f"{result['final_shares']:>6}주 "
                  f"{result['avg_price']:>8,.0f}원 "
                  f"{result['final_price']:>8,.0f}원 "
                  f"{result['stock_value']:>10,.0f}원 "
                  f"{result['dividend_received']:>8,.0f}원 "
                  f"{result['total_return']:>8.2f}% "
                  f"{result['buy_hold_return']:>8.2f}% "
                  f"{result['strategy_vs_buyhold']:>+6.2f}%p")
        
        # 평균 수익률 계산
        avg_strategy_return = sum(r['total_return'] for r in results) / len(results)
        avg_buyhold_return = sum(r['buy_hold_return'] for r in results) / len(results)
        avg_difference = avg_strategy_return - avg_buyhold_return
        
        print("-" * 100)
        print(f"{'평균':<25} "
              f"{'':>6} "
              f"{'':>8} "
              f"{'':>8} "
              f"{'':>10} "
              f"{'':>8} "
              f"{avg_strategy_return:>8.2f}% "
              f"{avg_buyhold_return:>8.2f}% "
              f"{avg_difference:>+6.2f}%p")
        
        print(f"\n총 {len(results)}개 배당주식 테스트 완료")
    else:
        print("\n❌ 테스트할 수 있는 배당주식이 없습니다.")

if __name__ == "__main__":
    test_dividend_stocks()
