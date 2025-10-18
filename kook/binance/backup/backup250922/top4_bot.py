'''
########################################################################################################################
#   Live Top4 Strategy Trading Bot for Binance Futures (By kook) - 4가지 전략 라이브 트레이딩 봇
#
#   === 개요 ===
#   top4_strategy_system.py의 4가지 전략을 사용하여 실시간 트레이딩을 수행합니다.
#   ml_bot.py의 구조를 참고하여 4가지 전략 기반으로 개선된 버전입니다.
#
#   === 사용 전략 ===
#   1. 모멘텀 전략 (20일 모멘텀)
#   2. 스캘핑 전략 (5시간 변동성)
#   3. MACD 전략 (12,26,9)
#   4. 이동평균 전략 (20,50)
#
#   === 작동 원리 ===
 #   1.  **실시간 데이터 수집**: 5분봉 데이터 수집 및 전략별 신호 생성
#   2.  **4가지 전략 실행**: 각 전략별로 매수/매도/보유 신호 생성
#   3.  **자산 배분**: 전체 자산의 50%를 4등분하여 각 전략에 배분
#   4.  **거래 실행**: 전략별 신호에 따라 롱/숏 포지션 진입/청산
#   5.  **리스크 관리**: ATR 기반 동적 손절매 적용
#   6.  **상태 저장**: 포지션 정보를 JSON 파일에 저장
#
 #   === 실행 주기 ===
 #   - crontab: "*/5 * * * *" (5분마다 실행)
#
#   === 의존성 ===
#   - myBinance.py: 바이낸스 API 연동
#   - telegram_sender.py: 텔레그램 알림
#
########################################################################################################################
'''

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

import ccxt
import pandas as pd
import numpy as np
import json
import datetime as dt
import logging
import traceback
import time
import gc
import psutil
import myBinance
import ende_key
import my_key
import telegram_sender as line_alert

# ========================= 전역 설정 변수 =========================
DEFAULT_LEVERAGE = 5  # 5배 레버리지
INVESTMENT_RATIO = 0.04  # 투자 비율 (자산의 50%)
COIN_CHARGE = 0.0005  # 수수료 설정 (0.06%)
ACTIVE_COINS = ['BTC/USDT']

# 포지션 사이즈 관리 (고정)

