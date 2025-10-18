import os
import json
from datetime import datetime, timedelta
import requests
import pandas as pd
import time

DATA_DIR = "py/kiwoom/data"

# 코스피 지수 API URL
KOSPI_INDEX_URL = "https://api.stock.naver.com/chart/domestic/index/KOSPI/day?startDateTime={start}0000&endDateTime={end}0000"

# 주식 데이터 API URL 추가
STOCK_URL = "https://api.stock.naver.com/chart/domestic/item/{code}/day?startDateTime={start}0000&endDateTime={end}0000"

def fetch_kospi_index_data(start_date, end_date):
    """
    네이버 API에서 코스피 지수 데이터를 가져옴
    """
    try:
        url = KOSPI_INDEX_URL.format(start=start_date, end=end_date)
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers)
        
        if resp.status_code != 200:
            print(f"[오류] 코스피 지수 데이터 요청 실패: {resp.status_code}")
            print(f"[URL] {url}")
            return None
            
        data = resp.json()
        if not data:
            print(f"[경고] 코스피 지수 데이터가 비어있음")
            return None
            
        df = pd.DataFrame(data)
        
        # 컬럼 추출 및 이름 변경
        if 'localDate' in df.columns:
            df = df[['localDate', 'closePrice', 'openPrice', 'highPrice', 'lowPrice']]
            df.rename(columns={
                'localDate': 'date',
                'closePrice': 'close',
                'openPrice': 'open',
                'highPrice': 'high',
                'lowPrice': 'low'
            }, inplace=True)
            
            # volume 컬럼 추가 (지수는 거래량이 없으므로 0으로 설정)
            df['volume'] = 0
            
            # date 컬럼을 datetime으로 변환
            df['date'] = pd.to_datetime(df['date'])
        else:
            print(f"[경고] 코스피 지수 데이터 형식이 예상과 다름")
            return None
            
        return df
        
    except Exception as e:
        print(f"[오류] 코스피 지수 데이터 수집 실패: {e}")
        return None

def fetch_stock_data(code, start_date, end_date):
    """
    네이버 API에서 주식 데이터를 가져옴
    """
    try:
        url = STOCK_URL.format(code=code, start=start_date, end=end_date)
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers)
        
        if resp.status_code != 200:
            print(f"[오류] {code} 데이터 요청 실패: {resp.status_code}")
            return None
            
        data = resp.json()
        if not data:
            print(f"[경고] {code} 데이터가 비어있음")
            return None
            
        df = pd.DataFrame(data)
        
        # 컬럼 추출 및 이름 변경
        if 'localDate' in df.columns:
            df = df[['localDate', 'closePrice', 'openPrice', 'highPrice', 'lowPrice', 'volume']]
            df.rename(columns={
                'localDate': 'date',
                'closePrice': 'close',
                'openPrice': 'open',
                'highPrice': 'high',
                'lowPrice': 'low',
                'volume': 'volume'
            }, inplace=True)
            
            # date 컬럼을 datetime으로 변환
            df['date'] = pd.to_datetime(df['date'])
        else:
            print(f"[경고] {code} 데이터 형식이 예상과 다름")
            return None
            
        return df
        
    except Exception as e:
        print(f"[오류] {code} 데이터 수집 실패: {e}")
        return None

def get_stock_info(code):
    """
    종목 코드로 종목 정보 가져오기 (KRX API 사용)
    """
    try:
        url = "http://kind.krx.co.kr/corpgeneral/corpList.do"
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        # KOSPI, KOSDAQ, ETF 모두 검색
        markets = [
            {"method": "download", "marketType": "stockMkt"},  # KOSPI
            {"method": "download", "marketType": "kosdaqMkt"},  # KOSDAQ
            {"method": "download", "marketType": "etfMkt"}  # ETF
        ]
        
        for market in markets:
            resp = requests.get(url, params=market, headers=headers, timeout=30)
            if resp.status_code == 200:
                try:
                    from io import StringIO
                    df = pd.read_html(StringIO(resp.text))[0]
                    df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
                    
                    # 해당 종목 찾기
                    stock_info = df[df['종목코드'] == code]
                    if not stock_info.empty:
                        name = stock_info['회사명'].iloc[0]
                        if market["marketType"] == "stockMkt":
                            market_type = "KOSPI"
                        elif market["marketType"] == "kosdaqMkt":
                            market_type = "KOSDAQ"
                        else:
                            market_type = "ETF"
                        return {"name": name, "market": market_type}
                except:
                    continue
            time.sleep(1)
        
        return None
        
    except Exception as e:
        print(f"[오류] 종목 정보 조회 실패: {e}")
        return None

