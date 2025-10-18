#-*-coding:utf-8 -*-
'''

기간을 알기 위한 샘플 예
이 파이썬 파일 코딩 후 시간이 지났을 것이기 때문에
아래의 숫자들은 변경해서 사용하세요 ^^! 

관련 포스팅

연복리 200에 가까운 이평조합 전략!
https://blog.naver.com/zacra/223074617299

위 포스팅을 꼭 참고하세요!!!

📌 게만아의 모든 코드는 특정 종목 추천이나 투자 권유를 위한 것이 아닙니다.  
제작자의 개인적인 견해를 바탕으로 구성된 교육용 예시 코드이며, 수익을 보장하지 않습니다
실제 투자 판단 및 실행은 전적으로 사용자 본인의 책임입니다.

주식/코인 자동매매 FAQ
https://blog.naver.com/zacra/223203988739

FAQ로 해결 안되는 기술적인 문제는 클래스101 강의의 댓글이나 위 포스팅에 댓글로 알려주세요.
파이썬 코딩에 대한 답변만 가능합니다. 현행법 상 투자 관련 질문은 답변 불가하다는 점 알려드려요!



'''

import pyupbit



coin_ticker = "KRW-BTC"

#1. 전체 기간
#df = pyupbit.get_ohlcv(coin_ticker,interval="day",count=6000, period=0.3)
#2. 상승장
#df = pyupbit.get_ohlcv(coin_ticker,interval="day",count=1150, period=0.3)
#3. 횡보장
#df = pyupbit.get_ohlcv(coin_ticker,interval="day",count=350, period=0.3)
#4. 하락장
df = pyupbit.get_ohlcv(coin_ticker,interval="day",count=570, period=0.3)


############# 이동평균선! ###############
df['30ma'] = df['close'].rolling(30).mean() #30일선까지 테스트할때 사용하니깐 이걸 정의 해줘야 아래 데이터 없는 항목이 있는 걸 날릴 때 동일하게 날려져서 같은 기간으로 시작 된다.
########################################

df.dropna(inplace=True) #데이터 없는건 날린다!


#1. 전체 기간
#df = df
#2. 상승장
#df = df[:len(df)-730]
#3. 횡보장
#df = df[:len(df)-35]
#4. 하락장
df = df[:len(df)-290]

print(df.iloc[21].name, " ~ ", df.iloc[-1].name) #구간분할과 비교하기 위해 21일 이후에 투자가 시작되는 걸 감안!

