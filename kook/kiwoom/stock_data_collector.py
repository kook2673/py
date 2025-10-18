import os
import json
from datetime import datetime, timedelta
import requests
import pandas as pd
import time
from io import StringIO
import sys
import os
import platform
import importlib.util

# 운영체제별 telegram 모듈 경로 설정
if platform.system() == "Windows":
    telegram_path = "C:/work/GitHub/moapick-web/py/telegram.py"
else:
    telegram_path = "/opt/my/py/telegram.py"  # 임시 경로

# 직접 파일에서 모듈 로드 (패키지 충돌 방지)
spec = importlib.util.spec_from_file_location("telegram_module", telegram_path)
telegram_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(telegram_module)
send_telegram = telegram_module.send

import platform

# 운영체제별 데이터 저장 경로 설정
if platform.system() == "Windows":
    DATA_DIR = "C:/work/GitHub/moapick-web/py/kiwoom/data"
    JSON_PATH = "C:/work/GitHub/moapick-web/py/kiwoom/stock_data_collector.json"
else:
    # Linux 경로는 나중에 사용자가 설정할 예정
    DATA_DIR = "/opt/my/py/kiwoom/data"  # 임시 경로
    JSON_PATH = "/opt/my/py/kiwoom/stock_data_collector.json"  # 임시 경로

def send_error_telegram(code, error_type, error_msg, url=None):
    """
    오류 발생 시 텔레그램으로 알림 전송
    """
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"🚨 [주식 데이터 수집 오류]\n\n"
        message += f"📅 시간: {current_time}\n"
        message += f"📊 종목코드: {code}\n"
        message += f"❌ 오류유형: {error_type}\n"
        message += f"💬 오류내용: {error_msg}\n"
        
        if url:
            message += f"🔗 URL: {url}\n"
        
        send_telegram(message)
        print(f"[텔레그램] 오류 알림 전송 완료")
    except Exception as e:
        print(f"[텔레그램 오류] 알림 전송 실패: {e}")

# 네이버 API URL
STOCK_URL = "https://api.stock.naver.com/chart/domestic/item/{code}/day?startDateTime={start}0000&endDateTime={end}0000"
# 코스피 지수 API URL 추가
KOSPI_INDEX_URL = "https://api.stock.naver.com/chart/domestic/index/KOSPI/day?startDateTime={start}0000&endDateTime={end}0000"