def get_csv_filename(code, market, name):
    """
    CSV 파일명 생성 (market_code_name 형식)
    """
    safe_name = name.replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
    return f"{DATA_DIR}/{market}_{code}_{safe_name}.csv"

def save_stock_data(code, df, market, name):
    """
    주식 데이터를 CSV 파일로 저장
    """
    try:
        # data 폴더가 없으면 생성
        os.makedirs(DATA_DIR, exist_ok=True)
        
        filename = get_csv_filename(code, market, name)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"[성공] {code} 데이터 저장: {filename}")
        return filename
    except Exception as e:
        print(f"[오류] {code} 데이터 저장 실패: {e}")
        return None

def get_kospi_index_filename():
    """
    코스피 지수 CSV 파일명 생성
    """
    return f"{DATA_DIR}/INDEX_KOSPI_코스피지수.csv"

def save_kospi_index_data(df):
    """
    코스피 지수 데이터를 CSV 파일로 저장
    """
    try:
        # data 폴더가 없으면 생성
        os.makedirs(DATA_DIR, exist_ok=True)
        
        filename = get_kospi_index_filename()
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"[성공] 코스피 지수 데이터 저장: {filename}")
        return filename
    except Exception as e:
        print(f"[오류] 코스피 지수 데이터 저장 실패: {e}")
        return None

def find_existing_kospi_index_file():
    """
    기존 코스피 지수 CSV 파일 찾기
    """
    if not os.path.exists(DATA_DIR):
        return None
    
    filename = get_kospi_index_filename()
    if os.path.exists(filename):
        return filename
    
    return None

def load_existing_csv_data(filepath):
    """
    기존 CSV 파일 로드
    """
    try:
        df = pd.read_csv(filepath, encoding='utf-8-sig')
        # date 컬럼을 datetime으로 변환
        df['date'] = pd.to_datetime(df['date'])
        return df
    except Exception as e:
        print(f"[오류] CSV 파일 로드 실패: {e}")
        return None

def merge_and_save_kospi_index_data(existing_df, new_df):
    """
    기존 코스피 지수 데이터와 새 데이터를 병합하여 저장
    """
    try:
        # 날짜 컬럼 타입 통일
        if existing_df is not None and not existing_df.empty:
            existing_df['date'] = pd.to_datetime(existing_df['date'])
        if new_df is not None and not new_df.empty:
            new_df['date'] = pd.to_datetime(new_df['date'])
        
        # 날짜순으로 정렬
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        combined_df = combined_df.drop_duplicates(subset=['date']).sort_values('date')
        
        # 저장
        filename = get_kospi_index_filename()
        combined_df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"[성공] 코스피 지수 데이터 병합 저장: {filename}")
        return filename
    except Exception as e:
        print(f"[오류] 코스피 지수 데이터 병합 실패: {e}")
        return None

def collect_kospi_index_data():
    """
    코스피 지수 데이터 수집
    """
    print(f"[수집 시작] 코스피 지수")
    
    try:
        # 기존 파일 확인
        existing_file = find_existing_kospi_index_file()
        
        # 수집할 날짜 범위 결정
        today = datetime.now()
        start_date = "19830103"  # 코스피 지수 시작일 (1983년 1월 3일)
        end_date = today.strftime('%Y%m%d')
        
        if existing_file:
            # 기존 파일의 최신 날짜 확인
            existing_df = load_existing_csv_data(existing_file)
            if existing_df is not None and not existing_df.empty:
                latest_date = existing_df['date'].max()
                # 다음날부터 시작
                next_date = latest_date + timedelta(days=1)
                start_date = next_date.strftime('%Y%m%d')
        
        # 시작일이 종료일보다 늦으면 이미 완료된 것
        if start_date > end_date:
            print(f"[완료] 코스피 지수: 이미 최신 데이터 보유")
            return
        
        # 데이터 수집
        df = fetch_kospi_index_data(start_date, end_date)
        
        if df is None or df.empty:
            print(f"[실패] 코스피 지수: 데이터 수집 실패")
            return
        
        # 기존 파일과 병합 또는 새로 저장
        if existing_file:
            # 기존 파일이 있으면 병합
            existing_df = load_existing_csv_data(existing_file)
            if existing_df is not None:
                saved_file = merge_and_save_kospi_index_data(existing_df, df)
            else:
                saved_file = save_kospi_index_data(df)
        else:
            # 새로 저장
            saved_file = save_kospi_index_data(df)
        
        if saved_file:
            print(f"[성공] 코스피 지수: {start_date} ~ {end_date} 데이터 수집 완료")
        else:
            print(f"[실패] 코스피 지수: 데이터 저장 실패")
            
    except Exception as e:
        print(f"[오류] 코스피 지수 데이터 수집 중 오류: {e}")

