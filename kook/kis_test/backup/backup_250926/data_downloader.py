import os
import re
import time
from datetime import datetime, timedelta
import pandas as pd
import requests
from pykrx import stock
from tqdm import tqdm

# --- 설정 ---
# 데이터 저장 기본 경로 (이 스크립트가 있는 위치 기준)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')

# 데이터 저장 폴더
KOSPI_DIR = os.path.join(DATA_DIR, 'kospi100')
KOSDAQ_DIR = os.path.join(DATA_DIR, 'kosdaq100')
ETC_DIR = os.path.join(DATA_DIR, 'etf_index')

# 다운로드할 ETF 및 지수 목록
ETC_ASSETS = {
    "122630": "KODEX 레버리지",
    "252670": "KODEX 200선물인버스2X",
    "233740": "KODEX 코스닥150레버리지",
    "251340": "KODEX 코스닥150선물인버스",
    "132030": "KODEX 골드선물",
    "114800": "KODEX 국고채3년",
    "130680": "TIGER 단기통안채",
    "KOSPI": "코스피 지수"
}

# 네이버 API URL
STOCK_URL = "https://api.stock.naver.com/chart/domestic/item/{code}/day?startDateTime={start}0000&endDateTime={end}0000"
INDEX_URL = "https://api.stock.naver.com/chart/domestic/index/{code}/day?startDateTime={start}0000&endDateTime={end}0000"


def sanitize_filename(name):
    """파일 이름으로 사용할 수 없는 문자를 제거합니다."""
    return re.sub(r'[\\/*?:"<>|]', "", name)


def get_top_tickers(today_str):
    """pykrx를 사용하여 시가총액 기준 KOSPI 100, KOSDAQ 100 종목 코드와 이름을 가져옵니다."""
    print("시가총액 기준 KOSPI 100, KOSDAQ 100 종목 목록을 가져옵니다...")
    try:
        # KOSPI
        print("KOSPI 시가총액 데이터 조회 중...")
        kospi_cap = stock.get_market_cap_by_ticker(today_str, market="KOSPI")
        # 관리종목, 우선주 등 제외
        kospi_cap = kospi_cap[kospi_cap['시가총액'] > 0]
        kospi_cap['종목명'] = kospi_cap.index.map(lambda x: stock.get_market_ticker_name(x))
        kospi_cap = kospi_cap[~kospi_cap['종목명'].str.endswith('우')]
        kospi100_df = kospi_cap.sort_values(by="시가총액", ascending=False).head(100)
        kospi100_map = dict(zip(kospi100_df.index, kospi100_df['종목명']))
        time.sleep(1)

        # KOSDAQ
        print("KOSDAQ 시가총액 데이터 조회 중...")
        kosdaq_cap = stock.get_market_cap_by_ticker(today_str, market="KOSDAQ")
        kosdaq_cap = kosdaq_cap[kosdaq_cap['시가총액'] > 0]
        kosdaq_cap['종목명'] = kosdaq_cap.index.map(lambda x: stock.get_market_ticker_name(x))
        kosdaq_cap = kosdaq_cap[~kosdaq_cap['종목명'].str.endswith('우')]
        kosdaq100_df = kosdaq_cap.sort_values(by="시가총액", ascending=False).head(100)
        kosdaq100_map = dict(zip(kosdaq100_df.index, kosdaq100_df['종목명']))
        
        print(f"KOSPI 100: {len(kospi100_map)}개, KOSDAQ 100: {len(kosdaq100_map)}개 종목 확인")
        return kospi100_map, kosdaq100_map
    except Exception as e:
        print(f"pykrx로 시가총액 목록을 가져오는 중 오류 발생: {e}")
        return {}, {}


def fetch_price_data(ticker, start_date, end_date):
    """네이버 금융 API를 사용하여 개별 종목 또는 지수의 OHLCV 데이터를 가져옵니다."""
    is_index = ticker.upper() == "KOSPI"
    url = INDEX_URL.format(code=ticker, start=start_date, end=end_date) if is_index else STOCK_URL.format(code=ticker, start=start_date, end=end_date)
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status() # 200이 아니면 오류 발생
        
        data = resp.json()
        if not data:
            return None
            
        df = pd.DataFrame(data)
        
        if 'localDate' in df.columns:
            df = df.rename(columns={
                'localDate': 'date',
                'closePrice': 'close',
                'openPrice': 'open',
                'highPrice': 'high',
                'lowPrice': 'low',
            })
            if 'accumulatedTradingVolume' in df.columns:
                 df = df.rename(columns={'accumulatedTradingVolume': 'volume'})
            else:
                 df['volume'] = 0 # 지수 데이터에는 volume이 없음

            df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')
            required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
            df = df[required_cols]
            
            # 가격 데이터에서 쉼표 제거 및 숫자형으로 변환
            for col in ['open', 'high', 'low', 'close']:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''))

            return df
        else:
            return None

    except requests.exceptions.RequestException as e:
        print(f"[{ticker}] 데이터 요청 실패: {e}")
    except Exception as e:
        print(f"[{ticker}] 데이터 처리 중 오류: {e}")
    return None


