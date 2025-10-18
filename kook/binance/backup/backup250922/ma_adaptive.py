#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MA 적응형 롱/숏 전략 시스템 - 라이브 트레이딩 버전
- 6개 전략 x 롱/숏 = 12개 전략
- MA 10일~100일 기반으로 롱/숏 비율 동적 조정 (0:100 ~ 100:0)
- 성과 기반 동적 자본 배분
- 바이낸스 선물 거래 연동
"""

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
DEFAULT_LEVERAGE = 10  # 5배 레버리지
INVESTMENT_RATIO = 0.5  # 투자 비율 (자산의 4%)
COIN_CHARGE = 0.0005  # 수수료 설정 (0.05%)
ACTIVE_COINS = ['BTC/USDT']

# ========================= 로깅 설정 =========================
def setup_logging():
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    today = dt.datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(log_dir, f"ma_adaptive_{today}.log")
    trade_log_file = os.path.join(log_dir, "ma_adaptive_trades.log")
    
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

# ========================= 로깅 유틸리티 =========================
def log_trade_action(action_type, coin_ticker, strategy_name, position_side, price, quantity, reason="", profit=0, profit_rate=0):
    try:
        if profit > 0:
            profit_button = "🟢"
        elif profit < 0:
            profit_button = "🔴"
        else:
            profit_button = "⚪"
        
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

class MAAdaptiveStrategySystem:
    """MA 적응형 롱/숏 전략 시스템 - 라이브 트레이딩 버전"""
    
    def __init__(self, initial_balance: float = 10000, leverage: int = 5, position_data: dict = None):
        self.initial_balance = initial_balance
        self.leverage = leverage
        self.trading_fee = COIN_CHARGE
        self.stop_loss_pct = 0.15  # 15% 손절라인 (더 안전)
        
        # 전략별 자본 (전체 자산의 50%를 3등분 - 롱 2개 + 숏 1개)
        self.strategy_capitals = {
            'moving_average_long': initial_balance * INVESTMENT_RATIO / 3,
            'macd_long': initial_balance * INVESTMENT_RATIO / 3,
            'bb_short': initial_balance * INVESTMENT_RATIO / 3
        }
        
        # 전략별 포지션 (JSON 파일에서 로드) - 3개 전략만
        self.strategy_positions = {
            'moving_average_long': 0.0,
            'macd_long': 0.0,
            'bb_short': 0.0
        }
        
        # 기존 포지션 데이터가 있으면 로드
        if position_data:
            for strategy_name in self.strategy_positions:
                if strategy_name in position_data:
                    position_size = float(position_data[strategy_name].get('position_size', 0.0))
                    self.strategy_positions[strategy_name] = position_size
                    logger.info(f"{strategy_name} 전략 포지션 로드: {self.strategy_positions[strategy_name]}")
        
        # 전략별 거래 기록 (3개 전략만)
        self.strategy_trades = {
            'moving_average_long': [],
            'macd_long': [],
            'bb_short': []
        }
        
        # 전략별 진입가 (JSON 파일에서 로드) - 3개 전략만
        self.strategy_entry_prices = {
            'moving_average_long': 0.0,
            'macd_long': 0.0,
            'bb_short': 0.0
        }
        
        # 기존 진입가 데이터가 있으면 로드
        if position_data:
            for strategy_name in self.strategy_entry_prices:
                if strategy_name in position_data:
                    entry_price = float(position_data[strategy_name].get('entry_price', 0.0))
                    self.strategy_entry_prices[strategy_name] = entry_price
                    if self.strategy_entry_prices[strategy_name] > 0:
                        logger.info(f"{strategy_name} 전략 진입가 로드: {self.strategy_entry_prices[strategy_name]}")
        
        # 전략별 성과 추적 (동적 자본 배분용) - 3개 전략만
        self.strategy_performance = {
            'moving_average_long': {'trades': 0, 'wins': 0, 'total_return': 0},
            'macd_long': {'trades': 0, 'wins': 0, 'total_return': 0},
            'bb_short': {'trades': 0, 'wins': 0, 'total_return': 0}
        }
        
    def calculate_ma_long_short_ratio(self, data: pd.DataFrame) -> tuple:
        """MA 기반 롱/숏 비율 계산 (0:100 ~ 100:0)"""
        df = data.copy()
        
        # MA 20일, 50일, 100일, 200일 (표준 MA 기간)
        ma_periods = [20, 50, 100, 200]
        ma_values = {}
        
        for period in ma_periods:
            ma_values[f'ma{period}'] = df['close'].rolling(window=period).mean()
        
        # 현재 가격이 각 MA 위에 있는지 확인
        above_ma_count = 0
        for period in ma_periods:
            above_ma_count += (df['close'] > ma_values[f'ma{period}']).astype(int)
        
        # 0~10개 MA 위에 있으면 0~100% 롱 비율
        long_ratio = (above_ma_count / len(ma_periods)) * 100
        short_ratio = 100 - long_ratio
        
        return long_ratio, short_ratio

    def generate_signals(self, data: pd.DataFrame) -> dict:
        """3가지 전략으로 신호 생성 (롱 2개 + 숏 1개)"""
        signals = {}
        
        # 최근 데이터로 신호 생성
        i = len(data) - 1
        
        # MA 기반 롱/숏 비율 계산
        long_ratio, short_ratio = self.calculate_ma_long_short_ratio(data)
        long_probability = float(long_ratio.iloc[-1]) / 100.0
        short_probability = float(short_ratio.iloc[-1]) / 100.0
        
        # MA 비율 로깅 (현재 시점의 값)
        current_long_ratio = float(long_ratio.iloc[-1]) if len(long_ratio) > 0 else 0
        current_short_ratio = float(short_ratio.iloc[-1]) if len(short_ratio) > 0 else 0
        logger.info(f"📊 MA 비율 - 롱: {current_long_ratio:.1f}%, 숏: {current_short_ratio:.1f}%")
        logger.info(f"📊 진입 확률 - 롱: {long_probability:.3f}, 숏: {short_probability:.3f}")
        
        # 1. 이동평균 롱 전략 신호
        if i >= 50:
            ma20 = data['close'].rolling(window=20).mean()
            ma50 = data['close'].rolling(window=50).mean()
            
            current_ma20 = float(ma20.iloc[i])
            current_ma50 = float(ma50.iloc[i])
            prev_ma20 = float(ma20.iloc[i-1])
            prev_ma50 = float(ma50.iloc[i-1])
            
            # 이동평균 롱 신호 (랜덤 확률 적용)
            if current_ma20 > current_ma50 and prev_ma20 <= prev_ma50 and np.random.random() < long_probability:
                signals['moving_average_long'] = 1
            elif current_ma20 < current_ma50 and prev_ma20 >= prev_ma50:
                signals['moving_average_long'] = -1
            else:
                signals['moving_average_long'] = 0
        else:
            signals['moving_average_long'] = 0
        
        # 2. MACD 롱 전략 신호
        if i >= 26:
            ema12 = data['close'].ewm(span=12).mean()
            ema26 = data['close'].ewm(span=26).mean()
            macd = ema12 - ema26
            macd_signal = macd.ewm(span=9).mean()
            
            current_macd = float(macd.iloc[i])
            current_signal = float(macd_signal.iloc[i])
            prev_macd = float(macd.iloc[i-1])
            prev_signal = float(macd_signal.iloc[i-1])
            
            # MACD 롱 신호 (랜덤 확률 적용)
            if current_macd > current_signal and prev_macd <= prev_signal and np.random.random() < long_probability:
                signals['macd_long'] = 1
            elif current_macd < current_signal and prev_macd >= prev_signal:
                signals['macd_long'] = -1
            else:
                signals['macd_long'] = 0
        else:
            signals['macd_long'] = 0
        
        # 3. 볼린저 밴드 숏 전략 신호
        if i >= 20:
            bb_upper = data['close'].rolling(20).mean() + (data['close'].rolling(20).std() * 2)
            bb_lower = data['close'].rolling(20).mean() - (data['close'].rolling(20).std() * 2)
            
            current_price = float(data['close'].iloc[i])
            current_bb_upper = float(bb_upper.iloc[i])
            current_bb_lower = float(bb_lower.iloc[i])
            
            # 볼린저 밴드 숏 신호 (랜덤 확률 적용)
            if current_price >= current_bb_upper and np.random.random() < short_probability:
                signals['bb_short'] = 1
            elif current_price <= current_bb_lower:
                signals['bb_short'] = -1
            else:
                signals['bb_short'] = 0
        else:
            signals['bb_short'] = 0
        
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

    def execute_trade(self, strategy_name: str, signal: int, coin_price: float, binanceX, coin_ticker: str, dic: dict = None):
        """거래 실행"""
        current_position = self.strategy_positions[strategy_name]
        current_capital = self.strategy_capitals[strategy_name]
        
        # 포지션 상태 확인 로그
        logger.info(f"{strategy_name} 전략 포지션 상태: {current_position}, 신호: {signal}")
        
        # 실제 바이낸스 잔고에서 포지션 확인 (안전장치)
        try:
            balance = binanceX.fetch_balance(params={"type": "future"})
            actual_position = 0.0
            
            # 롱/숏 포지션 확인
            for posi in balance['info']['positions']:
                if posi['symbol'] == coin_ticker.replace('/', '') and posi['positionSide'] == ('LONG' if not strategy_name.endswith('_short') else 'SHORT'):
                    actual_position = float(posi['positionAmt'])
                    break
            
            # 실제 포지션과 봇 상태가 다르면 경고
            if abs(actual_position - current_position) > 0.001:
                logger.warning(f"{strategy_name} 전략 포지션 불일치! 봇: {current_position}, 실제 잔고: {actual_position}")
                
                # 사용자가 수동으로 포지션을 청산한 경우
                if actual_position == 0 and current_position > 0:
                    logger.info(f"{strategy_name} 전략: 사용자 수동 청산 감지, 포지션 초기화")
                    self.strategy_positions[strategy_name] = 0.0
                    self.strategy_entry_prices[strategy_name] = 0.0
                    self.strategy_capitals[strategy_name] = self.initial_balance * INVESTMENT_RATIO / 12
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
        
        is_short_strategy = strategy_name.endswith('_short')
        
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
                
                # 롱/숏 포지션 진입
                if is_short_strategy:
                    data = binanceX.create_order(coin_ticker, 'market', 'sell', position_size, None, {'positionSide': 'SHORT'})
                    action_type = 'SHORT_SELL'
                    position_side = 'short'
                else:
                    data = binanceX.create_order(coin_ticker, 'market', 'buy', position_size, None, {'positionSide': 'LONG'})
                    action_type = 'BUY_LONG'
                    position_side = 'long'
                
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
                    'action': action_type,
                    'price': entry_price,
                    'quantity': position_size,
                    'leverage': self.leverage,
                    'strategy': strategy_name
                })
                
                # 성과 데이터 업데이트 (진입 시)
                if dic and 'strategy_performance' in dic:
                    dic['strategy_performance'][strategy_name]['trades'] += 1
                
                log_trade_action(action_type, coin_ticker, strategy_name, position_side, entry_price, position_size, f"{strategy_name}_strategy")
                line_alert.SendMessage(f"🤖📈 {strategy_name.upper()} 전략 {position_side.upper()} 진입\n- 코인: {coin_ticker}\n- 가격: {entry_price:.2f}\n- 수량: {position_size:.3f}")
                
                logger.info(f"{strategy_name} 전략 {position_side.upper()} 포지션 진입: {entry_price:.2f}, 수량: {position_size}")
                
            except Exception as e:
                log_error(f"{strategy_name} 전략 {position_side.upper()} 진입 실패: {e}", traceback.format_exc())
        
        elif signal == -1 and current_position > 0:  # 매도
            try:
                # 최소 주문 수량 확인
                minimum_amount = myBinance.GetMinimumAmount(binanceX, coin_ticker)
                if current_position < minimum_amount:
                    logger.warning(f"{strategy_name} 전략: 현재 포지션({current_position:.6f})이 최소 수량({minimum_amount:.6f})보다 작아 매도 불가")
                    return
                
                # 매도 수량 확인 로그
                logger.info(f"{strategy_name} 전략 매도 수량: {current_position:.6f} (최소: {minimum_amount:.6f})")
                
                # 롱/숏 포지션 청산
                if is_short_strategy:
                    data = binanceX.create_order(coin_ticker, 'market', 'buy', current_position, None, {'positionSide': 'SHORT'})
                    action_type = 'SHORT_COVER'
                    position_side = 'short'
                else:
                    data = binanceX.create_order(coin_ticker, 'market', 'sell', current_position, None, {'positionSide': 'LONG'})
                    action_type = 'SELL_LONG'
                    position_side = 'long'
                
                exit_price = float(data.get('average', coin_price))
                
                # 수익/손실 계산 (진입가 사용)
                buy_price = self.strategy_entry_prices[strategy_name]
                if buy_price > 0:
                    if is_short_strategy:
                        profit = (buy_price - exit_price) * current_position * (1 - (self.trading_fee * 2))
                    else:
                        profit = (exit_price - buy_price) * current_position * (1 - (self.trading_fee * 2))
                    profit_rate = (exit_price - buy_price) / buy_price * 100.0 if not is_short_strategy else (buy_price - exit_price) / buy_price * 100.0
                    
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
                    'action': action_type,
                    'price': exit_price,
                    'quantity': current_position,
                    'leverage': self.leverage,
                    'strategy': strategy_name,
                    'profit': profit,
                    'profit_rate': profit_rate
                })
                
                # 성과 데이터 업데이트 (청산 시)
                if dic and 'strategy_performance' in dic:
                    if profit > 0:
                        dic['strategy_performance'][strategy_name]['wins'] += 1
                    dic['strategy_performance'][strategy_name]['total_return'] += profit / (current_capital - profit) if (current_capital - profit) > 0 else 0
                
                log_trade_action(action_type, coin_ticker, strategy_name, position_side, exit_price, current_position, f"{strategy_name}_strategy", profit, profit_rate)
                
                profit_emoji = "🟢" if profit > 0 else ("🔴" if profit < 0 else "⚪")
                line_alert.SendMessage(f"{profit_emoji} {strategy_name.upper()} 전략 {position_side.upper()} 청산\n- 코인: {coin_ticker}\n- 청산가: {exit_price:.2f}\n- 수량: {current_position:.3f}\n- 수익: {profit:.2f} USDT ({profit_rate:.2f}%)")
                
                logger.info(f"{strategy_name} 전략 {position_side.upper()} 포지션 청산: {exit_price:.2f}, 수익: {profit:.2f} USDT ({profit_rate:.2f}%)")
                
            except Exception as e:
                log_error(f"{strategy_name} 전략 {position_side.upper()} 청산 실패: {e}", traceback.format_exc())
        
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

    def calculate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """모든 전략의 신호를 벡터화로 계산"""
        df = data.copy()
        
        # MA 기반 롱/숏 비율 계산
        long_ratio, short_ratio = self.calculate_ma_long_short_ratio(df)
        df['long_ratio'] = long_ratio
        df['short_ratio'] = short_ratio
        
        # MA 비율을 0~1 범위로 정규화 (거래 확률용)
        df['long_probability'] = long_ratio / 100.0
        df['short_probability'] = short_ratio / 100.0
        
        # MA 비율 로깅 (현재 시점의 값)
        current_long_ratio = long_ratio.iloc[-1] if len(long_ratio) > 0 else 0
        current_short_ratio = short_ratio.iloc[-1] if len(short_ratio) > 0 else 0
        logger.info(f"📊 MA 비율 - 롱: {current_long_ratio:.1f}%, 숏: {current_short_ratio:.1f}%")
        logger.info(f"📊 진입 확률 - 롱: {current_long_ratio/100:.3f}, 숏: {current_short_ratio/100:.3f}")
        
        # 1. 이동평균 롱 전략 신호
        ma20 = df['close'].rolling(window=20).mean()
        ma50 = df['close'].rolling(window=50).mean()
        
        df['ma20'] = ma20
        df['ma50'] = ma50
        df['ma_cross_up'] = (ma20 > ma50) & (ma20.shift(1) <= ma50.shift(1))
        df['ma_cross_down'] = (ma20 < ma50) & (ma20.shift(1) >= ma50.shift(1))
        
        # 이동평균 롱 신호 (MA 비율 적용, 랜덤 확률)
        df['moving_average_long_signal'] = 0
        ma_long_entry = df['ma_cross_up'] & (np.random.random(len(df)) < df['long_probability'])
        df.loc[ma_long_entry, 'moving_average_long_signal'] = 1
        df.loc[df['ma_cross_down'], 'moving_average_long_signal'] = -1
        
        # 2. MACD 롱 전략 신호
        ema12 = df['close'].ewm(span=12).mean()
        ema26 = df['close'].ewm(span=26).mean()
        macd = ema12 - ema26
        macd_signal = macd.ewm(span=9).mean()
        macd_cross_up = (macd > macd_signal) & (macd.shift(1) <= macd_signal.shift(1))
        macd_cross_down = (macd < macd_signal) & (macd.shift(1) >= macd_signal.shift(1))
        
        # MACD 롱 신호 (MA 비율 적용, 랜덤 확률)
        df['macd_long_signal'] = 0
        macd_long_entry = macd_cross_up & (np.random.random(len(df)) < df['long_probability'])
        df.loc[macd_long_entry, 'macd_long_signal'] = 1
        df.loc[macd_cross_down, 'macd_long_signal'] = -1
        
        # 3. 볼린저 밴드 숏 전략 신호
        df['bb_upper'] = df['close'].rolling(20).mean() + (df['close'].rolling(20).std() * 2)
        df['bb_lower'] = df['close'].rolling(20).mean() - (df['close'].rolling(20).std() * 2)
        df['bb_middle'] = df['close'].rolling(20).mean()
        
        # 볼린저 밴드 숏 신호 (MA 비율 적용, 랜덤 확률)
        df['bb_short_signal'] = 0
        bb_short_condition = df['close'] >= df['bb_upper']  # 상단 밴드 터치 시 숏 진입
        bb_short_entry = bb_short_condition & (np.random.random(len(df)) < df['short_probability'])
        bb_short_exit = df['close'] <= df['bb_lower']   # 하단 밴드 터치 시 숏 청산
        df.loc[bb_short_entry, 'bb_short_signal'] = 1
        df.loc[bb_short_exit, 'bb_short_signal'] = -1
        
        return df
    
    def check_stop_loss(self, position: float, entry_price: float, current_price: float, is_short: bool) -> bool:
        """손절라인 체크"""
        if position == 0:
            return False
        
        if is_short:
            # 숏 포지션: 가격이 올라가면 손실
            loss_pct = (current_price - entry_price) / entry_price
        else:
            # 롱 포지션: 가격이 내려가면 손실
            loss_pct = (entry_price - current_price) / entry_price
        
        return loss_pct >= self.stop_loss_pct
    
    def backtest_strategy(self, data: pd.DataFrame, strategy_name: str) -> dict:
        """개별 전략 백테스트"""
        signal_col = f'{strategy_name}_signal'
        signals = data[signal_col].values
        prices = data['close'].values
        timestamps = data.index
        
        capital = self.strategy_capitals[strategy_name]
        position = 0
        entry_price = 0
        trades = []
        
        # 숏 전략 여부 확인
        is_short_strategy = strategy_name.endswith('_short')
        
        for i in range(len(signals)):
            current_price = prices[i]
            current_time = timestamps[i]
            signal = signals[i]
            
            # 손절라인 체크
            if position != 0:
                is_short = position < 0
                if self.check_stop_loss(position, entry_price, current_price, is_short):
                    # 손절라인 도달 - 강제 청산
                    if is_short:
                        gross_value = abs(position) * current_price
                        fee = gross_value * self.trading_fee
                        net_value = gross_value - fee
                        pnl = (entry_price - current_price) * abs(position)
                        original_capital = capital * self.leverage
                        capital_change = pnl
                        new_capital = max(0, original_capital + capital_change)
                        action = 'STOP_LOSS_SHORT'
                    else:
                        gross_value = position * current_price
                        fee = gross_value * self.trading_fee
                        net_value = gross_value - fee
                        pnl = (current_price - entry_price) * position
                        original_capital = capital * self.leverage
                        capital_change = pnl
                        new_capital = max(0, original_capital + capital_change)
                        action = 'STOP_LOSS_LONG'
                    
                    capital = new_capital
                    position = 0
                    entry_price = 0
                    
                    trades.append({
                        'timestamp': current_time,
                        'action': action,
                        'price': current_price,
                        'shares': abs(position),
                        'leverage': self.leverage,
                        'gross_value': gross_value,
                        'fee': fee,
                        'net_value': net_value,
                        'capital_change': capital_change
                    })
                    continue
            
            if signal == 1 and position == 0:  # 매수 (롱) 또는 숏 매수
                leveraged_value = capital * self.leverage
                fee = leveraged_value * self.trading_fee
                net_value = leveraged_value - fee
                shares = net_value / current_price
                
                if is_short_strategy:
                    position = -shares  # 음수 = 숏 포지션
                    action = 'SHORT_SELL'
                else:
                    position = shares   # 양수 = 롱 포지션
                    action = 'BUY'
                
                entry_price = current_price
                capital = 0
                
                trades.append({
                    'timestamp': current_time,
                    'action': action,
                    'price': current_price,
                    'shares': abs(shares),
                    'leverage': self.leverage,
                    'leveraged_value': leveraged_value,
                    'fee': fee,
                    'net_value': net_value
                })
                
            elif signal == -1 and position != 0:  # 매도 (롱) 또는 숏 매도
                if is_short_strategy:
                    # 숏 포지션 청산
                    gross_value = abs(position) * current_price
                    fee = gross_value * self.trading_fee
                    net_value = gross_value - fee
                    
                    # 숏 포지션 수익 계산
                    pnl = (entry_price - current_price) * abs(position)
                    original_capital = leveraged_value / self.leverage
                    capital_change = pnl
                    new_capital = max(0, original_capital + capital_change)
                    action = 'SHORT_COVER'
                else:
                    # 롱 포지션 청산
                    gross_value = position * current_price
                    fee = gross_value * self.trading_fee
                    net_value = gross_value - fee
                    
                    # 롱 포지션 수익 계산
                    pnl = (current_price - entry_price) * position
                    original_capital = leveraged_value / self.leverage
                    capital_change = pnl
                    new_capital = max(0, original_capital + capital_change)
                    action = 'SELL'
                
                capital = new_capital
                position = 0
                entry_price = 0
                
                trades.append({
                    'timestamp': current_time,
                    'action': action,
                    'price': current_price,
                    'shares': abs(position),
                    'leverage': self.leverage,
                    'gross_value': gross_value,
                    'fee': fee,
                    'net_value': net_value,
                    'capital_change': capital_change
                })
        
        # 최종 포지션 청산
        if position != 0:
            final_price = prices[-1]
            final_time = timestamps[-1]
            
            if is_short_strategy:
                gross_value = abs(position) * final_price
                fee = gross_value * self.trading_fee
                net_value = gross_value - fee
                pnl = (entry_price - final_price) * abs(position)
                original_capital = leveraged_value / self.leverage
                capital_change = pnl
                new_capital = max(0, original_capital + capital_change)
                action = 'FINAL_SHORT_COVER'
            else:
                gross_value = position * final_price
                fee = gross_value * self.trading_fee
                net_value = gross_value - fee
                pnl = (final_price - entry_price) * position
                original_capital = leveraged_value / self.leverage
                capital_change = pnl
                new_capital = max(0, original_capital + capital_change)
                action = 'FINAL_SELL'
            
            capital = new_capital
            
            trades.append({
                'timestamp': final_time,
                'action': action,
                'price': final_price,
                'shares': abs(position),
                'leverage': self.leverage,
                'gross_value': gross_value,
                'fee': fee,
                'net_value': net_value,
                'capital_change': capital_change
            })
        
        # 성과 업데이트
        total_trades = len(trades)
        winning_trades = sum(1 for trade in trades if trade.get('capital_change', 0) > 0)
        total_return = (capital - self.strategy_capitals[strategy_name]) / self.strategy_capitals[strategy_name]
        
        self.strategy_performance[strategy_name] = {
            'trades': total_trades,
            'wins': winning_trades,
            'total_return': total_return
        }
        
        return {
            'final_capital': capital,
            'trades': trades,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'win_rate': winning_trades / total_trades if total_trades > 0 else 0,
            'total_return': total_return
        }
    
    def rebalance_capitals(self):
        """성과 기반 자본 재배분"""
        # 각 전략의 성과를 기반으로 가중치 계산
        total_performance = sum(max(0, perf['total_return']) for perf in self.strategy_performance.values())
        
        if total_performance > 0:
            # 양의 수익을 낸 전략들에만 자본 재배분
            for strategy_name, performance in self.strategy_performance.items():
                if performance['total_return'] > 0:
                    weight = performance['total_return'] / total_performance
                    self.strategy_capitals[strategy_name] = self.initial_capital * weight * 0.8  # 80% 재배분
                else:
                    self.strategy_capitals[strategy_name] = self.initial_capital * 0.02  # 2% 최소 보장
    
    def run_continuous_backtest(self, start_year: int, end_year: int):
        """연속 백테스트 실행 (여러 연도) - 성과 누적"""
        print("🚀 MA 적응형 롱/숏 전략 시스템 연속 백테스트 시작!")
        print("=" * 80)
        print(f"💰 초기 자본: ${self.initial_capital:,.2f}")
        print(f"📊 전략 수: 12개")
        print(f"⚡ 레버리지: {self.leverage}배")
        print(f"💸 수수료: {self.trading_fee*100:.2f}%")
        print(f"📅 기간: {start_year}년 ~ {end_year}년")
        print("=" * 80)
        
        all_results = {}
        total_initial_capital = self.initial_capital
        current_capital = self.initial_capital
        
        # 전략별 누적 성과 추적 (연속성 유지) - 12개 전략
        cumulative_performance = {
            'momentum_long': {'total_trades': 0, 'total_wins': 0, 'total_return': 0, 'years': 0},
            'momentum_short': {'total_trades': 0, 'total_wins': 0, 'total_return': 0, 'years': 0},
            'scalping_long': {'total_trades': 0, 'total_wins': 0, 'total_return': 0, 'years': 0},
            'scalping_short': {'total_trades': 0, 'total_wins': 0, 'total_return': 0, 'years': 0},
            'macd_long': {'total_trades': 0, 'total_wins': 0, 'total_return': 0, 'years': 0},
            'macd_short': {'total_trades': 0, 'total_wins': 0, 'total_return': 0, 'years': 0},
            'moving_average_long': {'total_trades': 0, 'total_wins': 0, 'total_return': 0, 'years': 0},
            'moving_average_short': {'total_trades': 0, 'total_wins': 0, 'total_return': 0, 'years': 0},
            'trend_long': {'total_trades': 0, 'total_wins': 0, 'total_return': 0, 'years': 0},
            'trend_short': {'total_trades': 0, 'total_wins': 0, 'total_return': 0, 'years': 0},
            'bb_long': {'total_trades': 0, 'total_wins': 0, 'total_return': 0, 'years': 0},
            'bb_short': {'total_trades': 0, 'total_wins': 0, 'total_return': 0, 'years': 0}
        }
        
        for year in range(start_year, end_year + 1):
            print(f"\n📅 {year}년 백테스트 시작...")
            print("-" * 60)
            
            # 데이터 로드
            data = load_data('BTCUSDT', year)
            if data is None:
                print(f"❌ {year}년 데이터를 찾을 수 없습니다. 건너뜁니다.")
                continue
            
            # 성과 기반 자본 배분 (첫 해가 아닌 경우)
            if year > start_year:
                self.rebalance_capitals_from_performance(cumulative_performance, current_capital)
            else:
                # 첫 해는 균등 배분 (12개 전략)
                self.strategy_capitals = {
                    'momentum_long': current_capital * 0.0833,
                    'momentum_short': current_capital * 0.0833,
                    'scalping_long': current_capital * 0.0833,
                    'scalping_short': current_capital * 0.0833,
                    'macd_long': current_capital * 0.0833,
                    'macd_short': current_capital * 0.0833,
                    'moving_average_long': current_capital * 0.0833,
                    'moving_average_short': current_capital * 0.0833,
                    'trend_long': current_capital * 0.0833,
                    'trend_short': current_capital * 0.0833,
                    'bb_long': current_capital * 0.0833,
                    'bb_short': current_capital * 0.0833
                }
            
            # 현재 자본으로 초기 자본 업데이트
            self.initial_capital = current_capital
            
            # 백테스트 실행
            year_results = self.run_single_year_backtest(data, year)
            all_results[year] = year_results
            
            # 누적 성과 업데이트
            for strategy_name, result in year_results.items():
                cumulative_performance[strategy_name]['total_trades'] += result['total_trades']
                cumulative_performance[strategy_name]['total_wins'] += result['winning_trades']
                cumulative_performance[strategy_name]['total_return'] += result['total_return']
                cumulative_performance[strategy_name]['years'] += 1
            
            # 다음 해를 위한 자본 업데이트
            year_final_capital = sum(result['final_capital'] for result in year_results.values())
            current_capital = year_final_capital
            
            print(f"💰 {year}년 최종 자본: ${year_final_capital:,.2f}")
            print(f"📈 {year}년 수익률: {((year_final_capital - self.initial_capital) / self.initial_capital * 100):.2f}%")
            
            # 전략별 자본 배분 현황 출력
            self.print_capital_allocation(year)
        
        # 전체 결과 분석
        self.analyze_continuous_results(all_results, total_initial_capital, current_capital)
        return all_results

    def run_single_year_backtest(self, data: pd.DataFrame, year: int):
        """단일 연도 백테스트"""
        print(f"🔄 1단계: {year}년 신호 계산 중...")
        data_with_signals = self.calculate_signals(data)
        print("✅ 신호 계산 완료!")
        
        # MA 비율 분석
        self.analyze_ma_ratios(data_with_signals, year)
        
        print(f"🔄 2단계: {year}년 전략별 백테스트 중...")
        strategies = [
            'momentum_long', 'momentum_short',
            'scalping_long', 'scalping_short',
            'macd_long', 'macd_short',
            'moving_average_long', 'moving_average_short',
            'trend_long', 'trend_short',
            'bb_long', 'bb_short'
        ]
        results = {}
        
        for strategy in strategies:
            results[strategy] = self.backtest_strategy(data_with_signals, strategy)
        
        print("✅ 모든 전략 백테스트 완료!")
        return results

    def analyze_ma_ratios(self, data: pd.DataFrame, year: int):
        """MA 비율 분석 및 출력"""
        # 롱/숏 비율 통계
        long_ratios = data['long_ratio'].dropna()
        short_ratios = data['short_ratio'].dropna()
        
        print(f"📊 {year}년 MA 기반 롱/숏 비율 분석 (거래 빈도 조절):")
        print(f"   롱 비율: 평균 {long_ratios.mean():.1f}%, 최대 {long_ratios.max():.1f}%, 최소 {long_ratios.min():.1f}%")
        print(f"   숏 비율: 평균 {short_ratios.mean():.1f}%, 최대 {short_ratios.max():.1f}%, 최소 {short_ratios.min():.1f}%")
        print(f"   💡 MA 비율에 따라 롱/숏 전략의 진입 빈도가 조절됩니다!")
        
        # 비율 분포
        long_high = (long_ratios >= 70).sum()  # 70% 이상 롱
        long_medium = ((long_ratios >= 30) & (long_ratios < 70)).sum()  # 30-70% 롱
        long_low = (long_ratios < 30).sum()  # 30% 미만 롱
        
        print(f"   롱 비율 분포: 높음(70%+) {long_high:,}회, 중간(30-70%) {long_medium:,}회, 낮음(30%-) {long_low:,}회")

    def run_backtest(self, data: pd.DataFrame, start_date: str = None, end_date: str = None):
        """백테스트 실행"""
        print("🚀 MA 적응형 롱/숏 전략 시스템 백테스트 시작!")
        print("=" * 60)
        print(f"💰 초기 자본: ${self.initial_capital:,.2f}")
        print(f"📊 전략 수: 12개")
        print(f"⚡ 레버리지: {self.leverage}배")
        print(f"💸 수수료: {self.trading_fee*100:.2f}%")
        
        # 날짜 필터링
        if start_date:
            data = data[data.index >= start_date]
        if end_date:
            data = data[data.index <= end_date]
        
        print(f"📅 기간: {data.index[0].strftime('%Y-%m-%d')} ~ {data.index[-1].strftime('%Y-%m-%d')}")
        print(f"📊 백테스트 데이터: {len(data):,}개 캔들")
        print("=" * 60)
        
        # 1단계: 신호 계산
        print("🔄 1단계: 신호 계산 중...")
        data_with_signals = self.calculate_signals(data)
        print("✅ 신호 계산 완료!")
        
        # 2단계: 각 전략별 백테스트
        print("🔄 2단계: 전략별 백테스트 중...")
        strategies = [
            'momentum_long', 'momentum_short',
            'scalping_long', 'scalping_short',
            'macd_long', 'macd_short',
            'moving_average_long', 'moving_average_short',
            'trend_long', 'trend_short',
            'bb_long', 'bb_short'
        ]
        results = {}
        
        for strategy in strategies:
            print(f"   📊 {strategy} 전략 처리 중...")
            results[strategy] = self.backtest_strategy(data_with_signals, strategy)
        
        print("✅ 모든 전략 백테스트 완료!")
        
        # 3단계: 성과 분석
        print("\n🔄 3단계: 성과 분석 중...")
        self.analyze_results(results, data)
        
        return results
    
    def analyze_results(self, results: dict, data: pd.DataFrame):
        """결과 분석 및 출력"""
        print("\n📊 포트폴리오 성과 분석")
        print("=" * 60)
        
        # 전체 성과 계산
        total_initial_capital = self.initial_capital
        total_final_capital = sum(result['final_capital'] for result in results.values())
        total_return = (total_final_capital - total_initial_capital) / total_initial_capital
        
        print(f"💰 초기 자본: ${total_initial_capital:,.2f}")
        print(f"💰 최종 자본: ${total_final_capital:,.2f}")
        print(f"📈 총 수익률: {total_return*100:.2f}%")
        
        # 전략별 성과
        print(f"\n🎯 전략별 성과 (수수료 {self.trading_fee*100:.2f}% 적용)")
        print(f"📅 백테스트 기간: {data.index[0].strftime('%Y-%m-%d')} ~ {data.index[-1].strftime('%Y-%m-%d')}")
        print(f"📊 총 데이터: {len(data):,}개 캔들")
        print("-" * 60)
        
        # 성과 순으로 정렬
        strategy_performance = []
        for strategy_name, result in results.items():
            strategy_performance.append({
                'name': strategy_name,
                'trades': result['total_trades'],
                'win_rate': result['win_rate'] * 100,
                'return': result['total_return'] * 100,
                'final_capital': result['final_capital']
            })
        
        strategy_performance.sort(key=lambda x: x['return'], reverse=True)
        
        for perf in strategy_performance:
            print(f"{perf['name']:<20}: 거래 {perf['trades']:3d}회, 승률 {perf['win_rate']:5.1f}%, "
                  f"수익률 {perf['return']:7.2f}%, 최종자본 ${perf['final_capital']:8.2f}")
        
        print(f"\n🎉 백테스트 완료!")
        print(f"💰 최종 수익률: {total_return*100:.2f}%")

    def analyze_continuous_results(self, all_results: dict, initial_capital: float, final_capital: float):
        """연속 백테스트 결과 분석"""
        print("\n" + "=" * 80)
        print("📊 연속 백테스트 전체 결과 분석")
        print("=" * 80)
        
        # 전체 성과
        total_return = (final_capital - initial_capital) / initial_capital
        print(f"💰 초기 자본: ${initial_capital:,.2f}")
        print(f"💰 최종 자본: ${final_capital:,.2f}")
        print(f"📈 전체 수익률: {total_return*100:.2f}%")
        
        # 연도별 성과
        print(f"\n📅 연도별 성과:")
        print("-" * 60)
        for year, results in all_results.items():
            year_capital = sum(result['final_capital'] for result in results.values())
            if year == min(all_results.keys()):
                year_return = (year_capital - initial_capital) / initial_capital
            else:
                prev_year = year - 1
                if prev_year in all_results:
                    prev_capital = sum(result['final_capital'] for result in all_results[prev_year].values())
                    year_return = (year_capital - prev_capital) / prev_capital
                else:
                    year_return = 0
            
            print(f"{year}년: ${year_capital:,.2f} ({year_return*100:+.2f}%)")
        
        # 전략별 전체 성과 (연도별 평균)
        print(f"\n🎯 전략별 전체 성과 (연도별 평균):")
        print("-" * 60)
        
        strategy_totals = {}
        for year, results in all_results.items():
            for strategy_name, result in results.items():
                if strategy_name not in strategy_totals:
                    strategy_totals[strategy_name] = {
                        'total_trades': 0,
                        'total_wins': 0,
                        'total_return': 0,
                        'years': 0
                    }
                
                strategy_totals[strategy_name]['total_trades'] += result['total_trades']
                strategy_totals[strategy_name]['total_wins'] += result['winning_trades']
                strategy_totals[strategy_name]['total_return'] += result['total_return']
                strategy_totals[strategy_name]['years'] += 1
        
        # 평균 계산 및 정렬
        strategy_avg = []
        for strategy_name, totals in strategy_totals.items():
            avg_trades = totals['total_trades'] / totals['years']
            avg_wins = totals['total_wins'] / totals['years']
            avg_return = totals['total_return'] / totals['years']
            avg_win_rate = avg_wins / avg_trades if avg_trades > 0 else 0
            
            strategy_avg.append({
                'name': strategy_name,
                'trades': avg_trades,
                'win_rate': avg_win_rate * 100,
                'return': avg_return * 100
            })
        
        strategy_avg.sort(key=lambda x: x['return'], reverse=True)
        
        for perf in strategy_avg:
            print(f"{perf['name']:<20}: 거래 {perf['trades']:5.1f}회, 승률 {perf['win_rate']:5.1f}%, "
                  f"수익률 {perf['return']:7.2f}%")
        
        print(f"\n🎉 연속 백테스트 완료!")
        print(f"💰 전체 수익률: {total_return*100:.2f}%")

    def rebalance_capitals_from_performance(self, cumulative_performance: dict, current_capital: float):
        """누적 성과를 기반으로 자본 재배분 (하이브리드 접근법)"""
        # 최근 성과에 더 가중치를 주는 방식 (최근 1년 성과 70%, 전체 성과 30%)
        recent_performance = {}
        total_recent_positive = 0
        
        for strategy_name, performance in cumulative_performance.items():
            if performance['years'] > 0:
                # 최근 1년 성과 (마지막 해의 성과)
                recent_return = performance['total_return'] / performance['years']
                if recent_return > 0:
                    recent_performance[strategy_name] = recent_return
                    total_recent_positive += recent_return
        
        if total_recent_positive > 0:
            # 하이브리드 배분: 50% 성과 기반, 50% 균등 배분
            for strategy_name in self.strategy_capitals.keys():
                if strategy_name in recent_performance:
                    # 성과 기반 배분 (50%)
                    performance_weight = recent_performance[strategy_name] / total_recent_positive
                    performance_capital = current_capital * 0.5 * performance_weight
                    # 균등 배분 (50%)
                    equal_capital = current_capital * 0.5 / len(self.strategy_capitals)
                    self.strategy_capitals[strategy_name] = performance_capital + equal_capital
                else:
                    # 성과가 없는 전략은 균등 배분만
                    self.strategy_capitals[strategy_name] = current_capital * 0.5 / len(self.strategy_capitals)
        else:
            # 모든 전략이 손실이면 균등 배분
            equal_capital = current_capital / len(self.strategy_capitals)
            for strategy_name in self.strategy_capitals.keys():
                self.strategy_capitals[strategy_name] = equal_capital

    def print_capital_allocation(self, year: int):
        """전략별 자본 배분 현황 출력"""
        print(f"📊 {year}년 전략별 자본 배분:")
        total_capital = sum(self.strategy_capitals.values())
        
        # 성과 순으로 정렬
        sorted_strategies = sorted(self.strategy_capitals.items(), 
                                 key=lambda x: x[1], reverse=True)
        
        for strategy_name, capital in sorted_strategies[:6]:  # 상위 6개만 출력
            percentage = (capital / total_capital) * 100
            print(f"   {strategy_name:<20}: ${capital:8,.0f} ({percentage:5.1f}%)")
        
        if len(sorted_strategies) > 6:
            print(f"   ... 기타 {len(sorted_strategies) - 6}개 전략")

def load_data(symbol: str, year: int) -> pd.DataFrame:
    """데이터 로드"""
    filename = f"data/{symbol}/5m/{symbol}_5m_{year}.csv"
    if not os.path.exists(filename):
        print(f"❌ 파일을 찾을 수 없습니다: {filename}")
        return None
    
    print(f"📊 {symbol} {year}년 데이터 로드 중...")
    df = pd.read_csv(filename)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df = df.sort_index()
    
    print(f"✅ 데이터 로드 성공: {len(df):,}개 캔들")
    print(f"📅 기간: {df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}")
    print(f"💰 가격 범위: ${df['close'].min():.2f} ~ ${df['close'].max():.2f}")
    
    return df

# ========================= 메인 실행 코드 =========================
if __name__ == "__main__":
    logger.info("=== MA 적응형 롱/숏 전략 시스템 라이브 트레이딩 시작 ===")
    
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
    info_file_path = os.path.join(os.path.dirname(__file__), "ma_adaptive.json")
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
        
        # 연도 변경 체크 및 자산 재분배
        current_year = dt.datetime.now().year
        last_rebalance_year = dic.get('last_rebalance_year', current_year)
        
        if current_year > last_rebalance_year:
            logger.info(f"=== 연도 변경 감지: {last_rebalance_year} → {current_year} ===")
            logger.info("성과 기반 자산 재분배를 실행합니다...")
            
            # 전략별 성과 분석 및 재분배
            try:
                # 전략별 성과 데이터 로드
                strategy_performance = dic.get('strategy_performance', {})
                
                if strategy_performance:
                    # 성과 기반 자본 재분배 실행
                    total_positive_return = 0
                    positive_strategies = {}
                    
                    for strategy_name, perf in strategy_performance.items():
                        if perf.get('total_return', 0) > 0:
                            positive_strategies[strategy_name] = perf['total_return']
                            total_positive_return += perf['total_return']
                    
                    if total_positive_return > 0:
                        # 성과 기반 재분배 (80% 성과 기반, 20% 균등 배분)
                        for strategy_name in dic['coins']['BTC/USDT'].keys():
                            if strategy_name in positive_strategies:
                                # 성과 기반 배분 (80%)
                                performance_weight = positive_strategies[strategy_name] / total_positive_return
                                performance_capital = current_balance * INVESTMENT_RATIO * 0.8 * performance_weight
                                # 균등 배분 (20%)
                                equal_capital = current_balance * INVESTMENT_RATIO * 0.2 / 3
                                new_capital = performance_capital + equal_capital
                            else:
                                # 성과가 없는 전략은 균등 배분만
                                new_capital = current_balance * INVESTMENT_RATIO * 0.2 / 3
                            
                            # 자본 업데이트
                            dic['coins']['BTC/USDT'][strategy_name]['allocated_capital'] = new_capital
                            logger.info(f"{strategy_name}: {new_capital:.2f} USDT 배분")
                        
                        # 성과 데이터 초기화 (새 연도 시작)
                        dic['strategy_performance'] = {
                            'moving_average_long': {'trades': 0, 'wins': 0, 'total_return': 0},
                            'macd_long': {'trades': 0, 'wins': 0, 'total_return': 0},
                            'bb_short': {'trades': 0, 'wins': 0, 'total_return': 0}
                        }
                        
                        # 재분배 연도 업데이트
                        dic['last_rebalance_year'] = current_year
                        
                        # 텔레그램 알림
                        line_alert.SendMessage(f"🔄 **연도 변경 자산 재분배 완료**\n- {last_rebalance_year}년 → {current_year}년\n- 성과 기반 자본 재분배 실행\n- 새 연도 성과 추적 시작")
                        
                        logger.info("성과 기반 자산 재분배 완료!")
                    else:
                        logger.info("양의 수익을 낸 전략이 없어 균등 배분을 유지합니다.")
                else:
                    logger.info("성과 데이터가 없어 균등 배분을 유지합니다.")
                    
            except Exception as e:
                logger.error(f"자산 재분배 실행 실패: {e}")
                log_error(f"자산 재분배 실행 실패: {e}", traceback.format_exc())
            
    except FileNotFoundError:
        logger.info("설정 파일이 없어 새로 생성합니다.")
        balance = binanceX.fetch_balance(params={"type": "future"})['USDT']['total']
        time.sleep(0.1)
        dic = {
            "start_money": balance, "my_money": balance,
            "last_rebalance_year": dt.datetime.now().year,
            "coins": {
                "BTC/USDT": {
                    "moving_average_long": {"position": 0, "entry_price": 0, "position_size": 0, "allocated_capital": balance * INVESTMENT_RATIO / 3},
                    "macd_long": {"position": 0, "entry_price": 0, "position_size": 0, "allocated_capital": balance * INVESTMENT_RATIO / 3},
                    "bb_short": {"position": 0, "entry_price": 0, "position_size": 0, "allocated_capital": balance * INVESTMENT_RATIO / 3}
                }
            },
            "strategy_performance": {
                "moving_average_long": {"trades": 0, "wins": 0, "total_return": 0},
                "macd_long": {"trades": 0, "wins": 0, "total_return": 0},
                "bb_short": {"trades": 0, "wins": 0, "total_return": 0}
            },
            "position_tracking": {
                "consecutive_losses": 0,
                "consecutive_wins": 0
            }
        }

    for Target_Coin_Ticker in ACTIVE_COINS:
        logger.info(f"=== {Target_Coin_Ticker} | MA 적응형 롱/숏 전략 시스템 ===")
        
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

        # 데이터 수집 (최근 200개 캔들) - 1시간 캔들
        df = myBinance.GetOhlcv(binanceX, Target_Coin_Ticker, '1h', 200)
        coin_price = df['close'].iloc[-1]
        
        # 현재 가격을 dic에 저장
        dic['current_price'] = coin_price
        
        # 메모리 사용량 모니터링 (데이터 수집 후)
        initial_memory = cleanup_memory()
        
        # 데이터프레임 메모리 사용량 로깅
        if hasattr(df, 'memory_usage'):
            df_memory = df.memory_usage(deep=True).sum() / 1024 / 1024
            logger.info(f"데이터프레임 메모리 사용량: {df_memory:.2f} MB")
        
        # MA 적응형 전략 시스템을 사용한 신호 생성 및 거래
        bot = None
        signals = None
        
        try:
            # 봇 생성 (기존 포지션 데이터 포함)
            position_data = dic['coins'][Target_Coin_Ticker] if Target_Coin_Ticker in dic['coins'] else None
            bot = MAAdaptiveStrategySystem(initial_balance=dic['my_money'], leverage=DEFAULT_LEVERAGE, position_data=position_data)
            
            # 전체 포지션 초기화 확인 (사용자 수동 청산 감지)
            try:
                # 바이낸스 잔고에서 실제 포지션 확인
                balance = binanceX.fetch_balance(params={"type": "future"})
                actual_total_position = 0.0
                
                # 롱/숏 포지션 확인
                for posi in balance['info']['positions']:
                    if posi['symbol'] == Target_Coin_Symbol and posi['positionSide'] in ['LONG', 'SHORT']:
                        actual_total_position += abs(float(posi['positionAmt']))
                        logger.info(f"실제 {posi['positionSide']} 포지션 발견: {posi['positionAmt']} BTC")
                
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
                                bot.strategy_capitals[strategy_name] = dic['my_money'] * INVESTMENT_RATIO / 12
                                
                                # JSON 상태도 초기화
                                dic['coins'][Target_Coin_Ticker][strategy_name]['position'] = 0
                                dic['coins'][Target_Coin_Ticker][strategy_name]['position_size'] = 0.0
                                dic['coins'][Target_Coin_Ticker][strategy_name]['entry_price'] = 0.0
                                
                                logger.info(f"{strategy_name} 전략 전체 초기화 완료 (JSON: {json_position} → 0)")
                    
                    # 텔레그램 알림
                    line_alert.SendMessage(f"⚠️ **수동 청산 감지**\n- 전체 포지션이 수동으로 청산되었습니다\n- 모든 전략이 초기화되었습니다\n- 다음 신호에서 새로 진입합니다")
                    
            except Exception as e:
                logger.warning(f"전체 포지션 확인 실패: {e}")
            
            # 12가지 전략으로 신호 생성
            signals = bot.generate_signals(df)
            
            logger.info(f"전략 신호: {signals}")
            logger.info(f"현재 포지션 상태: {bot.strategy_positions}")
                
        except Exception as e:
            log_error(f"전략 신호 생성 실패: {e}", traceback.format_exc())
            signals = {strategy: 0 for strategy in bot.strategy_positions.keys()}
        finally:
            # 전략 관련 변수들 정리
            cleanup_variables(bot=bot, signals=signals)
            
            # 데이터프레임 정리
            cleanup_dataframes(df)
            
            # 메모리 정리
            cleanup_memory()

        # 각 전략별로 거래 실행
        for strategy_name, signal in signals.items():
            if signal != 0:
                try:
                    bot.execute_trade(strategy_name, signal, coin_price, binanceX, Target_Coin_Ticker, dic)
                except Exception as e:
                    log_error(f"{strategy_name} 전략 거래 실행 실패: {e}", traceback.format_exc())
        
        # 포지션 정보 파일에 저장 (봇의 실제 포지션 정보 포함)
        if 'bot' in locals() and bot is not None:
            # 봇의 포지션 정보를 dic에 업데이트
            for strategy_name in bot.strategy_positions:
                dic['coins'][Target_Coin_Ticker][strategy_name]['position'] = 1 if bot.strategy_positions[strategy_name] > 0 else 0
                # 타입 안전성을 위해 float로 저장 (소수점 3자리까지)
                dic['coins'][Target_Coin_Ticker][strategy_name]['position_size'] = round(float(bot.strategy_positions[strategy_name]), 3)
                dic['coins'][Target_Coin_Ticker][strategy_name]['entry_price'] = float(bot.strategy_entry_prices[strategy_name])
        
        with open(info_file_path, 'w', encoding='utf-8') as f:
            json.dump(dic, f, indent=4)
        
        # 각 코인 처리 후 메모리 정리
        cleanup_dataframes(df)
        cleanup_memory()

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
    
    logger.info(f"=== MA 적응형 롱/숏 전략 시스템 라이브 트레이딩 종료 (최종 메모리: {final_memory:.2f} MB) ===")
