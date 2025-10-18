# -*- coding: utf-8 -*-
'''

관련 포스팅
https://blog.naver.com/zacra/223622479916
위 포스팅을 꼭 참고하세요!!!

'''
import requests

URL = "여러분의 웹훅URL"

def SendMessage(msg):
    try:
        message = {"content": f"{str(msg)}"}
        requests.post(URL, data=message)
    except Exception as ex:
        print(ex)