def collect_stock_data(code):
    """
    특정 종목의 데이터 수집
    """
    print(f"[수집 시작] 종목 {code}")
    
    try:
        # 종목 정보 가져오기
        stock_info = get_stock_info(code)
        if not stock_info:
            print(f"[실패] 종목 {code}: 종목 정보를 찾을 수 없습니다.")
            return
        
        market = stock_info['market']
        name = stock_info['name']
        
        print(f"[정보] 종목 {code}: {market} - {name}")
        
        # 기존 파일 확인
        existing_filename = get_csv_filename(code, market, name)
        if os.path.exists(existing_filename):
            print(f"[정보] 기존 파일 존재: {existing_filename}")
            choice = input("기존 파일을 덮어쓰시겠습니까? (y/N): ")
            if choice.lower() != 'y':
                print("[취소] 파일 생성이 취소되었습니다.")
                return
        
        # 수집할 날짜 범위 결정
        today = datetime.now()
        start_date = "20200101"  # 기본 시작일
        end_date = today.strftime('%Y%m%d')
        
        # 사용자 입력 받기
        print(f"\n수집할 기간을 입력하세요:")
        start_input = input(f"시작일 (YYYYMMDD, 기본값: {start_date}): ").strip()
        if start_input:
            start_date = start_input
        
        end_input = input(f"종료일 (YYYYMMDD, 기본값: {end_date}): ").strip()
        if end_input:
            end_date = end_input
        
        print(f"[정보] 수집 기간: {start_date} ~ {end_date}")
        
        # 데이터 수집
        df = fetch_stock_data(code, start_date, end_date)
        
        if df is None or df.empty:
            print(f"[실패] 종목 {code}: 데이터 수집 실패")
            return
        
        print(f"[정보] 수집된 데이터: {len(df)}개")
        
        # 파일 저장
        saved_file = save_stock_data(code, df, market, name)
        
        if saved_file:
            print(f"[성공] 종목 {code} ({name}) 데이터 수집 완료")
            print(f"[파일] {saved_file}")
        else:
            print(f"[실패] 종목 {code}: 데이터 저장 실패")
            
    except Exception as e:
        print(f"[오류] 종목 {code} 데이터 수집 중 오류: {e}")

def main():
    print("=" * 50)
    print("[주식 데이터 수집기 시작]")
    print("=" * 50)
    
    while True:
        print("\n선택하세요:")
        print("1. 코스피 지수 데이터 수집")
        print("2. 특정 종목 데이터 수집")
        print("3. 종료")
        
        choice = input("\n번호를 입력하세요 (1-3): ").strip()
        
        if choice == "1":
            print("\n" + "=" * 30)
            collect_kospi_index_data()
            print("=" * 30)
        elif choice == "2":
            print("\n" + "=" * 30)
            code = input("종목 코드를 입력하세요 (예: 000020): ").strip()
            if code:
                collect_stock_data(code)
            else:
                print("[오류] 종목 코드를 입력해주세요.")
            print("=" * 30)
        elif choice == "3":
            print("\n[프로그램 종료]")
            break
        else:
            print("[오류] 1-3 중에서 선택해주세요.")
    
    print("=" * 50)
    print("[주식 데이터 수집기 완료]")
    print("=" * 50)

if __name__ == "__main__":
    main() 