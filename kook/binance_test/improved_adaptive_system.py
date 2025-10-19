"""
개선된 적응형 트레이딩 시스템

=== 주요 개선사항 ===
1. 동적 포지션 사이징 (변동성 기반)
2. 연속 손실 방지 메커니즘
3. 시장 상황별 거래 빈도 조절
4. 향상된 리스크 관리
5. 하락장 특화 전략
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class ImprovedRiskManager:
    """개선된 리스크 관리자"""
    
    def __init__(self):
        self.max_daily_loss = 0.02  # 일일 최대 손실 2%
        self.max_position_size = 0.8  # 최대 포지션 크기 80%
        self.consecutive_loss_limit = 3  # 연속 손실 제한
        self.cooldown_period = 12  # 쿨다운 기간 (1시간)
        self.daily_trade_limit = 20  # 일일 거래 제한
        
        # 상태 추적
        self.consecutive_losses = 0
        self.last_loss_time = None
        self.daily_trades = 0
        self.daily_pnl = 0
        self.last_reset_date = None
    
    def can_trade(self, current_time, current_capital, initial_capital):
        """거래 가능 여부 확인"""
        current_date = current_time.date()
        
        # 날짜 변경 시 리셋
        if self.last_reset_date != current_date:
            self.daily_trades = 0
            self.daily_pnl = 0
            self.last_reset_date = current_date
        
        # 일일 거래 제한
        if self.daily_trades >= self.daily_trade_limit:
            return False, "일일 거래 제한"
        
        # 일일 손실 제한
        daily_loss_ratio = abs(self.daily_pnl) / initial_capital
        if daily_loss_ratio >= self.max_daily_loss:
            return False, "일일 손실 제한"
        
        # 연속 손실 제한
        if self.consecutive_losses >= self.consecutive_loss_limit:
            if self.last_loss_time and (current_time - self.last_loss_time).total_seconds() < self.cooldown_period * 300:  # 5분 단위
                return False, "연속 손실 쿨다운"
        
        return True, "거래 가능"
    
    def update_trade_result(self, pnl, trade_time):
        """거래 결과 업데이트"""
        self.daily_trades += 1
        self.daily_pnl += pnl
        
        if pnl < 0:
            self.consecutive_losses += 1
            self.last_loss_time = trade_time
        else:
            self.consecutive_losses = 0
    
    def calculate_position_size(self, current_capital, volatility, market_trend):
        """동적 포지션 사이징"""
        base_size = self.max_position_size
        
        # 변동성 조정
        if volatility > 0.03:  # 고변동성
            size_multiplier = 0.5
        elif volatility < 0.01:  # 저변동성
            size_multiplier = 1.2
        else:
            size_multiplier = 1.0
        
        # 시장 트렌드 조정
        if market_trend == 'strong_downtrend':
            size_multiplier *= 0.6  # 하락장에서 더 보수적
        elif market_trend == 'downtrend':
            size_multiplier *= 0.8
        
        # 연속 손실 조정
        if self.consecutive_losses > 0:
            size_multiplier *= (0.5 ** self.consecutive_losses)
        
        final_size = min(base_size * size_multiplier, self.max_position_size)
        return current_capital * final_size

class MarketRegimeDetector:
    """시장 상황 감지기 (개선된 버전)"""
    
    def __init__(self):
        self.trend_periods = [20, 50, 100]
        self.volatility_period = 20
        self.momentum_period = 14
    
    def detect_market_regime(self, data):
        """시장 상황 종합 분석"""
        if len(data) < max(self.trend_periods):
            return 'unknown'
        
        # 트렌드 분석
        short_trend = data['close'].iloc[-self.trend_periods[0]:].pct_change().mean()
        mid_trend = data['close'].iloc[-self.trend_periods[1]:].pct_change().mean()
        long_trend = data['close'].iloc[-self.trend_periods[2]:].pct_change().mean()
        
        # 변동성 분석
        returns = data['close'].pct_change()
        volatility = returns.rolling(self.volatility_period).std().iloc[-1]
        
        # 모멘텀 분석
        rsi = self._calculate_rsi(data['close'])
        current_rsi = rsi.iloc[-1]
        
        # 시장 상황 분류
        if short_trend < -0.002 and mid_trend < -0.001 and long_trend < -0.0005:
            if volatility > 0.025:
                return 'crash'  # 폭락장
            else:
                return 'strong_downtrend'  # 강한 하락장
        elif short_trend < -0.001 and mid_trend < -0.0005:
            return 'downtrend'  # 하락장
        elif short_trend > 0.002 and mid_trend > 0.001 and long_trend > 0.0005:
            return 'strong_uptrend'  # 강한 상승장
        elif short_trend > 0.001 and mid_trend > 0.0005:
            return 'uptrend'  # 상승장
        else:
            if volatility > 0.02:
                return 'high_volatility_sideways'  # 고변동성 횡보
            else:
                return 'low_volatility_sideways'  # 저변동성 횡보
    
    def _calculate_rsi(self, prices, period=14):
        """RSI 계산"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

