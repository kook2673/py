#-*-coding:utf-8 -*-

import ende_key

'''
여러분의 시크릿 키와 엑세스 키를 
ende_key.py에 있는 키를 활용해서 암호화한 값을 넣으세요

마찬가지 방법으로 아래 로직을 실행하시면 됩니다.. (ende_key.py 참조)

'''
from cryptography.fernet import Fernet

class SimpleEnDecrypt:
    def __init__(self, key=None):
        if key is None: # 키가 없다면
            key = Fernet.generate_key() # 키를 생성한다
        self.key = key
        self.f   = Fernet(self.key)
    
    def encrypt(self, data, is_out_string=True):
        if isinstance(data, bytes):
            ou = self.f.encrypt(data) # 바이트형태이면 바로 암호화
        else:
            ou = self.f.encrypt(data.encode('utf-8')) # 인코딩 후 암호화
        if is_out_string is True:
            return ou.decode('utf-8') # 출력이 문자열이면 디코딩 후 반환
        else:
            return ou
        
    def decrypt(self, data, is_out_string=True):
        if isinstance(data, bytes):
            ou = self.f.decrypt(data) # 바이트형태이면 바로 복호화
        else:
            ou = self.f.decrypt(data.encode('utf-8')) # 인코딩 후 복호화
        if is_out_string is True:
            return ou.decode('utf-8') # 출력이 문자열이면 디코딩 후 반환
        else:
            return ou

         

simpleEnDecrypt = SimpleEnDecrypt(ende_key.ende_key) #ende_key.py 에 있는 키를 넣으세요

access = "ItfQH5bqirDlzxL2oFrFWhMZLWDTWqWZI6jSWwNK0fZuztzoCq2GodmYL4rolzFg"          # 본인 값으로 변경
secret = "8yykgyVOIdkyXuyyzLbtG34SiinZsLX0cylr2OVyvw5DMAji5r2XQRNNoOUd4UYn"          # 본인 값으로 변경

#print("access_key: ", simpleEnDecrypt.encrypt(access))
#print("scret_key: ", simpleEnDecrypt.encrypt(secret))

#바이낸스
binance_access = "gAAAAABombuMXBzryecRchtVBd5WNtrDOit1EFBvZbl5pweJSRxGxkrbrhmtWhiLN97Rj23Tw7rXKJmD4LiQ1trEYprG3EwEt91GBDuF_w7myFSZ6ob6lkA1a4GN_JbJ34vZS_PpopapB1OsfCcCsowxM8EkRXuYUOewpBqPOoA2FUzCEINDpJ0="
binance_secret = "gAAAAABombuMJ_KLgEMs7R2ZX7RrgjK4IXNihdqNRpI5EWdQoYNoaP88ddtlQLzgEwFCp4vMVVMRc_XPZr2qlMS0GfTxKmi1wn2BUoDTaOF4IKWoCxw7wp0e-1pswApay-n8mpS-bCPVvy3R-YkMqRAav2ZT1Fiwehwe0MEBfH45HnyYhFE4VKQ="