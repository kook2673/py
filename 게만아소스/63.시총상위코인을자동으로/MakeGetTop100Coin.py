#-*-coding:utf-8 -*-
'''

관련 포스팅

https://blog.naver.com/zacra/223728753947


위 포스팅을 꼭 참고하세요!!!

📌 게만아의 모든 코드는 특정 종목 추천이나 투자 권유를 위한 것이 아닙니다.  
제작자의 개인적인 견해를 바탕으로 구성된 교육용 예시 코드이며, 수익을 보장하지 않습니다
실제 투자 판단 및 실행은 전적으로 사용자 본인의 책임입니다.

주식/코인 파이썬 매매 FAQ
https://blog.naver.com/zacra/223203988739

FAQ로 해결 안되는 기술적인 문제는 클래스101 강의의 댓글이나 위 포스팅에 댓글로 알려주세요.
파이썬 코딩에 대한 답변만 가능합니다. 현행법 상 투자 관련 질문은 답변 불가하다는 점 알려드려요!

  
'''
import json
from requests import  Session
import pprint

#코인을 저장할 리스트!!
Top100CoinList = list()

#파일 경로입니다.
#top100coin_file_path = "./Top100CoinList.json" #내 PC에서
top100coin_file_path = "/var/autobot/Top100CoinList.json" #서버에서

url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
parameters = {
    'start': '1',
    'limit': '100',  
    'convert': 'USD'
}
headers = {
    'Accepts': 'application/json',
    'X-CMC_PRO_API_KEY': '여러분의 API키'  # 여기에 본인의 API 키를 입력하세요
}

session = Session()
session.headers.update(headers)

try:
    response = session.get(url, params=parameters)
    data = json.loads(response.text)
    
    # 데이터 구조 확인을 위한 디버깅 출력
    print("데이터 구조:", type(data))
    if 'data' in data:
        print("첫 번째 코인 데이터:", data['data'][0] if data['data'] else "데이터 없음")
    
    # 모든 코인의 정보를 저장
    coins_list = []
    for coin in data['data']:
        pprint.pprint(coin)

        if isinstance(coin, dict) and 'symbol' in coin:
            coin_info = {
                'symbol': coin['symbol'],
                'tags': coin.get('tags', [])  # tags가 없는 경우 빈 리스트 반환
            }
            coins_list.append(coin_info)
    
    # 상위 100개만 선택
    top_100_coins = coins_list[:100]
    
    print("필터링된 코인:", top_100_coins)
    print(f'가져온 코인 수: {len(top_100_coins)}')

    # 파일에 저장
    with open(top100coin_file_path, 'w') as outfile:
        json.dump(top_100_coins, outfile, indent=4)
        
except Exception as e:
    print(f'에러 발생: {e}')
    # 에러 상세 정보 출력
    import traceback
    print(traceback.format_exc())

