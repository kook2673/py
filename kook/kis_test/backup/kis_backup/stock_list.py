# -*- coding: utf-8 -*-
'''
종목 관리 전담 모듈

다른 코드에서 종목 코드 리스트를 요청하면 해당 정보를 찾아서 제공합니다.
없는 종목은 새로 검색해서 추가하고 리턴합니다.

사용법:
from stock_list import get_stock_info_list

# 종목 정보 요청
stock_info_list = get_stock_info_list(['005930', '000660'])

관련 포스팅
https://blog.naver.com/zacra/223597500754
'''

import KIS_Common as Common
import pandas as pd
import requests
import json
import os
import logging
import time
from datetime import datetime
import sys

# KIS API 설정
Common.SetChangeMode("REAL")  # REAL or VIRTUAL

# MA_Strategy_FindMa_Optimized에서 최적의 MA 값을 찾는 함수 import
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'kook'))
try:
    import MA_Strategy_FindMa_Optimized as FindMA
except ImportError:
    # kook_test 폴더에서 찾을 수 없는 경우 현재 폴더에서 찾기
    sys.path.append(os.path.join(os.path.dirname(__file__), 'kook_test'))
    import MA_Strategy_FindMa_Optimized as FindMA

def setup_logging():
    """
    로깅 설정을 초기화하는 함수
    """
    # 소스 파일이 있는 폴더 경로 가져오기
    source_dir = os.path.dirname(os.path.abspath(__file__))
    
    # logs 폴더가 없으면 생성
    logs_dir = os.path.join(source_dir, 'logs')
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # 로깅 설정
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(logs_dir, "stock_list.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8', mode='a'),  # mode='a'로 기존 로그에 이어서 붙임
            logging.StreamHandler()
        ]
    )
    
    return timestamp, source_dir

def get_top_market_cap_stocks(count=100):
    """
    네이버 주식 API에서 코스피와 코스닥 시가총액 상위 종목들을 가져오는 함수
    
    Args:
        count (int): 각 시장에서 가져올 종목 수 (기본값: 100)
        
    Returns:
        dict: {'kospi': [종목코드리스트], 'kosdaq': [종목코드리스트]}
    """
    try:
        kospi_stocks = []
        kosdaq_stocks = []
        
        # 코스피 시가총액 상위 종목 가져오기 (ETF 제외)
        kospi_url = f"https://m.stock.naver.com/api/stocks/marketValue/KOSPI?page=1&pageSize={count}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        logging.info(f"코스피 시가총액 상위 {count}개 종목을 가져오는 중...")
        kospi_response = requests.get(kospi_url, headers=headers)
        kospi_response.raise_for_status()
        kospi_data = kospi_response.json()
        kospi_stock_data = kospi_data.get('stocks', [])
        
        for stock in kospi_stock_data:
            stock_code = stock.get('itemCode')
            stock_name = stock.get('stockName')
            market_value = stock.get('marketValue', '0')
            
            if stock_code:
                kospi_stocks.append({
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'market_value': market_value
                })
                logging.info(f"코스피 종목 추가: {stock_name} ({stock_code}) - 시가총액: {market_value}")
        
        # 코스닥 시가총액 상위 종목 가져오기 (ETF 제외)
        kosdaq_url = f"https://m.stock.naver.com/api/stocks/marketValue/KOSDAQ?page=1&pageSize={count}"
        
        logging.info(f"코스닥 시가총액 상위 {count}개 종목을 가져오는 중...")
        kosdaq_response = requests.get(kosdaq_url, headers=headers)
        kosdaq_response.raise_for_status()
        kosdaq_data = kosdaq_response.json()
        kosdaq_stock_data = kosdaq_data.get('stocks', [])
        
        for stock in kosdaq_stock_data:
            stock_code = stock.get('itemCode')
            stock_name = stock.get('stockName')
            market_value = stock.get('marketValue', '0')
            
            if stock_code:
                kosdaq_stocks.append({
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'market_value': market_value
                })
                logging.info(f"코스닥 종목 추가: {stock_name} ({stock_code}) - 시가총액: {market_value}")
        
        logging.info(f"총 {len(kospi_stocks)}개 코스피 종목, {len(kosdaq_stocks)}개 코스닥 종목을 가져왔습니다.")
        
        return {
            'kospi': kospi_stocks,
            'kosdaq': kosdaq_stocks
        }
        
    except Exception as e:
        logging.error(f"네이버 API에서 종목 정보 가져오기 실패: {e}")
        # 실패 시 기본 종목 리스트 반환
        return {
            'kospi': [{'stock_code': '005930', 'stock_name': '삼성전자', 'market_value': '0'}],
            'kosdaq': [{'stock_code': '000660', 'stock_name': 'SK하이닉스', 'market_value': '0'}]
        }

