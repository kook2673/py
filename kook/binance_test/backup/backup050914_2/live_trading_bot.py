#-*-coding:utf-8 -*-
'''
비트코인 선물 라이브 트레이딩 봇
=============================

=== 개요 ===
백테스트에서 검증된 전략을 실매매에 적용하는 라이브 트레이딩 봇입니다.
5가지 전략 중 선택하여 실시간으로 거래를 실행할 수 있습니다.

=== 지원 전략 ===
1. 변동성 돌파 전략 (volatility)
2. 모멘텀 전략 (momentum)
3. 스윙 트레이딩 (swing)
4. 브레이크아웃 전략 (breakout)
5. 스캘핑 전략 (scalping)

=== 주요 기능 ===
- 실시간 데이터 수집 및 분석
- 전략별 신호 생성 및 거래 실행
- 리스크 관리 및 포지션 관리
- 실시간 모니터링 및 알림
- 거래 내역 로깅 및 성과 추적

=== 사용법 ===
python live_trading_bot.py --strategy volatility --capital 1000 --leverage 10
'''

import os
import sys
import json
import time
import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
import ccxt
import requests

# 한글 폰트 설정
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

class LiveTradingBot:
    """라이브 트레이딩 봇"""
    
    def __init__(self, strategy: str, capital: float, leverage: float, 
                 api_key: str, secret_key: str, testnet: bool = True):
        self.strategy = strategy
        self.capital = capital
        self.leverage = leverage
        self.testnet = testnet
        
        # 바이낸스 API 설정
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': secret_key,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'adjustForTimeDifference': True,
            },
            'sandbox': testnet  # 테스트넷 사용 여부
        })
        
        # 거래 상태
        self.position = None
        self.entry_price = 0
        self.entry_time = None
        self.position_size = 0
        self.stop_loss = 0
        self.take_profit = 0
        
        # 성과 추적
        self.trades = []
        self.equity_curve = []
        self.current_equity = capital
        
        # 로깅 설정
        self.setup_logging()
        
        # 전략별 파라미터
        self.strategy_params = self.get_strategy_params()
        
    def setup_logging(self):
        """로깅 설정"""
        log_dir = os.path.join(os.path.dirname(__file__), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"live_trading_{self.strategy}_{timestamp}.log")
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        
    def get_strategy_params(self) -> Dict:
        """전략별 파라미터 설정"""
        params = {
            'volatility': {
                'timeframe': '1h',
                'atr_period': 14,
                'breakout_multiplier': 1.0,
                'volume_threshold': 1.2,
                'stop_loss_atr': 2.0,
                'take_profit_atr': 4.0,
                'max_hold_hours': 24
            },
            'momentum': {
                'timeframe': '1h',
                'ma_fast': 5,
                'ma_slow': 20,
                'rsi_period': 14,
                'rsi_oversold': 30,
                'rsi_overbought': 70,
                'stop_loss_atr': 2.5,
                'take_profit_atr': 5.0,
                'max_hold_hours': 48
            },
            'swing': {
                'timeframe': '4h',
                'ma_short': 10,
                'ma_long': 50,
                'ma_trend': 200,
                'rsi_period': 14,
                'adx_threshold': 25,
                'stop_loss_atr': 3.0,
                'take_profit_atr': 6.0,
                'max_hold_hours': 168
            },
            'breakout': {
                'timeframe': '1h',
                'lookback_period': 20,
                'volume_threshold': 1.5,
                'volatility_threshold': 0.8,
                'breakout_strength': 0.5,
                'stop_loss_atr': 2.0,
                'take_profit_atr': 4.0,
                'max_hold_hours': 12
            },
            'scalping': {
                'timeframe': '1m',
                'rsi_period': 14,
                'stoch_period': 14,
                'bb_period': 20,
                'volume_threshold': 1.0,
                'stop_loss_pct': 0.3,
                'take_profit_pct': 0.5,
                'max_hold_minutes': 30
            }
        }
        
        return params.get(self.strategy, {})
    
    def get_market_data(self, symbol: str = 'BTC/USDT', limit: int = 100) -> pd.DataFrame:
        """시장 데이터 수집"""
        try:
            timeframe = self.strategy_params['timeframe']
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.set_index('timestamp')
            
            return df
            
        except Exception as e:
            self.logger.error(f"데이터 수집 실패: {e}")
            return None
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """기술적 지표 계산"""
        try:
            # ATR
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            true_range = np.maximum(high_low, np.maximum(high_close, low_close))
            df['atr'] = true_range.rolling(self.strategy_params.get('atr_period', 14)).mean()
            
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=self.strategy_params.get('rsi_period', 14)).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=self.strategy_params.get('rsi_period', 14)).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # 이동평균선
            if 'ma_fast' in self.strategy_params:
                df['ma_fast'] = df['close'].rolling(self.strategy_params['ma_fast']).mean()
            if 'ma_slow' in self.strategy_params:
                df['ma_slow'] = df['close'].rolling(self.strategy_params['ma_slow']).mean()
            if 'ma_short' in self.strategy_params:
                df['ma_short'] = df['close'].rolling(self.strategy_params['ma_short']).mean()
            if 'ma_long' in self.strategy_params:
                df['ma_long'] = df['close'].rolling(self.strategy_params['ma_long']).mean()
            if 'ma_trend' in self.strategy_params:
                df['ma_trend'] = df['close'].rolling(self.strategy_params['ma_trend']).mean()
            
            # 거래량 지표
            df['volume_ma'] = df['volume'].rolling(20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_ma']
            
            # 변동성 지표
            df['volatility'] = df['close'].rolling(20).std()
            df['volatility_ratio'] = df['volatility'] / df['volatility'].rolling(50).mean()
            
            return df
            
        except Exception as e:
            self.logger.error(f"지표 계산 실패: {e}")
            return df
    
    def generate_signal(self, df: pd.DataFrame) -> Dict:
        """거래 신호 생성"""
        try:
            if len(df) < 50:  # 충분한 데이터가 없으면 보유
                return {'signal': 0, 'strength': 0.0, 'reason': '데이터 부족'}
            
            current_price = df['close'].iloc[-1]
            signal = 0
            strength = 0.0
            reason = ""
            
            if self.strategy == 'volatility':
                signal, strength, reason = self._volatility_signal(df, current_price)
            elif self.strategy == 'momentum':
                signal, strength, reason = self._momentum_signal(df, current_price)
            elif self.strategy == 'swing':
                signal, strength, reason = self._swing_signal(df, current_price)
            elif self.strategy == 'breakout':
                signal, strength, reason = self._breakout_signal(df, current_price)
            elif self.strategy == 'scalping':
                signal, strength, reason = self._scalping_signal(df, current_price)
            
            return {
                'signal': signal,
                'strength': strength,
                'reason': reason,
                'price': current_price,
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            self.logger.error(f"신호 생성 실패: {e}")
            return {'signal': 0, 'strength': 0.0, 'reason': f'오류: {e}'}
    
    def _volatility_signal(self, df: pd.DataFrame, current_price: float) -> tuple:
        """변동성 돌파 신호"""
        breakout_upper = df['high'].iloc[-2] + df['atr'].iloc[-2] * self.strategy_params['breakout_multiplier']
        breakout_lower = df['low'].iloc[-2] - df['atr'].iloc[-2] * self.strategy_params['breakout_multiplier']
        volume_ratio = df['volume_ratio'].iloc[-1]
        
        if (current_price > breakout_upper and 
            volume_ratio > self.strategy_params['volume_threshold']):
            strength = min((current_price - breakout_upper) / breakout_upper * 10, 1.0)
            return 1, strength, f"상승 돌파: {current_price:.0f} > {breakout_upper:.0f}"
        elif (current_price < breakout_lower and 
              volume_ratio > self.strategy_params['volume_threshold']):
            strength = min((breakout_lower - current_price) / breakout_lower * 10, 1.0)
            return -1, strength, f"하락 돌파: {current_price:.0f} < {breakout_lower:.0f}"
        
        return 0, 0.0, "신호 없음"
    
    def _momentum_signal(self, df: pd.DataFrame, current_price: float) -> tuple:
        """모멘텀 신호"""
        ma_fast = df['ma_fast'].iloc[-1]
        ma_slow = df['ma_slow'].iloc[-1]
        ma_fast_prev = df['ma_fast'].iloc[-2]
        ma_slow_prev = df['ma_slow'].iloc[-2]
        rsi = df['rsi'].iloc[-1]
        volume_ratio = df['volume_ratio'].iloc[-1]
        
        golden_cross = (ma_fast > ma_slow) and (ma_fast_prev <= ma_slow_prev)
        death_cross = (ma_fast < ma_slow) and (ma_fast_prev >= ma_slow_prev)
        
        if (golden_cross and 
            rsi > 50 and rsi < 70 and 
            volume_ratio > 1.1):
            strength = (rsi - 50) / 20
            return 1, strength, f"골든크로스: {ma_fast:.0f} > {ma_slow:.0f}"
        elif (death_cross and 
              rsi < 50 and rsi > 30 and 
              volume_ratio > 1.1):
            strength = (50 - rsi) / 20
            return -1, strength, f"데드크로스: {ma_fast:.0f} < {ma_slow:.0f}"
        
        return 0, 0.0, "신호 없음"
    
    def _swing_signal(self, df: pd.DataFrame, current_price: float) -> tuple:
        """스윙 트레이딩 신호"""
        ma_short = df['ma_short'].iloc[-1]
        ma_long = df['ma_long'].iloc[-1]
        ma_trend = df['ma_trend'].iloc[-1]
        rsi = df['rsi'].iloc[-1]
        volume_ratio = df['volume_ratio'].iloc[-1]
        
        uptrend = current_price > ma_trend
        downtrend = current_price < ma_trend
        
        if (uptrend and ma_short > ma_long and 
            current_price > ma_short and 
            30 <= rsi <= 70 and volume_ratio > 1.0):
            strength = (rsi - 30) / 40
            return 1, strength, f"상승 추세: {current_price:.0f} > {ma_trend:.0f}"
        elif (downtrend and ma_short < ma_long and 
              current_price < ma_short and 
              30 <= rsi <= 70 and volume_ratio > 1.0):
            strength = (70 - rsi) / 40
            return -1, strength, f"하락 추세: {current_price:.0f} < {ma_trend:.0f}"
        
        return 0, 0.0, "신호 없음"
    
    def _breakout_signal(self, df: pd.DataFrame, current_price: float) -> tuple:
        """브레이크아웃 신호"""
        lookback = self.strategy_params['lookback_period']
        resistance = df['high'].rolling(lookback).max().iloc[-2]
        support = df['low'].rolling(lookback).min().iloc[-2]
        volume_ratio = df['volume_ratio'].iloc[-1]
        volatility_ratio = df['volatility_ratio'].iloc[-1]
        
        if (current_price > resistance and 
            volume_ratio > self.strategy_params['volume_threshold'] and
            volatility_ratio > self.strategy_params['volatility_threshold']):
            strength = min((current_price - resistance) / resistance * 10, 1.0)
            return 1, strength, f"저항선 돌파: {current_price:.0f} > {resistance:.0f}"
        elif (current_price < support and 
              volume_ratio > self.strategy_params['volume_threshold'] and
              volatility_ratio > self.strategy_params['volatility_threshold']):
            strength = min((support - current_price) / support * 10, 1.0)
            return -1, strength, f"지지선 돌파: {current_price:.0f} < {support:.0f}"
        
        return 0, 0.0, "신호 없음"
    
    def _scalping_signal(self, df: pd.DataFrame, current_price: float) -> tuple:
        """스캘핑 신호"""
        rsi = df['rsi'].iloc[-1]
        rsi_prev = df['rsi'].iloc[-2]
        volume_ratio = df['volume_ratio'].iloc[-1]
        
        # RSI 반전 신호
        rsi_oversold = (rsi < 30 and rsi_prev >= 30)
        rsi_overbought = (rsi > 70 and rsi_prev <= 70)
        
        if rsi_oversold and volume_ratio > 1.0:
            strength = (30 - rsi) / 30
            return 1, strength, f"RSI 과매도 반전: {rsi:.1f}"
        elif rsi_overbought and volume_ratio > 1.0:
            strength = (rsi - 70) / 30
            return -1, strength, f"RSI 과매수 반전: {rsi:.1f}"
        
        return 0, 0.0, "신호 없음"
    
    def calculate_position_size(self, current_price: float, atr: float, signal_strength: float) -> float:
        """포지션 사이즈 계산"""
        # 기본 리스크: 계좌의 1%
        base_risk = self.current_equity * 0.01
        
        # ATR 기반 포지션 사이즈
        atr_risk = atr * 2
        position_size = base_risk / atr_risk
        
        # 신호 강도에 따른 조정
        position_size *= (0.5 + signal_strength * 0.5)
        
        # 레버리지 적용
        position_size *= self.leverage
        
        # 최대 포지션 제한
        max_position = self.current_equity * 0.2 * self.leverage / current_price
        position_size = min(position_size, max_position)
        
        return max(0, position_size)
    
    def place_order(self, side: str, amount: float, price: float = None, 
                   stop_price: float = None, order_type: str = 'market') -> Dict:
        """주문 실행"""
        try:
            symbol = 'BTC/USDT'
            
            if order_type == 'market':
                order = self.exchange.create_market_order(symbol, side, amount)
            elif order_type == 'limit':
                order = self.exchange.create_limit_order(symbol, side, amount, price)
            elif order_type == 'stop':
                order = self.exchange.create_order(symbol, 'stop', side, amount, price, stop_price)
            
            self.logger.info(f"주문 실행: {side} {amount:.3f} BTC @ {price or 'market'}")
            return order
            
        except Exception as e:
            self.logger.error(f"주문 실행 실패: {e}")
            return None
    
    def close_position(self, reason: str = "수동 청산") -> bool:
        """포지션 청산"""
        try:
            if not self.position:
                return False
            
            side = 'sell' if self.position == 'long' else 'buy'
            amount = abs(self.position_size)
            
            order = self.place_order(side, amount)
            
            if order:
                # 수익/손실 계산
                current_price = order.get('price', 0)
                if self.position == 'long':
                    pnl = (current_price - self.entry_price) / self.entry_price * self.leverage
                else:
                    pnl = (self.entry_price - current_price) / self.entry_price * self.leverage
                
                # 거래 기록
                trade = {
                    'entry_time': self.entry_time,
                    'exit_time': datetime.now(),
                    'entry_price': self.entry_price,
                    'exit_price': current_price,
                    'position': self.position,
                    'size': self.position_size,
                    'pnl': pnl,
                    'return_pct': pnl * 100,
                    'reason': reason
                }
                
                self.trades.append(trade)
                self.current_equity *= (1 + pnl)
                
                self.logger.info(f"포지션 청산: {reason} | 수익률: {pnl*100:.2f}%")
                
                # 포지션 초기화
                self.position = None
                self.entry_price = 0
                self.entry_time = None
                self.position_size = 0
                self.stop_loss = 0
                self.take_profit = 0
                
                return True
            
        except Exception as e:
            self.logger.error(f"포지션 청산 실패: {e}")
            return False
        
        return False
    
    def check_exit_conditions(self, current_price: float) -> str:
        """청산 조건 확인"""
        if not self.position:
            return None
        
        # 시간 기반 청산
        if self.entry_time:
            max_hold = self.strategy_params.get('max_hold_hours', 24)
            if self.strategy == 'scalping':
                max_hold = self.strategy_params.get('max_hold_minutes', 30) / 60
            
            hold_time = (datetime.now() - self.entry_time).total_seconds() / 3600
            if hold_time > max_hold:
                return "시간 초과"
        
        # 손절/익절 확인
        if self.position == 'long':
            if current_price <= self.stop_loss:
                return "손절"
            elif current_price >= self.take_profit:
                return "익절"
        else:  # short
            if current_price >= self.stop_loss:
                return "손절"
            elif current_price <= self.take_profit:
                return "익절"
        
        return None
    
    def run(self):
        """메인 실행 루프"""
        self.logger.info(f"🚀 {self.strategy} 전략 라이브 트레이딩 시작")
        self.logger.info(f"💰 초기 자본: {self.capital:,.2f} USDT")
        self.logger.info(f"⚡ 레버리지: {self.leverage}배")
        self.logger.info(f"🌐 테스트넷: {self.testnet}")
        
        try:
            while True:
                # 시장 데이터 수집
                df = self.get_market_data()
                if df is None:
                    time.sleep(60)
                    continue
                
                # 기술적 지표 계산
                df = self.calculate_indicators(df)
                
                # 현재 포지션 확인
                if self.position:
                    current_price = df['close'].iloc[-1]
                    exit_reason = self.check_exit_conditions(current_price)
                    
                    if exit_reason:
                        self.close_position(exit_reason)
                    else:
                        self.logger.info(f"포지션 보유 중: {self.position} @ {self.entry_price:.0f}")
                
                # 신호 생성
                signal_data = self.generate_signal(df)
                
                if signal_data['signal'] != 0 and not self.position:
                    # 신규 진입
                    current_price = signal_data['price']
                    atr = df['atr'].iloc[-1]
                    signal_strength = signal_data['strength']
                    
                    # 포지션 사이즈 계산
                    position_size = self.calculate_position_size(current_price, atr, signal_strength)
                    
                    if position_size > 0:
                        # 주문 실행
                        side = 'buy' if signal_data['signal'] == 1 else 'sell'
                        order = self.place_order(side, position_size)
                        
                        if order:
                            # 포지션 정보 저장
                            self.position = 'long' if signal_data['signal'] == 1 else 'short'
                            self.entry_price = current_price
                            self.entry_time = datetime.now()
                            self.position_size = position_size if signal_data['signal'] == 1 else -position_size
                            
                            # 손절/익절 설정
                            if self.strategy == 'scalping':
                                self.stop_loss = current_price * (1 - 0.003) if self.position == 'long' else current_price * (1 + 0.003)
                                self.take_profit = current_price * (1 + 0.005) if self.position == 'long' else current_price * (1 - 0.005)
                            else:
                                atr_multiplier = self.strategy_params.get('stop_loss_atr', 2.0)
                                self.stop_loss = current_price * (1 - atr * atr_multiplier / current_price) if self.position == 'long' else current_price * (1 + atr * atr_multiplier / current_price)
                                
                                take_profit_atr = self.strategy_params.get('take_profit_atr', 4.0)
                                self.take_profit = current_price * (1 + atr * take_profit_atr / current_price) if self.position == 'long' else current_price * (1 - atr * take_profit_atr / current_price)
                            
                            self.logger.info(f"🟢 {self.position.upper()} 진입: {current_price:.0f} | 크기: {position_size:.3f} | 이유: {signal_data['reason']}")
                
                # 자산 곡선 기록
                self.equity_curve.append({
                    'timestamp': datetime.now(),
                    'equity': self.current_equity,
                    'price': df['close'].iloc[-1]
                })
                
                # 대기 시간
                if self.strategy == 'scalping':
                    time.sleep(10)  # 1분봉 전략은 10초마다 체크
                else:
                    time.sleep(60)  # 다른 전략은 1분마다 체크
                
        except KeyboardInterrupt:
            self.logger.info("🛑 사용자에 의해 중단됨")
            if self.position:
                self.close_position("사용자 중단")
        except Exception as e:
            self.logger.error(f"❌ 오류 발생: {e}")
            if self.position:
                self.close_position("오류 발생")
        finally:
            self.logger.info("📊 최종 성과:")
            self.logger.info(f"💰 최종 자본: {self.current_equity:,.2f} USDT")
            self.logger.info(f"📈 총 수익률: {(self.current_equity - self.capital) / self.capital * 100:.2f}%")
            self.logger.info(f"🔄 총 거래 수: {len(self.trades)}회")

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='비트코인 선물 라이브 트레이딩 봇')
    parser.add_argument('--strategy', choices=['volatility', 'momentum', 'swing', 'breakout', 'scalping'],
                       required=True, help='사용할 전략')
    parser.add_argument('--capital', type=float, default=1000, help='초기 자본 (USDT)')
    parser.add_argument('--leverage', type=float, default=10, help='레버리지')
    parser.add_argument('--api-key', required=True, help='바이낸스 API 키')
    parser.add_argument('--secret-key', required=True, help='바이낸스 시크릿 키')
    parser.add_argument('--testnet', action='store_true', help='테스트넷 사용')
    
    args = parser.parse_args()
    
    # 봇 생성 및 실행
    bot = LiveTradingBot(
        strategy=args.strategy,
        capital=args.capital,
        leverage=args.leverage,
        api_key=args.api_key,
        secret_key=args.secret_key,
        testnet=args.testnet
    )
    
    bot.run()

if __name__ == "__main__":
    main()
