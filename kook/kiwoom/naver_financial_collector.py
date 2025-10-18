#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
네이버 금융 API 재무 데이터 수집기
백테스트를 위한 과거 시점별 재무 데이터 수집
"""

import os
import json
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests
import urllib.parse

class NaverFinancialCollector:
    """네이버 금융 API 재무 데이터 수집 클래스"""
    
    def __init__(self, data_dir: str = "kiwoom/data"):
        self.data_dir = data_dir
        self.financial_dir = os.path.join(data_dir, "naver_financial")
        os.makedirs(self.financial_dir, exist_ok=True)
        
        # 네이버 금융 API 헤더
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Referer': 'https://m.stock.naver.com/',
            'Origin': 'https://m.stock.naver.com'
        }
    
    def get_financial_summary(self, stock_code: str) -> Optional[Dict]:
        """네이버 금융에서 재무 요약 데이터 가져오기"""
        try:
            url = f"https://m.stock.naver.com/api/stock/{stock_code}/finance/summary"
            
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            return data
            
        except Exception as e:
            print(f"Error getting financial data for {stock_code}: {str(e)}")
            return None
    
    def parse_financial_data(self, data: Dict) -> Dict:
        """네이버 금융 API 응답을 파싱하여 정리된 형태로 변환"""
        result = {
            'stock_code': data.get('itemCode', ''),
            'eps_data': {},
            'income_statement': {
                'annual': {},
                'quarter': {}
            }
        }
        
        # EPS 데이터 파싱
        if 'chartEps' in data and 'columns' in data['chartEps']:
            columns = data['chartEps']['columns']
            if len(columns) >= 2:
                periods = columns[0][1:]  # 첫 번째는 'x' 제외
                eps_values = columns[1][1:]  # 첫 번째는 'EPS' 제외
                
                for period, eps in zip(periods, eps_values):
                    result['eps_data'][period] = float(eps) if eps != '-' else None
        
        # 손익계산서 데이터 파싱
        if 'chartIncomeStatement' in data:
            income_data = data['chartIncomeStatement']
            
            # 연간 데이터
            if 'annual' in income_data and 'columns' in income_data['annual']:
                columns = income_data['annual']['columns']
                if len(columns) >= 3:
                    periods = columns[0][1:]  # 첫 번째는 'x' 제외
                    revenue_values = columns[1][1:]  # 매출액
                    operating_income_values = columns[2][1:]  # 영업이익
                    
                    for period, revenue, operating_income in zip(periods, revenue_values, operating_income_values):
                        result['income_statement']['annual'][period] = {
                            'revenue': float(revenue) if revenue != '-' else None,
                            'operating_income': float(operating_income) if operating_income != '-' else None
                        }
            
            # 분기 데이터
            if 'quarter' in income_data and 'columns' in income_data['quarter']:
                columns = income_data['quarter']['columns']
                if len(columns) >= 3:
                    periods = columns[0][1:]  # 첫 번째는 'x' 제외
                    revenue_values = columns[1][1:]  # 매출액
                    operating_income_values = columns[2][1:]  # 영업이익
                    
                    for period, revenue, operating_income in zip(periods, revenue_values, operating_income_values):
                        result['income_statement']['quarter'][period] = {
                            'revenue': float(revenue) if revenue != '-' else None,
                            'operating_income': float(operating_income) if operating_income != '-' else None
                        }
        
        return result
    
    def get_stock_list(self) -> List[str]:
        """상장 종목 리스트 가져오기 (기존 데이터에서 추출)"""
        stock_codes = []
        
        # kiwoom/data 폴더에서 CSV 파일들을 읽어서 종목코드 추출
        for filename in os.listdir(self.data_dir):
            if filename.endswith('.csv') and '_' in filename:
                # 파일명에서 종목코드 추출 (예: KOSPI_005930_삼성전자.csv)
                parts = filename.split('_')
                if len(parts) >= 2:
                    stock_code = parts[1]
                    if stock_code.isdigit() and len(stock_code) == 6:
                        stock_codes.append(stock_code)
        
        return list(set(stock_codes))  # 중복 제거
    
    def collect_financial_data(self, stock_codes: List[str] = None, 
                             save_to_file: bool = True) -> Dict:
        """재무 데이터 수집"""
        if stock_codes is None:
            stock_codes = self.get_stock_list()
        
        financial_data = {}
        total_codes = len(stock_codes)
        
        print(f"총 {total_codes}개 종목의 재무 데이터를 수집합니다...")
        
        for i, stock_code in enumerate(stock_codes, 1):
            print(f"진행률: {i}/{total_codes} - {stock_code}")
            
            # 네이버 금융에서 데이터 가져오기
            raw_data = self.get_financial_summary(stock_code)
            
            if raw_data:
                # 데이터 파싱
                parsed_data = self.parse_financial_data(raw_data)
                financial_data[stock_code] = parsed_data
                
                # 파일에 개별 저장
                if save_to_file:
                    file_path = os.path.join(self.financial_dir, f"{stock_code}_financial.json")
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(parsed_data, f, ensure_ascii=False, indent=2)
            
            # API 호출 간격 조절 (서버 부하 방지)
            time.sleep(0.5)
        
        # 전체 데이터를 하나의 파일로 저장
        if save_to_file:
            all_data_path = os.path.join(self.financial_dir, "all_financial_data.json")
            with open(all_data_path, 'w', encoding='utf-8') as f:
                json.dump(financial_data, f, ensure_ascii=False, indent=2)
        
        print(f"재무 데이터 수집 완료! 총 {len(financial_data)}개 종목")
        return financial_data
    
    def get_financial_data_for_date(self, stock_code: str, target_date: str) -> Dict:
        """특정 날짜의 재무 데이터 조회"""
        file_path = os.path.join(self.financial_dir, f"{stock_code}_financial.json")
        
        if not os.path.exists(file_path):
            print(f"재무 데이터 파일이 없습니다: {stock_code}")
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # target_date에 가장 가까운 분기 데이터 찾기
            # 예: 2024-12-31 -> 2024.12.
            year = target_date[:4]
            month = target_date[5:7]
            target_period = f"{year}.{month}."
            
            result = {
                'stock_code': stock_code,
                'target_date': target_date,
                'eps': None,
                'revenue': None,
                'operating_income': None
            }
            
            # EPS 데이터에서 가장 가까운 분기 찾기
            if 'eps_data' in data:
                eps_periods = list(data['eps_data'].keys())
                closest_eps_period = self._find_closest_period(eps_periods, target_period)
                if closest_eps_period:
                    result['eps'] = data['eps_data'][closest_eps_period]
            
            # 손익계산서 데이터에서 가장 가까운 분기 찾기
            if 'income_statement' in data:
                # 분기 데이터 우선
                if 'quarter' in data['income_statement']:
                    quarter_periods = list(data['income_statement']['quarter'].keys())
                    closest_quarter = self._find_closest_period(quarter_periods, target_period)
                    if closest_quarter:
                        quarter_data = data['income_statement']['quarter'][closest_quarter]
                        result['revenue'] = quarter_data.get('revenue')
                        result['operating_income'] = quarter_data.get('operating_income')
                
                # 분기 데이터가 없으면 연간 데이터 사용
                elif 'annual' in data['income_statement']:
                    annual_periods = list(data['income_statement']['annual'].keys())
                    closest_annual = self._find_closest_period(annual_periods, target_period)
                    if closest_annual:
                        annual_data = data['income_statement']['annual'][closest_annual]
                        result['revenue'] = annual_data.get('revenue')
                        result['operating_income'] = annual_data.get('operating_income')
            
            return result
            
        except Exception as e:
            print(f"Error reading financial data for {stock_code}: {str(e)}")
            return None
    
    def _find_closest_period(self, periods: List[str], target_period: str) -> Optional[str]:
        """가장 가까운 분기를 찾는 헬퍼 함수"""
        if not periods:
            return None
        
        # target_period를 숫자로 변환 (예: "2024.12." -> 202412)
        target_num = int(target_period.replace('.', ''))
        
        closest_period = None
        min_diff = float('inf')
        
        for period in periods:
            try:
                period_num = int(period.replace('.', ''))
                diff = abs(target_num - period_num)
                
                if diff < min_diff:
                    min_diff = diff
                    closest_period = period
            except:
                continue
        
        return closest_period
    
    def calculate_financial_ratios(self, stock_code: str, target_date: str, 
                                 current_price: float) -> Dict:
        """재무 비율 계산 (PER, PBR 등)"""
        financial_data = self.get_financial_data_for_date(stock_code, target_date)
        
        if not financial_data or not current_price:
            return None
        
        ratios = {
            'stock_code': stock_code,
            'target_date': target_date,
            'current_price': current_price,
            'eps': financial_data.get('eps'),
            'revenue': financial_data.get('revenue'),
            'operating_income': financial_data.get('operating_income'),
            'per': None,
            'operating_margin': None
        }
        
        # PER 계산
        if ratios['eps'] and ratios['eps'] > 0:
            ratios['per'] = current_price / ratios['eps']
        
        # 영업이익률 계산
        if ratios['revenue'] and ratios['revenue'] > 0 and ratios['operating_income']:
            ratios['operating_margin'] = (ratios['operating_income'] / ratios['revenue']) * 100
        
        return ratios

def main():
    """메인 실행 함수"""
    collector = NaverFinancialCollector()
    
    # 테스트용 종목코드
    test_codes = ["005930", "000660", "035420", "256940"]
    
    print("네이버 금융 재무 데이터 수집 시작...")
    
    # 재무 데이터 수집
    financial_data = collector.collect_financial_data(test_codes)
    
    # 결과 확인
    for stock_code, data in financial_data.items():
        print(f"\n=== {stock_code} ===")
        print(f"EPS 데이터: {data.get('eps_data', {})}")
        print(f"연간 손익: {data.get('income_statement', {}).get('annual', {})}")
        print(f"분기 손익: {data.get('income_statement', {}).get('quarter', {})}")

if __name__ == "__main__":
    main() 