def load_stock_list_from_json(filename="stock_list.json"):
    """
    JSON 파일에서 종목 리스트를 로드하는 함수
    
    Args:
        filename (str): JSON 파일명
        
    Returns:
        dict: 종목 리스트 딕셔너리
    """
    try:
        # 소스 파일이 있는 폴더 경로 가져오기
        source_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(source_dir, filename)
        
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                stock_data = json.load(f)
                logging.info(f"기존 종목 리스트 파일을 로드했습니다: {file_path}")
                return stock_data
        else:
            logging.info(f"종목 리스트 파일이 존재하지 않습니다: {file_path}")
            return {}
    except Exception as e:
        logging.error(f"종목 리스트 파일 로드 중 오류 발생: {e}")
        return {}

def save_stock_list_to_json(stock_data, filename="stock_list.json"):
    """
    종목 리스트를 JSON 파일에 저장하는 함수
    
    Args:
        stock_data (dict): 종목 리스트 딕셔너리
        filename (str): JSON 파일명
    """
    try:
        # 소스 파일이 있는 폴더 경로 가져오기
        source_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(source_dir, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(stock_data, f, ensure_ascii=False, indent=4)
        
        logging.info(f"종목 리스트가 저장되었습니다: {file_path}")
    except Exception as e:
        logging.error(f"종목 리스트 파일 저장 중 오류 발생: {e}")

def find_optimal_ma_for_stock(stock_code, stock_name, test_area="KR"):
    """
    개별 종목에 대해 최적의 MA 값을 찾는 함수
    
    Args:
        stock_code (str): 종목 코드
        stock_name (str): 종목명
        test_area (str): 테스트 영역 ("KR" 또는 "US")
        
    Returns:
        dict: 최적 MA 값 정보
    """
    try:
        logging.info(f"{stock_name} ({stock_code}) 종목의 최적 MA 값을 찾는 중...")
        
        # KIS API 토큰 확인 (MA_Kosdaqpi100_Bot_v1.py 방식)
        # 토큰은 Common.GetToken()에서 자동으로 처리됨
        
        # 최적의 MA 값 찾기
        optimal_result = FindMA.FindOptimalMA(
            stock_code=stock_code,
            test_area=test_area,
            get_count=700,
            cut_count=0,
            fee=0.0025,
            total_money=1000000
        )
        
        if optimal_result is not None:
            ma_info = {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "small_ma": optimal_result['small_ma'],
                "big_ma": optimal_result['big_ma'],
                "revenue_rate": optimal_result['revenue_rate'],
                "mdd": optimal_result.get('mdd', 0),
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            logging.info(f"{stock_name} ({stock_code}): small_ma={optimal_result['small_ma']}, big_ma={optimal_result['big_ma']}, 수익률={optimal_result['revenue_rate']}%")
            return ma_info
        else:
            logging.warning(f"{stock_name} ({stock_code}) 종목의 최적 MA 값을 찾을 수 없습니다.")
            return None
            
    except Exception as e:
        logging.error(f"{stock_name} ({stock_code}) 종목 MA 값 계산 중 오류 발생: {e}")
        return None

def get_stock_name_from_api(stock_code):
    """
    API를 통해 종목명을 가져오는 함수
    
    Args:
        stock_code (str): 종목 코드
        
    Returns:
        str: 종목명
    """
    try:
        # KIS API를 통해 종목명 가져오기
        stock_name = Common.GetStockName(stock_code)
        if stock_name:
            return stock_name
        else:
            return stock_code
    except Exception as e:
        logging.error(f"종목명 가져오기 실패 ({stock_code}): {e}")
        return stock_code

def get_stock_info_list(requested_stock_codes):
    """
    요청된 종목 코드 리스트에 대한 정보를 반환하는 메인 함수
    
    Args:
        requested_stock_codes (list): 요청된 종목 코드 리스트
        
    Returns:
        list: 종목 정보 리스트
    """
    try:
        # 로깅 설정
        timestamp, source_dir = setup_logging()
        
        logging.info(f"=== 종목 정보 요청 처리 시작 ===")
        logging.info(f"요청된 종목: {requested_stock_codes}")
        
        # 1. 기존 파일에서 데이터 로드
        existing_data = load_stock_list_from_json()
        
        # 2. 요청된 종목들의 정보 수집
        result_stock_list = []
        new_stocks_added = {}
        
        for stock_code in requested_stock_codes:
            # 기존 데이터에서 찾기
            if stock_code in existing_data.get('stocks', {}):
                stock_info = existing_data['stocks'][stock_code]
                result_stock_list.append({
                    'stock_code': stock_code,
                    'stock_name': stock_info.get('stock_name', stock_code),
                    'small_ma': stock_info.get('small_ma', 20),
                    'big_ma': stock_info.get('big_ma', 60),
                    'revenue_rate': stock_info.get('revenue_rate', 0),
                    'mdd': stock_info.get('mdd', 0),
                    'last_updated': stock_info.get('last_updated', '')
                })
                logging.info(f"{stock_code} - 기존 데이터 사용")
            else:
                # 새로운 종목 - MA 값 계산
                stock_name = get_stock_name_from_api(stock_code)
                logging.info(f"{stock_code} ({stock_name}) - 새로운 MA 값 계산")
                
                ma_info = find_optimal_ma_for_stock(stock_code, stock_name, "KR")
                if ma_info:
                    new_stocks_added[stock_code] = ma_info
                    result_stock_list.append(ma_info)
                else:
                    # MA 값 계산 실패 시 None으로 설정
                    failed_info = {
                        "stock_code": stock_code,
                        "stock_name": stock_name,
                        "small_ma": None,
                        "big_ma": None,
                        "revenue_rate": None,
                        "mdd": None,
                        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    new_stocks_added[stock_code] = failed_info
                    result_stock_list.append(failed_info)
                    logging.warning(f"{stock_code} ({stock_name}) - MA 값 계산 실패, None으로 설정")
                
                # API 호출 제한을 위한 대기
                time.sleep(0.1)
        
        # 3. 새로운 종목이 있으면 파일에 저장
        if new_stocks_added:
            # 기존 stocks에 새로운 종목들 추가
            if 'stocks' not in existing_data:
                existing_data['stocks'] = {}
            
            existing_data['stocks'].update(new_stocks_added)
            existing_data['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            save_stock_list_to_json(existing_data)
            logging.info(f"새로운 종목 {len(new_stocks_added)}개가 저장되었습니다.")
        
        logging.info(f"=== 종목 정보 요청 처리 완료 ===")
        logging.info(f"총 {len(result_stock_list)}개 종목 정보 반환")
        
        return result_stock_list
        
    except Exception as e:
        logging.error(f"종목 정보 요청 처리 중 오류 발생: {e}")
        return []

def update_portfolio_config_ma_values(updated_stocks):
    """
    stock_list.json에서 업데이트된 MA 값들을 portfolio_config.json의 5개 특정 종목에 동기화하는 함수
    
    Args:
        updated_stocks (dict): stock_list.json에서 업데이트된 종목 정보
    """
    try:
        # 소스 파일이 있는 폴더 경로 가져오기
        source_dir = os.path.dirname(os.path.abspath(__file__))
        portfolio_config_file_path = os.path.join(source_dir, 'portfolio_config.json')
        
        # portfolio_config.json 파일 읽기
        with open(portfolio_config_file_path, 'r', encoding='utf-8') as f:
            portfolio_config = json.load(f)
        
        # MA_Strategy_KR_Bot_v3의 5개 특정 종목 코드들
        target_stock_codes = [
            "133690",  # TIGER 미국나스닥100
            "069500",  # KODEX 200
            "148070",  # KOSEF 국고채10년
            "305080",  # TIGER 미국채10년선물
            "132030"   # KODEX 골드선물(H)
        ]
        
        updated_count = 0
        
        # MA_Strategy_KR_Bot_v3 섹션이 있는지 확인
        if 'MA_Strategy_KR_Bot_v3' in portfolio_config.get('bots', {}):
            bot_v3_config = portfolio_config['bots']['MA_Strategy_KR_Bot_v3']
            
            if 'invest_stock_list' in bot_v3_config:
                for stock_item in bot_v3_config['invest_stock_list']:
                    stock_code = stock_item.get('stock_code')
                    
                    # 5개 특정 종목 중 하나인지 확인
                    if stock_code in target_stock_codes:
                        # stock_list.json에서 해당 종목의 업데이트된 정보 찾기
                        if stock_code in updated_stocks:
                            updated_stock_info = updated_stocks[stock_code]
                            
                            # small_ma와 big_ma 값이 업데이트되었는지 확인
                            if 'small_ma' in updated_stock_info and updated_stock_info['small_ma'] is not None:
                                old_small_ma = stock_item.get('small_ma')
                                new_small_ma = updated_stock_info['small_ma']
                                
                                if old_small_ma != new_small_ma:
                                    stock_item['small_ma'] = new_small_ma
                                    logging.info(f"portfolio_config.json 업데이트: {stock_item.get('stock_name', stock_code)} ({stock_code}) small_ma {old_small_ma} -> {new_small_ma}")
                                    updated_count += 1
                            
                            if 'big_ma' in updated_stock_info and updated_stock_info['big_ma'] is not None:
                                old_big_ma = stock_item.get('big_ma')
                                new_big_ma = updated_stock_info['big_ma']
                                
                                if old_big_ma != new_big_ma:
                                    stock_item['big_ma'] = new_big_ma
                                    logging.info(f"portfolio_config.json 업데이트: {stock_item.get('stock_name', stock_code)} ({stock_code}) big_ma {old_big_ma} -> {new_big_ma}")
                                    updated_count += 1
                
                # 변경사항이 있으면 파일 저장
                if updated_count > 0:
                    with open(portfolio_config_file_path, 'w', encoding='utf-8') as f:
                        json.dump(portfolio_config, f, ensure_ascii=False, indent=4)
                    
                    logging.info(f"portfolio_config.json의 5개 특정 종목 MA 값 동기화 완료: {updated_count}개 값 업데이트")
                else:
                    logging.info("portfolio_config.json의 5개 특정 종목 MA 값 동기화: 업데이트할 값이 없습니다.")
            else:
                logging.warning("portfolio_config.json에서 MA_Strategy_KR_Bot_v3의 invest_stock_list를 찾을 수 없습니다.")
        else:
            logging.warning("portfolio_config.json에서 MA_Strategy_KR_Bot_v3 섹션을 찾을 수 없습니다.")
            
    except Exception as e:
        logging.error(f"portfolio_config.json MA 값 동기화 중 오류 발생: {e}")

def update_kospi_kosdaq_lists():
    """
    코스피100, 코스닥100 리스트를 업데이트하고 전체 종목에 대해 MA 값을 계산하는 함수
    """
    try:
        # 로깅 설정
        timestamp, script_dir = setup_logging()
        
        logging.info("=== 코스피100, 코스닥100 리스트 업데이트 및 MA 값 계산 시작 ===")
        
        # 1. 네이버 API에서 코스피100, 코스닥100 종목 가져오기
        stock_data = get_top_market_cap_stocks(count=100)
        
        # 2. 기존 파일에서 데이터 로드
        existing_data = load_stock_list_from_json()
        
        # 3. 모든 종목 리스트 생성 (코스피100 + 코스닥100 + 기존 stocks)
        all_stocks_to_process = []
        
        # 코스피100 종목 추가
        for stock in stock_data['kospi']:
            all_stocks_to_process.append({
                'stock_code': stock['stock_code'],
                'stock_name': stock['stock_name'],
                'market': 'KOSPI'
            })
        
        # 코스닥100 종목 추가
        for stock in stock_data['kosdaq']:
            all_stocks_to_process.append({
                'stock_code': stock['stock_code'],
                'stock_name': stock['stock_name'],
                'market': 'KOSDAQ'
            })
        
        # 기존 stocks에 있는 종목들도 추가 (중복 제거)
        if 'stocks' in existing_data:
            for stock_code, stock_info in existing_data['stocks'].items():
                # 이미 추가되지 않은 종목만 추가
                if not any(s['stock_code'] == stock_code for s in all_stocks_to_process):
                    all_stocks_to_process.append({
                        'stock_code': stock_code,
                        'stock_name': stock_info.get('stock_name', stock_code),
                        'market': 'EXISTING'
                    })
        
        logging.info(f"총 {len(all_stocks_to_process)}개 종목의 MA 값을 계산합니다.")
        
        # 4. 모든 종목에 대해 MA 값 계산
        updated_stocks = {}
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        for i, stock in enumerate(all_stocks_to_process):
            stock_code = stock['stock_code']
            stock_name = stock['stock_name']
            market = stock['market']
            
            logging.info(f"[{i+1}/{len(all_stocks_to_process)}] {stock_name} ({stock_code}) - {market}")
            
            # 기존 데이터에서 오늘 업데이트된 종목인지 확인
            skip_ma_calculation = False
            if stock_code in existing_data.get('stocks', {}):
                existing_stock = existing_data['stocks'][stock_code]
                if 'last_updated' in existing_stock:
                    existing_date = existing_stock['last_updated'].split(' ')[0]  # 날짜 부분만 추출
                    if existing_date == today:
                        logging.info(f"  - 오늘 이미 업데이트된 종목이므로 MA 계산 건너뜀")
                        updated_stocks[stock_code] = existing_stock
                        skip_ma_calculation = True
            
            if not skip_ma_calculation:
                # 새로운 MA 값 계산
                logging.info(f"  - 새로운 MA 값 계산 중...")
                ma_info = find_optimal_ma_for_stock(stock_code, stock_name, "KR")
                if ma_info:
                    updated_stocks[stock_code] = ma_info
                    logging.info(f"  - MA 값 계산 완료: small_ma={ma_info['small_ma']}, big_ma={ma_info['big_ma']}")
                else:
                    # MA 값 계산 실패 시 None으로 설정
                    failed_info = {
                        "stock_code": stock_code,
                        "stock_name": stock_name,
                        "small_ma": None,
                        "big_ma": None,
                        "revenue_rate": None,
                        "mdd": None,
                        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    updated_stocks[stock_code] = failed_info
                    logging.warning(f"  - MA 값 계산 실패, None으로 설정")
            
            # API 호출 제한을 위한 대기
            time.sleep(0.1)
        
        # 5. 결과 저장
        # kospi100_list와 kosdaq100_list를 합쳐서 stock_list 생성
        stock_list = stock_data['kospi'] + stock_data['kosdaq']
        
        final_data = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stocks": updated_stocks
        }
        
        save_stock_list_to_json(final_data)
        
        # 6. portfolio_config.json의 5개 특정 종목 MA 값 동기화
        logging.info("=== portfolio_config.json의 5개 특정 종목 MA 값 동기화 시작 ===")
        update_portfolio_config_ma_values(updated_stocks)
        
        # portfolio_config.json에 stock_list 저장
        portfolio_config_file_path = os.path.join(script_dir, 'portfolio_config.json')
        try:
            # 기존 포트폴리오 설정 파일 읽기
            with open(portfolio_config_file_path, 'r', encoding='utf-8') as f:
                portfolio_config = json.load(f)
            
            # MA_Kosdaqpi100_Bot_v1 섹션에 stock_list 추가
            if 'MA_Kosdaqpi100_Bot_v1' in portfolio_config.get('bots', {}):
                # stock_list를 invest_stock_list 형식으로 변환
                formatted_stock_list = []
                for stock in stock_list:
                    # 기존 MA 값이 있으면 사용, 없으면 기본값 사용
                    stock_code = stock['stock_code']
                    stock_name = stock['stock_name']
                    
                    # 기존 stocks에서 MA 값 찾기
                    existing_ma = None
                    if stock_code in updated_stocks:
                        existing_ma = updated_stocks[stock_code]
                    
                    stock_info = {
                        "stock_code": stock_code,
                        "stock_name": stock_name,
                        "small_ma": existing_ma.get('small_ma', 5) if existing_ma else 5,
                        "big_ma": existing_ma.get('big_ma', 20) if existing_ma else 20,
                        "invest_rate": 0.05  # 기본 투자 비율 5%
                    }
                    formatted_stock_list.append(stock_info)
                
                # invest_stock_list 업데이트
                portfolio_config['bots']['MA_Kosdaqpi100_Bot_v1']['invest_stock_list'] = formatted_stock_list
                
                # 설정 파일 저장
                with open(portfolio_config_file_path, 'w', encoding='utf-8') as f:
                    json.dump(portfolio_config, f, ensure_ascii=False, indent=4)
                
                logging.info(f"portfolio_config.json에 stock_list 저장 완료 ({len(formatted_stock_list)}개 종목)")
            else:
                logging.warning("portfolio_config.json에서 MA_Kosdaqpi100_Bot_v1 섹션을 찾을 수 없습니다.")
        except Exception as e:
            logging.error(f"portfolio_config.json 저장 중 오류: {e}")
        
        logging.info(f"=== 코스피100, 코스닥100 리스트 업데이트 및 MA 값 계산 완료 ===")
        logging.info(f"총 {len(updated_stocks)}개 종목이 저장되었습니다.")
        logging.info(f"코스피: {len(stock_data['kospi'])}개, 코스닥: {len(stock_data['kosdaq'])}개")
        
        return final_data
        
    except Exception as e:
        logging.error(f"코스피100, 코스닥100 리스트 업데이트 및 MA 값 계산 중 오류 발생: {e}")
        return None

if __name__ == "__main__":
    # 메인 실행 - 코스피100, 코스닥100 리스트 업데이트 및 전체 MA 값 계산
    result = update_kospi_kosdaq_lists()
    
    if result:
        print(f"\n=== 코스피100, 코스닥100 리스트 업데이트 및 MA 값 계산 완료 ===")
        print(f"총 {len(result['stocks'])}개 종목이 처리되었습니다.")
        print(f"마지막 업데이트: {result['last_updated']}")
        
        # 처리된 종목 수 통계
        existing_count = 0
        new_count = 0
        today = datetime.now().strftime("%Y-%m-%d")
        for stock_code, stock_info in result['stocks'].items():
            if 'last_updated' in stock_info and today in stock_info['last_updated']:
                new_count += 1
            else:
                existing_count += 1
        
        print(f"기존 데이터 사용: {existing_count}개")
        print(f"새로 계산된 종목: {new_count}개")
    else:
        print("코스피100, 코스닥100 리스트 업데이트 및 MA 값 계산에 실패했습니다.") 