def get_broker_codes():
    """
    KRX에서 KOSPI/KOSDAQ 종목코드 리스트를 받아옴 (코넥스/ETF 제외)
    """
    try:
        url = "http://kind.krx.co.kr/corpgeneral/corpList.do"
        kospi_params = {"method": "download", "marketType": "stockMkt"}
        kosdaq_params = {"method": "download", "marketType": "kosdaqMkt"}
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        # KOSPI
        print("[정보] KOSPI 종목 데이터 수집 중...")
        try:
            resp_kospi = requests.get(url, params=kospi_params, headers=headers, timeout=30)
            print(f"[정보] KOSPI 응답 상태: {resp_kospi.status_code}")
            if resp_kospi.status_code != 200:
                print(f"[오류] KOSPI API 오류: {resp_kospi.text[:200]}")
        except Exception as e:
            print(f"[오류] KOSPI API 요청 실패: {e}")
            resp_kospi = None
        time.sleep(2)
        
        # KOSDAQ
        print("[정보] KOSDAQ 종목 데이터 수집 중...")
        try:
            resp_kosdaq = requests.get(url, params=kosdaq_params, headers=headers, timeout=30)
            print(f"[정보] KOSDAQ 응답 상태: {resp_kosdaq.status_code}")
            if resp_kosdaq.status_code != 200:
                print(f"[오류] KOSDAQ API 오류: {resp_kosdaq.text[:200]}")
        except Exception as e:
            print(f"[오류] KOSDAQ API 요청 실패: {e}")
            resp_kosdaq = None
        time.sleep(2)
        
        # DataFrame 변환
        print("[정보] DataFrame 변환 중...")
        
        try:
            kospi_df = pd.read_html(StringIO(resp_kospi.text))[0]
            print(f"[정보] KOSPI DataFrame 크기: {kospi_df.shape}")
        except Exception as e:
            print(f"[오류] KOSPI DataFrame 변환 실패: {e}")
            print(f"[디버깅] KOSPI 응답 내용 일부: {resp_kospi.text[:500]}")
            kospi_df = pd.DataFrame()
        
        try:
            kosdaq_df = pd.read_html(StringIO(resp_kosdaq.text))[0]
            print(f"[정보] KOSDAQ DataFrame 크기: {kosdaq_df.shape}")
        except Exception as e:
            print(f"[오류] KOSDAQ DataFrame 변환 실패: {e}")
            print(f"[디버깅] KOSDAQ 응답 내용 일부: {resp_kosdaq.text[:500]}")
            kosdaq_df = pd.DataFrame()
        
        # 빈 DataFrame 체크
        if kospi_df.empty:
            print("[경고] KOSPI 데이터가 비어있습니다!")
        else:
            kospi_df['종목코드'] = kospi_df['종목코드'].astype(str).str.zfill(6)
        
        if kosdaq_df.empty:
            print("[경고] KOSDAQ 데이터가 비어있습니다!")
        else:
            kosdaq_df['종목코드'] = kosdaq_df['종목코드'].astype(str).str.zfill(6)
        
        # 코드와 회사명 매핑 생성
        code_name_map = {}
        
        # KOSPI 종목들
        for _, row in kospi_df.iterrows():
            code = row['종목코드']
            name = row['회사명']
            code_name_map[code] = {'name': name, 'market': 'KOSPI'}
        
        # KOSDAQ 종목들
        for _, row in kosdaq_df.iterrows():
            code = row['종목코드']
            name = row['회사명']
            code_name_map[code] = {'name': name, 'market': 'KOSDAQ'}
        
        codes = list(code_name_map.keys())
        kospi_count = len([c for c in codes if code_name_map[c]['market'] == 'KOSPI'])
        kosdaq_count = len([c for c in codes if code_name_map[c]['market'] == 'KOSDAQ'])
        print(f"[정보] 종목 수집 완료: KOSPI {kospi_count}개, KOSDAQ {kosdaq_count}개")
        
        return codes, code_name_map
    except Exception as e:
        print(f"[경고] KRX 종목코드 추출 실패: {e}")
        return [], {}

def fetch_stock_data(code, start_date, end_date):
    """
    네이버 API에서 주식 데이터를 가져옴
    """
    try:
        url = STOCK_URL.format(code=code, start=start_date, end=end_date)
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers)
        
        if resp.status_code != 200:
            error_msg = f"HTTP {resp.status_code} 오류"
            print(f"[오류] {code} 데이터 요청 실패: {resp.status_code}")
            print(f"[URL] {url}")
            send_error_telegram(code, "API 요청 실패", error_msg, url)
            print(f"[종료] 오류로 인해 프로그램을 종료합니다.")
            exit(1)
            
        data = resp.json()
        if not data:
            print(f"[경고] {code} 데이터가 비어있음")
            return None
            
        df = pd.DataFrame(data)
        
        # 컬럼 추출 및 이름 변경
        if 'localDate' in df.columns:
            df = df[['localDate', 'closePrice', 'openPrice', 'highPrice', 'lowPrice', 'accumulatedTradingVolume']]
            df.rename(columns={
                'localDate': 'date',
                'closePrice': 'close',
                'openPrice': 'open',
                'highPrice': 'high',
                'lowPrice': 'low',
                'accumulatedTradingVolume': 'volume'
            }, inplace=True)
            
            # date 컬럼을 datetime으로 변환
            df['date'] = pd.to_datetime(df['date'])
        else:
            print(f"[경고] {code} 데이터 형식이 예상과 다름")
            return None
            
        return df
        
    except Exception as e:
        error_msg = str(e)
        print(f"[오류] {code} 데이터 수집 실패: {e}")
        send_error_telegram(code, "데이터 수집 실패", error_msg)
        return None

def fetch_kospi_index_data(start_date, end_date):
    """
    네이버 API에서 코스피 지수 데이터를 가져옴
    """
    try:
        url = KOSPI_INDEX_URL.format(start=start_date, end=end_date)
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers)
        
        if resp.status_code != 200:
            error_msg = f"HTTP {resp.status_code} 오류"
            print(f"[오류] 코스피 지수 데이터 요청 실패: {resp.status_code}")
            print(f"[URL] {url}")
            send_error_telegram("KOSPI", "지수 API 요청 실패", error_msg, url)
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
        error_msg = str(e)
        print(f"[오류] 코스피 지수 데이터 수집 실패: {e}")
        send_error_telegram("KOSPI", "지수 데이터 수집 실패", error_msg)
        return None

