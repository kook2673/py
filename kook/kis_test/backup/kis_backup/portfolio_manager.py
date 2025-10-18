import json
import os
import sys
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)
import telegram_sender as telegram
from datetime import datetime, timedelta

class PortfolioManager:
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_file = os.path.join(self.script_dir, "portfolio_config.json")
        self.config = self.load_config()
    
    def load_config(self):
        """설정 파일을 로드합니다."""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"설정 파일을 찾을 수 없습니다: {self.config_file}")
            print("portfolio_config.json 파일이 필요합니다.")
            raise FileNotFoundError(f"설정 파일이 없습니다: {self.config_file}")
        except json.JSONDecodeError as e:
            print(f"설정 파일 형식이 잘못되었습니다: {e}")
            print("portfolio_config.json 파일을 확인해주세요.")
            raise json.JSONDecodeError(f"설정 파일 형식 오류: {e}")
        except Exception as e:
            print(f"설정 파일 로드 중 오류 발생: {e}")
            raise Exception(f"설정 파일 로드 실패: {e}")
    
    def save_config(self, config=None):
        """설정을 파일에 저장합니다."""
        try:
            if config is None:
                config = self.config
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            self.config = config
        except PermissionError:
            print(f"파일 저장 권한이 없습니다: {self.config_file}")
            raise PermissionError(f"파일 저장 권한 없음: {self.config_file}")
        except Exception as e:
            print(f"설정 파일 저장 중 오류 발생: {e}")
            raise Exception(f"설정 파일 저장 실패: {e}")
    
    def get_initial_investment(self):
        """최초 투자금액을 반환합니다."""
        return self.config.get("initial_investment", 15000000)
    
    def get_bot_allocation(self, bot_name):
        """특정 봇의 할당 비율을 반환합니다."""
        return self.config.get("bots", {}).get(bot_name, {}).get("allocation_rate", 0.5)
    
    def get_bot_investment_amount(self, bot_name):
        """특정 봇의 투자 금액을 계산합니다."""
        initial_investment = self.get_initial_investment()
        allocation_rate = self.get_bot_allocation(bot_name)
        return initial_investment * allocation_rate
    
    def update_dividend_income(self, amount):
        """배당금을 업데이트합니다."""
        self.config["dividend_income"] += amount
        self.config["total_dividend_income"] += amount
        self.config["performance"]["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save_config()
    
    def update_performance(self, total_value, total_profit):
        """성과를 업데이트합니다."""
        initial_investment = self.get_initial_investment()
        self.config["performance"]["total_value"] = total_value
        self.config["performance"]["total_profit"] = total_profit
        self.config["performance"]["total_profit_rate"] = (total_profit / initial_investment * 100) if initial_investment > 0 else 0
        self.config["performance"]["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save_config()
    
    def get_portfolio_summary(self):
        """포트폴리오 요약 정보를 반환합니다."""
        return {
            "portfolio_name": self.config.get("portfolio_name", "자동매매 포트폴리오"),
            "initial_investment": self.get_initial_investment(),
            "dividend_income": self.config.get("dividend_income", 0),
            "total_dividend_income": self.config.get("total_dividend_income", 0),
            "investment_date": self.config.get("investment_date", ""),
            "performance": self.config.get("performance", {}),
            "bots": self.config.get("bots", {})
        }
    
    def update_bot_profit(self, bot_name, profit_amount, profit_rate):
        """특정 봇의 수익을 업데이트합니다."""
        try:
            if "bot_profits" not in self.config:
                self.config["bot_profits"] = {}
            
            if bot_name not in self.config["bot_profits"]:
                self.config["bot_profits"][bot_name] = {
                    "total_profit": 0,
                    "total_profit_rate": 0,
                    "monthly_profits": {},
                    "yearly_profits": {},
                    "last_updated": ""
                }
            
            current_date = datetime.now()
            current_month = current_date.strftime("%Y-%m")
            current_year = current_date.strftime("%Y")
            
            # 봇별 수익 업데이트
            self.config["bot_profits"][bot_name]["total_profit"] += profit_amount
            self.config["bot_profits"][bot_name]["total_profit_rate"] = profit_rate
            self.config["bot_profits"][bot_name]["last_updated"] = current_date.strftime("%Y-%m-%d %H:%M:%S")
            
            # 월별 수익 업데이트
            if current_month not in self.config["bot_profits"][bot_name]["monthly_profits"]:
                self.config["bot_profits"][bot_name]["monthly_profits"][current_month] = {
                    "profit": 0,
                    "profit_rate": 0
                }
            self.config["bot_profits"][bot_name]["monthly_profits"][current_month]["profit"] += profit_amount
            
            # 연별 수익 업데이트
            if current_year not in self.config["bot_profits"][bot_name]["yearly_profits"]:
                self.config["bot_profits"][bot_name]["yearly_profits"][current_year] = {
                    "profit": 0,
                    "profit_rate": 0
                }
            self.config["bot_profits"][bot_name]["yearly_profits"][current_year]["profit"] += profit_amount
            
            self.save_config()
        except Exception as e:
            print(f"봇 수익 업데이트 중 오류 발생: {e}")
            raise Exception(f"봇 수익 업데이트 실패: {e}")
    
    def send_daily_profit_report(self):
        """하루에 한번 수익률 현황을 텔레그램으로 전송합니다."""
        try:
            summary = self.get_portfolio_summary()
            performance = summary["performance"]
            
            # 마지막 전송 날짜 확인
            last_sent_date = self.config.get("last_daily_report_date", "")
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            if last_sent_date == current_date:
                return  # 이미 오늘 전송했으면 중복 전송 방지
            
            message = f"📊 일일 포트폴리오 현황 ({current_date})\n\n"
            message += f"💰 총 평가금액: {format(performance['total_value'], ',')}원\n"
            message += f"📈 총 수익금: {format(performance['total_profit'], ',')}원\n"
            message += f"📊 수익률: {performance['total_profit_rate']:.2f}%\n"
            message += f"💵 배당금: {format(summary['dividend_income'], ',')}원\n\n"
            
            # 봇별 수익 현황
            if "bot_profits" in self.config:
                message += "🤖 봇별 수익 현황:\n"
                for bot_name, bot_profit in self.config["bot_profits"].items():
                    message += f"• {bot_name}: {format(bot_profit['total_profit'], ',')}원 ({bot_profit['total_profit_rate']:.2f}%)\n"
            
            telegram.send(message)
            self.config["last_daily_report_date"] = current_date
            self.save_config()
        except Exception as e:
            print(f"일일 수익률 보고서 전송 실패: {e}")
            raise Exception(f"일일 보고서 전송 실패: {e}")
    
    def send_monthly_profit_report(self):
        """한달에 한번 월별 수익률을 텔레그램으로 전송합니다."""
        try:
            current_date = datetime.now()
            current_month = current_date.strftime("%Y-%m")
            
            # 마지막 월간 전송 날짜 확인
            last_sent_month = self.config.get("last_monthly_report_date", "")
            
            if last_sent_month == current_month:
                return  # 이미 이번 달 전송했으면 중복 전송 방지
            
            message = f"📅 월간 포트폴리오 현황 ({current_month})\n\n"
            
            if "bot_profits" in self.config:
                for bot_name, bot_profit in self.config["bot_profits"].items():
                    if current_month in bot_profit["monthly_profits"]:
                        monthly_data = bot_profit["monthly_profits"][current_month]
                        message += f"🤖 {bot_name}:\n"
                        message += f"   월 수익금: {format(monthly_data['profit'], ',')}원\n"
                        message += f"   월 수익률: {monthly_data['profit_rate']:.2f}%\n\n"
            
            # 세금 계산을 위한 연간 수익금 요약
            total_yearly_profit = 0
            for bot_name, bot_profit in self.config.get("bot_profits", {}).items():
                if current_date.strftime("%Y") in bot_profit["yearly_profits"]:
                    total_yearly_profit += bot_profit["yearly_profits"][current_date.strftime("%Y")]["profit"]
            
            message += f"💰 연간 총 수익금 (세금계산용): {format(total_yearly_profit, ',')}원\n"
            
            telegram.send(message)
            self.config["last_monthly_report_date"] = current_month
            self.save_config()
        except Exception as e:
            print(f"월간 수익률 보고서 전송 실패: {e}")
            raise Exception(f"월간 보고서 전송 실패: {e}")
    
    def send_yearly_profit_report(self):
        """1년에 한번 연간 수익률을 텔레그램으로 전송합니다."""
        try:
            current_date = datetime.now()
            current_year = current_date.strftime("%Y")
            
            # 마지막 연간 전송 날짜 확인
            last_sent_year = self.config.get("last_yearly_report_date", "")
            
            if last_sent_year == current_year:
                return  # 이미 이번 년도 전송했으면 중복 전송 방지
            
            message = f"📊 연간 포트폴리오 현황 ({current_year})\n\n"
            
            if "bot_profits" in self.config:
                for bot_name, bot_profit in self.config["bot_profits"].items():
                    if current_year in bot_profit["yearly_profits"]:
                        yearly_data = bot_profit["yearly_profits"][current_year]
                        message += f"🤖 {bot_name}:\n"
                        message += f"   연 수익금: {format(yearly_data['profit'], ',')}원\n"
                        message += f"   연 수익률: {yearly_data['profit_rate']:.2f}%\n\n"
            
            # 세금 계산 정보
            total_yearly_profit = 0
            for bot_name, bot_profit in self.config.get("bot_profits", {}).items():
                if current_year in bot_profit["yearly_profits"]:
                    total_yearly_profit += bot_profit["yearly_profits"][current_year]["profit"]
            
            message += f"💰 연간 총 수익금 (세금계산용): {format(total_yearly_profit, ',')}원\n"
            message += f"📋 세금 신고 시 참고하세요!"
            
            telegram.send(message)
            self.config["last_yearly_report_date"] = current_year
            self.save_config()
        except Exception as e:
            print(f"연간 수익률 보고서 전송 실패: {e}")
            raise Exception(f"연간 보고서 전송 실패: {e}")
    
    def send_telegram_message(self, message):
        """일반 텔레그램 메시지를 전송합니다."""
        try:
            telegram.send(message)
            print(f"텔레그램 메시지 전송 완료: {message[:50]}...")
        except Exception as e:
            print(f"텔레그램 메시지 전송 실패: {e}")
            raise Exception(f"텔레그램 메시지 전송 실패: {e}")
    
    def get_portfolio_summary(self):
        """포트폴리오 요약 정보 가져오기"""
        try:
            summary = {
                'initial_investment': self.config.get('initial_investment', 0),
                'investment_date': self.config.get('investment_date', ''),
                'dividend_income': self.config.get('dividend_income', 0),
                'total_dividend_income': self.config.get('total_dividend_income', 0),
                'portfolio_name': self.config.get('portfolio_name', '자동매매 포트폴리오'),
                'bot_profits': self.config.get('bot_profits', {}),
                'bots': self.config.get('bots', {}),
                'performance': {}
            }
            
            # 총 수익 계산
            total_profit = 0
            total_value = summary['initial_investment']
            
            # 봇별 수익 계산
            for bot_name, bot_data in summary['bot_profits'].items():
                bot_profit = bot_data.get('total_profit', 0)
                total_profit += bot_profit
                total_value += bot_profit
            
            # 배당금 추가
            total_value += summary['dividend_income']
            total_profit += summary['dividend_income']
            
            # 수익률 계산
            if summary['initial_investment'] > 0:
                total_profit_rate = (total_profit / summary['initial_investment']) * 100
            else:
                total_profit_rate = 0
            
            summary['performance'] = {
                'total_profit': total_profit,
                'total_value': total_value,
                'total_profit_rate': total_profit_rate,
                'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            return summary
            
        except Exception as e:
            print(f"포트폴리오 요약 정보 가져오기 실패: {e}")
            return {
                'initial_investment': 0,
                'investment_date': '',
                'dividend_income': 0,
                'total_dividend_income': 0,
                'portfolio_name': '자동매매 포트폴리오',
                'bot_profits': {},
                'bots': {},
                'performance': {
                    'total_profit': 0,
                    'total_value': 0,
                    'total_profit_rate': 0,
                    'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            }

# 전역 인스턴스 생성
portfolio_manager = PortfolioManager() 