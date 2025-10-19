"""
개선된 적응형 트레이딩 시스템 (V2.0)

=== 주요 개선사항 ===
1. MarketRegimeDetector: ADX 기반 횡보장/추세장 진단 강화
2. ImprovedRiskManager: 동적 포지션 사이징 로직 정교화 및 일원화
3. ImprovedStrategySelector: 시장 국면별 파라미터 세분화 (특히 횡보장/상승장)
4. 백테스트 로직: 포지션 사이징 로직 통합 및 최적화
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class ImprovedRiskManager:
    """개선된 리스크 관리자 (동적 포지션 사이징 로직 강화)"""
    
    def __init__(self):
        self.max_daily_loss = 0.02  # 일일 최대 손실 2%
        self.max_position_size = 0.8  # 최대 포지션 크기 80% (레버리지 1배 기준)
        self.consecutive_loss_limit = 3  # 연속 손실 제한
        self.cooldown_period = 12  # 쿨다운 기간 (1시간 / 5분봉 12개)
        self.daily_trade_limit = 5  # 일일 거래 제한
        
        # 상태 추적
        self.consecutive_losses = 0
        self.last_loss_time = None
        self.daily_trades = 0
        self.daily_pnl = 0
        self.last_reset_date = None
        self.initial_capital_snapshot = 0 # 초기 자본 스냅샷
    
    def initialize_capital(self, initial_capital):
        """초기 자본 설정"""
        self.initial_capital_snapshot = initial_capital
    
    def can_trade(self, current_time, current_capital):
        """거래 가능 여부 확인"""
        current_date = current_time.date()
        
        # 날짜 변경 시 리셋
        if self.last_reset_date != current_date:
            self.daily_trades = 0
            self.daily_pnl = 0
            self.last_reset_date = current_date
        
        # 일일 거래 제한
        if self.daily_trades >= self.daily_trade_limit:
            return False, "일일 거래 제한 초과"
        
        # 일일 손실 제한 (누적 PnL 기준)
        if self.initial_capital_snapshot > 0:
            daily_loss_ratio = abs(self.daily_pnl) / self.initial_capital_snapshot
            if daily_loss_ratio >= self.max_daily_loss and self.daily_pnl < 0:
                return False, "일일 손실 제한 도달 (Stop-Out)"
        
        # 연속 손실 제한
        if self.consecutive_losses >= self.consecutive_loss_limit:
            if self.last_loss_time and (current_time - self.last_loss_time).total_seconds() < self.cooldown_period * 300: # 5분봉 12개(1시간) 쿨다운
                return False, "연속 손실 쿨다운 중"
        
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
    
    def calculate_position_size(self, current_capital, volatility, market_regime):
        """동적 포지션 사이징 (시장 상황, 변동성, 연속 손실 기반)"""
        base_size = self.max_position_size
        
        # 1. 변동성 조정 (ATR 기반으로 대체 가능)
        if volatility > 0.035:  # 극심한 고변동성
            size_multiplier = 0.4
        elif volatility > 0.02:  # 일반적 고변동성
            size_multiplier = 0.7
        elif volatility < 0.008:  # 극심한 저변동성
            size_multiplier = 1.1
        else:
            size_multiplier = 1.0
        
        # 2. 시장 트렌드 조정
        if market_regime in ['crash', 'strong_downtrend']:
            size_multiplier *= 0.5  # 하락장에서는 50% 축소
        elif market_regime == 'downtrend':
            size_multiplier *= 0.7
        elif market_regime in ['low_volatility_sideways']:
            size_multiplier *= 0.8  # 지루한 횡보장에서는 소극적
        
        # 3. 연속 손실 조정
        if self.consecutive_losses > 0:
            # 연속 손실에 따라 기하급수적으로 축소
            size_multiplier *= (0.5 ** self.consecutive_losses)
        
        final_size_ratio = min(base_size * size_multiplier, self.max_position_size)
        
        # 최종 포지션 금액 = 현재 자본 * 최종 사이즈 비율
        return current_capital * final_size_ratio

class MarketRegimeDetector:
    """시장 상황 감지기 (ADX 추가로 횡보장/추세장 진단 강화)"""
    
    def __init__(self):
        self.trend_periods = [20, 50, 100]
        self.volatility_period = 20
        self.adx_period = 14
    
    def _calculate_adx(self, data):
        """ADX (Average Directional Index) 계산"""
        if len(data) < self.adx_period * 2:
            return 50.0 # 기본값
            
        df = data.copy()
        
        # True Range 계산
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        df['tr'] = np.maximum(high_low, np.maximum(high_close, low_close))
        
        # Directional Movement
        df['dm_plus'] = np.where((df['high'] > df['high'].shift()) & ((df['high'] - df['high'].shift()) > (df['low'].shift() - df['low'])), df['high'] - df['high'].shift(), 0)
        df['dm_minus'] = np.where((df['low'].shift() > df['low']) & ((df['low'].shift() - df['low']) > (df['high'] - df['high'].shift())), df['low'].shift() - df['low'], 0)
        
        # Smooth TR and DM
        atr = df['tr'].ewm(alpha=1/self.adx_period, adjust=False).mean()
        di_plus = (df['dm_plus'].ewm(alpha=1/self.adx_period, adjust=False).mean() / atr) * 100
        di_minus = (df['dm_minus'].ewm(alpha=1/self.adx_period, adjust=False).mean() / atr) * 100
        
        # DX and ADX
        df['dx'] = (np.abs(di_plus - di_minus) / (di_plus + di_minus)) * 100
        adx = df['dx'].ewm(alpha=1/self.adx_period, adjust=False).mean()
        
        return adx.iloc[-1]
    
    def detect_market_regime(self, data):
        """시장 상황 종합 분석"""
        if len(data) < max(self.trend_periods):
            return 'unknown'
        
        # 트렌드 분석 (평균 변화율)
        short_trend = data['close'].iloc[-self.trend_periods[0]:].pct_change().mean()
        mid_trend = data['close'].iloc[-self.trend_periods[1]:].pct_change().mean()
        long_trend = data['close'].iloc[-self.trend_periods[2]:].pct_change().mean()
        
        # 변동성 분석 (ATR로 대체 가능하나, 일단 StDev 유지)
        returns = data['close'].pct_change().dropna()
        volatility = returns.rolling(self.volatility_period).std().iloc[-1] if len(returns) >= self.volatility_period else 0
        
        # 추세 강도 분석 (ADX)
        adx_value = self._calculate_adx(data)
        
        # 시장 상황 분류
        # 1. 강한 추세장 (ADX > 30)
        if adx_value > 30:
            if short_trend > 0.002 and mid_trend > 0.001:
                return 'strong_uptrend'
            elif short_trend < -0.002 and mid_trend < -0.001:
                if volatility > 0.03:
                    return 'crash'  # 폭락장 (ADX와 고변동성 조합)
                else:
                    return 'strong_downtrend'
        
        # 2. 일반 추세장 (ADX > 20)
        elif adx_value > 20:
            if short_trend > 0.001 and mid_trend > 0.0005:
                return 'uptrend'
            elif short_trend < -0.001 and mid_trend < -0.0005:
                return 'downtrend'
        
        # 3. 횡보장 (ADX <= 20)
        else:
            if volatility > 0.02:
                return 'high_volatility_sideways'  # 고변동성 횡보 (박스권 매매)
            else:
                return 'low_volatility_sideways'  # 저변동성 횡보 (거래 최소화)
        
        return 'low_volatility_sideways' # 기본값
    
    def _calculate_rsi(self, prices, period=14):
        """RSI 계산 (보조 지표)"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