def get_csv_filename(code, market, name):
    """
    CSV 파일명 생성 (market_code_name 형식)
    """
    safe_name = name.replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
    return f"{DATA_DIR}/{market}_{code}_{safe_name}.csv"

def get_kospi_index_filename():
    """
    코스피 지수 CSV 파일명 생성
    """
    return f"{DATA_DIR}/INDEX_KOSPI_코스피지수.csv"

def save_stock_data(code, df, code_name_map):
    """
    주식 데이터를 CSV 파일로 저장 (market_code_name 형식)
    """
    try:
        # data 폴더가 없으면 생성
        os.makedirs(DATA_DIR, exist_ok=True)
        
        # 종목 정보 가져오기
        if code in code_name_map:
            market = code_name_map[code]['market']
            name = code_name_map[code]['name']
            filename = get_csv_filename(code, market, name)
        else:
            # 종목 정보가 없으면 기본 형식 사용
            filename = f"{DATA_DIR}/UNKNOWN_{code}.csv"
        
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"[성공] {code} 데이터 저장: {filename}")
        return filename
    except Exception as e:
        print(f"[오류] {code} 데이터 저장 실패: {e}")
        return None

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

def find_existing_csv_file(code, market, name):
    """
    기존 CSV 파일 찾기
    """
    if not os.path.exists(DATA_DIR):
        return None
    
    # 정확한 파일명으로 찾기
    expected_filename = get_csv_filename(code, market, name)
    if os.path.exists(expected_filename):
        return expected_filename
    
    # 부분 매칭으로 찾기 (코드만으로)
    for file in os.listdir(DATA_DIR):
        if file.startswith(f"{market}_{code}_") and file.endswith(".csv"):
            return os.path.join(DATA_DIR, file)
    
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

