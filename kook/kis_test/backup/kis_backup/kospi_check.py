# -*- coding: utf-8 -*-
import os
import sys

# 인코딩 문제 방지를 위한 환경 변수 설정
os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.platform.startswith('win'):
    os.environ['PYTHONLEGACYWINDOWSSTDIO'] = 'utf-8'
    # Windows에서 출력 버퍼링 비활성화
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import json
from datetime import datetime, timedelta
import requests
import pandas as pd
import time
import numpy as np

# 스크립트 파일의 절대 경로
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 코스피 지수 API URL
KOSPI_INDEX_URL = "https://api.stock.naver.com/chart/domestic/index/KOSPI/day?startDateTime={start}0000&endDateTime={end}0000"

# 텔레그램 설정 파일 (스크립트 위치 기준)
TELEGRAM_STATUS_FILE = os.path.join(SCRIPT_DIR, "kospi_check.json")

def load_telegram_status():
    """
    텔레그램 상태 로드
    """
    if os.path.exists(TELEGRAM_STATUS_FILE):
        try:
            with open(TELEGRAM_STATUS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 필수 키들이 있는지 확인하고 없으면 기본값 추가
                if "sent_5" not in data:
                    data["sent_5"] = False
                if "sent_10" not in data:
                    data["sent_10"] = False
                if "sent_15" not in data:
                    data["sent_15"] = False
                if "last_reset_date" not in data:
                    data["last_reset_date"] = None
                return data
        except Exception as e:
            print(f"[경고] 텔레그램 상태 파일 읽기 실패: {e}")
    
    # 기본값 반환
    return {
        "sent_5": False,
        "sent_10": False,
        "sent_15": False,
        "last_reset_date": None
    }

def save_telegram_status(status):
    """
    텔레그램 상태 저장
    """
    try:
        with open(TELEGRAM_STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[오류] 텔레그램 상태 저장 실패: {e}")

def reset_telegram_status_if_needed(status, current_date):
    """
    필요시 텔레그램 상태 초기화
    """
    # last_reset_date 키가 없으면 추가
    if "last_reset_date" not in status or status["last_reset_date"] is None:
        status["last_reset_date"] = current_date.strftime('%Y-%m-%d')
        return status
    
    try:
        last_reset = datetime.strptime(status["last_reset_date"], '%Y-%m-%d')
        
        # 하루가 지났으면 초기화
        if (current_date - last_reset).days >= 1:
            status["sent_5"] = False
            status["sent_10"] = False
            status["sent_15"] = False
            status["last_reset_date"] = current_date.strftime('%Y-%m-%d')
            print(f"[정보] 텔레그램 상태 초기화됨")
    except Exception as e:
        print(f"[경고] 날짜 파싱 실패, 상태 초기화: {e}")
        # 날짜 파싱에 실패하면 초기화
        status["sent_5"] = False
        status["sent_10"] = False
        status["sent_15"] = False
        status["last_reset_date"] = current_date.strftime('%Y-%m-%d')
    
    return status

def send_telegram_message(message):
    """
    텔레그램 메시지 전송
    """
    try:
        # 텔레그램 설정 파일에서 토큰과 채팅 ID 가져오기
        real_token_file = os.path.join(SCRIPT_DIR, "real_token.json")
        if os.path.exists(real_token_file):
            with open(real_token_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                token = config.get("telegram_token")
                chat_id = config.get("telegram_chat_id")
                
                if token and chat_id:
                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    data = {
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "HTML"
                    }
                    
                    response = requests.post(url, data=data)
                    if response.status_code == 200:
                        print(f"[성공] 텔레그램 메시지 전송됨")
                        return True
                    else:
                        print(f"[오류] 텔레그램 메시지 전송 실패: {response.status_code}")
                        return False
                else:
                    print(f"[오류] 텔레그램 설정이 없습니다.")
                    return False
        else:
            print(f"[오류] real_token.json 파일이 없습니다.")
            return False
            
    except Exception as e:
        print(f"[오류] 텔레그램 메시지 전송 중 오류: {e}")
        return False

def check_and_send_telegram(change_percentage, current_kospi, max_kospi, current_date):
    """
    변화율에 따라 텔레그램 메시지 전송
    """
    status = load_telegram_status()
    
    # 필수 키들이 있는지 확인하고 없으면 기본값 설정
    if "sent_5" not in status:
        status["sent_5"] = False
    if "sent_10" not in status:
        status["sent_10"] = False
    if "sent_15" not in status:
        status["sent_15"] = False
    if "last_reset_date" not in status:
        status["last_reset_date"] = None
    
    status = reset_telegram_status_if_needed(status, current_date)
    
    message_sent = False
    
    # -15% 이상일 때는 항상 전송
    if change_percentage <= -15:
        message = f"🚨 <b>코스피 급락 알림</b>\n\n"
        message += f"📅 날짜: {current_date.strftime('%Y년 %m월 %d일')}\n"
        message += f"📊 현재 코스피: {current_kospi:,.2f}\n"
        message += f"🏆 최고점: {max_kospi:,.2f}\n"
        message += f"📉 변화율: {change_percentage:+.2f}%\n\n"
        message += f"⚠️ -15% 이상 하락 중입니다!"
        
        if send_telegram_message(message):
            message_sent = True
    
    # -15% 미만일 때는 한번만 전송
    elif change_percentage <= -10 and not status["sent_10"]:
        message = f"⚠️ <b>코스피 하락 알림</b>\n\n"
        message += f"📅 날짜: {current_date.strftime('%Y년 %m월 %d일')}\n"
        message += f"📊 현재 코스피: {current_kospi:,.2f}\n"
        message += f"🏆 최고점: {max_kospi:,.2f}\n"
        message += f"📉 변화율: {change_percentage:+.2f}%\n\n"
        message += f"⚠️ -10% 이상 하락했습니다!"
        
        if send_telegram_message(message):
            status["sent_10"] = True
            message_sent = True
    
    elif change_percentage <= -5 and not status["sent_5"]:
        message = f"📉 <b>코스피 하락 알림</b>\n\n"
        message += f"📅 날짜: {current_date.strftime('%Y년 %m월 %d일')}\n"
        message += f"📊 현재 코스피: {current_kospi:,.2f}\n"
        message += f"🏆 최고점: {max_kospi:,.2f}\n"
        message += f"📉 변화율: {change_percentage:+.2f}%\n\n"
        message += f"📉 -5% 이상 하락했습니다!"
        
        if send_telegram_message(message):
            status["sent_5"] = True
            message_sent = True
    
    # 상태 저장
    if message_sent:
        save_telegram_status(status)

def save_kospi_analysis_info(current_kospi, max_kospi, max_date, change_percentage, current_date):
    """
    코스피 분석 정보를 JSON 파일에 저장
    """
    try:
        analysis_info = {
            "last_analysis_date": current_date.strftime('%Y-%m-%d'),
            "last_analysis_time": current_date.strftime('%H:%M:%S'),
            "current_kospi": current_kospi,
            "max_kospi": max_kospi,
            "max_date": max_date.strftime('%Y-%m-%d'),
            "change_percentage": round(change_percentage, 2),
            "analysis_summary": {
                "status": "상승" if change_percentage > 0 else "하락" if change_percentage < 0 else "동일",
                "level": "심각" if change_percentage <= -15 else "주의" if change_percentage <= -10 else "관찰" if change_percentage <= -5 else "정상"
            },
            "notification_history": []
        }
        
        # 기존 파일이 있으면 읽어서 히스토리 추가
        kospi_check_file = os.path.join(SCRIPT_DIR, "kospi_check.json")
        if os.path.exists(kospi_check_file):
            try:
                with open(kospi_check_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    if "notification_history" in existing_data:
                        analysis_info["notification_history"] = existing_data["notification_history"]
            except:
                pass
        
        # 현재 분석을 히스토리에 추가
        history_entry = {
            "date": current_date.strftime('%Y-%m-%d'),
            "time": current_date.strftime('%H:%M:%S'),
            "current_kospi": current_kospi,
            "change_percentage": round(change_percentage, 2),
            "status": analysis_info["analysis_summary"]["status"]
        }
        
        # 최근 30일 히스토리만 유지
        analysis_info["notification_history"].append(history_entry)
        if len(analysis_info["notification_history"]) > 30:
            analysis_info["notification_history"] = analysis_info["notification_history"][-30:]
        
        # 파일에 저장
        with open(kospi_check_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_info, f, ensure_ascii=False, indent=2)
        
        print(f"[정보] 코스피 분석 정보가 kospi_check.json에 저장되었습니다.")
        
    except Exception as e:
        print(f"[오류] 코스피 분석 정보 저장 실패: {e}")

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
            
            # date 컬럼을 datetime으로 변환
            df['date'] = pd.to_datetime(df['date'])
        else:
            print(f"[경고] 코스피 지수 데이터 형식이 예상과 다름")
            return None
            
        return df
        
    except Exception as e:
        print(f"[오류] 코스피 지수 데이터 수집 실패: {e}")
        return None

def get_kospi_data_for_period(days=365):
    """
    지정된 기간의 코스피 데이터를 가져옴
    """
    today = datetime.now()
    start_date = (today - timedelta(days=days)).strftime('%Y%m%d')
    end_date = today.strftime('%Y%m%d')
    
    print(f"[정보] 코스피 데이터 수집 기간: {start_date} ~ {end_date} ({days}일)")
    
    df = fetch_kospi_index_data(start_date, end_date)
    if df is None or df.empty:
        print("[오류] 코스피 데이터를 가져올 수 없습니다.")
        return None
    
    # 날짜순으로 정렬
    df = df.sort_values('date')
    return df

def calculate_percentage_change(current_value, reference_value):
    """
    변화율 계산
    """
    if reference_value == 0:
        return 0
    return ((current_value - reference_value) / reference_value) * 100

def analyze_kospi_vs_highest(df):
    """
    1년 중 가장 높은 코스피 대비 현재 코스피 분석
    """
    if df is None or df.empty:
        print("[오류] 분석할 데이터가 없습니다.")
        return
    
    # 최신 데이터 (오늘)
    latest_data = df.iloc[-1]
    current_kospi = latest_data['close']
    current_date = latest_data['date']
    
    # 1년 내 최고점 찾기
    max_kospi = df['close'].max()
    max_date = df.loc[df['close'].idxmax(), 'date']
    
    # 현재가 대비 최고점 변화율 계산
    change_from_highest = calculate_percentage_change(current_kospi, max_kospi)
    
    print(f"\n{'='*37}")
    print(f"[1년 내 최고점 대비 현재 코스피 분석]")
    print(f"{'='*37}")
    print(f"📅 오늘 날짜: {current_date.strftime('%Y년 %m월 %d일')}")
    print(f"📊 현재 코스피: {current_kospi:,.2f}")
    print(f"")
    print(f"🏆 1년 내 최고점: {max_kospi:,.2f}")
    print(f"📅 최고점 날짜: {max_date.strftime('%Y년 %m월 %d일')}")
    print(f"")
    print(f"📈 변화율: {change_from_highest:+.2f}%")
    
    if change_from_highest > 0:
        print(f"✅ 최고점 대비 상승 중")
    elif change_from_highest < 0:
        print(f"📉 최고점 대비 하락 중")
    else:
        print(f"➡️ 최고점과 동일")
    
    # 텔레그램 메시지 전송
    check_and_send_telegram(change_from_highest, current_kospi, max_kospi, current_date)
    
    # 코스피 분석 정보를 JSON 파일에 저장
    save_kospi_analysis_info(current_kospi, max_kospi, max_date, change_from_highest, current_date)

def main():
    try:
        print("\n[데이터 수집 중...]")
        df = get_kospi_data_for_period(365)  # 1년 데이터
        
        if df is not None:
            analyze_kospi_vs_highest(df)
        else:
            print("[오류] 코스피 데이터를 가져올 수 없습니다.")
        
        print("\n" + "=" * 37)
        print("[프로그램 완료]")
        print("=" * 37)
        
    except UnicodeDecodeError as e:
        print(f"[인코딩 오류] {e}")
        print("[해결 방법] 환경 변수 PYTHONIOENCODING=utf-8 설정을 확인하세요.")
        sys.exit(1)
    except Exception as e:
        print(f"[예상치 못한 오류] {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()