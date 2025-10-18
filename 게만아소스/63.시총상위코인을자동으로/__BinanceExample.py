#-*-coding:utf-8 -*-
'''
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

바이낸스 ccxt 버전
pip3 install --upgrade ccxt==4.2.19
이렇게 버전을 맞춰주세요!

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

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
import ccxt
import myBinance
import pprint


#########################################################
import ende_key  #암복호화키
import my_key   


#암복호화 클래스 객체를 미리 생성한 키를 받아 생성한다.
simpleEnDecrypt = myBinance.SimpleEnDecrypt(ende_key.ende_key)


#암호화된 액세스키와 시크릿키를 읽어 복호화 한다.
Binance_AccessKey = simpleEnDecrypt.decrypt(my_key.binance_access)
Binance_ScretKey = simpleEnDecrypt.decrypt(my_key.binance_secret)
#########################################################

'''
#위 암복호화가 어려우면 아래 코드를 활용하자!

Binance_AccessKey = "여러분의 액세스키"
Binance_ScretKey = "여러분의 시크릿키"

'''

# binance 객체 생성
binanceX = ccxt.binance(config={
    'apiKey': Binance_AccessKey, 
    'secret': Binance_ScretKey,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'futures' #spot 또는 futures
    }
})


Top100CoinList = list()

#파일 경로입니다.
#top100coin_file_path = "./Top100CoinList.json" #내 PC에서
top100coin_file_path = "/var/autobot/Top100CoinList.json" #서버에서

try:
    #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
    with open(top100coin_file_path, 'r') as json_file:
        Top100CoinList = json.load(json_file)

except Exception as e:
    #처음에는 파일이 존재하지 않을테니깐 당연히 예외처리가 됩니다!
    print("Exception by First")


pprint.pprint(Top100CoinList)


# 'stablecoin' : 스테이블 코인, 'centralized-exchange' : 중앙화 거래소 코인
def GetTopCoinList(Top100CoinList, count, include_tags=['all'], exclude_tags=['none']):
    """
    시가총액 상위 코인들을 가져오되, 특정 태그를 포함하거나 제외하여 필터링합니다.
    
    Args:
        count (int): 가져올 코인의 개수
        include_tags (list): 포함할 태그 리스트 (기본값: ['all'] - 모든 태그 포함)
        exclude_tags (list): 제외할 태그 리스트 (기본값: ['none'])
    
    Returns:
        list: 필터링된 코인 심볼 리스트
    """
    
    filtered_coins = []
    
    for coin_info in Top100CoinList:
        # include_tags가 'all'이 아닌 경우, 포함할 태그 확인
        if 'all' not in include_tags:
            if not any(tag in coin_info['tags'] for tag in include_tags):
                continue
        
        # exclude_tags는 include_tags에 명시적으로 요청된 태그는 제외하지 않음
        if any(tag in coin_info['tags'] for tag in exclude_tags) and not any(tag in include_tags for tag in coin_info['tags']):
            continue
                
        filtered_coins.append(coin_info['symbol'])
        
        if len(filtered_coins) >= count:
            break
            
    return filtered_coins


#업비트
def GetTopMarketCapCoinList(TopCoinList, count):
    """
    시가총액 상위 코인 중 업비트에 상장된 코인만 필터링하여 반환
    :param count: 원하는 코인 개수
    :return: 필터링된 코인 리스트
    """
    BinanceCoinList = binanceX.fetch_tickers()

    binance_coins = set(coin.replace("/USDT", "").replace(":USDT", "") for coin in BinanceCoinList)
    filtered_coins = []
    
    for coin in TopCoinList:
        if coin in binance_coins:
            filtered_coins.append(f"{coin}/USDT")
        if len(filtered_coins) >= count:
            break
            
    return filtered_coins



# 상위 20개 코인을 가져오되 스테이블 코인과 거래소 코인은 제외합니다
print("#########################################################")
print("시총 상위 20개 코인을 가져오되 스테이블 코인과 거래소 코인은 제외합니다")
ResultList = GetTopCoinList(Top100CoinList, 20,['all'],['stablecoin','centralized-exchange'])
print(ResultList)
for idx, coin in enumerate(ResultList, 1):
    print(f"{idx}위: {coin}")
print("#########################################################\n")


# 바이낸스 상장된 상위 10개 코인을 가져옵니다.
print("#########################################################")
print("바이낸스 상장된 상위 10개 코인을 가져옵니다.")
UpbitCoinTopList = GetTopMarketCapCoinList(ResultList, 10)
print(UpbitCoinTopList)
for idx, coin in enumerate(UpbitCoinTopList, 1):
    print(f"{idx}위: {coin}")

print("#########################################################")