def merge_and_save_data(code, existing_df, new_df, market, name):
    """
    기존 데이터와 새 데이터를 병합하여 저장
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
        filename = get_csv_filename(code, market, name)
        combined_df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"[성공] {code} 데이터 병합 저장: {filename}")
        return filename
    except Exception as e:
        error_msg = str(e)
        print(f"[오류] {code} 데이터 병합 실패: {e}")
        send_error_telegram(code, "데이터 병합 실패", error_msg)
        print(f"[종료] 병합 오류로 인해 프로그램을 종료합니다.")
        exit(1)

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
        error_msg = str(e)
        print(f"[오류] 코스피 지수 데이터 병합 실패: {e}")
        send_error_telegram("KOSPI", "지수 데이터 병합 실패", error_msg)
        print(f"[종료] 병합 오류로 인해 프로그램을 종료합니다.")
        exit(1)

def get_date_range_for_collection(code, info):
    """
    수집할 날짜 범위를 결정
    """
    today = datetime.now()
    
    # JSON에서 start_date 가져오기
    start_date_str = info.get('start_date', '20200101')
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').strftime('%Y%m%d')
    except:
        start_date = "20200101"
    
    # 기존 CSV 파일 확인
    market = info.get('market', 'UNKNOWN')
    name = info.get('name', 'UNKNOWN')
    existing_file = find_existing_csv_file(code, market, name)
    
    if existing_file:
        # 기존 파일의 최신 날짜 확인
        existing_df = load_existing_csv_data(existing_file)
        if existing_df is not None and not existing_df.empty:
            latest_date = existing_df['date'].max()
            # 다음날부터 시작
            next_date = latest_date + timedelta(days=1)
            start_date = next_date.strftime('%Y%m%d')
    
    # 종료일은 오늘
    end_date = today.strftime('%Y%m%d')
    
    return start_date, end_date

def check_and_fill_missing_start_data(code, info):
    """
    시작 부분 누락 데이터 확인 및 채우기
    """
    market = info.get('market', 'UNKNOWN')
    name = info.get('name', 'UNKNOWN')
    start_date_str = info.get('start_date', '20200101')
    
    # 기존 CSV 파일 확인
    existing_file = find_existing_csv_file(code, market, name)
    
    if not existing_file:
        print(f"[정보] {code}: 기존 파일 없음, 처음부터 수집 필요")
        return False
    
    # 기존 데이터 로드
    existing_df = load_existing_csv_data(existing_file)
    if existing_df is None or existing_df.empty:
        print(f"[경고] {code}: 기존 파일 로드 실패")
        return False
    
    # 시작일 확인
    try:
        target_start = datetime.strptime(start_date_str, '%Y-%m-%d')
        actual_start = existing_df['date'].min()
        
        if actual_start > target_start:
            print(f"[발견] {code}: 시작 부분 누락 데이터 발견")
            print(f"  - 목표 시작일: {target_start.strftime('%Y-%m-%d')}")
            print(f"  - 실제 시작일: {actual_start.strftime('%Y-%m-%d')}")
            
            # 누락된 기간 데이터 수집
            missing_start_date = target_start.strftime('%Y%m%d')
            missing_end_date = (actual_start - timedelta(days=1)).strftime('%Y%m%d')
            
            print(f"[수집] {code}: 누락 기간 {missing_start_date} ~ {missing_end_date}")
            
            missing_df = fetch_stock_data(code, missing_start_date, missing_end_date)
            if missing_df is not None and not missing_df.empty:
                # 기존 데이터와 병합
                merged_file = merge_and_save_data(code, missing_df, existing_df, market, name)
                if merged_file:
                    print(f"[완료] {code}: 누락 데이터 채우기 완료")
                    return True
            
            return False
        else:
            print(f"[확인] {code}: 시작 부분 데이터 완료")
            return True
            
    except Exception as e:
        print(f"[오류] {code} 시작 부분 확인 실패: {e}")
        return False

# collector.json 로드/저장

def load_collector_json():
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_collector_json(data):
    with open(JSON_PATH, "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# 상장폐지 여부 확인 (네이버 API 응답으로 판단)
def is_delisted(code):
    """
    네이버 API 응답으로 상장폐지 여부 확인
    """
    try:
        # 최근 30일 데이터 요청
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
        
        df = fetch_stock_data(code, start_date, end_date)
        if df is None or df.empty:
            return True
        return False
    except Exception as e:
        print(f"[오류] {code} 상장폐지 확인 중 예외 발생: {e}")
        return True

# 실제 데이터 수집 함수
def collect_data_for_code(code, info, code_name_map):
    """
    실제 데이터 수집 및 info 상태 갱신
    """
    print(f"[수집 시작] {code}")
    
    try:
        # 시작 부분 누락 데이터 확인 및 채우기
        if not info.get('start_date_complet', False):
            if check_and_fill_missing_start_data(code, info):
                info['start_date_complet'] = True
        
        # 수집할 날짜 범위 결정
        start_date, end_date = get_date_range_for_collection(code, info)
        
        # 시작일이 종료일보다 늦으면 이미 완료된 것
        if start_date > end_date:
            print(f"[완료] {code}: 이미 최신 데이터 보유")
            info['updated'] = False
            return
        
        # 데이터 수집
        df = fetch_stock_data(code, start_date, end_date)
        
        if df is None or df.empty:
            print(f"[실패] {code}: 데이터 수집 실패")
            return
        
        # 기존 파일과 병합 또는 새로 저장
        # code_name_map의 정보를 우선 사용, 없으면 JSON 정보 사용
        if code in code_name_map:
            market = code_name_map[code]['market']
            name = code_name_map[code]['name']
        else:
            market = info.get('market', 'UNKNOWN')
            name = info.get('name', 'UNKNOWN')
        existing_file = find_existing_csv_file(code, market, name)
        
        if existing_file:
            # 기존 파일이 있으면 병합
            existing_df = load_existing_csv_data(existing_file)
            if existing_df is not None:
                saved_file = merge_and_save_data(code, existing_df, df, market, name)
            else:
                saved_file = save_stock_data(code, df, code_name_map)
        else:
            # 새로 저장
            saved_file = save_stock_data(code, df, code_name_map)
        
        if saved_file:
            # 상태 업데이트
            if start_date == "20200101":  # 처음부터 수집한 경우
                info['start_date_complet'] = True
            
            # 최신 데이터까지 수집했는지 확인
            if end_date == datetime.now().strftime("%Y%m%d"):
                info['end_date_complet'] = True
                info['process'] = False  # 완료되었으므로 더 이상 처리 불필요
            else:
                # 아직 최신이 아니면 계속 처리 필요
                info['process'] = True
            
            print(f"[성공] {code}: {start_date} ~ {end_date} 데이터 수집 완료")
        else:
            print(f"[실패] {code}: 데이터 저장 실패")
            
    except Exception as e:
        print(f"[오류] {code} 데이터 수집 중 오류: {e}")

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
        send_error_telegram("KOSPI", "지수 수집 오류", str(e))

def main():
    # 코스피 지수 수집 먼저 실행
    print("=" * 50)
    print("[코스피 지수 수집 시작]")
    collect_kospi_index_data()
    print("=" * 50)
    
    codes, code_name_map = get_broker_codes()
    collector = load_collector_json()

    # 증권사 코드와 대조해서 없으면 collector에 추가, 있으면 market 정보 업데이트
    for code in codes:
        if code not in collector:
            # code_name_map에서 정보 가져오기
            if code in code_name_map:
                market = code_name_map[code]['market']
                name = code_name_map[code]['name']
            else:
                market = "UNKNOWN"
                name = "UNKNOWN"
            
            # 호스팩/스팩 종목은 처리 제외
            process_status = False if ("호스팩" in name or "스팩" in name) else True
            
            collector[code] = {
                "market": market,
                "name": name,
                "start_date": "2020-01-01",  # 기본값
                "start_date_complet": False,
                "end_date_complet": False,
                "process": process_status,  # 호스팩 종목은 처리 제외
                "delisted": False,
                "last_update": None
            }
        else:
            # 기존 종목이 있으면 market 정보 업데이트 (code_name_map에 있는 경우)
            if code in code_name_map:
                old_market = collector[code].get('market', 'UNKNOWN')
                new_market = code_name_map[code]['market']
                collector[code]['market'] = new_market
                collector[code]['name'] = code_name_map[code]['name']
                
                # ETF로 변경된 경우 강제로 다시 수집
                # if old_market != 'ETF' and new_market == 'ETF': # ETF 관련 로직 제거
                #     print(f"[업데이트] {code}: ETF로 변경됨 - 강제 재수집 설정")
                #     collector[code]['process'] = True
                #     collector[code]['start_date_complet'] = False
                #     collector[code]['end_date_complet'] = False
                # else:
                print(f"[업데이트] {code}: market 정보 업데이트 - {new_market}")

    # (collector에만 있고 실제 코드리스트에 없는 종목은 삭제하지 않음)

    for code, info in collector.items():
        # 스팩 종목 제외
        name = info.get('name', '')
        if '호스팩' in name or '스팩' in name:
            print(f"{code}: 스팩 종목 제외 ({name})")
            continue
        
        # ETF 종목은 강제로 처리 (market 정보 업데이트를 위해)
        # if info.get('market') == 'ETF': # ETF 관련 로직 제거
        #     print(f"{code}: ETF 종목 강제 처리 ({name})")
        #     info['process'] = True  # 강제로 처리 필요로 설정
        #     info['start_date_complet'] = False  # 시작 부분 다시 수집
        #     info['end_date_complet'] = False  # 끝 부분 다시 수집
        
        # 처리할 필요가 없는 종목은 건너뛰기 (process가 false이거나 이미 완료된 경우)
        if not info.get("process", False) or (info.get("start_date_complet", False) and info.get("end_date_complet", False)):
            print(f"{code}: 처리 불필요 (process: {info.get('process', False)}, 완료: {info.get('start_date_complet', False)}/{info.get('end_date_complet', False)})")
            continue
        # 시작부분 이미 완료면 패스
        if info.get("start_date_complet", False):
            print(f"{code}: 시작부분 이미 완료 (start_date_complet)")
            continue
        # 상장폐지면 end_date_complet 처리
        if not info.get("end_date_complet", False) and is_delisted(code):
            info["end_date_complet"] = True
            info["delisted"] = True
            print(f"{code}: 상장폐지로 end_date_complet 처리")
            continue
        # 실제 데이터 수집
        collect_data_for_code(code, info, code_name_map)
        # 마지막 업데이트 기록
        info["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 각 종목 처리 후 JSON 저장 (진행 상황 보존)
        save_collector_json(collector)
        
        # API 호출 제한을 위한 대기
        time.sleep(0.5)

if __name__ == "__main__":
    main() 