# ========================= 로깅 설정 =========================
def setup_logging():
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    today = dt.datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(log_dir, f"top4_bot_{today}.log")
    trade_log_file = os.path.join(log_dir, "top4_bot_trades.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    trade_logger = logging.getLogger('trade_logger')
    trade_logger.setLevel(logging.INFO)
    trade_logger.handlers = []
    trade_logger.propagate = False
    trade_logger.addHandler(logging.FileHandler(trade_log_file, encoding='utf-8'))
    
    logging.getLogger('ccxt').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    return logging.getLogger(__name__), trade_logger

logger, trade_logger = setup_logging()

# ========================= 메모리 관리 유틸리티 =========================
def cleanup_memory():
    """메모리 정리 함수"""
    try:
        # 0세대, 1세대, 2세대 가비지 컬렉션 모두 실행
        collected = gc.collect()
        collected += gc.collect()  # 두 번 실행으로 확실한 정리
        
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        # 메모리 사용량이 500MB 이상이면 경고
        if memory_mb > 500:
            logger.warning(f"⚠️ 높은 메모리 사용량: {memory_mb:.2f} MB")
        
        logger.info(f"메모리 정리 완료: {collected}개 객체 수집, 현재 사용량: {memory_mb:.2f} MB")
        return memory_mb
    except Exception as e:
        logger.warning(f"메모리 정리 중 오류: {e}")
        return 0

def cleanup_dataframes(*dataframes):
    """데이터프레임들 명시적 삭제"""
    for df in dataframes:
        if df is not None:
            try:
                # 데이터프레임의 메모리 사용량 확인
                if hasattr(df, 'memory_usage'):
                    memory_usage = df.memory_usage(deep=True).sum() / 1024 / 1024
                    logger.debug(f"삭제할 데이터프레임 메모리: {memory_usage:.2f} MB")
                
                # 데이터프레임 완전 삭제
                df.drop(df.index, inplace=True)
                del df
            except Exception as e:
                logger.debug(f"데이터프레임 삭제 중 오류: {e}")
            finally:
                # 강제 가비지 컬렉션
                gc.collect()

def cleanup_variables(**kwargs):
    """변수들 명시적 삭제"""
    for var_name, var_value in kwargs.items():
        if var_value is not None:
            try:
                del var_value
            except:
                pass

# ========================= 일일 결과보고 유틸리티 =========================
def generate_daily_report(bot, dic, current_balance, coin_ticker):
    """일일 결과보고 생성"""
    try:
        # 현재 시간
        now = dt.datetime.now()
        report_time = now.strftime("%Y-%m-%d %H:%M:%S")
        
        # 전략별 포지션 상태 정리
        position_summary = []
        total_profit = 0
        active_positions = 0
        
        for strategy_name in bot.strategy_positions:
            position_size = bot.strategy_positions[strategy_name]
            entry_price = bot.strategy_entry_prices[strategy_name]
            capital = bot.strategy_capitals[strategy_name]
            
            if position_size > 0:
                active_positions += 1
                # 현재 가격으로 수익 계산
                current_price = dic.get('current_price', 0)
                if current_price > 0 and entry_price > 0:
                    unrealized_profit = (current_price - entry_price) * position_size
                    unrealized_profit_rate = (current_price - entry_price) / entry_price * 100
                    total_profit += unrealized_profit
                else:
                    unrealized_profit = 0
                    unrealized_profit_rate = 0
                
                position_summary.append(f"📊 {strategy_name.upper()}: {position_size:.4f} BTC (진입가: {entry_price:.2f})")
            else:
                position_summary.append(f"💤 {strategy_name.upper()}: 포지션 없음 (자본: {capital:.2f} USDT)")
        
        # 전체 수익률 계산
        start_money = dic.get('start_money', current_balance)
        total_return_rate = ((current_balance - start_money) / start_money * 100) if start_money > 0 else 0
        
        # 거래 기록에서 당일 거래 통계
        today_trades = []
        try:
            with open(os.path.join(os.path.dirname(__file__), "logs", "top4_bot_trades.log"), 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        trade_data = json.loads(line.strip())
                        trade_time = dt.datetime.fromisoformat(trade_data['timestamp'].replace('Z', '+00:00'))
                        if trade_time.date() == now.date():
                            today_trades.append(trade_data)
        except:
            pass
        
        # 당일 거래 통계
        buy_count = len([t for t in today_trades if t['action'] == 'BUY_LONG'])
        sell_count = len([t for t in today_trades if t['action'] == 'SELL_LONG'])
        total_profit_today = sum([t.get('profit_usdt', 0) for t in today_trades])
        
        # 보고서 생성
        report = f"""
🤖 **일일 결과보고** - {report_time}

📈 **전체 현황**
• 현재 잔고: {current_balance:.2f} USDT
• 시작 잔고: {start_money:.2f} USDT
• 총 수익률: {total_return_rate:.2f}%
• 활성 포지션: {active_positions}/4개

📊 **전략별 포지션 상태**
{chr(10).join(position_summary)}

📅 **당일 거래 현황**
• 매수 거래: {buy_count}회
• 매도 거래: {sell_count}회
• 당일 실현 수익: {total_profit_today:.2f} USDT

💰 **미실현 수익**
• 총 미실현 수익: {total_profit:.2f} USDT
• 미실현 수익률: {(total_profit/start_money*100):.2f}%

⏰ **다음 보고**: 내일 {now.strftime('%H:%M')}
        """
        
        return report.strip()
        
    except Exception as e:
        logger.error(f"일일 보고서 생성 실패: {e}")
        return f"❌ 일일 보고서 생성 실패: {e}"

def should_send_daily_report():
    """일일 보고서를 보낼 시점인지 확인"""
    try:
        report_file = os.path.join(os.path.dirname(__file__), "logs", "last_daily_report.json")
        
        # 파일이 없으면 새로 생성
        if not os.path.exists(report_file):
            last_report_time = dt.datetime.now() - dt.timedelta(days=1)  # 하루 전으로 설정
        else:
            with open(report_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                last_report_time = dt.datetime.fromisoformat(data['last_report_time'])
        
        # 현재 시간과 비교
        now = dt.datetime.now()
        time_diff = now - last_report_time
        
        # 24시간이 지났으면 보고서 전송
        return time_diff.total_seconds() >= 24 * 3600
        
    except Exception as e:
        logger.warning(f"일일 보고서 시점 확인 실패: {e}")
        return False

def save_daily_report_time():
    """일일 보고서 전송 시간 저장"""
    try:
        report_file = os.path.join(os.path.dirname(__file__), "logs", "last_daily_report.json")
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        
        data = {
            'last_report_time': dt.datetime.now().isoformat()
        }
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            
    except Exception as e:
        logger.warning(f"일일 보고서 시간 저장 실패: {e}")

# ========================= 로깅 유틸리티 =========================
def log_trade_action(action_type, coin_ticker, strategy_name, position_side, price, quantity, reason="", profit=0, profit_rate=0):
    try:
        # 수익/손실에 따른 색상 버튼 생성
        if profit > 0:
            profit_button = "🟢"  # 초록색 동그라미 (수익)
        elif profit < 0:
            profit_button = "🔴"  # 빨간색 동그라미 (손실)
        else:
            profit_button = "⚪"  # 흰색 동그라미 (수익/손실 없음)
        
        trade_record = {
            "timestamp": dt.datetime.now().isoformat(), 
            "profit_button": profit_button,
            "action": action_type, 
            "coin": coin_ticker,
            "strategy": strategy_name,
            "position": position_side, 
            "price": round(price, 2), 
            "quantity": round(quantity, 3),
            "reason": reason, 
            "profit_usdt": round(profit, 2) if profit != 0 else 0,
            "profit_rate": round(profit_rate, 2) if profit_rate != 0 else 0
        }
        trade_logger.info(json.dumps(trade_record, ensure_ascii=False))
    except Exception as e:
        logger.error(f"거래 기록 로깅 실패: {e}")

def log_error(error_msg, error_detail=None):
    logger.error(f"오류: {error_msg}")
    if error_detail:
        logger.error(f"상세: {error_detail}")

# ========================= 4가지 전략 클래스 =========================
class Top4StrategyBot:
    """4가지 전략을 사용하는 라이브 트레이딩 봇"""
    
    def __init__(self, initial_balance: float = 10000, leverage: int = 5, position_data: dict = None):
        self.initial_balance = initial_balance
        self.leverage = leverage
        self.trading_fee = COIN_CHARGE
        
        # 전략별 자본 (전체 자산의 50%를 4등분)
        self.strategy_capitals = {
            'momentum': initial_balance * INVESTMENT_RATIO / 4,
            'scalping': initial_balance * INVESTMENT_RATIO / 4,
            'macd': initial_balance * INVESTMENT_RATIO / 4,
            'moving_average': initial_balance * INVESTMENT_RATIO / 4
        }
        
        # 전략별 포지션 (JSON 파일에서 로드)
        self.strategy_positions = {
            'momentum': 0.0,
            'scalping': 0.0,
            'macd': 0.0,
            'moving_average': 0.0
        }
        
        # 기존 포지션 데이터가 있으면 로드
        if position_data:
            for strategy_name in self.strategy_positions:
                if strategy_name in position_data:
                    # 타입 안전성을 위해 float로 변환
                    position_size = float(position_data[strategy_name].get('position_size', 0.0))
                    self.strategy_positions[strategy_name] = position_size
                    logger.info(f"{strategy_name} 전략 포지션 로드: {self.strategy_positions[strategy_name]}")
        
        # 전략별 거래 기록
        self.strategy_trades = {
            'momentum': [],
            'scalping': [],
            'macd': [],
            'moving_average': []
        }
        
        # 전략별 진입가 (JSON 파일에서 로드)
        self.strategy_entry_prices = {
            'momentum': 0.0,
            'scalping': 0.0,
            'macd': 0.0,
            'moving_average': 0.0
        }
        
        # 기존 진입가 데이터가 있으면 로드
        if position_data:
            for strategy_name in self.strategy_entry_prices:
                if strategy_name in position_data:
                    # 타입 안전성을 위해 float로 변환
                    entry_price = float(position_data[strategy_name].get('entry_price', 0.0))
                    self.strategy_entry_prices[strategy_name] = entry_price
                    if self.strategy_entry_prices[strategy_name] > 0:
                        logger.info(f"{strategy_name} 전략 진입가 로드: {self.strategy_entry_prices[strategy_name]}")
    
    def momentum_strategy(self, data: pd.DataFrame, i: int) -> int:
        """모멘텀 전략 (20일 모멘텀)"""
        if i < 20:
            return 0
            
        # 20일 모멘텀 계산
        current_price = data['close'].iloc[i]
        past_price = data['close'].iloc[i-20]
        momentum = (current_price - past_price) / past_price
        
        # 모멘텀 > 0.02이면 매수, < -0.02이면 매도
        if momentum > 0.02:
            return 1  # 매수
        elif momentum < -0.02:
            return -1  # 매도
        else:
            return 0  # 보유
    
    def scalping_strategy(self, data: pd.DataFrame, i: int) -> int:
        """스캘핑 전략 (5시간 변동성)"""
        if i < 5:
            return 0
            
        # 5시간 변동성 계산
        recent_data = data['close'].iloc[i-5:i+1]
        volatility = recent_data.pct_change().std()
        
        # 현재 가격과 5시간 전 가격 비교
        current_price = data['close'].iloc[i]
        past_price = data['close'].iloc[i-5]
        price_change = (current_price - past_price) / past_price
        
        # 변동성이 높고 상승하면 매수, 하락하면 매도
        if volatility > 0.005 and price_change > 0.003:
            return 1  # 매수
        elif volatility > 0.005 and price_change < -0.003:
            return -1  # 매도
        else:
            return 0  # 보유
    
    def macd_strategy(self, data: pd.DataFrame, i: int) -> int:
        """MACD 전략 (12,26,9)"""
        if i < 26:
            return 0
            
        # MACD 계산
        ema12 = data['close'].ewm(span=12).mean()
        ema26 = data['close'].ewm(span=26).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9).mean()
        
        current_macd = macd_line.iloc[i]
        current_signal = signal_line.iloc[i]
        prev_macd = macd_line.iloc[i-1]
        prev_signal = signal_line.iloc[i-1]
        
        # MACD가 시그널을 상향돌파하면 매수
        if current_macd > current_signal and prev_macd <= prev_signal:
            return 1  # 매수
        # MACD가 시그널을 하향돌파하면 매도
        elif current_macd < current_signal and prev_macd >= prev_signal:
            return -1  # 매도
        else:
            return 0  # 보유
    
    def moving_average_strategy(self, data: pd.DataFrame, i: int) -> int:
        """이동평균 전략 (20,50)"""
        if i < 50:
            return 0
            
        # 단기(20)와 장기(50) 이동평균
        ma20 = data['close'].rolling(window=20).mean()
        ma50 = data['close'].rolling(window=50).mean()
        
        current_ma20 = ma20.iloc[i]
        current_ma50 = ma50.iloc[i]
        prev_ma20 = ma20.iloc[i-1]
        prev_ma50 = ma50.iloc[i-1]
        
        # 단기 이평이 장기 이평을 상향돌파하면 매수
        if current_ma20 > current_ma50 and prev_ma20 <= prev_ma50:
            return 1  # 매수
        # 단기 이평이 장기 이평을 하향돌파하면 매도
        elif current_ma20 < current_ma50 and prev_ma20 >= prev_ma50:
            return -1  # 매도
        else:
            return 0  # 보유
    
    def generate_signals(self, data: pd.DataFrame) -> dict:
        """4가지 전략으로 신호 생성"""
        signals = {}
        
        # 최근 데이터로 신호 생성
        i = len(data) - 1
        
        strategies = {
            'momentum': self.momentum_strategy,
            'scalping': self.scalping_strategy,
            'macd': self.macd_strategy,
            'moving_average': self.moving_average_strategy
        }
        
        for strategy_name, strategy_func in strategies.items():
            signals[strategy_name] = strategy_func(data, i)
        
        return signals
    
    def calculate_position_size(self, strategy_name: str, coin_price: float) -> float:
        """전략별 포지션 사이즈 계산"""
        current_capital = self.strategy_capitals[strategy_name]
        
        # 레버리지를 적용한 거래 금액 계산
        leveraged_value = current_capital * self.leverage
        fee = leveraged_value * self.trading_fee
        net_value = leveraged_value - fee
        position_size = net_value / coin_price
        
        return position_size
    
    def execute_trade(self, strategy_name: str, signal: int, coin_price: float, binanceX, coin_ticker: str):
        """거래 실행"""
        current_position = self.strategy_positions[strategy_name]
        current_capital = self.strategy_capitals[strategy_name]
        
        # 포지션 상태 확인 로그
        logger.info(f"{strategy_name} 전략 포지션 상태: {current_position}, 신호: {signal}")
        
        # 실제 바이낸스 잔고에서 포지션 확인 (안전장치)
        try:
            balance = binanceX.fetch_balance(params={"type": "future"})
            actual_position = 0.0
            
            # 롱 포지션 확인
            for posi in balance['info']['positions']:
                if posi['symbol'] == coin_ticker.replace('/', '') and posi['positionSide'] == 'LONG':
                    actual_position = float(posi['positionAmt'])
                    break
            
            # 실제 포지션과 봇 상태가 다르면 경고
            if abs(actual_position - current_position) > 0.001:
                logger.warning(f"{strategy_name} 전략 포지션 불일치! 봇: {current_position}, 실제 잔고: {actual_position}")
                
                # 사용자가 수동으로 포지션을 청산한 경우 (실제 잔고에 포지션이 0인데 봇은 포지션을 가지고 있음)
                if actual_position == 0 and current_position > 0:
                    logger.info(f"{strategy_name} 전략: 사용자 수동 청산 감지, 포지션 초기화")
                    self.strategy_positions[strategy_name] = 0.0
                    self.strategy_entry_prices[strategy_name] = 0.0
                    # 자본을 초기 자본으로 복원
                    self.strategy_capitals[strategy_name] = self.initial_balance * INVESTMENT_RATIO / 4
                    current_position = 0.0
                    logger.info(f"{strategy_name} 전략 포지션 초기화 완료, 자본 복원: {self.strategy_capitals[strategy_name]:.2f} USDT")
                    
                    # 텔레그램 알림
                    line_alert.SendMessage(f"⚠️ **{strategy_name.upper()} 전략 수동 청산 감지**\n- 포지션이 수동으로 청산되었습니다\n- 전략이 초기화되었습니다")
                else:
                    # 실제 포지션으로 동기화
                    self.strategy_positions[strategy_name] = actual_position
                    current_position = actual_position
                
        except Exception as e:
            logger.warning(f"실제 포지션 확인 실패: {e}")
        
        if signal == 1 and current_position == 0:  # 매수 (포지션이 없을 때만)
            # 추가 안전장치: 자본이 0이면 매수 불가
            if current_capital <= 0:
                logger.warning(f"{strategy_name} 전략: 자본 부족으로 매수 불가 (자본: {current_capital})")
                return
            try:
                position_size = self.calculate_position_size(strategy_name, coin_price)
                
                # 최소 주문 수량 확인
                minimum_amount = myBinance.GetMinimumAmount(binanceX, coin_ticker)
                if position_size < minimum_amount:
                    logger.warning(f"{strategy_name} 전략: 계산된 수량({position_size:.6f})이 최소 수량({minimum_amount:.6f})보다 작아 최소 수량으로 조정")
                    position_size = minimum_amount
                
                # 최소 수량 확인 로그
                logger.info(f"{strategy_name} 전략 매수 수량: {position_size:.6f} (최소: {minimum_amount:.6f})")
                
                # 롱 포지션 진입
                data = binanceX.create_order(coin_ticker, 'market', 'buy', position_size, None, {'positionSide': 'LONG'})
                entry_price = float(data.get('average', coin_price))
                
                # 포지션 정보 즉시 업데이트 (중복 매수 방지)
                self.strategy_positions[strategy_name] = position_size
                self.strategy_capitals[strategy_name] = 0  # 모든 자본을 사용
                self.strategy_entry_prices[strategy_name] = entry_price  # 진입가 업데이트
                
                # 포지션 업데이트 확인 로그
                logger.info(f"{strategy_name} 전략 포지션 업데이트 완료: {self.strategy_positions[strategy_name]}, 진입가: {entry_price}")
                
                # 거래 기록
                self.strategy_trades[strategy_name].append({
                    'timestamp': dt.datetime.now(),
                    'action': 'BUY',
                    'price': entry_price,
                    'quantity': position_size,
                    'leverage': self.leverage,
                    'strategy': strategy_name
                })
                
                log_trade_action('BUY_LONG', coin_ticker, strategy_name, 'long', entry_price, position_size, f"{strategy_name}_strategy")
                line_alert.SendMessage(f"🤖📈 {strategy_name.upper()} 전략 롱 진입\n- 코인: {coin_ticker}\n- 가격: {entry_price:.2f}\n- 수량: {position_size}")
                
                logger.info(f"{strategy_name} 전략 롱 포지션 진입: {entry_price:.2f}, 수량: {position_size}")
                
            except Exception as e:
                log_error(f"{strategy_name} 전략 롱 진입 실패: {e}", traceback.format_exc())
        
        elif signal == -1 and current_position > 0:  # 매도
            try:
                # 최소 주문 수량 확인
                minimum_amount = myBinance.GetMinimumAmount(binanceX, coin_ticker)
                if current_position < minimum_amount:
                    logger.warning(f"{strategy_name} 전략: 현재 포지션({current_position:.6f})이 최소 수량({minimum_amount:.6f})보다 작아 매도 불가")
                    return
                
                # 매도 수량 확인 로그
                logger.info(f"{strategy_name} 전략 매도 수량: {current_position:.6f} (최소: {minimum_amount:.6f})")
                
                # 롱 포지션 청산
                data = binanceX.create_order(coin_ticker, 'market', 'sell', current_position, None, {'positionSide': 'LONG'})
                exit_price = float(data.get('average', coin_price))
                
                # 수익/손실 계산 (진입가 사용)
                buy_price = self.strategy_entry_prices[strategy_name]
                if buy_price > 0:
                    profit = (exit_price - buy_price) * current_position * (1 - (self.trading_fee * 2))
                    profit_rate = (exit_price - buy_price) / buy_price * 100.0
                    
                    # 자본 업데이트
                    self.strategy_capitals[strategy_name] = current_capital + profit
                else:
                    profit = 0
                    profit_rate = 0
                    logger.warning(f"{strategy_name} 전략: 진입가 정보 없음, 수익 계산 불가")
                
                # 포지션 정보 즉시 업데이트 (중복 매수 방지)
                self.strategy_positions[strategy_name] = 0
                self.strategy_entry_prices[strategy_name] = 0  # 진입가 초기화
                
                # 포지션 업데이트 확인 로그
                logger.info(f"{strategy_name} 전략 포지션 업데이트 완료: {self.strategy_positions[strategy_name]}, 진입가 초기화")
                
                # 거래 기록
                self.strategy_trades[strategy_name].append({
                    'timestamp': dt.datetime.now(),
                    'action': 'SELL',
                    'price': exit_price,
                    'quantity': current_position,
                    'leverage': self.leverage,
                    'strategy': strategy_name,
                    'profit': profit,
                    'profit_rate': profit_rate
                })
                
                log_trade_action('SELL_LONG', coin_ticker, strategy_name, 'long', exit_price, current_position, f"{strategy_name}_strategy", profit, profit_rate)
                
                profit_emoji = "🟢" if profit > 0 else ("🔴" if profit < 0 else "⚪")
                line_alert.SendMessage(f"{profit_emoji} {strategy_name.upper()} 전략 롱 청산\n- 코인: {coin_ticker}\n- 청산가: {exit_price:.2f}\n- 수량: {current_position}\n- 수익: {profit:.2f} USDT ({profit_rate:.2f}%)")
                
                logger.info(f"{strategy_name} 전략 롱 포지션 청산: {exit_price:.2f}, 수익: {profit:.2f} USDT ({profit_rate:.2f}%)")
                
            except Exception as e:
                log_error(f"{strategy_name} 전략 롱 청산 실패: {e}", traceback.format_exc())
        
        # 포지션 상태 로그
        logger.info(f"{strategy_name} 전략 최종 포지션: {self.strategy_positions[strategy_name]}")
        
        # 거래 실행 여부 로그
        if signal == 1 and current_position == 0:
            logger.info(f"✅ {strategy_name} 전략: 매수 신호 감지, 거래 실행")
        elif signal == -1 and current_position > 0:
            logger.info(f"✅ {strategy_name} 전략: 매도 신호 감지, 거래 실행")
        elif signal == 1 and current_position > 0:
            logger.info(f"⚠️ {strategy_name} 전략: 매수 신호이지만 이미 포지션 보유 중 (거래 스킵)")
        elif signal == -1 and current_position == 0:
            logger.info(f"⚠️ {strategy_name} 전략: 매도 신호이지만 포지션 없음 (거래 스킵)")
        else:
            logger.info(f"ℹ️ {strategy_name} 전략: 보유 신호 (거래 없음)")

# ========================= 포지션 사이즈 관리 =========================

# ========================= 메인 실행 코드 =========================
if __name__ == "__main__":
    logger.info("=== Live Top4 Strategy Trading Bot 시작 ===")
    
    # 바이낸스 API 설정
    simpleEnDecrypt = myBinance.SimpleEnDecrypt(ende_key.ende_key)
    Binance_AccessKey = simpleEnDecrypt.decrypt(my_key.binance_access)
    Binance_ScretKey = simpleEnDecrypt.decrypt(my_key.binance_secret)
    
    binanceX = ccxt.binance(config={
        'apiKey': Binance_AccessKey, 
        'secret': Binance_ScretKey,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',
            'adjustForTimeDifference': True,
        }
    })

    # 봇 시작 시 서버 시간과 동기화
    logger.info("서버 시간과 동기화를 시도합니다...")
    try:
        binanceX.load_time_difference()
        original_offset = binanceX.options.get('timeDifference', 0)
        safety_margin = -1000
        final_offset = original_offset + safety_margin
        binanceX.options['timeDifference'] = final_offset
        logger.info(f"서버 시간 동기화 완료: 오프셋 {final_offset}ms")
    except Exception as e:
        logger.critical(f"시간 동기화 실패: {e}")
        sys.exit(1)

    # 설정파일 json로드
    info_file_path = os.path.join(os.path.dirname(__file__), "top4_bot.json")
    try:
        with open(info_file_path, 'r', encoding='utf-8') as f:
            dic = json.load(f)
        
        # 매 실행 시 실제 잔고를 가져와서 my_money 업데이트
        try:
            current_balance = binanceX.fetch_balance(params={"type": "future"})['USDT']['total']
            old_money = dic['my_money']
            dic['my_money'] = current_balance
            logger.info(f"잔고 업데이트: {old_money:.2f} USDT → {current_balance:.2f} USDT")
            time.sleep(0.1)
        except Exception as e:
            logger.warning(f"잔고 조회 실패, 기존 값 유지: {e}")
            
    except FileNotFoundError:
        logger.info("설정 파일이 없어 새로 생성합니다.")
        balance = binanceX.fetch_balance(params={"type": "future"})['USDT']['total']
        time.sleep(0.1)
        dic = {
            "start_money": balance, "my_money": balance,
            "coins": {
                "BTC/USDT": {
                    "momentum": {"position": 0, "entry_price": 0, "position_size": 0},
                    "scalping": {"position": 0, "entry_price": 0, "position_size": 0},
                    "macd": {"position": 0, "entry_price": 0, "position_size": 0},
                    "moving_average": {"position": 0, "entry_price": 0, "position_size": 0}
                }
            },
             "position_tracking": {
                 "consecutive_losses": 0,
                 "consecutive_wins": 0
             }
        }

    for Target_Coin_Ticker in ACTIVE_COINS:
        logger.info(f"=== {Target_Coin_Ticker} | Top4 Strategy Bot ===")
        
        Target_Coin_Symbol = Target_Coin_Ticker.replace("/", "")

        # 레버리지 설정
        try:
            leverage_result = binanceX.fapiPrivate_post_leverage({'symbol': Target_Coin_Symbol, 'leverage': DEFAULT_LEVERAGE})
            logger.info(f"{Target_Coin_Symbol} 레버리지 설정 성공: {DEFAULT_LEVERAGE}배")
        except Exception as e:
            try:
                leverage_result = binanceX.fapiprivate_post_leverage({'symbol': Target_Coin_Symbol, 'leverage': DEFAULT_LEVERAGE})
                logger.info(f"{Target_Coin_Symbol} 레버리지 설정 성공 (대체): {DEFAULT_LEVERAGE}배")
            except Exception as e2:
                error_msg = f"{Target_Coin_Symbol} 레버리지 설정 실패: {e2}"
                log_error(error_msg)
                continue

        # 데이터 수집 (최근 200개 캔들)
        df = myBinance.GetOhlcv(binanceX, Target_Coin_Ticker, '5m', 200)
        coin_price = df['close'].iloc[-1]
        
        # 현재 가격을 dic에 저장 (일일 보고서용)
        dic['current_price'] = coin_price
        
        # 메모리 사용량 모니터링
        initial_memory = cleanup_memory()
        
        # ATR 계산 (손절가 설정용)
        try:
            import talib
            last_atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14).iloc[-1]
        except:
            last_atr = None
        
        # Top4StrategyBot을 사용한 신호 생성 및 거래
        bot = None
        signals = None
        
        try:
            # 봇 생성 (기존 포지션 데이터 포함)
            position_data = dic['coins'][Target_Coin_Ticker] if Target_Coin_Ticker in dic['coins'] else None
            bot = Top4StrategyBot(initial_balance=dic['my_money'], leverage=DEFAULT_LEVERAGE, position_data=position_data)
            
            # 전체 포지션 초기화 확인 (사용자 수동 청산 감지)
            try:
                # 바이낸스 잔고에서 실제 포지션 확인
                balance = binanceX.fetch_balance(params={"type": "future"})
                actual_total_position = 0.0
                
                # 롱 포지션 확인
                for posi in balance['info']['positions']:
                    if posi['symbol'] == Target_Coin_Symbol and posi['positionSide'] == 'LONG':
                        actual_total_position += float(posi['positionAmt'])
                        logger.info(f"실제 롱 포지션 발견: {posi['positionAmt']} BTC")
                        break
                
                # JSON에서 로드된 포지션과 실제 포지션 비교
                json_total_position = 0.0
                for strategy_name in bot.strategy_positions:
                    if strategy_name in dic['coins'][Target_Coin_Ticker]:
                        json_position = float(dic['coins'][Target_Coin_Ticker][strategy_name].get('position_size', 0.0))
                        json_total_position += json_position
                
                # 디버깅 로그
                logger.info(f"포지션 비교 - 실제 잔고: {actual_total_position}, JSON: {json_total_position}")
                
                # 실제 잔고에 포지션이 0인데 JSON에 포지션이 기록되어 있으면 수동 청산으로 판단
                if actual_total_position == 0 and json_total_position > 0:
                    logger.warning("사용자 수동 청산 감지: 전체 포지션 초기화")
                    for strategy_name in bot.strategy_positions:
                        if strategy_name in dic['coins'][Target_Coin_Ticker]:
                            json_position = float(dic['coins'][Target_Coin_Ticker][strategy_name].get('position_size', 0.0))
                            if json_position > 0:
                                # 봇 상태 초기화
                                bot.strategy_positions[strategy_name] = 0.0
                                bot.strategy_entry_prices[strategy_name] = 0.0
                                bot.strategy_capitals[strategy_name] = dic['my_money'] * INVESTMENT_RATIO / 4
                                
                                # JSON 상태도 초기화
                                dic['coins'][Target_Coin_Ticker][strategy_name]['position'] = 0
                                dic['coins'][Target_Coin_Ticker][strategy_name]['position_size'] = 0.0
                                dic['coins'][Target_Coin_Ticker][strategy_name]['entry_price'] = 0.0
                                
                                logger.info(f"{strategy_name} 전략 전체 초기화 완료 (JSON: {json_position} → 0)")
                    
                    # 텔레그램 알림
                    line_alert.SendMessage(f"⚠️ **수동 청산 감지**\n- 전체 포지션이 수동으로 청산되었습니다\n- 모든 전략이 초기화되었습니다\n- 다음 신호에서 새로 진입합니다")
                    
            except Exception as e:
                logger.warning(f"전체 포지션 확인 실패: {e}")
            
            # 4가지 전략으로 신호 생성
            signals = bot.generate_signals(df)
            
            logger.info(f"전략 신호: {signals}")
            logger.info(f"현재 포지션 상태: {bot.strategy_positions}")
                
        except Exception as e:
            log_error(f"전략 신호 생성 실패: {e}", traceback.format_exc())
            signals = {'momentum': 0, 'scalping': 0, 'macd': 0, 'moving_average': 0}
        finally:
            # 전략 관련 변수들 정리
            cleanup_variables(bot=bot, signals=signals)

        # 각 전략별로 거래 실행
        for strategy_name, signal in signals.items():
            if signal != 0:
                try:
                    bot.execute_trade(strategy_name, signal, coin_price, binanceX, Target_Coin_Ticker)
                except Exception as e:
                    log_error(f"{strategy_name} 전략 거래 실행 실패: {e}", traceback.format_exc())
        
        # 포지션 정보 파일에 저장 (봇의 실제 포지션 정보 포함)
        if 'bot' in locals() and bot is not None:
            # 봇의 포지션 정보를 dic에 업데이트
            for strategy_name in bot.strategy_positions:
                dic['coins'][Target_Coin_Ticker][strategy_name]['position'] = 1 if bot.strategy_positions[strategy_name] > 0 else 0
                # 타입 안전성을 위해 float로 저장
                dic['coins'][Target_Coin_Ticker][strategy_name]['position_size'] = float(bot.strategy_positions[strategy_name])
                dic['coins'][Target_Coin_Ticker][strategy_name]['entry_price'] = float(bot.strategy_entry_prices[strategy_name])
        
        with open(info_file_path, 'w', encoding='utf-8') as f:
            json.dump(dic, f, indent=4)
        
        # 각 코인 처리 후 메모리 정리
        cleanup_dataframes(df)
        cleanup_memory()

    # 일일 결과보고 전송 (24시간마다)
    try:
        if should_send_daily_report():
            logger.info("=== 일일 결과보고 전송 시작 ===")
            
            # 현재 잔고 조회
            current_balance = binanceX.fetch_balance(params={"type": "future"})['USDT']['total']
            
            # 봇이 생성되어 있으면 보고서 생성
            if 'bot' in locals() and bot is not None:
                daily_report = generate_daily_report(bot, dic, current_balance, ACTIVE_COINS[0])
                
                # 텔레그램으로 전송
                line_alert.SendMessage(daily_report)
                logger.info("일일 결과보고 전송 완료")
                
                # 전송 시간 저장
                save_daily_report_time()
            else:
                logger.warning("봇 객체가 없어 일일 보고서를 생성할 수 없습니다.")
                
    except Exception as e:
        logger.error(f"일일 결과보고 전송 실패: {e}")

    # 최종 메모리 정리
    logger.info("=== 최종 메모리 정리 시작 ===")
    final_memory = cleanup_memory()
    
    # API 연결 정리
    try:
        if 'binanceX' in locals():
            del binanceX
    except:
        pass
    
    # 전역 변수들 정리
    cleanup_variables(
        dic=dic,
        simpleEnDecrypt=simpleEnDecrypt
    )
    
    # 최종 가비지 컬렉션
    gc.collect()
    
    logger.info(f"=== Live Top4 Strategy Trading Bot 종료 (최종 메모리: {final_memory:.2f} MB) ===")