def update_data(ticker, name, save_dir):
    """단일 종목/지수 데이터를 다운로드하거나 업데이트합니다."""
    # 기존 파일 (코드.csv) 경로
    old_filepath = os.path.join(save_dir, f"{ticker}.csv")

    # 새 파일 (코드_이름.csv) 경로
    safe_name = sanitize_filename(name)
    new_filename = f"{ticker}_{safe_name}.csv"
    filepath = os.path.join(save_dir, new_filename)

    # 마이그레이션: 기존 파일이 있으면 새 이름으로 변경
    if os.path.exists(old_filepath):
        try:
            if os.path.exists(filepath): # 혹시 새 파일도 이미 있으면 기존 파일 삭제
                 os.remove(old_filepath)
            else:
                os.rename(old_filepath, filepath)
                print(f"파일 이름 변경: {os.path.basename(old_filepath)} -> {os.path.basename(filepath)}")
        except Exception as e:
            print(f"파일 이름 변경 실패: {e}")
            filepath = old_filepath # 실패 시 기존 파일 경로 유지

    start_date = "20150101" # 기본 시작일
    
    if os.path.exists(filepath):
        try:
            existing_df = pd.read_csv(filepath, parse_dates=['date'])
            if not existing_df.empty:
                last_date = existing_df['date'].max()
                start_date = (last_date + timedelta(days=1)).strftime('%Y%m%d')
        except Exception as e:
            print(f"기존 파일 '{filepath}'을 읽는 중 오류 발생: {e}")
            existing_df = pd.DataFrame() # 파일이 손상되었을 경우 새로 시작
    else:
        existing_df = pd.DataFrame()

    end_date = datetime.now().strftime('%Y%m%d')

    if start_date > end_date:
        # print(f"[{ticker}] 이미 최신 데이터입니다.")
        return

    # print(f"[{ticker}] 데이터 다운로드 중... ({start_date} ~ {end_date})")
    new_df = fetch_price_data(ticker, start_date, end_date)
    
    if new_df is not None and not new_df.empty:
        combined_df = pd.concat([existing_df, new_df]).drop_duplicates(subset='date').sort_values(by='date').reset_index(drop=True)
        combined_df.to_csv(filepath, index=False, encoding='utf-8-sig')
    else:
        # print(f"[{ticker}] 다운로드된 데이터가 없습니다.")
        pass
    
    time.sleep(0.5) # API 과부하 방지


def main():
    """메인 실행 함수"""
    print("백테스팅을 위한 데이터 다운로드를 시작합니다.")
    
    # 필요한 폴더 생성
    os.makedirs(KOSPI_DIR, exist_ok=True)
    os.makedirs(KOSDAQ_DIR, exist_ok=True)
    os.makedirs(ETC_DIR, exist_ok=True)

    # KOSPI 100, KOSDAQ 100 종목 가져오기
    today = datetime.now().strftime('%Y%m%d')
    kospi100_map, kosdaq100_map = get_top_tickers(today)
    
    # 전체 다운로드 목록
    tasks = []
    if kospi100_map:
        tasks.extend([(ticker, name, KOSPI_DIR) for ticker, name in kospi100_map.items()])
    if kosdaq100_map:
        tasks.extend([(ticker, name, KOSDAQ_DIR) for ticker, name in kosdaq100_map.items()])
    tasks.extend([(ticker, name, ETC_DIR) for ticker, name in ETC_ASSETS.items()])

    if not tasks:
        print("다운로드할 종목이 없습니다. 스크립트를 종료합니다.")
        return

    # tqdm을 사용하여 진행률 표시
    for ticker, name, save_dir in tqdm(tasks, desc="전체 종목 데이터 업데이트"):
        update_data(ticker, name, save_dir)
        
    print("\n모든 데이터 다운로드 및 업데이트가 완료되었습니다.")
    print(f"데이터 저장 위치: {os.path.abspath(DATA_DIR)}")


if __name__ == "__main__":
    print("이 스크립트를 실행하려면 'pykrx', 'tqdm', 'requests' 라이브러리가 필요합니다.")
    print("이전에 'pip install pykrx tqdm requests' 명령어로 설치했습니다.")
    main()
