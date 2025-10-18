import os
import requests
import pandas as pd
from datetime import datetime
import platform

# 운영체제별 데이터 저장 경로 설정
if platform.system() == "Windows":
    DATA_DIR = "C:/work/GitHub/py/kiwoom/data"
else:
    # Linux 경로는 나중에 사용자가 설정할 예정
    DATA_DIR = "/opt/my/py/kiwoom/data"  # 임시 경로

STOCK_URL = "https://api.stock.naver.com/chart/domestic/item/{code}/day?startDateTime={start}0000&endDateTime={end}0000"

def save_etf_data(code, name, start_date="20200101", end_date=None):
    """
    ETF 종목코드(code)와 이름(name)을 받아 ETF_코드_이름.csv 파일을 생성
    """
    if end_date is None:
        end_date = datetime.now().strftime('%Y%m%d')
    os.makedirs(DATA_DIR, exist_ok=True)
    filename = f"{DATA_DIR}/ETF_{code}_{name}.csv"

    url = STOCK_URL.format(code=code, start=start_date, end=end_date)
    headers = {'User-Agent': 'Mozilla/5.0'}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"[오류] 데이터 요청 실패: {resp.status_code}")
        return

    data = resp.json()
    if not data:
        print(f"[경고] 데이터가 비어있음")
        return

    df = pd.DataFrame(data)
    if 'localDate' in df.columns:
        # volume 컬럼이 있는지 확인하고 처리
        required_columns = ['localDate', 'closePrice', 'openPrice', 'highPrice', 'lowPrice']
        available_columns = [col for col in required_columns if col in df.columns]
        
        # volume 컬럼이 있으면 추가
        if 'volume' in df.columns:
            available_columns.append('volume')
        
        df = df[available_columns]
        
        # 컬럼명 변경
        column_mapping = {
            'localDate': 'date',
            'closePrice': 'close',
            'openPrice': 'open',
            'highPrice': 'high',
            'lowPrice': 'low',
            'volume': 'volume'
        }
        
        # 실제 존재하는 컬럼만 변경
        existing_columns = {k: v for k, v in column_mapping.items() if k in df.columns}
        df.rename(columns=existing_columns, inplace=True)
        
        # volume 컬럼이 없으면 0으로 추가
        if 'volume' not in df.columns:
            df['volume'] = 0
        
        df['date'] = pd.to_datetime(df['date'])
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"[성공] {filename} 저장 완료")
        print(f"[정보] 수집된 데이터: {len(df)}개")
    else:
        print(f"[경고] 데이터 형식이 예상과 다름")
        print(f"[디버깅] 실제 컬럼: {df.columns.tolist()}")

if __name__ == "__main__":
    print("ETF 종목코드와 이름을 입력하세요.")
    code = input("ETF 종목코드 (예: 069500): ").strip()
    name = input("ETF 이름 (예: KODEX 200): ").strip()
    start_date = input("시작일 (YYYYMMDD, 기본값: 20200101): ").strip() or "20200101"
    end_date = input("종료일 (YYYYMMDD, 기본값: 오늘): ").strip() or None
    save_etf_data(code, name, start_date, end_date) 