class ImprovedStrategySelector:
    """개선된 전략 선택기"""
    
    def __init__(self):
        self.strategies = {
            'conservative_ma': '보수적 MA 전략',
            'momentum_reversal': '모멘텀 반전 전략',
            'volatility_breakout': '변동성 돌파 전략',
            'trend_following': '트렌드 추종 전략',
            'mean_reversion': '평균 회귀 전략',
            'defensive': '방어적 전략'
        }
        
        # 시장 상황별 전략 매핑
        self.strategy_mapping = {
            'crash': 'defensive',  # 폭락장: 방어적
            'strong_downtrend': 'mean_reversion',  # 강한 하락장: 평균 회귀
            'downtrend': 'conservative_ma',  # 하락장: 보수적 MA
            'strong_uptrend': 'trend_following',  # 강한 상승장: 트렌드 추종
            'uptrend': 'momentum_reversal',  # 상승장: 모멘텀 반전
            'high_volatility_sideways': 'volatility_breakout',  # 고변동성 횡보: 변동성 돌파
            'low_volatility_sideways': 'conservative_ma'  # 저변동성 횡보: 보수적 MA
        }
    
    def select_strategy(self, market_regime, volatility, rsi):
        """시장 상황에 따른 전략 선택"""
        base_strategy = self.strategy_mapping.get(market_regime, 'conservative_ma')
        
        # 추가 조건에 따른 조정
        if market_regime in ['crash', 'strong_downtrend'] and rsi < 20:
            return 'mean_reversion'  # 과매도에서 반전 기대
        elif market_regime in ['strong_uptrend', 'uptrend'] and rsi > 80:
            return 'momentum_reversal'  # 과매수에서 반전 기대
        elif volatility > 0.03:
            return 'volatility_breakout'  # 고변동성에서는 돌파 전략
        
        return base_strategy

