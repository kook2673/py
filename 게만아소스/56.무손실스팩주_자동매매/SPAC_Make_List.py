# -*- coding: utf-8 -*-
'''

python -m pip install --upgrade pykrx
python install --upgrade pykrx
python3 install --upgrade pykrx 

관련 포스팅
https://blog.naver.com/zacra/223548787076

위 포스팅을 꼭 참고하세요!!!


📌 게만아의 모든 코드는 특정 종목 추천이나 투자 권유를 위한 것이 아닙니다.  
제공된 전략은 학습 및 테스트 목적으로 구성된 예시 코드이며
실제 투자 판단 및 실행은 전적으로 사용자 본인의 책임입니다.
   

주식/코인 자동매매 FAQ
https://blog.naver.com/zacra/223203988739

FAQ로 해결 안되는 기술적인 문제는 클래스101 강의의 댓글이나 위 포스팅에 댓글로 알려주세요.
파이썬 코딩에 대한 답변만 가능합니다. 현행법 상 투자 관련 질문은 답변 불가하다는 점 알려드려요!
   

'''
import KIS_Common as Common
import KIS_API_Helper_KR as KisKR
import json
import line_alert
import time

from pykrx import stock

Common.SetChangeMode("VIRTUAL")

#스팩주는 코스닥에 있다. 코스닥 종목 다 가져옴
kosdaq_list = stock.get_market_ticker_list(market="KOSDAQ")

print(len(kosdaq_list))

result = "스팩주 종목 코드 수집"
print(result)
line_alert.SendMessage(result)
    
SpacList = list()
for ticker in kosdaq_list:
    name = stock.get_market_ticker_name(ticker)
    time.sleep(0.2)
    if "스팩" in name:
        SpacList.append(ticker)
        print(name,ticker)
    print("..")
        
        
#파일 경로입니다.
file_path = "/var/autobot/SPAC_TickerList.json"
#파일에 리스트를 저장합니다
with open(file_path, 'w') as outfile:
    json.dump(SpacList, outfile)


result = "스팩주 종목 코드 수집 끝"
print(result)
line_alert.SendMessage(result)
