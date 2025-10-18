# -*- coding: utf-8 -*-
'''

관련 포스팅
https://blog.naver.com/zacra/223622479916
위 포스팅을 꼭 참고하세요!!!

'''
import requests

URL = '여러분의 웹훅URL 값'

def SendMessage(msg, title='myAutobot'):
    
    try:
        # 메시지 전송
        requests.post(
            URL,
            headers={  # 'header'가 아닌 'headers'로 수정
                'content-type': 'application/json'
            },
            json={
                'text': title,
                'blocks': [
                    {
                        'type': 'section',
                        'text': {
                            'type': 'mrkdwn',
                            'text': msg
                        }
                    }
                ]
            }
        )
    except Exception as ex:
        print(ex)
