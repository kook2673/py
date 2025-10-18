#-*-coding:utf-8 -*-
'''

관련 포스팅
https://blog.naver.com/zacra/223341020867

위 포스팅을 꼭 참고하세요!!!
 
📌 게만아의 모든 코드는 특정 종목 추천이나 투자 권유를 위한 것이 아닙니다.  
제작자의 개인적인 견해를 바탕으로 구성된 교육용 예시 코드이며, 수익을 보장하지 않습니다
실제 투자 판단 및 실행은 전적으로 사용자 본인의 책임입니다.

주식/코인 파이썬 매매 FAQ
https://blog.naver.com/zacra/223203988739

FAQ로 해결 안되는 기술적인 문제는 클래스101 강의의 댓글이나 위 포스팅에 댓글로 알려주세요.
파이썬 코딩에 대한 답변만 가능합니다. 현행법 상 투자 관련 질문은 답변 불가하다는 점 알려드려요!

'''
import myUpbit   #우리가 만든 함수들이 들어있는 모듈
import json


top_file_path = "/var/autobot/UpbitTopCoinList.json"

#거래대금이 많은 탑코인 30개의 리스트
TopCoinList = myUpbit.GetTopCoinList("day",30)

#파일에 리스트를 저장합니다
with open(top_file_path, 'w') as outfile:
    json.dump(TopCoinList, outfile)

