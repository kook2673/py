import os
import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

class KiwoomOpenAPI:
    def __init__(self, account_no: str = "", env_path: Optional[str] = None):
        # .env 로드
        if env_path is None:
            env_path = os.path.join(os.path.dirname(__file__), ".env")
        load_dotenv(env_path)
        self.api_key = os.getenv("KIWOOM_APP_KEY")
        self.api_secret = os.getenv("KIWOOM_SECRET_KEY")
        self.account_no = account_no
        self.mock = os.getenv("KIWOOM_MOCK", "false").lower() == "true"
        self.base_url = "https://mockapi.kiwoom.com" if self.mock else "https://api.kiwoom.com"
        self.env_path = env_path
        self.access_token = os.getenv("KIWOOM_ACCESS_TOKEN")
        self.token_expires_at = None

    def get_access_token(self):
        url = self.base_url + "/oauth2/token"
        headers = {"Content-Type": "application/json;charset=UTF-8"}
        data = {
            "grant_type": "client_credentials",
            "appkey": self.api_key,
            "secretkey": self.api_secret
        }
        resp = requests.post(url, headers=headers, json=data)
        resp.raise_for_status()
        result = resp.json()
        
        # 키움 API는 'token' 필드를 사용
        token = result.get("token") or result.get("access_token")
        
        if token:
            self.save_token_to_env(token)
            self.access_token = token
            print(f"[DEBUG] 토큰 발급 성공: {token[:20]}...")
            return token
        else:
            raise Exception(f"토큰 발급 실패: {result}")

    def save_token_to_env(self, token):
        lines = []
        if os.path.exists(self.env_path):
            with open(self.env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        found = False
        for i, line in enumerate(lines):
            if line.startswith("KIWOOM_ACCESS_TOKEN="):
                lines[i] = f"KIWOOM_ACCESS_TOKEN={token}\n"
                found = True
                break
        if not found:
            lines.append(f"KIWOOM_ACCESS_TOKEN={token}\n")
        with open(self.env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

    def ensure_token(self):
        if not self.access_token:
            self.access_token = self.get_access_token()
        return self.access_token
    
    def is_token_valid(self, response: dict) -> bool:
        """응답에서 토큰 유효성 확인"""
        if 'return_code' in response:
            return_code = response['return_code']
            return_msg = response.get('return_msg', '')
            
            # 토큰 관련 오류 코드들
            token_error_codes = ['3', '8005']  # 토큰이 유효하지 않습니다
            token_error_messages = ['Token이 유효하지 않습니다', '인증에 실패했습니다']
            
            if str(return_code) in token_error_codes:
                return False
            
            for error_msg in token_error_messages:
                if error_msg in return_msg:
                    return False
        
        return True
    
    def make_api_request(self, url: str, headers: dict, params: dict, retry_count: int = 0) -> dict:
        """API 요청을 수행하고 토큰 재발급이 필요한 경우 자동 처리"""
        max_retries = 1  # 최대 1번 재시도
        
        try:
            resp = requests.post(url, headers=headers, json=params)
            result = resp.json()
            
            # 토큰이 유효하지 않은 경우
            if not self.is_token_valid(result) and retry_count < max_retries:
                print(f"[DEBUG] 토큰이 유효하지 않습니다. 새로운 토큰을 발급받습니다. (재시도 {retry_count + 1}/{max_retries + 1})")
                
                # 새로운 토큰 발급
                new_token = self.get_access_token()
                
                # 헤더의 토큰 업데이트
                headers['authorization'] = f'Bearer {new_token}'
                
                # 재시도
                return self.make_api_request(url, headers, params, retry_count + 1)
            
            return result
            
        except Exception as e:
            print(f"[DEBUG] API 요청 중 오류 발생: {e}")
            return {'return_code': '9999', 'return_msg': f'API 요청 오류: {e}'}

    # ================== 테마 API ==================
    def get_theme_groups(self, date_tp: str = '10', flu_pl_amt_tp: str = '1', cont_yn: str = 'N', next_key: str = '') -> dict:
        """
        테마그룹별요청 (ka90001)
        """
        url = self.base_url + '/api/dostk/thme'
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {self.ensure_token()}',
            'cont-yn': cont_yn,
            'next-key': next_key,
            'api-id': 'ka90001'
        }
        params = {
            'qry_tp': '0',
            'stk_cd': '',
            'date_tp': date_tp,
            'thema_nm': '',
            'flu_pl_amt_tp': flu_pl_amt_tp,
            'stex_tp': '1'
        }
        
        print(f"[DEBUG] API URL: {url}")
        print(f"[DEBUG] Headers: {headers}")
        print(f"[DEBUG] Params: {params}")
        
        # 새로운 토큰 관리 구조 사용
        result = self.make_api_request(url, headers, params)
        
        print(f"[DEBUG] Response JSON: {result}")
        
        return result

    def get_theme_stocks(self, theme_grp_cd: str, date_tp: str = '2', cont_yn: str = 'N', next_key: str = '') -> dict:
        """
        테마구성종목요청 (ka90002)
        """
        url = self.base_url + '/api/dostk/thme'
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {self.ensure_token()}',
            'cont-yn': cont_yn,
            'next-key': next_key,
            'api-id': 'ka90002'
        }
        params = {
            'date_tp': date_tp,
            'thema_grp_cd': theme_grp_cd,
            'stex_tp': '1'
        }
        
        # 새로운 토큰 관리 구조 사용
        return self.make_api_request(url, headers, params)

    def get_daily_ohlcv(self, stock_code, base_dt=None, upd_stkpc_tp='1', cont_yn='N', next_key=''):
        """
        일일 OHLCV(일봉) 데이터 조회
        stock_code: 종목코드 (예: '005930')
        base_dt: 기준일자 (YYYYMMDD, 기본값 오늘)
        upd_stkpc_tp: 수정주가구분 (기본 1)
        cont_yn, next_key: 연속조회용
        """
        if base_dt is None:
            base_dt = datetime.now().strftime('%Y%m%d')
        url = self.base_url + '/api/dostk/chart'
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {self.access_token}',
            'cont-yn': cont_yn,
            'next-key': next_key,
            'api-id': 'ka10081',
        }
        data = {
            'stk_cd': stock_code,
            'base_dt': base_dt,
            'upd_stkpc_tp': upd_stkpc_tp,
        }
        resp = requests.post(url, headers=headers, json=data)
        resp.raise_for_status()
        result = resp.json()
        return result

    def get_hoga(self, stock_code):
        """
        주식호가요청(ka10004) - 최우선 매수/매도호가 반환
        반환값: {'best_bid': int, 'best_ask': int}
        """
        url = self.base_url + '/api/dostk/mrkcond'
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {self.ensure_token()}',
            'cont-yn': 'N',
            'next-key': '',
            'api-id': 'ka10004',
        }
        data = {
            'stk_cd': stock_code,
        }
        resp = requests.post(url, headers=headers, json=data)
        resp.raise_for_status()
        result = resp.json()
        # 실제 응답 구조에 따라 최우선 매수/매도호가 필드 파싱
        # 예시: result['output'][0]['bidprc_1'], result['output'][0]['askprc_1']
        if 'output' in result and result['output']:
            output = result['output'][0]
            best_bid = int(str(output.get('bidprc_1', '0')).replace(',', ''))
            best_ask = int(str(output.get('askprc_1', '0')).replace(',', ''))
            return {'best_bid': best_bid, 'best_ask': best_ask}
        return {'best_bid': 0, 'best_ask': 0}

    # ================== 기존 주요 API (예시) ==================
    def get_account_balance(self, qry_tp: str = '0') -> Dict:
        url = f"{self.base_url}/api/dostk/acnt"
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "authorization": f"Bearer {self.ensure_token()}",
            "cont-yn": "N",
            "next-key": "",
            "api-id": "kt00004"
        }
        params = {
            "qry_tp": qry_tp,
            "dmst_stex_tp": "KRX"
        }
        
        # 새로운 토큰 관리 구조 사용
        return self.make_api_request(url, headers, params)

    # ================== 선물 API ==================
    def get_futures_list(self, cont_yn: str = 'N', next_key: str = '') -> dict:
        """
        선물 종목 목록 조회
        """
        url = self.base_url + '/api/dofut/item'
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {self.ensure_token()}',
            'cont-yn': cont_yn,
            'next-key': next_key,
            'api-id': 'ka20001'
        }
        params = {
            'qry_tp': '0',  # 전체 조회
            'stex_tp': 'KRX'  # 한국거래소
        }
        
        return self.make_api_request(url, headers, params)

    def get_futures_minute_data(self, futures_code: str, start_date: str, end_date: str, 
                               interval: str = '1', cont_yn: str = 'N', next_key: str = '') -> dict:
        """
        선물 분봉 데이터 조회
        futures_code: 선물코드 (예: '101K200' - 코스피200 근월물)
        start_date: 시작일 (YYYYMMDD)
        end_date: 종료일 (YYYYMMDD)
        interval: 분봉 단위 (1: 1분, 3: 3분, 5: 5분, 10: 10분, 15: 15분, 30: 30분, 60: 60분)
        """
        url = self.base_url + '/api/dofut/chart'
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {self.ensure_token()}',
            'cont-yn': cont_yn,
            'next-key': next_key,
            'api-id': 'ka20081'
        }
        params = {
            'fut_cd': futures_code,
            'strt_dt': start_date,
            'end_dt': end_date,
            'min_tp': interval,
            'stex_tp': 'KRX'
        }
        
        return self.make_api_request(url, headers, params)

    def get_futures_daily_data(self, futures_code: str, start_date: str, end_date: str,
                              cont_yn: str = 'N', next_key: str = '') -> dict:
        """
        선물 일봉 데이터 조회
        futures_code: 선물코드 (예: '101K200')
        start_date: 시작일 (YYYYMMDD)
        end_date: 종료일 (YYYYMMDD)
        """
        url = self.base_url + '/api/dofut/chart'
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {self.ensure_token()}',
            'cont-yn': cont_yn,
            'next-key': next_key,
            'api-id': 'ka20082'
        }
        params = {
            'fut_cd': futures_code,
            'strt_dt': start_date,
            'end_dt': end_date,
            'day_tp': '1',  # 일봉
            'stex_tp': 'KRX'
        }
        
        return self.make_api_request(url, headers, params)

    def get_futures_current_price(self, futures_code: str) -> dict:
        """
        선물 현재가 조회
        futures_code: 선물코드 (예: '101K200')
        """
        url = self.base_url + '/api/dofut/mrkcond'
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {self.ensure_token()}',
            'cont-yn': 'N',
            'next-key': '',
            'api-id': 'ka20004'
        }
        params = {
            'fut_cd': futures_code,
            'stex_tp': 'KRX'
        }
        
        return self.make_api_request(url, headers, params)

# 사용 예시
if __name__ == "__main__":
    api = KiwoomOpenAPI()
    print("[테마 그룹 조회 예시]")
    theme_groups = api.get_theme_groups()
    print(json.dumps(theme_groups, indent=2, ensure_ascii=False))
    if 'output' in theme_groups and theme_groups['output']:
        first_theme = theme_groups['output'][0]
        theme_code = first_theme.get('thema_grp_cd')
        print(f"\n[테마 {theme_code} 구성종목 조회 예시]")
        theme_stocks = api.get_theme_stocks(theme_code)
        print(json.dumps(theme_stocks, indent=2, ensure_ascii=False)) 