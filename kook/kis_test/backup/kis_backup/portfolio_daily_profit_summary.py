#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

# KIS API 및 텔레그램 모듈 import
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import KIS_API_Helper_KR as KisKR
import KIS_Common as Common
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)
import telegram_sender as telegram

class DailyProfitSummary:
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_file_path = os.path.join(self.script_dir, "portfolio_config.json")
        self.profit_history_file = os.path.join(self.script_dir, "profit_history.json")
        self.daily_summary_file = os.path.join(self.script_dir, "portfolio_daily_profit_summary.json")
        # 한국투자증권 API 모드 설정 (REAL)
        try:
            Common.SetChangeMode("REAL")
        except Exception:
            pass
        
    def load_config(self):
        """포트폴리오 설정을 로드합니다."""
        try:
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"설정 파일 로드 실패: {e}")
            return None
    
    def save_config(self, config):
        """설정을 파일에 저장합니다."""
        try:
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"설정 파일 저장 실패: {e}")
    
    def load_profit_history(self):
        """수익 이력을 로드합니다."""
        try:
            if os.path.exists(self.profit_history_file):
                with open(self.profit_history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return {"daily": {}, "weekly": {}, "monthly": {}, "yearly": {}}
        except Exception as e:
            print(f"수익 이력 로드 실패: {e}")
            return {"daily": {}, "weekly": {}, "monthly": {}, "yearly": {}}
    
    def save_profit_history(self, history_data):
        """수익 이력을 저장합니다."""
        try:
            with open(self.profit_history_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"수익 이력 저장 실패: {e}")
    
    def get_bot_profits(self):
        """각 봇별 수익을 계산합니다."""
        try:
            config = self.load_config()
            if not config:
                return {}
            
            MyStockList = KisKR.GetMyStockList()
            if not MyStockList:
                print("보유 주식 정보를 가져올 수 없습니다.")
                return {}
            
            bot_profits = {}
            
            for bot_name, bot_config in config.get('bots', {}).items():
                if not bot_config.get('enabled', False):
                    continue
                
                # 봇별 투자 대상 종목 코드 리스트 생성
                invest_stock_list = bot_config.get('invest_stock_list', [])
                exclude_stock_list = bot_config.get('exclude_stock_list', [])
                exclude_stock_codes = [list(item.keys())[0] for item in exclude_stock_list]
                
                # 투자 대상 종목 코드 리스트 (제외 리스트 적용)
                if not invest_stock_list:
                    invest_stock_codes = []
                elif isinstance(invest_stock_list[0], dict):
                    invest_stock_codes = [
                        stock['stock_code'] for stock in invest_stock_list
                        if stock.get('stock_code') not in exclude_stock_codes
                    ]
                else:
                    # Kosdaqpi_Bot의 경우 문자열 리스트
                    invest_stock_codes = invest_stock_list
                
                # 보유 종목 기준 계산 (백업 용)
                holdings_value = 0
                holdings_profit = 0
                holdings_investment = 0
                
                for stock in MyStockList:
                    if stock['StockCode'] in invest_stock_codes:
                        try:
                            stock_value = float(stock['StockNowMoney'])
                            stock_profit = float(stock['StockRevenueMoney'])
                            stock_investment = float(stock['StockAvgPrice']) * int(stock['StockAmt'])
                            
                            holdings_value += stock_value
                            holdings_profit += stock_profit
                            holdings_investment += stock_investment
                            
                        except (ValueError, KeyError) as e:
                            print(f"주식 데이터 처리 중 오류: {e}")
                            continue
                
                # 봇별 수익 계산
                initial_allocation = bot_config.get('initial_allocation', 0)
                total_sold_profit = bot_config.get('total_sold_profit', 0)
                daily_sold_profit = bot_config.get('daily_sold_profit', 0)
                monthly_sold_profit = bot_config.get('monthly_sold_profit', 0)
                yearly_sold_profit = bot_config.get('yearly_sold_profit', 0)
                
                # 현재 보유 주식 가치
                current_stock_value = float(holdings_value)
                
                # 총 가치 = 현재 보유 주식 가치 (평가금액 표시용)
                total_value = current_stock_value

                # 총 수익(표시용) = 누적 판매 수익(실현) + 현재 보유 평가손익(미실현)
                total_profit = float(total_sold_profit) + float(holdings_profit)
                profit_rate = (total_profit / initial_allocation * 100) if initial_allocation > 0 else 0
                
                bot_profits[bot_name] = {
                    'current_stock_value': current_stock_value,      # 현재 보유 주식 가치
                    'total_sold_profit': total_sold_profit,  # 누적 판매 수익
                    'daily_sold_profit': daily_sold_profit,         # 일간 판매 수익
                    'monthly_sold_profit': monthly_sold_profit,     # 월간 판매 수익
                    'yearly_sold_profit': yearly_sold_profit,       # 연간 판매 수익
                    'unrealized_profit': float(holdings_profit),     # 현재 보유 주식의 평가손익
                    'total_value': total_value,                     # 총 가치
                    'total_profit': total_profit,                   # 총 수익
                    'total_investment': holdings_investment,        # 총 투자금
                    'profit_rate': profit_rate,                     # 총 수익률
                    'initial_allocation': initial_allocation        # 초기 배분금
                }
            
            return bot_profits
            
        except Exception as e:
            print(f"봇별 수익 계산 중 오류: {e}")
            return {}
    
    def get_current_portfolio_value(self):
        """현재 포트폴리오 가치를 계산합니다."""
        try:
            # 계좌 잔고 정보 사용
            Balance = KisKR.GetBalance()
            if not isinstance(Balance, dict):
                print(f"계좌 잔고 정보를 가져올 수 없습니다. 반환값: {Balance}")
                return 0, 0, 0

            total_portfolio_value = float(Balance.get('TotalMoney', 0))
            total_stock_value = float(Balance.get('StockMoney', 0))
            cash_balance = float(Balance.get('RemainMoney', 0))

            # 총수익은 전체 평가금액 - 초기투자금으로 정의
            config = self.load_config() or {}
            initial_investment = float(config.get('initial_investment', 0))
            
            # 모든 봇의 판매 수익(실현 손익) 합계 계산
            total_sold_profit = 0
            for bot_name, bot_config in config.get('bots', {}).items():
                if bot_config.get('enabled', False):
                    total_sold_profit += float(bot_config.get('total_sold_profit', 0))
            
            # 판매 수익을 포함한 총 수익 계산
            # total_portfolio_value에는 이미 각 봇의 current_allocation이 반영되어 있으므로
            # total_sold_profit는 별도로 더하지 않음 (중복 방지)
            total_profit = total_portfolio_value - initial_investment

            return total_portfolio_value, total_profit, initial_investment
            
        except Exception as e:
            print(f"포트폴리오 가치 계산 중 오류: {e}")
            return 0, 0, 0
    
    def calculate_period_profits(self, current_value, current_profit, bot_profits):
        """기간별 수익을 계산합니다."""
        config = self.load_config()
        if not config:
            return {}, {}
        
        initial_investment = config.get('initial_investment', 0)
        current_date = datetime.now()
        
        # 수익 이력 로드
        history = self.load_profit_history()
        
        # 전체 포트폴리오 기간별 수익 계산
        today_key = current_date.strftime("%Y-%m-%d")
        yesterday_key = (current_date - timedelta(days=1)).strftime("%Y-%m-%d")
        
        yesterday_value = history.get('daily', {}).get(yesterday_key, {}).get('total_value', initial_investment)
        today_profit = current_value - yesterday_value
        
        week_start = current_date - timedelta(days=current_date.weekday())
        week_start_key = week_start.strftime("%Y-%m-%d")
        week_start_value = history.get('daily', {}).get(week_start_key, {}).get('total_value', initial_investment)
        week_profit = current_value - week_start_value
        
        month_start = current_date.replace(day=1)
        month_start_key = month_start.strftime("%Y-%m-%d")
        month_start_value = history.get('daily', {}).get(month_start_key, {}).get('total_value', initial_investment)
        month_profit = current_value - month_start_value
        
        year_start = current_date.replace(month=1, day=1)
        year_start_key = year_start.strftime("%Y-%m-%d")
        year_start_value = history.get('daily', {}).get(year_start_key, {}).get('total_value', initial_investment)
        year_profit = current_value - year_start_value
        
        def calculate_profit_rate(profit, base_value):
            if base_value > 0:
                return (profit / base_value) * 100
            return 0
        
        portfolio_periods = {
            'today': {
                'profit': today_profit,
                'profit_rate': calculate_profit_rate(today_profit, yesterday_value)
            },
            'week': {
                'profit': week_profit,
                'profit_rate': calculate_profit_rate(week_profit, week_start_value)
            },
            'month': {
                'profit': month_profit,
                'profit_rate': calculate_profit_rate(month_profit, month_start_value)
            },
            'year': {
                'profit': year_profit,
                'profit_rate': calculate_profit_rate(year_profit, year_start_value)
            },
            'total': {
                'profit': current_profit,
                'profit_rate': calculate_profit_rate(current_profit, initial_investment)
            }
        }
        
        # 봇별 기간별 수익 계산 - 새로운 방식으로 수정
        bot_periods = {}
        for bot_name, bot_data in bot_profits.items():
            bot_initial = float(bot_data['initial_allocation'])
            bot_current_stock_value = float(bot_data['current_stock_value'])
            bot_total_sold_profit = float(bot_data['total_sold_profit'])
            bot_daily_sold_profit = float(bot_data['daily_sold_profit'])
            bot_monthly_sold_profit = float(bot_data['monthly_sold_profit'])
            bot_yearly_sold_profit = float(bot_data['yearly_sold_profit'])
            
            # 이전 기간의 보유 주식 가치 (판매 수익 제외)
            # 이전 데이터에 current_stock_value가 없는 경우 total_value를 사용 (하위 호환성)
            bot_yesterday_data = history.get('bot_daily', {}).get(yesterday_key, {}).get(bot_name, {})
            bot_month_start_data = history.get('bot_daily', {}).get(month_start_key, {}).get(bot_name, {})
            bot_year_start_data = history.get('bot_daily', {}).get(year_start_key, {}).get(bot_name, {})
            
            bot_yesterday_stock_value = bot_yesterday_data.get('current_stock_value', bot_yesterday_data.get('total_value', bot_initial))
            bot_month_start_stock_value = bot_month_start_data.get('current_stock_value', bot_month_start_data.get('total_value', bot_initial))
            bot_year_start_stock_value = bot_year_start_data.get('current_stock_value', bot_year_start_data.get('total_value', bot_initial))
            
            # 기간별 수익 = 해당 기간 판매 수익 + 현재 보유 주식 가치 수익
            # 즉, 기간별 판매수익 + 현재 보유주식의 평가손익(현재 시점)
            unrealized_profit_now = float(bot_data.get('unrealized_profit', 0))
            bot_today_profit = bot_daily_sold_profit + unrealized_profit_now
            bot_month_profit = bot_monthly_sold_profit + unrealized_profit_now
            bot_year_profit = bot_yearly_sold_profit + unrealized_profit_now
            

            
            # 총 수익은 기존과 동일 (보유 주식 가치 + 총 판매 수익 - 초기 투자금)
            bot_total_profit = float(bot_data['total_profit'])
            
            bot_periods[bot_name] = {
                'today': {
                    'profit': bot_today_profit,
                    'profit_rate': calculate_profit_rate(bot_today_profit, bot_yesterday_stock_value) if bot_yesterday_stock_value > 0 else 0
                },
                'month': {
                    'profit': bot_month_profit,
                    'profit_rate': calculate_profit_rate(bot_month_profit, bot_month_start_stock_value) if bot_month_start_stock_value > 0 else 0
                },
                'year': {
                    'profit': bot_year_profit,
                    'profit_rate': calculate_profit_rate(bot_year_profit, bot_year_start_stock_value) if bot_year_start_stock_value > 0 else 0
                },
                'total': {
                    'profit': bot_total_profit,
                    'profit_rate': calculate_profit_rate(bot_total_profit, bot_initial)
                }
            }
        
        return portfolio_periods, bot_periods
    
    def update_profit_history(self, current_value, current_profit, bot_profits):
        """수익 이력을 업데이트합니다."""
        history = self.load_profit_history()
        current_date = datetime.now()
        today_key = current_date.strftime("%Y-%m-%d")
        yesterday_key = (current_date - timedelta(days=1)).strftime("%Y-%m-%d")
        # 기간 시작 키들
        week_start = current_date - timedelta(days=current_date.weekday())
        week_start_key = week_start.strftime("%Y-%m-%d")
        month_start = current_date.replace(day=1)
        month_start_key = month_start.strftime("%Y-%m-%d")
        year_start = current_date.replace(month=1, day=1)
        year_start_key = year_start.strftime("%Y-%m-%d")
        # 초기 투자금
        config = self.load_config() or {}
        initial_investment = float(config.get('initial_investment', 0))
        
        # 전체 포트폴리오 데이터 저장
        prev_total_value = history.get('daily', {}).get(yesterday_key, {}).get('total_value', None)
        # 첫 실행(전일 데이터 없음)인 경우 initial_investment를 기준으로 일간 수익을 계산하여 모든 기간과 일관되게 표시
        if prev_total_value is None:
            daily_profit = current_value - initial_investment
            daily_profit_rate = (daily_profit / initial_investment * 100) if initial_investment > 0 else 0
        else:
            daily_profit = current_value - prev_total_value
            daily_profit_rate = (daily_profit / prev_total_value * 100) if prev_total_value > 0 else 0
        history['daily'][today_key] = {
            'total_value': current_value,
            'total_profit': current_profit,
            'daily_profit': daily_profit,
            'daily_profit_rate': daily_profit_rate,
            'timestamp': current_date.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 봇별 데이터 저장
        if 'bot_daily' not in history:
            history['bot_daily'] = {}
        
        if today_key not in history['bot_daily']:
            history['bot_daily'][today_key] = {}
        
        for bot_name, bot_data in bot_profits.items():
            # 봇 일일 수익/수익률 계산
            bot_prev_stock_value = history.get('bot_daily', {}).get(yesterday_key, {}).get(bot_name, {}).get('current_stock_value', bot_data.get('initial_allocation', 0))
            bot_daily_profit = bot_data['total_value'] - bot_prev_stock_value
            bot_daily_profit_rate = (bot_daily_profit / bot_prev_stock_value * 100) if bot_prev_stock_value > 0 else 0
            history['bot_daily'][today_key][bot_name] = {
                'total_value': bot_data['total_value'],
                'current_stock_value': bot_data['current_stock_value'],  # 보유 주식 가치 추가
                'total_profit': bot_data['total_profit'],
                'profit_rate': bot_data['profit_rate'],
                'daily_profit': bot_daily_profit,
                'daily_profit_rate': bot_daily_profit_rate,
                'timestamp': current_date.strftime("%Y-%m-%d %H:%M:%S")
            }
        
        # 주별/월별/년도별 데이터 업데이트 (전체 포트폴리오)
        week_key = current_date.strftime("%Y-W%U")
        if week_key not in history['weekly']:
            # 기간 시작 기준값: 해당 주 첫날 스냅샷이 존재하고 그날이 오늘이 아닌 경우 사용, 아니면 초기투자금
            start_value = history.get('daily', {}).get(week_start_key, {}).get('total_value', None)
            if (start_value is None) or (week_start_key == today_key):
                start_value = initial_investment
            profit = current_value - start_value
            profit_rate = (profit / start_value * 100) if start_value > 0 else 0
            history['weekly'][week_key] = {
                'start_value': start_value,
                'end_value': current_value,
                'profit': profit,
                'profit_rate': profit_rate
            }
        else:
            history['weekly'][week_key]['end_value'] = current_value
            history['weekly'][week_key]['profit'] = current_value - history['weekly'][week_key]['start_value']
            start_val = history['weekly'][week_key]['start_value']
            history['weekly'][week_key]['profit_rate'] = (history['weekly'][week_key]['profit'] / start_val * 100) if start_val > 0 else 0
        
        month_key = current_date.strftime("%Y-%m")
        if month_key not in history['monthly']:
            start_value = history.get('daily', {}).get(month_start_key, {}).get('total_value', None)
            if (start_value is None) or (month_start_key == today_key):
                start_value = initial_investment
            profit = current_value - start_value
            profit_rate = (profit / start_value * 100) if start_value > 0 else 0
            history['monthly'][month_key] = {
                'start_value': start_value,
                'end_value': current_value,
                'profit': profit,
                'profit_rate': profit_rate
            }
        else:
            history['monthly'][month_key]['end_value'] = current_value
            history['monthly'][month_key]['profit'] = current_value - history['monthly'][month_key]['start_value']
            start_val = history['monthly'][month_key]['start_value']
            history['monthly'][month_key]['profit_rate'] = (history['monthly'][month_key]['profit'] / start_val * 100) if start_val > 0 else 0
        # 연-월 중첩 구조(포트폴리오)
        if 'monthly_by_year' not in history:
            history['monthly_by_year'] = {}
        year_only = current_date.strftime('%Y')
        if year_only not in history['monthly_by_year']:
            history['monthly_by_year'][year_only] = {}
        history['monthly_by_year'][year_only][month_key] = history['monthly'][month_key]
        
        year_key = current_date.strftime("%Y")
        if year_key not in history['yearly']:
            start_value = history.get('daily', {}).get(year_start_key, {}).get('total_value', None)
            if (start_value is None) or (year_start_key == today_key):
                start_value = initial_investment
            profit = current_value - start_value
            profit_rate = (profit / start_value * 100) if start_value > 0 else 0
            history['yearly'][year_key] = {
                'start_value': start_value,
                'end_value': current_value,
                'profit': profit,
                'profit_rate': profit_rate
            }
        else:
            history['yearly'][year_key]['end_value'] = current_value
            history['yearly'][year_key]['profit'] = current_value - history['yearly'][year_key]['start_value']
            start_val = history['yearly'][year_key]['start_value']
            history['yearly'][year_key]['profit_rate'] = (history['yearly'][year_key]['profit'] / start_val * 100) if start_val > 0 else 0

        # 봇별 월/연도별 데이터 업데이트
        if 'bot_monthly' not in history:
            history['bot_monthly'] = {}
        if 'bot_yearly' not in history:
            history['bot_yearly'] = {}
        if month_key not in history['bot_monthly']:
            history['bot_monthly'][month_key] = {}
        if year_key not in history['bot_yearly']:
            history['bot_yearly'][year_key] = {}

        # 봇 월별 연-월 중첩 구조
        if 'bot_monthly_by_year' not in history:
            history['bot_monthly_by_year'] = {}
        if year_only not in history['bot_monthly_by_year']:
            history['bot_monthly_by_year'][year_only] = {}
        if month_key not in history['bot_monthly_by_year'][year_only]:
            history['bot_monthly_by_year'][year_only][month_key] = {}

        for bot_name, bot_data in bot_profits.items():
            # 월별 업데이트(봇)
            bot_month = history['bot_monthly'][month_key].get(bot_name, None)
            if bot_month is None:
                # 기간 시작 기준: 해당 월 첫날 봇의 스냅샷이 존재하고 그날이 오늘이 아닌 경우 사용, 아니면 initial_allocation
                bot_start_value = history.get('bot_daily', {}).get(month_start_key, {}).get(bot_name, {}).get('total_value', None)
                if (bot_start_value is None) or (month_start_key == today_key):
                    bot_start_value = float(bot_data.get('initial_allocation', 0))
                profit = bot_data['total_value'] - bot_start_value
                profit_rate = (profit / bot_start_value * 100) if bot_start_value > 0 else 0
                history['bot_monthly'][month_key][bot_name] = {
                    'start_value': bot_start_value,
                    'end_value': bot_data['total_value'],
                    'profit': profit,
                    'profit_rate': profit_rate
                }
            else:
                bot_month['end_value'] = bot_data['total_value']
                bot_month['profit'] = bot_month['end_value'] - bot_month['start_value']
                start_val = bot_month['start_value']
                bot_month['profit_rate'] = (bot_month['profit'] / start_val * 100) if start_val > 0 else 0
            # 월별 by year 복사
            history['bot_monthly_by_year'][year_only][month_key][bot_name] = history['bot_monthly'][month_key][bot_name]

            # 연도별 업데이트(봇)
            bot_year = history['bot_yearly'][year_key].get(bot_name, None)
            if bot_year is None:
                bot_start_value = history.get('bot_daily', {}).get(year_start_key, {}).get(bot_name, {}).get('total_value', None)
                if (bot_start_value is None) or (year_start_key == today_key):
                    bot_start_value = float(bot_data.get('initial_allocation', 0))
                profit = bot_data['total_value'] - bot_start_value
                profit_rate = (profit / bot_start_value * 100) if bot_start_value > 0 else 0
                history['bot_yearly'][year_key][bot_name] = {
                    'start_value': bot_start_value,
                    'end_value': bot_data['total_value'],
                    'profit': profit,
                    'profit_rate': profit_rate
                }
            else:
                bot_year['end_value'] = bot_data['total_value']
                bot_year['profit'] = bot_year['end_value'] - bot_year['start_value']
                start_val = bot_year['start_value']
                bot_year['profit_rate'] = (bot_year['profit'] / start_val * 100) if start_val > 0 else 0
        
        self.save_profit_history(history)
    
    def update_portfolio_config(self, current_value, current_profit, bot_profits, portfolio_periods, bot_periods):
        """portfolio_config.json을 업데이트합니다."""
        try:
            config = self.load_config()
            if not config:
                return
            
            current_date = datetime.now()
            
            # 전체 성과 업데이트
            if 'performance' not in config:
                config['performance'] = {}
            
            config['performance']['total_value'] = current_value
            config['performance']['total_profit'] = current_profit
            config['performance']['total_profit_rate'] = (current_profit / config.get('initial_investment', 1) * 100) if config.get('initial_investment', 0) > 0 else 0
            config['performance']['last_updated'] = current_date.strftime("%Y-%m-%d %H:%M:%S")
            # 기간별 수익 반영 (주간 제거)
            config['performance']['periods'] = {
                'daily': portfolio_periods.get('today', {}),
                'monthly': portfolio_periods.get('month', {}),
                'yearly': portfolio_periods.get('year', {}),
                'total': portfolio_periods.get('total', {})
            }
            
            # 봇별 수익 업데이트
            if 'bot_profits' not in config:
                config['bot_profits'] = {}
            
            for bot_name, bot_data in bot_profits.items():
                if bot_name not in config['bot_profits']:
                    config['bot_profits'][bot_name] = {
                        'total_profit': 0,
                        'total_profit_rate': 0,
                        'monthly_profits': {},
                        'yearly_profits': {},
                        'last_updated': ''
                    }
                
                current_month = current_date.strftime("%Y-%m")
                current_year = current_date.strftime("%Y")
                
                # 봇별 수익 업데이트
                config['bot_profits'][bot_name]['total_profit'] = bot_data['total_profit']
                config['bot_profits'][bot_name]['total_profit_rate'] = bot_data['profit_rate']
                config['bot_profits'][bot_name]['last_updated'] = current_date.strftime("%Y-%m-%d %H:%M:%S")
                # 봇별 기간별 수익 반영 (주간 제거)
                config['bot_profits'][bot_name]['periods'] = {
                    'daily': bot_periods.get(bot_name, {}).get('today', {}),
                    'monthly': bot_periods.get(bot_name, {}).get('month', {}),
                    'yearly': bot_periods.get(bot_name, {}).get('year', {}),
                    'total': bot_periods.get(bot_name, {}).get('total', {})
                }
                
                # 월별 수익 업데이트
                if current_month not in config['bot_profits'][bot_name]['monthly_profits']:
                    config['bot_profits'][bot_name]['monthly_profits'][current_month] = {
                        'profit': 0,
                        'profit_rate': 0
                    }
                month_info = bot_periods.get(bot_name, {}).get('month', {})
                config['bot_profits'][bot_name]['monthly_profits'][current_month]['profit'] = month_info.get('profit', 0)
                config['bot_profits'][bot_name]['monthly_profits'][current_month]['profit_rate'] = month_info.get('profit_rate', 0)
                
                # 연별 수익 업데이트
                if current_year not in config['bot_profits'][bot_name]['yearly_profits']:
                    config['bot_profits'][bot_name]['yearly_profits'][current_year] = {
                        'profit': 0,
                        'profit_rate': 0
                    }
                year_info = bot_periods.get(bot_name, {}).get('year', {})
                config['bot_profits'][bot_name]['yearly_profits'][current_year]['profit'] = year_info.get('profit', 0)
                config['bot_profits'][bot_name]['yearly_profits'][current_year]['profit_rate'] = year_info.get('profit_rate', 0)
            
            self.save_config(config)
            
        except Exception as e:
            print(f"포트폴리오 설정 업데이트 중 오류: {e}")

    def save_daily_summary_json(self, current_value, current_profit, portfolio_periods, bot_profits, bot_periods):
        """portfolio_daily_profit_summary.json 파일에 일일 요약을 저장합니다."""
        try:
            config = self.load_config() or {}
            initial_investment = float(config.get('initial_investment', 0))
            output = {
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'performance': {
                    'total_value': current_value,
                    'total_profit': current_profit,
                    'total_profit_rate': (current_profit / initial_investment * 100) if initial_investment > 0 else 0,
                    'periods': {
                        'daily': portfolio_periods.get('today', {}),
                        'weekly': portfolio_periods.get('week', {}),
                        'monthly': portfolio_periods.get('month', {}),
                        'yearly': portfolio_periods.get('year', {}),
                        'total': portfolio_periods.get('total', {})
                    }
                },
                'bots': {}
            }

            for bot_name, bot_data in bot_profits.items():
                output['bots'][bot_name] = {
                    'total_value': bot_data.get('total_value', 0),
                    'total_profit': bot_data.get('total_profit', 0),
                    'profit_rate': bot_data.get('profit_rate', 0),
                    'initial_allocation': bot_data.get('initial_allocation', 0),
                    'periods': {
                        'daily': bot_periods.get(bot_name, {}).get('today', {}),
                        'weekly': bot_periods.get(bot_name, {}).get('week', {}),
                        'monthly': bot_periods.get(bot_name, {}).get('month', {}),
                        'yearly': bot_periods.get(bot_name, {}).get('year', {}),
                        'total': bot_periods.get(bot_name, {}).get('total', {})
                    }
                }

            with open(self.daily_summary_file, 'w', encoding='utf-8') as f:
                json.dump(output, f, ensure_ascii=False, indent=4)

        except Exception as e:
            print(f"일일 요약 저장 실패: {e}")
    
    def format_currency(self, amount):
        """통화 형식으로 포맷합니다."""
        return f"{amount:,.0f}원"
    
    def format_percentage(self, rate):
        """퍼센트 형식으로 포맷합니다."""
        return f"{rate:+.2f}%"
    
    def create_summary_message(self, portfolio_periods, bot_periods, current_value, current_profit, bot_profits):
        """요약 메시지를 생성합니다."""
        current_date = datetime.now()
        
        message = f" 일일 수익 현황 ({current_date.strftime('%Y-%m-%d %H:%M:%S')})\n"
        message += "=" * 37 + "\n\n"
        
        # 전체 포트폴리오 수익
        message += f"🎯 전체 포트폴리오\n"
        message += f"   총 평가금액: {self.format_currency(current_value)}\n"
        message += f"   총 수익금: {self.format_currency(portfolio_periods['total']['profit'])}\n"
        message += f"   총 수익률: {self.format_percentage(portfolio_periods['total']['profit_rate'])}\n\n"
        
        # 기간별 수익 (주간 제거)
        message += f"💰 오늘의 수익: {self.format_currency(portfolio_periods['today']['profit'])} ({self.format_percentage(portfolio_periods['today']['profit_rate'])})\n"
        message += f"📊 이번 달 수익: {self.format_currency(portfolio_periods['month']['profit'])} ({self.format_percentage(portfolio_periods['month']['profit_rate'])})\n"
        message += f"📈 올해 수익: {self.format_currency(portfolio_periods['year']['profit'])} ({self.format_percentage(portfolio_periods['year']['profit_rate'])})\n\n"
        
        # 봇별 수익
        message += f"🤖 봇별 수익 현황\n"
        message += "-" * 40 + "\n"
        
        for bot_name, bot_data in bot_profits.items():
            if bot_name in bot_periods:
                bot_today = bot_periods[bot_name]['today']
                bot_month = bot_periods[bot_name]['month']
                bot_year = bot_periods[bot_name]['year']
                bot_total = bot_periods[bot_name]['total']
                
                message += f"📊 {bot_name}\n"
                message += f"   오늘 수익: {self.format_currency(bot_today['profit'])} ({self.format_percentage(bot_today['profit_rate'])})\n"
                message += f"   월간 수익: {self.format_currency(bot_month['profit'])} ({self.format_percentage(bot_month['profit_rate'])})\n"
                message += f"   연간 수익: {self.format_currency(bot_year['profit'])} ({self.format_percentage(bot_year['profit_rate'])})\n"
                message += f"   총 수익: {self.format_currency(bot_total['profit'])} ({self.format_percentage(bot_total['profit_rate'])})\n"
                message += f"   평가금액: {self.format_currency(bot_data['current_stock_value'])}\n\n"
        
        return message
    
    def run_daily_summary(self):
        """일일 수익 요약을 실행합니다."""
        try:
            print("일일 수익 요약 시작...")
            
            # 현재 포트폴리오 가치 계산
            current_value, current_profit, total_investment = self.get_current_portfolio_value()
            
            if current_value == 0:
                print("포트폴리오 가치를 계산할 수 없습니다.")
                return
            
            # 봇별 수익 계산
            bot_profits = self.get_bot_profits()
            
            # 기간별 수익 계산
            portfolio_periods, bot_periods = self.calculate_period_profits(current_value, current_profit, bot_profits)
            
            # 수익 이력 업데이트
            self.update_profit_history(current_value, current_profit, bot_profits)
            
            # portfolio_daily_profit_summary.json 저장
            self.save_daily_summary_json(current_value, current_profit, portfolio_periods, bot_profits, bot_periods)
            
            # 요약 메시지 생성
            summary_message = self.create_summary_message(portfolio_periods, bot_periods, current_value, current_profit, bot_profits)
            
            # 텔레그램 전송
            try:
                telegram.send(summary_message)
                print("일일 수익 요약 텔레그램 전송 완료")
            except Exception as e:
                print(f"텔레그램 전송 실패: {e}")
            
            print("일일 수익 요약 완료")
            
        except Exception as e:
            print(f"일일 수익 요약 중 오류 발생: {e}")

def main():
    """메인 실행 함수"""
    # 주말 가드: 토(5)/일(6)에는 실행하지 않고 즉시 종료 (텔레그램 전송 없음)
    current_weekday = datetime.now().weekday()
    if current_weekday >= 5:
        print("주말(토/일)에는 일일 수익 요약을 실행하지 않습니다.")
        return

    summary = DailyProfitSummary()
    summary.run_daily_summary()

if __name__ == "__main__":
    main()