class ImprovedStrategySelector:
    """개선된 전략 선택기 (시장 상황별 파라미터 세분화)"""
    
    def __init__(self):
        self.strategies = {
            'trend_following': '트렌드 추종 전략 (MACD)',
            'mean_reversion': '평균 회귀 전략 (BB + RSI)',
            'volatility_breakout': '변동성 돌파 전략 (BB)'
        }
        
        # 시장 상황별 파라미터 맵핑
        self.market_params = {
            # 🟢 강한 상승장 (Trend Following 극대화)
            'strong_uptrend': {
                'rsi_oversold': 45,     # 진입 문턱 낮춤
                'rsi_overbought': 85,   # 청산 문턱 높임
                'bb_std': 2.5,          # 밴드를 넓게, 추세에 덜 민감
                'stop_loss': 0.05,      # 손절폭 확대 (추세 유지)
                'take_profit': 0.15,    # 익절폭 확대 (수익 극대화)
                'strategy': 'trend_following'
            },
            # 🟢 상승장 (Trend Following)
            'uptrend': {
                'rsi_oversold': 40,
                'rsi_overbought': 80,
                'bb_std': 2.0,
                'stop_loss': 0.04,
                'take_profit': 0.10,
                'strategy': 'trend_following'
            },
            # 🔴 폭락장 (Mean Reversion 극대화)
            'crash': {
                'rsi_oversold': 5,       # 극도 과매도에서만 반등 진입
                'rsi_overbought': 95,
                'bb_std': 1.0,           # 밴드를 좁게, 민감하게
                'stop_loss': 0.015,      # 초단기 손절 (더 빠른 손절)
                'take_profit': 0.04,     # 작은 수익이라도 빠르게 확보
                'strategy': 'mean_reversion'
            },
            # 🔴 강한 하락장 (Mean Reversion)
            'strong_downtrend': {
                'rsi_oversold': 10,
                'rsi_overbought': 90,
                'bb_std': 1.2,
                'stop_loss': 0.02,
                'take_profit': 0.05,
                'strategy': 'mean_reversion'
            },
            # 🔴 하락장 (Mean Reversion)
            'downtrend': {
                'rsi_oversold': 15,
                'rsi_overbought': 85,
                'bb_std': 1.5,
                'stop_loss': 0.025,
                'take_profit': 0.06,
                'strategy': 'mean_reversion'
            },
            # ⏸️ 고변동성 횡보 (Mean Reversion + Volatility Breakout)
            'high_volatility_sideways': {
                'rsi_oversold': 25,
                'rsi_overbought': 75,
                'bb_std': 1.8,           # 박스권 매매에 적합한 민감도
                'stop_loss': 0.03,
                'take_profit': 0.08,
                'strategy': 'mean_reversion' # 박스권 중앙에서는 MR, 돌파시 VB로 전환하는 복합 전략 고려
            },
            # ⏸️ 저변동성 횡보 (Mean Reversion, 거래 최소화)
            'low_volatility_sideways': {
                'rsi_oversold': 20,      # 과매도/과매수 신호의 신뢰도 높임
                'rsi_overbought': 80,
                'bb_std': 1.5,
                'stop_loss': 0.01,       # 손절폭을 매우 좁게
                'take_profit': 0.02,     # 익절폭을 매우 좁게
                'strategy': 'mean_reversion'
            }
        }
    
    def get_market_condition(self, market_regime):
        """시장 상황에 따른 파라미터 반환"""
        return self.market_params.get(market_regime)
    
    def select_strategy(self, market_regime):
        """시장 상황에 따른 전략 선택"""
        params = self.get_market_condition(market_regime)
        return params['strategy'] if params else 'mean_reversion' # 안전장치

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
        
        # 전략별 기본 파라미터 (MarketParams와 충돌 방지)
        self.strategy_params = {
            'trend_following': {
                'ema_fast': 12,
                'ema_slow': 26,
                'macd_signal': 9,
            },
            'mean_reversion': {
                'bb_period': 20,
                'rsi_period': 14
            },
            'volatility_breakout': {
                'bb_period': 20,
            }
        }
        
        self.data = None
    
    # (load_data, get_cached_data, clear_cache 메서드는 변경 없음 - 생략)
    def load_data(self, file_path):
        """데이터 로드 (캐싱 적용)"""
        if file_path in self._data_cache:
            self.data = self._data_cache[file_path]
            return True
        if os.path.exists(file_path):
            print(f"데이터 로딩 중: {file_path}")
            df = pd.read_csv(file_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            self._data_cache[file_path] = df
            self.data = df
            self._data_loaded = True
            return True
        return False
    
    def calculate_indicators(self, data, strategy, cache_key=None, market_params=None):
        """지표 계산 (캐싱 최적화)"""
        # 캐시 키 생성 및 확인 (생략)
        if cache_key in self._indicators_cache:
            return self._indicators_cache[cache_key]
        
        df = data.copy()
        params = self.strategy_params.get(strategy, {}) # 안전하게 get 사용
        
        # market_params에서 bb_std 가져오기
        bb_std_value = market_params.get('bb_std', 2.0) if market_params else 2.0
        
        # Mean Reversion / Volatility Breakout 전략 (볼린저 밴드 + RSI)
        if strategy in ['mean_reversion', 'volatility_breakout']:
            bb_period = params.get('bb_period', 20)
            rsi_period = params.get('rsi_period', 14)
            
            # Bollinger Bands
            df['bb_middle'] = df['close'].rolling(bb_period).mean()
            bb_std = df['close'].rolling(bb_period).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std * bb_std_value)
            df['bb_lower'] = df['bb_middle'] - (bb_std * bb_std_value)
            
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(rsi_period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(rsi_period).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
        # Trend Following 전략 (MACD)
        elif strategy == 'trend_following':
            ema_fast = params.get('ema_fast', 12)
            ema_slow = params.get('ema_slow', 26)
            macd_signal = params.get('macd_signal', 9)
            
            ema_fast_line = df['close'].ewm(span=ema_fast, adjust=False).mean()
            ema_slow_line = df['close'].ewm(span=ema_slow, adjust=False).mean()
            df['macd_line'] = ema_fast_line - ema_slow_line
            df['macd_signal'] = df['macd_line'].ewm(span=macd_signal, adjust=False).mean()
            df['macd_histogram'] = df['macd_line'] - df['macd_signal']
        
        # ... 기타 전략은 현재 사용하지 않으므로 생략 ...
        
        if cache_key is not None:
            self._indicators_cache[cache_key] = df
            
        return df
    
    def generate_signals(self, df, strategy, cache_key=None, market_params=None):
        """신호 생성 (캐싱 최적화)"""
        if cache_key in self._signals_cache:
            return self._signals_cache[cache_key]
        
        df = df.copy() # 원본 데이터 보호
        
        # market_params에서 RSI 파라미터 가져오기 (필수)
        rsi_oversold = market_params.get('rsi_oversold', 30)
        rsi_overbought = market_params.get('rsi_overbought', 70)
        
        long_signal = pd.Series(False, index=df.index)
        short_signal = pd.Series(False, index=df.index)
        
        if strategy == 'trend_following':
            # MACD 크로스오버
            long_signal = (df['macd_line'] > df['macd_signal']) & (df['macd_line'].shift(1) <= df['macd_signal'].shift(1))
            short_signal = (df['macd_line'] < df['macd_signal']) & (df['macd_line'].shift(1) >= df['macd_signal'].shift(1))
            
        elif strategy == 'mean_reversion':
            # BB 하단 터치 & RSI 과매도 (롱 진입)
            long_signal = (df['close'] <= df['bb_lower']) & (df['rsi'] < rsi_oversold)
            # BB 상단 터치 & RSI 과매수 (숏 진입)
            short_signal = (df['close'] >= df['bb_upper']) & (df['rsi'] > rsi_overbought)
            
        elif strategy == 'volatility_breakout':
            # BB 밴드 돌파 (추세 전환 포착)
            # 하단 돌파 시 숏, 상단 돌파 시 롱 (추세 추종과 유사)
            long_signal = (df['close'] > df['bb_upper']) & (df['close'].shift(1) <= df['bb_upper'].shift(1))
            short_signal = (df['close'] < df['bb_lower']) & (df['close'].shift(1) >= df['bb_lower'].shift(1))
        
        df['long_signal'] = long_signal
        df['short_signal'] = short_signal
        
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
        
        # 리스크 관리자 초기화
        self.risk_manager.initialize_capital(initial_capital)
        self.risk_manager.daily_trades = 0
        self.risk_manager.daily_pnl = 0
        self.risk_manager.last_reset_date = start_dt.date() # 초기 리셋
        
        # 백테스트 변수
        current_capital = initial_capital
        position = None
        entry_price = 0
        entry_time = None
        position_size = 0 # 포지션 진입 시 금액
        btc_amount = 0 # 포지션 진입 시 수량
        trades = []
        window_size = 200 # 지표 계산을 위한 룩백 윈도우
        
        # 백테스트 실행
        for i in range(window_size, len(test_data)):
            current_time = test_data.index[i]
            
            # 필요한 최소 데이터만 슬라이싱
            current_data = test_data.iloc[max(0, i - window_size + 1):i+1]
            
            # 시장 상황 분석 (캐싱)
            market_regime = self.regime_detector.detect_market_regime(current_data)
            
            # 변동성 계산 (StDev)
            volatility = current_data['close'].pct_change().rolling(20).std().iloc[-1] if len(current_data) >= 20 else 0.02
            
            # RSI 계산
            rsi = self.regime_detector._calculate_rsi(current_data['close'])
            current_rsi = rsi.iloc[-1] if len(rsi) >= 14 else 50
            
            # 전략 선택 및 파라미터 가져오기
            selected_strategy = self.strategy_selector.select_strategy(market_regime)
            market_params = self.strategy_selector.get_market_condition(market_regime)
            
            # 거래 가능 여부 확인
            can_trade, reason = self.risk_manager.can_trade(current_time, current_capital)
            
            # 포지션 관리 및 청산
            if position is not None:
                # 청산 로직 (손익실현 및 신호 반전)
                should_exit = False
                exit_reason = ""
                
                # 시장 상황별 파라미터 적용
                stop_loss = market_params['stop_loss']
                take_profit = market_params['take_profit']
                rsi_oversold = market_params['rsi_oversold']
                rsi_overbought = market_params['rsi_overbought']
                
                # 지표 계산 및 신호 생성 (청산 시점에 필요)
                indicators_key = f"indicators_{selected_strategy}_{i}"
                df_with_indicators = self.calculate_indicators(current_data, selected_strategy, cache_key=indicators_key, market_params=market_params)
                signals_key = f"signals_{selected_strategy}_{i}"
                df_with_signals = self.generate_signals(df_with_indicators, selected_strategy, cache_key=signals_key, market_params=market_params)
                current_row = df_with_signals.iloc[-1]

                # 롱 포지션 청산 조건
                if position == 'long':
                    if current_row['short_signal']:
                        should_exit = True
                        exit_reason = "반대 신호 (숏)"
                    elif current_rsi > rsi_overbought:
                        should_exit = True
                        exit_reason = f"RSI 과매수({rsi_overbought}) 청산"
                    elif current_row['close'] <= entry_price * (1 - stop_loss):
                        should_exit = True
                        exit_reason = f"손절매 ({stop_loss*100:.1f}%)"
                    elif current_row['close'] >= entry_price * (1 + take_profit):
                        should_exit = True
                        exit_reason = f"익절 ({take_profit*100:.1f}%)"
                
                # 숏 포지션 청산 조건
                elif position == 'short':
                    if current_row['long_signal']:
                        should_exit = True
                        exit_reason = "반대 신호 (롱)"
                    elif current_rsi < rsi_oversold:
                        should_exit = True
                        exit_reason = f"RSI 과매도({rsi_oversold}) 청산"
                    elif current_row['close'] >= entry_price * (1 + stop_loss):
                        should_exit = True
                        exit_reason = f"손절매 ({stop_loss*100:.1f}%)"
                    elif current_row['close'] <= entry_price * (1 - take_profit):
                        should_exit = True
                        exit_reason = f"익절 ({take_profit*100:.1f}%)"
                
                if should_exit:
                    # 거래 실행 및 PnL 계산
                    exit_price = current_row['close']
                    pnl = self._calculate_pnl(entry_price, exit_price, position_size, position)
                    
                    # 수수료 계산 및 차감
                    exit_fee = position_size * 0.0005
                    total_fee = (position_size * 0.0005) + exit_fee
                    
                    current_capital += pnl - total_fee
                    
                    trades.append({
                        'entry_time': entry_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'exit_time': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'position': position,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl': pnl - total_fee, # 순 PnL
                        'strategy': selected_strategy,
                        'exit_reason': exit_reason,
                        'total_fee': total_fee,
                        'market_regime': market_regime
                    })
                    
                    # 리스크 관리자 업데이트
                    self.risk_manager.update_trade_result(pnl - total_fee, current_time)
                    
                    pnl_percent = ((pnl - total_fee) / position_size) * 100
                    
                    if pnl > total_fee:
                        print(f"{current_time}: {position} 청산 [수익🟢] (P/L: {pnl_percent:.2f}%, 자본: {current_capital:.2f}달러, 사유: {exit_reason}, 국면: {market_regime})")
                    else:
                        print(f"{current_time}: {position} 청산 [손실🔴] (P/L: {pnl_percent:.2f}%, 자본: {current_capital:.2f}달러, 사유: {exit_reason}, 국면: {market_regime})")
                    
                    position = None
                    position_size = 0 # 포지션 사이즈 리셋
            
            # 포지션 진입
            if position is None and can_trade:
                
                # 지표 계산 및 신호 생성 (진입 시점에 필요)
                indicators_key = f"indicators_{selected_strategy}_{i}"
                df_with_indicators = self.calculate_indicators(current_data, selected_strategy, cache_key=indicators_key, market_params=market_params)
                signals_key = f"signals_{selected_strategy}_{i}"
                df_with_signals = self.generate_signals(df_with_indicators, selected_strategy, cache_key=signals_key, market_params=market_params)
                current_row = df_with_signals.iloc[-1]
                
                # 동적 포지션 사이즈 결정
                position_size = self.risk_manager.calculate_position_size(
                    current_capital, volatility, market_regime)
                
                # 진입 신호 확인
                if current_row['long_signal']:
                    position = 'long'
                    entry_price = current_row['close']
                    entry_time = current_time
                    
                    # 진입 수수료 계산 및 차감
                    entry_fee = position_size * 0.0005
                    current_capital -= entry_fee
                    
                    btc_amount = position_size / entry_price
                    print(f"{current_time}: 롱 진입 (전략: {selected_strategy}, 가격: {entry_price:.2f}, 사이즈: {position_size:.2f}달러, fee: {entry_fee:.2f}달러, 국면: {market_regime})")
                    
                elif current_row['short_signal']:
                    position = 'short'
                    entry_price = current_row['close']
                    entry_time = current_time
                    
                    # 진입 수수료 계산 및 차감
                    entry_fee = position_size * 0.0005
                    current_capital -= entry_fee
                    
                    btc_amount = position_size / entry_price
                    print(f"{current_time}: 숏 진입 (전략: {selected_strategy}, 가격: {entry_price:.2f}, 사이즈: {position_size:.2f}달러, fee: {entry_fee:.2f}달러, 국면: {market_regime})")

        # ... (결과 계산 및 출력 로직은 변경 없음 - 생략) ...
        # 결과 계산
        total_return = (current_capital - initial_capital) / initial_capital * 100
        winning_trades = len([t for t in trades if t['pnl'] > 0])
        win_rate = (winning_trades / len(trades) * 100) if len(trades) > 0 else 0
        max_drawdown = self._calculate_max_drawdown(initial_capital, trades)
        yearly_performance = self._analyze_yearly_performance(trades, initial_capital)
        
        result = {
            'total_return': total_return,
            'final_capital': current_capital,
            'total_trades': len(trades),
            'win_rate': win_rate,
            'max_drawdown': max_drawdown,
            'trades': trades,
            'yearly_performance': yearly_performance
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
        current_capital = initial_capital
        for trade in trades:
            current_capital += trade['pnl']
            capital_series.append(current_capital)
        
        capital_series = np.array(capital_series)
        peak = np.maximum.accumulate(capital_series)
        # 0으로 나누는 오류 방지
        drawdown = np.where(peak > 0, (peak - capital_series) / peak * 100, 0)
        
        return np.max(drawdown)
    
    def _analyze_yearly_performance(self, trades, initial_capital):
        """연도별 성과 분석"""
        # (기존 코드와 동일하게 유지)
        yearly_stats = {}
        
        current_capital = initial_capital
        
        for trade in trades:
            entry_time = pd.to_datetime(trade['entry_time'])
            year = entry_time.year
            
            if year not in yearly_stats:
                # 해당 연도의 시작 자본을 설정 (이전 연도의 최종 자본)
                start_capital = yearly_stats.get(year - 1, {}).get('final_capital', initial_capital)
                
                yearly_stats[year] = {
                    'trades': 0,
                    'wins': 0,
                    'total_pnl': 0,
                    'total_fee': 0,
                    'start_capital': start_capital
                }
            
            yearly_stats[year]['trades'] += 1
            yearly_stats[year]['total_pnl'] += trade['pnl']
            yearly_stats[year]['total_fee'] += trade['total_fee']
            
            if trade['pnl'] > 0:
                yearly_stats[year]['wins'] += 1
        
        # 연도별 자본 계산 및 수익률 계산
        sorted_years = sorted(yearly_stats.keys())
        for i, year in enumerate(sorted_years):
            stats = yearly_stats[year]
            
            # 기준 자본 설정 (첫 해는 초기 자본, 이후는 전 해의 최종 자본)
            base_capital = initial_capital if i == 0 else yearly_stats[sorted_years[i-1]]['final_capital']
            
            stats['return_pct'] = (stats['total_pnl'] / base_capital) * 100
            stats['final_capital'] = base_capital + stats['total_pnl']
            stats['win_rate'] = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0
        
        return yearly_stats

# 전역 캐시 변수
_data_cache = {}

def main():
    """메인 실행 함수"""
    print("=== 개선된 적응형 트레이딩 시스템 (V2.0) ===")
    
    # 시스템 초기화
    system = ImprovedAdaptiveTradingSystem()
    
    # 데이터 로드 (간단한 캐싱)
    data_files = [
        "data/BTCUSDT/5m/BTCUSDT_5m_2018.csv",
        "data/BTCUSDT/5m/BTCUSDT_5m_2019.csv",
        # 필요하다면 2020년 데이터도 추가하여 일반화 성능 확인
        # "data/BTCUSDT/5m/BTCUSDT_5m_2020.csv" 
    ]
    
    all_data = []
    for file_path in data_files:
        if file_path in _data_cache:
            all_data.append(_data_cache[file_path])
        else:
            if system.load_data(file_path):
                _data_cache[file_path] = system.data
                all_data.append(system.data)
    
    if all_data:
        system.data = pd.concat(all_data, ignore_index=False).sort_index()
        print(f"전체 데이터: {len(system.data)}개 캔들")
        
        # 개선된 시스템 테스트 (2018년~2019년)
        result = system.run_improved_backtest('2018-01-01', '2019-12-31')
        
        if result:
            print(f"\n개선된 시스템 결과:")
            print(f"  총 수익률: {result['total_return']:.2f}%")
            print(f"  최종 자본: {result['final_capital']:.2f}")
            print(f"  총 거래: {result['total_trades']}회")
            print(f"  승률: {result['win_rate']:.2f}%")
            print(f"  최대 낙폭: {result['max_drawdown']:.2f}%")
            
            # 연도별 성과 출력
            print(f"\n📅 연도별 성과 분석:")
            print("-" * 60)
            for year in sorted(result['yearly_performance'].keys()):
                stats = result['yearly_performance'][year]
                print(f"{year}년: 거래 {stats['trades']:3d}회, 승률 {stats['win_rate']:5.1f}%, "
                      f"수익률 {stats['return_pct']:7.2f}%, 최종자본 ${stats['final_capital']:8.2f}, "
                      f"수수료 ${stats['total_fee']:6.2f}")
            
            # 전략별 거래 분포 (국면별 분석)
            regime_trades = {}
            for trade in result['trades']:
                regime = trade['market_regime']
                strategy = trade['strategy']
                key = f"{regime} ({strategy})"
                if key not in regime_trades:
                    regime_trades[key] = {'count': 0, 'pnl_sum': 0}
                regime_trades[key]['count'] += 1
                regime_trades[key]['pnl_sum'] += trade['pnl']
            
            print(f"\n시장 국면별/전략별 거래 분포:")
            for key, data in sorted(regime_trades.items(), key=lambda item: item[1]['count'], reverse=True):
                percentage = (data['count'] / result['total_trades']) * 100
                avg_pnl = data['pnl_sum'] / data['count'] if data['count'] > 0 else 0
                print(f"  {key}: {data['count']}회 ({percentage:.1f}%), 평균 PnL: {avg_pnl:.2f}달러")
            
            # 결과 저장
            output = {
                'system_type': 'Improved Adaptive Trading System V2.0',
                'test_period': '2018-01-01 ~ 2019-12-31',
                'improvements': [
                    'ADX 기반 시장 국면 진단 강화',
                    '동적 포지션 사이징 로직 일원화',
                    '극단적인 시장별 파라미터 세분화 (상승/하락/횡보)',
                    '하락장/폭락장 초단기 손절 강화'
                ],
                'result': result,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # 파일명을 구분하여 저장
            with open('improved_adaptive_results_v2.json', 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            
            print(f"\n결과가 improved_adaptive_results_v2.json에 저장되었습니다.")
    
    print("\n=== 완료 ===")

if __name__ == "__main__":
    main()