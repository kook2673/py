
# -*- coding: utf-8 -*-
"""
한국투자증권 API를 사용하여 선물 분봉 데이터를 다운로드하는 스크립트
"""
import os
import sys
import time
import requests
import json
import pandas as pd
from datetime import datetime, timedelta
from pytz import timezone

# 상위 폴더 경로 추가
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_DIR = os.path.join(PARENT_DIR, "kis")
if LIVE_DIR not in sys.path:
    sys.path.append(LIVE_DIR)

try:
    import KIS_Common as Common
    import KIS_API_Helper_KR as KisKR
except ImportError:
    print("Error: KIS_Common or KIS_API_Helper_KR module not found.")
    print("Please ensure the script is run from a location where these modules can be imported.")
    sys.exit(1)

# --- 설정 ---
# 다운로드할 선물 종목 코드 (예: 24년 9월물 코스피200 선물 -> 101U4)
FUTURE_CODE = "101W9000" 
# 저장할 파일명
OUTPUT_CSV_FILE = f"kook/kis_wfo/futures_data_{FUTURE_CODE}_1min.csv"
# ----------------

def get_futures_ohlcv_minute(future_code: str, to_time: str | None = None) -> tuple[pd.DataFrame, str | None]:
    """
    선물 분봉 데이터를 조회합니다. KIS API - 파생상품시세 > 선물/옵션 분/틱 시세[FHPZF01210000]
    """
    time.sleep(0.2)
    if Common.GetNowDist() == "VIRTUAL":
        time.sleep(0.31)

    PATH = "/uapi/domestic-futureoption/v1/quotations/inquire-time-fuopchartprice"
    URL = f"{Common.GetUrlBase(Common.GetNowDist())}/{PATH}"

    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {Common.GetToken(Common.GetNowDist())}",
        "appKey": Common.GetAppKey(Common.GetNowDist()),
        "appSecret": Common.GetAppSecret(Common.GetNowDist()),
        "tr_id": "FHPZF01210000",
        "custtype": "P",
    }

    if to_time is None:
        # KST(UTC+9) 기준 현재 시간
        now_kst = datetime.now(timezone('Asia/Seoul'))
        to_time = now_kst.strftime("%H%M%S")

    params = {
        "FID_COND_MRKT_DIV_CODE": "FUT",
        "FID_INPUT_ISCD": future_code,
        "FID_INPUT_HOUR_1": to_time,
        "FID_PW_DATA_INCU_YN": "Y", # 이전 데이터 포함
    }

    try:
        res = requests.get(URL, headers=headers, params=params, timeout=10)
        if res.status_code == 200 and res.json().get("rt_cd") == '0':
            output = res.json().get('output2', [])
            if not output:
                return pd.DataFrame(), None

            df = pd.DataFrame(output)
            
            # 컬럼명 변경 및 데이터 타입 변환
            column_map = {
                'stck_bsop_date': 'date',
                'stck_cntg_hour': 'time',
                'stck_oprc': 'open',
                'stck_hgpr': 'high',
                'stck_lwpr': 'low',
                'stck_prpr': 'close',
                'cntg_vol': 'volume'
            }
            df = df.rename(columns=column_map)

            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # datetime 인덱스 생성
            df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'], format='%Y%m%d %H%M%S')
            df = df.set_index('datetime')

            df = df[numeric_cols].sort_index()

            # 마지막 데이터의 시간 반환 (다음 조회를 위해)
            last_time = df.index.min().strftime('%H%M%S')
            return df, last_time

        else:
            print(f"Error fetching data: {res.status_code} | {res.text}")
            return pd.DataFrame(), None

    except Exception as e:
        print(f"Exception in get_futures_ohlcv_minute: {e}")
        return pd.DataFrame(), None


def main():
    """
    메인 실행 함수
    """
    print("--- 선물 1분봉 데이터 다운로드를 시작합니다 ---")
    print(f"대상 종목: {FUTURE_CODE}")
    print(f"저장 경로: {OUTPUT_CSV_FILE}")

    # 계좌 모드 설정 (REAL 또는 VIRTUAL)
    try:
        Common.SetChangeMode("REAL")
    except Exception:
        pass

    # 토큰 준비: 파일에 있으면 사용, 없으면 최초 1회 생성
    try:
        token = Common.GetToken(Common.GetNowDist())
        if not token or token == "FAIL":
            print("토큰 준비 실패: 토큰이 없습니다.")
            return
    except Exception as e:
        print(f"토큰 준비 실패: {e}")
        return

    all_data = pd.DataFrame()
    next_time = None
    
    # KIS API는 한 번에 약 100개 정도의 분봉을 반환하므로, 루프를 돌며 과거 데이터까지 수집
    for i in range(200): # 최대 200번 반복 (약 20000분 = 약 13일치 데이터)
        print(f"Fetching data loop {i+1}... (from time: {next_time or 'now'})")
        
        df, last_time = get_futures_ohlcv_minute(FUTURE_CODE, to_time=next_time)

        if df.empty:
            print("더 이상 조회할 데이터가 없습니다.")
            break

        if all_data.empty:
            all_data = df
        else:
            # 중복 데이터 제거 후 병합
            new_data = df[~df.index.isin(all_data.index)]
            if new_data.empty:
                print("새로운 데이터가 없습니다. 다운로드를 종료합니다.")
                break
            all_data = pd.concat([all_data, new_data])

        next_time = last_time
        
        # API 요청 간 딜레이
        time.sleep(0.5)

    if not all_data.empty:
        all_data = all_data.sort_index()
        os.makedirs(os.path.dirname(OUTPUT_CSV_FILE), exist_ok=True)
        all_data.to_csv(OUTPUT_CSV_FILE)
        print("--- 데이터 다운로드 완료 ---")
        print(f"총 {len(all_data)}개의 1분봉 데이터가 저장되었습니다.")
        print(f"시작: {all_data.index.min()}")
        print(f"종료: {all_data.index.max()}")
    else:
        print("--- 다운로드된 데이터가 없습니다 ---")


if __name__ == "__main__":
    main()
