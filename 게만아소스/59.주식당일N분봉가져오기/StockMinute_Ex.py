# -*- coding: utf-8 -*-
'''

관련 포스팅
https://blog.naver.com/zacra/223571914494

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

import pprint

Common.SetChangeMode("VIRTUAL")

df = KisKR.GetOhlcvMinute("005930",'10T') # '1T','3T','5T','10T','15T','30T', '60T'
pprint.pprint(df)

print("---------------------\n")

ma = Common.GetMA(df,5,-1)
print("10분봉 현재 5이평선: ",ma)

rsi = Common.GetRSI(df,14,-1)
print("10분봉 현재 RSI14지표 : ",rsi)



    
