# -*- coding: utf-8 -*-
'''

-*- 백테스팅 코드가 있는 전략들은 패키지 16번 부터 나오기 시작하니 참고하세요!! -*-


관련 포스팅

앞으로 30년간 주식시장이 하락해도 수익나는 미친 전략 - 순환적립식 투자 + 자산배분을 카나리아 자산들을 통해 스마트하게 개선하기!
https://blog.naver.com/zacra/222969725781

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
import json


#계좌 선택.. "VIRTUAL" 는 모의 계좌!
Common.SetChangeMode("VIRTUAL") #REAL or VIRTUAL



CanariaScoreDict = dict()

canaria_file_path = "/var/autobot/CanariaScore.json"
try:
    with open(canaria_file_path, 'r') as json_file:
        CanariaScoreDict = json.load(json_file)

except Exception as e:
    print("Exception by First")

'''
카나리아 자산

SPY : 미국 주식
VEA : 선진국 주식
VWO : 개발도상국 주식
BND : 미국 혼합채권

'''
StockCodeList = ["SPY","VEA","VWO","BND"]

Avg_Period = 10

Sum_Avg_MomenTum = 0
print("------------------------")
for stock_code in StockCodeList:

    df = Common.GetOhlcv("US",stock_code,200)
    Now_Price = Common.GetCloseData(df,-1) #현재가

   # print("Now_Price", Now_Price)

    Up_Count = 0
    Start_Num = -20
    for i in range(1,int(Avg_Period)+1):
        
        CheckPrice = Common.GetCloseData(df,Start_Num)
       # print(CheckPrice, "  <<-  df[-", Start_Num,"]")

        if Now_Price >= CheckPrice:
          #  print("UP!")
            Up_Count += 1.0


        Start_Num -= 20

    avg_momentum_score = Up_Count/Avg_Period

    CanariaScoreDict[stock_code] = avg_momentum_score

    Sum_Avg_MomenTum += avg_momentum_score

    print(stock_code, "10개월 평균 모멘텀 ", CanariaScoreDict[stock_code])


CanariaScoreDict['TOTAL_AVG'] = (Sum_Avg_MomenTum / len(StockCodeList))
print("------------------------")
print("모든 카나리아 자산의 10개월 평균 모멘텀의 평균 ", CanariaScoreDict['TOTAL_AVG'])
print("------------------------")
with open(canaria_file_path, 'w') as outfile:
    json.dump(CanariaScoreDict, outfile)