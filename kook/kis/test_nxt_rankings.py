# -*- coding: utf-8 -*-
"""
NXT 종목 조회 테스트 스크립트
"""

import os
import sys
import logging
from datetime import datetime

# 부모 디렉토리를 sys.path에 추가
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)

import KIS_Common as Common
import KIS_API_Helper_KR as KisKR

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_nxt_rankings.log')
    ]
)

Common.SetChangeMode("REAL")

def fetch_rising_stocks(count: int, market: str, sort_type: str) -> list:
    """상승률 상위 종목 조회"""
    try:
        # KIS API 호출
        result = KisKR.GetRisingStocks(market, sort_type, count)
        
        if result and 'output' in result:
            stocks = result['output']
            logging.info(f"KIS API 성공: {len(stocks)}개 종목 조회됨")
            return stocks
        else:
            logging.error(f"KIS API 실패: {result}")
            return []
            
    except Exception as e:
        logging.error(f"종목 조회 오류: {e}")
        return []

def get_nxt_rankings() -> list:
    """NXT 상위 5위 종목 조회 (시가대비 상승률)"""
    try:
        stocks = fetch_rising_stocks(5, "NX", "2")  # 시가대비 상승률 상위 5개
        logging.info(f"NXT API 조회 결과: {len(stocks)}개 종목")
        
        rankings = []
        
        for i, stock in enumerate(stocks):
            code = stock.get('code', '')
            name = stock.get('name', '')
            price = float(stock.get('price', 0))
            pct = float(stock.get('pct', 0))
            
            logging.info(f"NXT {i+1}위: {code} {name} - 가격: {price:,.0f}원, 상승률: {pct:.2f}%")
            
            if code and name and price > 0:
                rankings.append({
                    'rank': i + 1,
                    'code': code,
                    'name': name,
                    'price': price,
                    'pct': pct
                })
        
        logging.info(f"NXT 유효 종목: {len(rankings)}개")
        return rankings
    except Exception as e:
        logging.error(f"NXT 순위 조회 실패: {e}")
        return []

def main():
    """메인 테스트 함수"""
    print("=" * 50)
    print("NXT 종목 조회 테스트 시작")
    print(f"테스트 시간: {datetime.now()}")
    print("=" * 50)
    
    # NXT 종목 조회
    rankings = get_nxt_rankings()
    
    print("\n" + "=" * 50)
    print("조회 결과 요약")
    print("=" * 50)
    
    if rankings:
        print(f"총 {len(rankings)}개 종목 조회됨:")
        for ranking in rankings:
            print(f"  {ranking['rank']}위: {ranking['name']}({ranking['code']}) - {ranking['price']:,.0f}원 ({ranking['pct']:+.2f}%)")
    else:
        print("조회된 종목이 없습니다.")
    
    print("\n테스트 완료!")

if __name__ == "__main__":
    main()