class ImprovedAdaptiveTradingSystem:
    """개선된 적응형 트레이딩 시스템"""
    
    # 클래스 변수로 데이터 캐싱
    _data_cache = {}
    _data_loaded = False
    
    def __init__(self):
        self.risk_manager = ImprovedRiskManager()
        self.regime_detector = MarketRegimeDetector()
        self.strategy_selector = ImprovedStrategySelector()
        
        # 성능 최적화를 위한 캐시
        self._indicators_cache = {}
        self._signals_cache = {}
        self._market_regime_cache = {}
        self._strategy_cache = {}
        
        # 전략별 파라미터
        self.strategy_params = {
            'conservative_ma': {
                'sma_short': 20,
                'sma_long': 50,
                'rsi_oversold': 30,
                'rsi_overbought': 70,
                'dc_period': 20
            },
            'momentum_reversal': {
                'rsi_period': 14,
                'rsi_oversold': 25,
                'rsi_overbought': 75,
                'stoch_k': 14,
                'stoch_d': 3
            },
            'volatility_breakout': {
                'bb_period': 20,
                'bb_std': 2.0,
                'atr_period': 14,
                'atr_multiplier': 1.5
            },
            'trend_following': {
                'ema_fast': 12,
                'ema_slow': 26,
                'macd_signal': 9,
                'trend_strength': 0.001
            },
            'mean_reversion': {
                'bb_period': 20,
                'bb_std': 2.0,
                'rsi_period': 14,
                'rsi_oversold': 20,
                'rsi_overbought': 80
            },
            'defensive': {
                'sma_period': 50,
                'rsi_oversold': 15,
                'rsi_overbought': 85,
                'max_hold_hours': 4
            }
        }
        
        self.data = None
    
    def load_data(self, file_path):
        """데이터 로드 (캐싱 적용)"""
        # 캐시에서 데이터 확인
        if file_path in self._data_cache:
            self.data = self._data_cache[file_path]
            return True
            
        # 파일이 존재하는지 확인
        if os.path.exists(file_path):
            print(f"데이터 로딩 중: {file_path}")
            df = pd.read_csv(file_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            
            # 캐시에 저장
            self._data_cache[file_path] = df
            self.data = df
            self._data_loaded = True
            return True
        return False
    
    @classmethod
    def get_cached_data(cls, file_path):
        """캐시된 데이터 가져오기"""
        if file_path in cls._data_cache:
            return cls._data_cache[file_path]
        return None
    
    @classmethod
    def clear_cache(cls):
        """캐시 초기화"""
        cls._data_cache.clear()
        cls._data_loaded = False
    
    def calculate_indicators(self, data, strategy, cache_key=None):
        """지표 계산 (캐싱 최적화)"""
        # 캐시 키 생성
        if cache_key is None:
            cache_key = f"{strategy}_{len(data)}_{data.index[-1] if len(data) > 0 else 'empty'}"
        
        if cache_key in self._indicators_cache:
            return self._indicators_cache[cache_key]
        
        df = data.copy()
        params = self.strategy_params[strategy]
        
        if strategy == 'conservative_ma':
            df['sma_short'] = df['close'].rolling(params['sma_short']).mean()
            df['sma_long'] = df['close'].rolling(params['sma_long']).mean()
            # Donchian Channel
            df['dc_high'] = df['high'].rolling(params['dc_period']).max()
            df['dc_low'] = df['low'].rolling(params['dc_period']).min()
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
        elif strategy == 'momentum_reversal':
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(params['rsi_period']).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(params['rsi_period']).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # Stochastic
            low_min = df['low'].rolling(params['stoch_k']).min()
            high_max = df['high'].rolling(params['stoch_k']).max()
            df['stoch_k'] = 100 * (df['close'] - low_min) / (high_max - low_min)
            df['stoch_d'] = df['stoch_k'].rolling(params['stoch_d']).mean()
            
        elif strategy == 'volatility_breakout':
            # Bollinger Bands
            df['bb_middle'] = df['close'].rolling(params['bb_period']).mean()
            bb_std = df['close'].rolling(params['bb_period']).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std * params['bb_std'])
            df['bb_lower'] = df['bb_middle'] - (bb_std * params['bb_std'])
            
            # ATR
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            true_range = np.maximum(high_low, np.maximum(high_close, low_close))
            df['atr'] = true_range.rolling(params['atr_period']).mean()
            
        elif strategy == 'trend_following':
            # MACD
            ema_fast = df['close'].ewm(span=params['ema_fast']).mean()
            ema_slow = df['close'].ewm(span=params['ema_slow']).mean()
            df['macd_line'] = ema_fast - ema_slow
            df['macd_signal'] = df['macd_line'].ewm(span=params['macd_signal']).mean()
            df['macd_histogram'] = df['macd_line'] - df['macd_signal']
            
        elif strategy == 'mean_reversion':
            # Bollinger Bands
            df['bb_middle'] = df['close'].rolling(params['bb_period']).mean()
            bb_std = df['close'].rolling(params['bb_period']).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std * params['bb_std'])
            df['bb_lower'] = df['bb_middle'] - (bb_std * params['bb_std'])
            
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(params['rsi_period']).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(params['rsi_period']).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
        elif strategy == 'defensive':
            df['sma'] = df['close'].rolling(params['sma_period']).mean()
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
        
        return df
    
    def generate_signals(self, df, strategy, cache_key=None):
        """신호 생성 (캐싱 최적화)"""
        # 캐시 키 생성
        if cache_key is None:
            cache_key = f"signals_{strategy}_{len(df)}_{df.index[-1] if len(df) > 0 else 'empty'}"
        
        if cache_key in self._signals_cache:
            return self._signals_cache[cache_key]
        
        params = self.strategy_params[strategy]
        
        if strategy == 'conservative_ma':
            # MA 크로스오버 신호
            ma_long_signal = (df['sma_short'] > df['sma_long']) & (df['sma_short'].shift(1) <= df['sma_long'].shift(1))
            ma_short_signal = (df['sma_short'] < df['sma_long']) & (df['sma_short'].shift(1) >= df['sma_long'].shift(1))
            
            # DC 돌파 신호
            dc_long_signal = df['close'] > df['dc_high'].shift(1)
            dc_short_signal = df['close'] < df['dc_low'].shift(1)
            
            # RSI 필터
            rsi_long_filter = df['rsi'] < params['rsi_oversold']
            rsi_short_filter = df['rsi'] > params['rsi_overbought']
            
            # 최종 신호 (MA + DC + RSI)
            long_signal = ma_long_signal & dc_long_signal & rsi_long_filter
            short_signal = ma_short_signal & dc_short_signal & rsi_short_filter
            
        elif strategy == 'momentum_reversal':
            long_signal = (df['rsi'] < params['rsi_oversold']) & (df['stoch_k'] < 20)
            short_signal = (df['rsi'] > params['rsi_overbought']) & (df['stoch_k'] > 80)
            
        elif strategy == 'volatility_breakout':
            long_signal = df['close'] <= df['bb_lower'] * 1.01
            short_signal = df['close'] >= df['bb_upper'] * 0.99
            
        elif strategy == 'trend_following':
            long_signal = (df['macd_line'] > df['macd_signal']) & (df['macd_line'].shift(1) <= df['macd_signal'].shift(1))
            short_signal = (df['macd_line'] < df['macd_signal']) & (df['macd_line'].shift(1) >= df['macd_signal'].shift(1))
            
        elif strategy == 'mean_reversion':
            long_signal = (df['close'] <= df['bb_lower']) & (df['rsi'] < params['rsi_oversold'])
            short_signal = (df['close'] >= df['bb_upper']) & (df['rsi'] > params['rsi_overbought'])
            
        elif strategy == 'defensive':
            long_signal = (df['close'] > df['sma']) & (df['rsi'] < params['rsi_oversold'])
            short_signal = (df['close'] < df['sma']) & (df['rsi'] > params['rsi_overbought'])
        
        df['long_signal'] = long_signal
        df['short_signal'] = short_signal
        
        # 캐시에 저장
        if cache_key is not None:
            self._signals_cache[cache_key] = df
        
        return df
    
    def run_improved_backtest(self, start_date, end_date, initial_capital=10000):
        """개선된 백테스트 실행"""
        print("=== 개선된 적응형 트레이딩 시스템 백테스트 시작 ===")
        
        # 데이터 필터링
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        mask = (self.data.index >= start_dt) & (self.data.index <= end_dt)
        test_data = self.data[mask].copy()
        
        if len(test_data) == 0:
            print("테스트 데이터가 없습니다.")
            return None
        
        print(f"테스트 기간: {start_date} ~ {end_date}")
        print(f"데이터 길이: {len(test_data)}개 캔들")
        
        # 성능 최적화: 배치 크기 설정
        batch_size = min(1000, len(test_data) // 10)  # 데이터의 10% 또는 최대 1000개
        print(f"배치 크기: {batch_size}개")
        
        # 백테스트 실행
        current_capital = initial_capital
        position = None
        entry_price = 0
        entry_time = None
        trades = []
        
        # 윈도우 크기
        window_size = 100
        
        # 성능 최적화: 단순 루프로 변경 (배치 처리 제거)
        for i in range(window_size, len(test_data)):
            current_time = test_data.index[i]
            
            # 성능 최적화: 필요한 최소 데이터만 사용
            lookback_window = min(200, i + 1)
            current_data = test_data.iloc[max(0, i - lookback_window + 1):i+1]
            
            # 캐시 키 생성
            cache_key = f"{i}_{len(current_data)}_{current_data.index[-1] if len(current_data) > 0 else 'empty'}"
            
            # 시장 상황 분석 (캐싱)
            if f"regime_{cache_key}" in self._market_regime_cache:
                market_regime = self._market_regime_cache[f"regime_{cache_key}"]
            else:
                market_regime = self.regime_detector.detect_market_regime(current_data)
                self._market_regime_cache[f"regime_{cache_key}"] = market_regime
            
            # 변동성 계산 (최적화)
            if len(current_data) >= 20:
                returns = current_data['close'].pct_change()
                volatility = returns.rolling(20).std().iloc[-1]
            else:
                volatility = 0.02  # 기본값
            
            # RSI 계산 (최적화)
            if len(current_data) >= 14:
                rsi = self.regime_detector._calculate_rsi(current_data['close'])
                current_rsi = rsi.iloc[-1]
            else:
                current_rsi = 50  # 기본값
            
            # 전략 선택 (캐싱)
            strategy_key = f"strategy_{market_regime}_{volatility:.4f}_{current_rsi:.2f}"
            if strategy_key in self._strategy_cache:
                selected_strategy = self._strategy_cache[strategy_key]
            else:
                selected_strategy = self.strategy_selector.select_strategy(market_regime, volatility, current_rsi)
                self._strategy_cache[strategy_key] = selected_strategy
            
            # 거래 가능 여부 확인
            can_trade, reason = self.risk_manager.can_trade(current_time, current_capital, initial_capital)
            
            if not can_trade:
                continue
            
            # 지표 계산 및 신호 생성 (캐싱)
            indicators_key = f"indicators_{selected_strategy}_{cache_key}"
            if indicators_key in self._indicators_cache:
                df_with_indicators = self._indicators_cache[indicators_key]
            else:
                df_with_indicators = self.calculate_indicators(current_data, selected_strategy, cache_key=indicators_key)
            
            signals_key = f"signals_{selected_strategy}_{cache_key}"
            if signals_key in self._signals_cache:
                df_with_signals = self._signals_cache[signals_key]
            else:
                df_with_signals = self.generate_signals(df_with_indicators, selected_strategy, cache_key=signals_key)
            
            # 현재 신호
            current_row = df_with_signals.iloc[-1]
            
            # 포지션 관리
            if position is None and can_trade:
                # 진입 신호
                if current_row['long_signal']:
                    position = 'long'
                    entry_price = current_row['close']
                    entry_time = current_time
                    
                    # 포지션 사이징
                    position_size = self.risk_manager.calculate_position_size(
                        current_capital, volatility, market_regime
                    )
                    
                    # 진입 수수료 계산
                    entry_fee = position_size * 0.0005  # 0.05%
                    current_capital -= entry_fee
                    
                    btc_amount = position_size / entry_price
                    print(f"{current_time}: 롱 진입 (전략: {selected_strategy}, 가격: {entry_price:.2f}, 금액: {position_size:.2f}달러, 수량: {btc_amount:.6f}BTC, fee: {entry_fee:.2f}달러)")
                    
                elif current_row['short_signal']:
                    position = 'short'
                    entry_price = current_row['close']
                    entry_time = current_time
                    
                    # 포지션 사이징
                    position_size = self.risk_manager.calculate_position_size(
                        current_capital, volatility, market_regime
                    )
                    
                    # 진입 수수료 계산
                    entry_fee = position_size * 0.0005  # 0.05%
                    current_capital -= entry_fee
                    
                    btc_amount = position_size / entry_price
                    print(f"{current_time}: 숏 진입 (전략: {selected_strategy}, 가격: {entry_price:.2f}, 금액: {position_size:.2f}달러, 수량: {btc_amount:.6f}BTC, fee: {entry_fee:.2f}달러)")
            
            elif position is not None:
                # 청산 신호
                should_exit = False
                exit_reason = ""
                
                if position == 'long':
                    if current_row['short_signal']:
                        should_exit = True
                        exit_reason = "숏 신호"
                    elif current_rsi > 80:
                        should_exit = True
                        exit_reason = "RSI 과매수"
                    elif current_row['close'] <= entry_price * 0.98:  # 2% 손절
                        should_exit = True
                        exit_reason = "2% 손절매"
                    # elif entry_time and (current_time - entry_time).total_seconds() > 3600:  # 1시간 후 강제 청산
                    #     should_exit = True
                    #     exit_reason = "시간 만료"
                
                elif position == 'short':
                    if current_row['long_signal']:
                        should_exit = True
                        exit_reason = "롱 신호"
                    elif current_rsi < 20:
                        should_exit = True
                        exit_reason = "RSI 과매도"
                    elif current_row['close'] >= entry_price * 1.02:  # 2% 손절
                        should_exit = True
                        exit_reason = "2% 손절매"
                    # elif entry_time and (current_time - entry_time).total_seconds() > 3600:  # 1시간 후 강제 청산
                    #     should_exit = True
                    #     exit_reason = "시간 만료"
                
                if should_exit:
                    # 거래 실행
                    exit_price = current_row['close']
                    pnl = self._calculate_pnl(entry_price, exit_price, position_size, position)
                    current_capital += pnl
                    
                    # 청산 수수료 계산
                    exit_fee = position_size * 0.0005  # 0.05%
                    current_capital -= exit_fee
                    
                    trades.append({
                        'entry_time': entry_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'exit_time': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'position': position,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl': pnl,
                        'strategy': selected_strategy,
                        'exit_reason': exit_reason,
                        'entry_fee': entry_fee,
                        'exit_fee': exit_fee,
                        'total_fee': entry_fee + exit_fee
                    })
                    
                    # 리스크 관리자 업데이트
                    self.risk_manager.update_trade_result(pnl, current_time)
                    
                    # PnL에 따른 색상 표시
                    total_fee = entry_fee + exit_fee
                    pnl_percent = (pnl / position_size) * 100
                    btc_amount = position_size / entry_price
                    if pnl > 0:
                        print(f"{current_time}: {position} 청산 [수익🟢] (진입가: {entry_price:.2f}달러, 청산가: {exit_price:.2f}달러, 수량: {btc_amount:.6f}BTC, 수익률: {pnl_percent:.2f}%, PnL: {pnl:.2f}달러, fee: {total_fee:.2f}달러, 자본: {current_capital:.2f}달러)")
                    else:
                        print(f"{current_time}: {position} 청산 [손실🔴] (진입가: {entry_price:.2f}달러, 청산가: {exit_price:.2f}달러, 수량: {btc_amount:.6f}BTC, 손실률: {pnl_percent:.2f}%, PnL: {pnl:.2f}달러, fee: {total_fee:.2f}달러, 자본: {current_capital:.2f}달러)")
                    
                    position = None
        
        # 결과 계산
        total_return = (current_capital - initial_capital) / initial_capital * 100
        winning_trades = len([t for t in trades if t['pnl'] > 0])
        win_rate = (winning_trades / len(trades) * 100) if len(trades) > 0 else 0
        
        # 최대 낙폭 계산
        max_drawdown = self._calculate_max_drawdown(initial_capital, trades)
        
        result = {
            'total_return': total_return,
            'final_capital': current_capital,
            'total_trades': len(trades),
            'win_rate': win_rate,
            'max_drawdown': max_drawdown,
            'trades': trades
        }
        
        return result
    
    def _calculate_pnl(self, entry_price, exit_price, capital, position_type):
        """PnL 계산"""
        if position_type == 'long':
            return (exit_price - entry_price) / entry_price * capital
        else:  # short
            return (entry_price - exit_price) / entry_price * capital
    
    def _calculate_max_drawdown(self, initial_capital, trades):
        """최대 낙폭 계산"""
        if not trades:
            return 0.0
        
        capital_series = [initial_capital]
        for trade in trades:
            capital_series.append(capital_series[-1] + trade['pnl'])
        
        capital_series = np.array(capital_series)
        peak = np.maximum.accumulate(capital_series)
        drawdown = (peak - capital_series) / peak * 100
        
        return np.max(drawdown)

# 전역 캐시 변수
_data_cache = {}

def main():
    """메인 실행 함수"""
    print("=== 개선된 적응형 트레이딩 시스템 ===")
    
    # 시스템 초기화
    system = ImprovedAdaptiveTradingSystem()
    
    # 데이터 로드 (간단한 캐싱)
    data_files = [
        "data/BTCUSDT/5m/BTCUSDT_5m_2018.csv"
    ]
    
    all_data = []
    for file_path in data_files:
        if file_path in _data_cache:
            all_data.append(_data_cache[file_path])
            print(f"캐시에서 데이터 로드: {file_path}")
        else:
            if system.load_data(file_path):
                _data_cache[file_path] = system.data
                all_data.append(system.data)
                print(f"데이터 로드 완료: {file_path}")
    
    if all_data:
        system.data = pd.concat(all_data, ignore_index=False).sort_index()
        print(f"전체 데이터: {len(system.data)}개 캔들")
        
        # 개선된 시스템 테스트 (2018년)
        result = system.run_improved_backtest('2018-01-01', '2018-12-31')
        
        if result:
            print(f"\n개선된 시스템 결과:")
            print(f"  총 수익률: {result['total_return']:.2f}%")
            print(f"  최종 자본: {result['final_capital']:.2f}")
            print(f"  총 거래: {result['total_trades']}회")
            print(f"  승률: {result['win_rate']:.2f}%")
            print(f"  최대 낙폭: {result['max_drawdown']:.2f}%")
            
            # 전략별 거래 분포
            strategy_trades = {}
            for trade in result['trades']:
                strategy = trade['strategy']
                if strategy not in strategy_trades:
                    strategy_trades[strategy] = 0
                strategy_trades[strategy] += 1
            
            print(f"\n전략별 거래 분포:")
            for strategy, count in strategy_trades.items():
                percentage = (count / result['total_trades']) * 100
                print(f"  {strategy}: {count}회 ({percentage:.1f}%)")
            
            # 결과 저장
            output = {
                'system_type': 'Improved Adaptive Trading System',
                'test_period': '2018-01-01 ~ 2018-12-31',
                'improvements': [
                    '동적 포지션 사이징',
                    '연속 손실 방지 메커니즘',
                    '시장 상황별 거래 빈도 조절',
                    '향상된 리스크 관리',
                    '하락장 특화 전략'
                ],
                'result': result,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            with open('improved_adaptive_results.json', 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            
            print(f"\n결과가 improved_adaptive_results.json에 저장되었습니다.")
    
    print("\n=== 완료 ===")

if __name__ == "__main__":
    main()
