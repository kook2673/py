# -*- coding: utf-8 -*-
'''

관련 포스팅
https://blog.naver.com/zacra/223622479916
위 포스팅을 꼭 참고하세요!!!

'''
import requests
import json

#파일 경로입니다.
kakao_token_file_path = "/var/autobot/kakao_token.json"

url = 'https://kauth.kakao.com/oauth/token'
rest_api_key = '여러분의 REST API값'
redirect_uri = 'https://localhost:8080' #Redirect URI값!
authorize_code = '여러분의 인증코드'



Tokens = None 
IsAlreadyGetToken = False

try:
    #이 부분이 파일을 읽어서 리스트에 넣어주는 로직입니다. 
    with open(kakao_token_file_path, 'r') as json_file:
        Tokens = json.load(json_file)
        print("현재 저장된 값들: ", Tokens)
        
    IsAlreadyGetToken = True
except Exception as e:
    print(e)
    
    IsAlreadyGetToken = False
    

if IsAlreadyGetToken == True:
    print("액세스 토큰 재발급!! ")
    
    data = {
        "grant_type": "refresh_token",
        "client_id": rest_api_key,
        "refresh_token": Tokens['refresh_token']
    }
    response = requests.post(url, data=data)
    tokens = response.json()
    print("------------------------")
    print(tokens)
    print("------------------------")


    Tokens['access_token'] = tokens['access_token']

    try:
        Tokens['refresh_token'] = tokens['refresh_token']
    except Exception as e:
        print("아직 리프레쉬토큰 재발급 기간이 아니라 없음")


    with open(kakao_token_file_path, 'w') as outfile:
        json.dump(Tokens, outfile)
        

else:
    
    print("최초 1번만 실행되고 첫 토큰 값들을 파일로 저장해둠 ")
    data = {
        'grant_type':'authorization_code',
        'client_id':rest_api_key,
        'redirect_uri':redirect_uri,
        'code': authorize_code,
        }

    response = requests.post(url, data=data)
    tokens = response.json()
    print(tokens)


    with open(kakao_token_file_path, 'w') as outfile:
        json.dump(tokens, outfile)
        
    print("토큰발행 완료!")

        

