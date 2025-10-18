#-*-coding:utf-8 -*-

'''

여러 백테스팅 결과를 종합해서 보여주는 예시!


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

import myUpbit   #우리가 만든 함수들이 들어있는 모듈
import pyupbit

import ende_key  #암복호화키
import my_key    #업비트 시크릿 액세스키
import pandas as pd
import pprint

import json
import pandas as pd

import time

All_List = list()

#파일 경로입니다.
test_file_path = "/var/autobot/BackTest_All_upbit.json"
try:
    with open(test_file_path, 'r') as json_file:
        All_List = json.load(json_file)

except Exception as e:
    print("Exception by First")




Up_List = list()

#파일 경로입니다.
test_file_path = "/var/autobot/BackTest_Up_upbit.json"
try:
    with open(test_file_path, 'r') as json_file:
        Up_List = json.load(json_file)

except Exception as e:
    print("Exception by First")



Wave_List = list()

#파일 경로입니다.
test_file_path = "/var/autobot/BackTest_Wave_upbit.json"
try:
    with open(test_file_path, 'r') as json_file:
        Wave_List = json.load(json_file)

except Exception as e:
    print("Exception by First")



Down_List = list()

#파일 경로입니다.
test_file_path = "/var/autobot/BackTest_Down_upbit.json"
try:
    with open(test_file_path, 'r') as json_file:
        Down_List = json.load(json_file)

except Exception as e:
    print("Exception by First")





df_all = pd.DataFrame(All_List)

df_all['RevenueRate_rank'] = df_all['RevenueRate'].rank(ascending=True)
df_all['MDD_rank'] = df_all['MDD'].rank(ascending=True)
df_all['Score'] = df_all['RevenueRate_rank'] + df_all['MDD_rank']
df_all = df_all.sort_values(by="Score",ascending=False)

print("---- 전체 ----")
pprint.pprint(df_all.head(50))




df_up = pd.DataFrame(Up_List)

df_up['RevenueRate_rank'] = df_up['RevenueRate'].rank(ascending=True)
df_up['MDD_rank'] = df_up['MDD'].rank(ascending=True)
df_up['Score'] = df_up['RevenueRate_rank'] + df_up['MDD_rank'] 
df_up = df_up.sort_values(by="Score",ascending=False)


print("---- 상승장 ----")
pprint.pprint(df_up.head(50))





df_wave = pd.DataFrame(Wave_List)

df_wave['RevenueRate_rank'] = df_wave['RevenueRate'].rank(ascending=True)
df_wave['MDD_rank'] = df_wave['MDD'].rank(ascending=True)
df_wave['Score'] = df_wave['RevenueRate_rank'] + df_wave['MDD_rank'] 
df_wave = df_wave.sort_values(by="Score",ascending=False)

print("---- 횡보장 ----")
pprint.pprint(df_wave.head(50))





df_down = pd.DataFrame(Down_List)

df_down['RevenueRate_rank'] = df_down['RevenueRate'].rank(ascending=True)
df_down['MDD_rank'] = df_down['MDD'].rank(ascending=True)
df_down['Score'] = df_down['RevenueRate_rank'] + df_down['MDD_rank']
df_down = df_down.sort_values(by="Score",ascending=False)

print("---- 하락장 ----")
pprint.pprint(df_down.head(50))



ResultList = list()

for ma1 in range(3,6):
    for ma2 in range(3,11):
        for ma3 in range(3,31):

            if ma1 < ma2 < ma3:
                print(ma1,' ',ma2, ' ',ma3, "...make total data..")

                ResultData = dict()
                ResultData['ma_str'] = str(ma1) + " " + str(ma2) + " " + str(ma3)

                Score = 0
                for idx, row in df_all.iterrows():
                    if row['ma_str'] == ResultData['ma_str']:
                        ResultData['AllRevenueRate'] = row['RevenueRate']
                        ResultData['AllMDD'] = row['MDD']
                        Score += (row['Score'] * 0.25) #전체 기간 비중
                        break
        
                for idx, row in df_up.iterrows():
                    if row['ma_str'] == ResultData['ma_str']:
                        ResultData['UpRevenueRate'] = row['RevenueRate']
                        ResultData['UpMDD'] = row['MDD']
                        Score += (row['Score'] * 0.25) #상승장 비중

                        break

                for idx, row in df_wave.iterrows():
                    if row['ma_str'] == ResultData['ma_str']:
                        ResultData['WaveRevenueRate'] = row['RevenueRate']
                        ResultData['WaveMDD'] = row['MDD']
                        Score += (row['Score'] * 0.25) #횡보장 비중

                        break
                    
                for idx, row in df_down.iterrows():
                    if row['ma_str'] == ResultData['ma_str']:
                        ResultData['DownRevenueRate'] = row['RevenueRate']
                        ResultData['DownMDD'] = row['MDD']
                        Score += (row['Score'] * 0.25) #하락장 비중

                        break


                ResultData['Score'] = Score


                ResultList.append(ResultData)



print("----------------------------")

df = pd.DataFrame(ResultList)

df  = df.sort_values(by="Score",ascending=False) #스코어

pprint.pprint(df.head(50))

