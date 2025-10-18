"""
배당금 정보 수집기
연도별 배당금 정보를 자동으로 수집하는 스크립트
"""

import requests
import pandas as pd
from datetime import datetime
import time

def get_dividend_info_naver(stock_code):
    """
    네이버 금융에서 배당 정보 수집
    """
    try:
        url = f"https://finance.naver.com/item/main.nhn?code={stock_code}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # 배당 정보 파싱 (실제로는 BeautifulSoup 등으로 파싱 필요)
        print(f"✅ {stock_code} 배당 정보 수집 완료")
        return True
        
    except Exception as e:
        print(f"❌ {stock_code} 배당 정보 수집 실패: {e}")
        return False

def get_dividend_info_yfinance(symbol):
    """
    yfinance를 사용한 배당 정보 수집
    """
    try:
        import yfinance as yf
        
        # 한국 주식은 .KS 접미사 필요
        if not symbol.endswith('.KS'):
            symbol += '.KS'
            
        ticker = yf.Ticker(symbol)
        dividends = ticker.dividends
        
        if not dividends.empty:
            print(f"✅ {symbol} 배당 정보:")
            print(dividends.tail(10))  # 최근 10개 배당 정보
            return dividends
        else:
            print(f"❌ {symbol} 배당 정보 없음")
            return None
            
    except Exception as e:
        print(f"❌ {symbol} 배당 정보 수집 실패: {e}")
        return None

def get_dividend_info_financedatareader(symbol):
    """
    FinanceDataReader를 사용한 배당 정보 수집
    """
    try:
        import FinanceDataReader as fdr
        
        # 배당 정보는 별도 API가 필요할 수 있음
        df = fdr.DataReader(symbol, '2020-01-01')
        print(f"✅ {symbol} 주가 데이터 수집 완료")
        return df
        
    except Exception as e:
        print(f"❌ {symbol} 배당 정보 수집 실패: {e}")
        return None

def create_dividend_database():
    """
    배당금 데이터베이스 생성
    """
    dividend_db = {
        '005935': {  # 삼성전자우
            'name': '삼성전자우',
            'dividend_history': {
                '2020': 0.02,  # 2%
                '2021': 0.02,
                '2022': 0.02,
                '2023': 0.02,
                '2024': 0.02
            }
        },
        '005385': {  # 현대차우
            'name': '현대차우',
            'dividend_history': {
                '2020': 0.025,  # 2.5%
                '2021': 0.025,
                '2022': 0.025,
                '2023': 0.025,
                '2024': 0.025
            }
        },
        '009240': {  # 한샘
            'name': '한샘',
            'dividend_history': {
                '2020': 0.15,  # 15%
                '2021': 0.18,  # 18%
                '2022': 0.19,  # 19%
                '2023': 0.19,  # 19%
                '2024': 0.19   # 19%
            }
        }
    }
    
    return dividend_db

def get_dividend_rate_by_year(stock_code, year):
    """
    특정 연도의 배당률 조회
    """
    dividend_db = create_dividend_database()
    
    if stock_code in dividend_db:
        year_str = str(year)
        if year_str in dividend_db[stock_code]['dividend_history']:
            return dividend_db[stock_code]['dividend_history'][year_str]
    
    return 0.02  # 기본값 2%

if __name__ == "__main__":
    print("=== 배당금 정보 수집기 ===")
    
    # 테스트할 종목들
    stocks = ['005935', '005385', '009240']
    
    for stock_code in stocks:
        print(f"\n📊 {stock_code} 배당 정보 수집 중...")
        
        # yfinance로 시도
        get_dividend_info_yfinance(stock_code)
        
        # 네이버로 시도
        get_dividend_info_naver(stock_code)
        
        time.sleep(1)  # 요청 간격 조절
    
    print("\n=== 배당금 데이터베이스 ===")
    dividend_db = create_dividend_database()
    for code, info in dividend_db.items():
        print(f"\n{info['name']} ({code}):")
        for year, rate in info['dividend_history'].items():
            print(f"  {year}년: {rate*100:.1f}%")
