#-*-coding:utf-8 -*-
'''
바이낸스 선물거래 1분봉 MA + 추세 추종 + 물타기 전략 백테스트

=== 전략 구성 ===
1. 기본 MA: 5MA와 20MA 크로스오버
2. 추세 추종: 5가지 추세 지표 조합
3. 양방향 거래: 롱/숏 모두 지원
4. 물타기 로직: 가격 하락률 기반 + 상승/하락 신호 동시 만족
5. 자산 분할: 200분할하여 단계별 투자

=== 진입 조건 ===
롱 진입: 5MA > 20MA + 추세 지표 3개 이상 만족
숏 진입: 5MA < 20MA + 추세 지표 3개 이상 만족

=== 물타기 로직 ===
1차 물타기: 진입가 대비 -1% 하락 시 + 상승 신호
2차 물타기: 진입가 대비 -2% 하락 시 + 상승 신호  
3차 물타기: 진입가 대비 -3% 하락 시 + 상승 신호
4차 물타기: 진입가 대비 -4% 하락 시 + 상승 신호

물타기 자본: 각 단계별 누적 총 개수
- 최초 진입: 1개
- 1차 물타기: 2개 (총 3개)
- 2차 물타기: 6개 (총 9개)
- 3차 물타기: 18개 (총 27개)
- 4차 물타기: 54개 (총 81개)

=== 청산 조건 ===
1. 수익 실현: 평균단가 기준 0.3% 이상 수익 + MA 크로스오버 신호
    - 롱: 평균단가 기준 0.3% 이상 + 5MA < 20MA (데드크로스)
    - 숏: 평균단가 기준 0.3% 이상 + 5MA > 20MA (골든크로스)

2. 손절처리: 4차 물타기 완료 후 1배 기준 -1% 하락 시
    - 모든 물타기 기회 소진 후 리스크 관리
    - 초기 진입가 대비 -1% 손실 시 강제 청산

3. 백테스트 종료: 마지막 데이터에서 보유 포지션 강제 청산

=== 추세 지표 (5가지) ===
1. 모멘텀 (5분, 10분)
2. 추세 연속성 (5분 윈도우)
3. 볼린저 밴드 위치
4. RSI (14분)
5. 거래량 증가율

=== 전략 특징 ===
- 체계적인 물타기로 평균단가 낮춤
- 평균단가 기준 수익 실현으로 물타기 효과 극대화
- 수익 실현과 손절처리로 리스크 관리
- 추세 신호와 가격 조건을 동시에 만족해야 물타기 실행
- 최대 4차까지 물타기하여 회복 기회 제공
- 200분할 자산으로 리스크 분산
- 롱/숏 양방향 거래로 시장 방향성에 관계없이 수익 추구
'''

import sys, os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
import ccxt
import time
import datetime as dt
import logging
import traceback
import myBinance
import ende_key  #암복호화키
import my_key    #업비트 시크릿 액세스키
import telegram_sender as line_alert
import numpy as np
import json

# ========================= 전역 설정 변수 =========================
# 기본 설정값
DEFAULT_LEVERAGE = 20                 # 기본 레버리지
DEFAULT_CHARGE = 0.001                # 기본 수수료 (0.1% = 0.001)
INVESTMENT_RATIO = 1.0                # 투자 비율 (100%)
DIVIDE = 200                          # 자산 분할 수 (162분할)

# 기본 추세 지표 설정값
DEFAULT_TREND_CONTINUITY_MIN = 3      # 최소 추세 연속성 (3일)
DEFAULT_RSI_OVERSOLD = 30             # RSI 과매도 기준
DEFAULT_RSI_OVERBOUGHT = 70           # RSI 과매수 기준
DEFAULT_MIN_VOLUME_RATIO = 1.2        # 최소 거래량 비율 (20일 평균 대비)
DEFAULT_MA1_PERIOD = 5                # MA1 기간 (5일선)
DEFAULT_MA2_PERIOD = 20               # MA2 기간 (20일선)
DEFAULT_MA_TIMEFRAME = '1m'           # MA 계산 시간프레임 (1분)
DEFAULT_TARGET_REVENUE_RATE = 0.3     # 기본 목표 수익률 (0.3%)

# 거래할 코인 목록 (비트코인만)
ACTIVE_COINS = ['BTC/USDT']

# ========================= 추세 지표 계산 함수 =========================
def calculate_trend_indicators(df, coin_ticker):
    """
    추세 지표 계산 (HMA_Backtest.py와 동일, 코인별 설정 적용)
    
    === 계산되는 지표들 ===
    1. 모멘텀 (5일, 10일): 가격 변화의 강도와 방향
    2. 추세 강도: 가격 변화율의 표준편차로 변동성 측정
    3. 추세 연속성: 연속 상승/하락 일수로 추세 지속성 확인
    4. 볼린저 밴드: 가격의 상대적 위치 (0=하단, 1=상단)
    5. RSI: 상대강도지수로 과매수/과매도 상태 판단
    """
    # 코인별 설정 가져오기
    ma1_period = DEFAULT_MA1_PERIOD
    ma2_period = DEFAULT_MA2_PERIOD
    trend_continuity_min = DEFAULT_TREND_CONTINUITY_MIN
    rsi_oversold = DEFAULT_RSI_OVERSOLD
    rsi_overbought = DEFAULT_RSI_OVERBOUGHT
    
    # 1. 가격 모멘텀 (현재가 - N일 전 가격)
    df['momentum_5'] = df['close'] - df['close'].shift(5)   # 5일 모멘텀
    df['momentum_10'] = df['close'] - df['close'].shift(10) # 10일 모멘텀
    
    # 2. 추세 강도 (가격 변화율의 표준편차)
    df['price_change'] = df['close'].pct_change()
    df['trend_strength'] = df['price_change'].rolling(20).std()
    
    # 3. 추세 방향 (연속 상승/하락 일수)
    # 양수: 상승 연속, 음수: 하락 연속, 절댓값이 클수록 강한 추세
    df['trend_direction'] = np.where(df['close'] > df['close'].shift(1), 1, -1)
    df['trend_continuity'] = df['trend_direction'].rolling(5).sum()  # 5일 윈도우 (HMA_Backtest.py와 동일)
    
    # 4. 볼린저 밴드 기반 추세
    df['bb_upper'] = df['close'].rolling(20).mean() + 2 * df['close'].rolling(20).std()
    df['bb_lower'] = df['close'].rolling(20).mean() - 2 * df['close'].rolling(20).std()
    # 0-division 방지
    width = (df['bb_upper'] - df['bb_lower']).replace(0, np.nan)
    df['bb_position'] = ((df['close'] - df['bb_lower']) / width).clip(0, 1)
    
    # 5. RSI 기반 추세 (14분)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    # 0-division 방지
    rs = np.where(loss == 0, np.inf, gain / loss)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # 6. 거래량 증가율 (20분 평균 대비)
    df['volume_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
    
    # 6. 코인별 MA 계산
    df[f'ma_{ma1_period}'] = df['close'].rolling(ma1_period).mean()
    df[f'ma_{ma2_period}'] = df['close'].rolling(ma2_period).mean()
    
    return df

# ========================= 로깅 시스템 설정 =========================
def setup_logging():
    """로깅 시스템 초기화"""
    # 로그 디렉토리 생성 (소스 파일과 같은 위치)
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    # 로그 파일명 (날짜별)
    today = dt.datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(log_dir, f"MA_Martingale_v1_{today}.log")
    
    # 거래 기록용 별도 로그 파일
    trade_log_file = os.path.join(log_dir, "MA_Martingale_v1_list.log")
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()  # 콘솔에도 출력
        ]
    )
    
    # 거래 기록용 로거 설정
    trade_logger = logging.getLogger('trade_logger')
    trade_logger.setLevel(logging.INFO)
    trade_logger.handlers = []  # 기존 핸들러 제거
    trade_logger.addHandler(logging.FileHandler(trade_log_file, encoding='utf-8'))
    
    # 외부 라이브러리 로그 레벨 조정
    logging.getLogger('ccxt').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    return logging.getLogger(__name__), trade_logger

# 로거 초기화
logger, trade_logger = setup_logging()

# ========================= 로깅 유틸리티 함수 =========================
def log_trade_action(action_type, coin_ticker, position_side, price, quantity, reason="", profit=0, profit_rate=0):
    """거래 기록 로깅 (JSON 형식)"""
    try:
        trade_record = {
            "timestamp": dt.datetime.now().isoformat(),
            "action": action_type,  # BUY, SELL, MARTINGALE, STOP_LOSS
            "coin": coin_ticker,
            "position": position_side,  # LONG, SHORT
            "price": round(price, 2),
            "quantity": round(quantity, 3),
            "reason": reason,
            "profit_usdt": round(profit, 2) if profit != 0 else 0,
            "profit_rate": round(profit_rate, 2) if profit_rate != 0 else 0
        }
        
        # JSON 형식으로 로그 기록
        trade_logger.info(f"TRADE: {json.dumps(trade_record, ensure_ascii=False)}")
        
        # 한 줄 요약도 함께 기록
        if action_type in ['BUY', 'MARTINGALE']:
            summary = f"📈 {action_type} | {coin_ticker} {position_side} | 가격: {price:.2f} | 수량: {quantity:.3f} | 사유: {reason}"
        elif action_type == 'SELL':
            summary = f"💰 {action_type} | {coin_ticker} {position_side} | 가격: {price:.2f} | 수량: {quantity:.3f} | 수익: {profit:+.2f} USDT ({profit_rate:+.2f}%) | 사유: {reason}"
        elif action_type == 'STOP_LOSS':
            summary = f"🛑 {action_type} | {coin_ticker} {position_side} | 가격: {price:.2f} | 수량: {quantity:.3f} | 손실: {profit:+.2f} USDT ({profit_rate:+.2f}%) | 사유: {reason}"
        
        trade_logger.info(f"SUMMARY: {summary}")
        
    except Exception as e:
        logger.error(f"거래 기록 로깅 실패: {e}")

def log_error(error_msg, error_detail=None):
    """오류 로깅"""
    try:
        logger.error(f"오류: {error_msg}")
        if error_detail:
            logger.error(f"상세: {error_detail}")
        # 심각한 오류는 텔레그램으로도 전송
        if "청산" in error_msg or "API" in error_msg or "거래" in error_msg:
            alert_msg = f"🚨 봇 오류 발생: {error_msg}"
            line_alert.SendMessage(alert_msg)
    except Exception as e:
        print(f"로깅 시스템 오류: {e}")

def log_position_status(position, entry_price, current_price, coin_symbol="", slices_count=0):
    """포지션 상태 로깅"""
    try:
        if position == 1:  # 포지션 보유 중
            revenue_rate = (current_price - entry_price) / entry_price * 100.0
            coin_leverage = DEFAULT_LEVERAGE
            roi = revenue_rate * coin_leverage
            msg = f"포지션 상태 | 보유 중 | 진입가: {entry_price:.2f} | 현재가: {current_price:.2f} | 수익률: {revenue_rate:+.2f}% | ROI({coin_leverage}배): {roi:+.2f}% | 슬라이스: {slices_count}개"
            if coin_symbol:
                msg += f" | 코인: {coin_symbol}"
            logger.info(msg)
        else:
            logger.info("포지션 상태 | 포지션 없음")
    except Exception as e:
        logger.error(f"포지션 상태 로깅 실패: {e}")

def create_daily_report(dic, balance):
    """일일 리포트 생성"""
    try:
        # 현재 시간
        current_time = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 기본 정보
        report = f"📊 MA + 추세 전략 봇 일일 리포트\n"
        report += f"📅 {current_time}\n"
        report += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # 자본 정보
        start_money = dic.get('start_money', 0)
        current_money = dic.get('my_money', 0)
        today_profit = dic.get('today', 0)
        yesterday_profit = dic.get('yesterday', 0)
        
        report += f"💰 자본 현황\n"
        report += f"• 시작 자본: {start_money:.2f} USDT\n"
        report += f"• 현재 자본: {current_money:.2f} USDT\n"
        report += f"• 오늘 수익: {today_profit:+.2f} USDT\n"
        report += f"• 어제 수익: {yesterday_profit:+.2f} USDT\n"
        report += f"• 총 수익률: {((current_money - start_money) / start_money * 100):+.2f}%\n\n"
        
        # 코인별 상세 정보
        coins_info = dic.get('coins', {})
        if coins_info:
            report += f"🪙 코인별 상세 현황\n"
            report += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            
            for coin_ticker, coin_data in coins_info.items():
                report += f"\n📈 {coin_ticker}\n"
                
                # 롱 포지션 정보
                long_data = coin_data.get('long', {})
                long_position = long_data.get('position', 0)
                long_entry_price = long_data.get('entry_price', 0)
                long_slices = long_data.get('slices_count', 0)
                long_trades = long_data.get('total_trades', 0)
                long_success = long_data.get('success_trades', 0)
                long_failed = long_data.get('failed_trades', 0)
                long_success_rate = long_data.get('success_rate', 0.0)
                long_profit = long_data.get('total_profit', 0)
                
                if long_position == 1:
                    report += f"🟢 롱 포지션 보유 중\n"
                    report += f"   • 진입가: {long_entry_price:.2f} USDT\n"
                    report += f"   • 슬라이스: {long_slices}개\n"
                else:
                    report += f"⚪ 롱 포지션 없음\n"
                
                report += f"   • 총 거래: {long_trades}회\n"
                report += f"   • 성공: {long_success}회, 실패: {long_failed}회\n"
                report += f"   • 성공률: {long_success_rate:.1f}%\n"
                report += f"   • 총 수익: {long_profit:+.2f} USDT\n"
                
                # 숏 포지션 정보
                short_data = coin_data.get('short', {})
                short_position = short_data.get('position', 0)
                short_entry_price = short_data.get('entry_price', 0)
                short_slices = short_data.get('slices_count', 0)
                short_trades = short_data.get('total_trades', 0)
                short_success = short_data.get('success_trades', 0)
                short_failed = short_data.get('failed_trades', 0)
                short_success_rate = short_data.get('success_rate', 0.0)
                short_profit = short_data.get('total_profit', 0)
                
                if short_position == 1:
                    report += f"🔴 숏 포지션 보유 중\n"
                    report += f"   • 진입가: {short_entry_price:.2f} USDT\n"
                    report += f"   • 슬라이스: {short_slices}개\n"
                else:
                    report += f"⚪ 숏 포지션 없음\n"
                
                report += f"   • 총 거래: {short_trades}회\n"
                report += f"   • 성공: {short_success}회, 실패: {short_failed}회\n"
                report += f"   • 성공률: {short_success_rate:.1f}%\n"
                report += f"   • 총 수익: {short_profit:+.2f} USDT\n"
                
                # 전체 통계
                total_trades = coin_data.get('total_trades', 0)
                total_success = coin_data.get('success_trades', 0)
                total_failed = coin_data.get('failed_trades', 0)
                total_success_rate = coin_data.get('success_rate', 0.0)
                total_profit = coin_data.get('total_profit', 0)
                
                report += f"📊 전체 통계\n"
                report += f"   • 총 거래: {total_trades}회\n"
                report += f"   • 성공: {total_success}회, 실패: {total_failed}회\n"
                report += f"   • 전체 성공률: {total_success_rate:.1f}%\n"
                report += f"   • 전체 수익: {total_profit:+.2f} USDT\n"
        
        # 설정 정보
        settings = dic.get('settings', {})
        investment_ratio = settings.get('investment_ratio', 0.5)
        divide = settings.get('divide', 200)
        
        report += f"\n⚙️ 봇 설정\n"
        report += f"• 투자 비율: {investment_ratio*100:.1f}%\n"
        report += f"• 자산 분할: {divide}분할\n"
        report += f"• 1슬라이스: {investment_ratio/divide*100:.3f}%\n"
        
        report += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        report += f"🤖 MA + 추세 전략 봇 자동 리포트"
        
        return report
        
    except Exception as e:
        error_msg = f"일일 리포트 생성 실패: {e}"
        logger.error(error_msg)
        return f"❌ 일일 리포트 생성 실패: {error_msg}"

# ========================= 메인 거래 로직 =========================
def check_trend_signals(df, i, position_type):
    """추세 신호 확인 (5개 중 3개 이상 만족) - 백테스트와 동일"""
    
    if i < 20:  # 충분한 데이터가 없으면 False
        return False
    
    signals = 0
    total_signals = 5
    
    # 1. 모멘텀 신호
    momentum_5 = df['momentum_5'].iloc[i]
    momentum_10 = df['momentum_10'].iloc[i]
    
    if position_type == 'LONG':
        if momentum_5 > 0 and momentum_10 > 0:
            signals += 1
    else:  # SHORT
        if momentum_5 < 0 and momentum_10 < 0:
            signals += 1
    
    # 2. 추세 연속성 신호
    trend_continuity = df['trend_continuity'].iloc[i]
    
    if position_type == 'LONG':
        if trend_continuity >= DEFAULT_TREND_CONTINUITY_MIN:  # 3분 이상 연속 상승
            signals += 1
    else:  # SHORT
        if trend_continuity <= -DEFAULT_TREND_CONTINUITY_MIN:  # 3분 이상 연속 하락
            signals += 1
    
    # 3. 볼린저 밴드 위치 신호
    bb_position = df['bb_position'].iloc[i]
    
    if position_type == 'LONG':
        if 0.3 <= bb_position <= 0.8:  # 적정 구간
            signals += 1
    else:  # SHORT
        if 0.2 <= bb_position <= 0.7:  # 적정 구간
            signals += 1
    
    # 4. RSI 신호
    rsi = df['rsi'].iloc[i]
    
    if position_type == 'LONG':
        if DEFAULT_RSI_OVERSOLD <= rsi <= DEFAULT_RSI_OVERBOUGHT:  # 30 <= RSI <= 70
            signals += 1
    else:  # SHORT
        if DEFAULT_RSI_OVERSOLD <= rsi <= DEFAULT_RSI_OVERBOUGHT:  # 30 <= RSI <= 70
            signals += 1
    
    # 5. 거래량 신호
    volume_ratio = df['volume_ratio'].iloc[i]
    
    if volume_ratio > DEFAULT_MIN_VOLUME_RATIO:  # 1.2배 이상
        signals += 1
    
    # 5개 중 3개 이상 만족하면 True
    return signals >= 3

def get_martingale_stage_totals():
    # 누적 유닛 수: 1, 3, 9, 27, 81 (초기 + 1~4차 물타기)
    return [1, 3, 9, 27, 81]


def get_martingale_delta_units(current_units: int) -> int:
    # current_units는 현재 누적 유닛(슬라이스) 수. 다음 단계로 가기 위한 추가 유닛 수를 반환
    # 예) 1 -> +2, 2 -> +6, 3 -> +18, 4 -> +54, 5 이상 -> 0
    stage_totals = get_martingale_stage_totals()
    if current_units <= 0:
        return 0
    if current_units >= len(stage_totals):
        return 0
    return stage_totals[current_units] - stage_totals[current_units - 1]


def execute_ma_trend_strategy(binanceX, Target_Coin_Ticker, df, long_position, short_position, long_entry_price, short_entry_price, dic):
    """
    MA + 추세 전략 실행 (롱/숏 양방향 거래)
    
    Args:
        binanceX: 바이낸스 API 객체
        Target_Coin_Ticker: 거래할 코인 티커
        df: OHLCV 데이터프레임
        long_position: 롱 포지션 상태 (0: 없음, 1: 보유)
        short_position: 숏 포지션 상태 (0: 없음, 1: 보유)
        long_entry_price: 롱 진입 가격
        short_entry_price: 숏 진입 가격
        dic: 설정 파일 데이터
    
    Returns:
        action: 'BUY_LONG', 'BUY_SHORT', 'SELL_LONG', 'SELL_SHORT', 'HOLD'
        reason: 행동 이유
    """
    try:
        # 추세 지표 계산
        df = calculate_trend_indicators(df, Target_Coin_Ticker)
        
        # 최신 데이터 가져오기
        if len(df) < 20:
            return 'HOLD', '데이터 부족'
        
        # MA 계산을 위한 최소 데이터 확인
        ma1_period = DEFAULT_MA1_PERIOD  # 5
        ma2_period = DEFAULT_MA2_PERIOD  # 20
        if len(df) < max(ma1_period, ma2_period) + 1:
            return 'HOLD', f'MA 계산을 위한 데이터 부족 (필요: {max(ma1_period, ma2_period) + 1}개)'
        
        latest = df.iloc[-1]
        
        # NaN 체크 (지표 초기화 대기)
        if latest[['momentum_5', 'momentum_10', 'trend_continuity', 'bb_position', 'rsi']].isna().any():
            return 'HOLD', '지표 초기화 대기'
        
        # 추세 신호 생성
        momentum_5 = latest['momentum_5']
        momentum_10 = latest['momentum_10']
        trend_continuity = latest['trend_continuity']
        bb_position = latest['bb_position']
        rsi = latest['rsi']
        
        # MA 계산 (5MA와 20MA)
        ma1_period = DEFAULT_MA1_PERIOD  # 5
        ma2_period = DEFAULT_MA2_PERIOD  # 20
        
        df[f'ma_{ma1_period}'] = df['close'].rolling(ma1_period).mean()
        df[f'ma_{ma2_period}'] = df['close'].rolling(ma2_period).mean()
        
        # 현재와 이전 MA값
        ma1_current = df[f'ma_{ma1_period}'].iloc[-1]
        ma2_current = df[f'ma_{ma2_period}'].iloc[-1]
        ma1_prev = df[f'ma_{ma1_period}'].iloc[-2]
        ma2_prev = df[f'ma_{ma2_period}'].iloc[-2]
        
        # MA 골든크로스/데드크로스 확인
        ma_golden_cross = ma1_current > ma2_current and ma1_prev <= ma2_prev
        ma_dead_cross = ma1_current < ma2_current and ma1_prev >= ma2_prev
        
        # 롱 진입 신호: MA 골든크로스 + 추세 신호 3개 이상
        if (long_position == 0 and 
            ma_golden_cross and
            check_trend_signals(df, len(df)-1, 'LONG')):  # 5개 중 3개 이상 만족
            
            return 'BUY', f'MA골든크로스+추세신호3개이상 | MA1:{ma1_current:.2f}, MA2:{ma2_current:.2f} | 모멘텀5:{momentum_5:.2f}, 모멘텀10:{momentum_10:.2f}, 연속성:{trend_continuity}, BB:{bb_position:.2f}, RSI:{rsi:.1f}'
        
        # 숏 진입 신호: MA 데드크로스 + 추세 신호 3개 이상
        if (short_position == 0 and 
            ma_dead_cross and
            check_trend_signals(df, len(df)-1, 'SHORT')):  # 5개 중 3개 이상 만족
            
            return 'BUY_SHORT', f'MA데드크로스+추세신호3개이상 | MA1:{ma1_current:.2f}, MA2:{ma2_current:.2f} | 모멘텀5:{momentum_5:.2f}, 모멘텀10:{momentum_10:.2f}, 연속성:{trend_continuity}, BB:{bb_position:.2f}, RSI:{rsi:.1f}'
        
        # 롱 포지션 청산 신호: 수익이 났을 때만 청산
        elif long_position == 1:  # 롱 포지션 보유 중
            # 현재 수익률 계산
            current_price = latest['close']
            current_profit_rate = (current_price - long_entry_price) / long_entry_price * 100.0
            
            # 수익이 났을 때만 청산 (0.3% 이상)
            if current_profit_rate >= DEFAULT_TARGET_REVENUE_RATE:
                if (ma_dead_cross or
                    momentum_5 < 0 or momentum_10 < 0 or  # 모멘텀 전환
                    trend_continuity <= 0 or               # 추세 전환
                    rsi > DEFAULT_RSI_OVERBOUGHT):  # RSI 과매수
                    
                    reason = []
                    if ma_dead_cross:
                        reason.append('MA데드크로스')
                    if momentum_5 < 0 or momentum_10 < 0:
                        reason.append('모멘텀전환')
                    if trend_continuity <= 0:
                        reason.append('추세전환')
                    if rsi > DEFAULT_RSI_OVERBOUGHT:
                        reason.append('RSI과매수')
                    
                    return 'SELL', f"수익실현청산신호({current_profit_rate:.2f}%): {'+'.join(reason)} | MA1:{ma1_current:.2f}, MA2:{ma2_current:.2f} | 모멘텀5:{momentum_5:.2f}, 모멘텀10:{momentum_10:.2f}, 연속성:{trend_continuity}, BB:{bb_position:.2f}, RSI:{rsi:.1f}"
        
        # 숏 포지션 청산 신호: 수익이 났을 때만 청산
        elif short_position == 1:  # 숏 포지션 보유 중
            # 현재 수익률 계산 (숏은 가격이 내려갈 때 수익)
            current_price = latest['close']
            current_profit_rate = (short_entry_price - current_price) / short_entry_price * 100.0
            
            # 수익이 났을 때만 청산 (0.3% 이상) + MA 크로스오버만 (설명대로 엄격화)
            if current_profit_rate >= DEFAULT_TARGET_REVENUE_RATE and ma_golden_cross:
                return 'SELL_SHORT', f"숏수익실현청산신호({current_profit_rate:.2f}%): MA골든크로스 | MA1:{ma1_current:.2f}, MA2:{ma2_current:.2f} | 모멘텀5:{momentum_5:.2f}, 모멘텀10:{momentum_10:.2f}, 연속성:{trend_continuity}, BB:{bb_position:.2f}, RSI:{rsi:.1f}"
        
        return 'HOLD', '신호 없음'
        
    except Exception as e:
        log_error(f"전략 실행 중 오류: {e}", traceback.format_exc())
        return 'HOLD', f'오류: {e}'

# ========================= 메인 실행 코드 =========================
if __name__ == "__main__":
    #암복호화 클래스 객체를 미리 생성한 키를 받아 생성한다.
    simpleEnDecrypt = myBinance.SimpleEnDecrypt(ende_key.ende_key)
    #암호화된 액세스키와 시크릿키를 읽어 복호화 한다.
    Binance_AccessKey = simpleEnDecrypt.decrypt(my_key.binance_access)
    Binance_ScretKey = simpleEnDecrypt.decrypt(my_key.binance_secret)
    
    # binance 객체 생성
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

    # 라이브 모드 시작 로깅
    logger.info("="*60)
    logger.info("=== MA + 추세 전략 봇 라이브 모드 시작 ===")
    logger.info(f"기본 설정: 기본레버리지={DEFAULT_LEVERAGE}, 투자비율={INVESTMENT_RATIO*100}%, 자산분할={DIVIDE}분할")
    logger.info(f"활성화된 코인: {ACTIVE_COINS}")

    # 거래할 코인 목록 (설정에서 활성화된 코인만)
    Coin_Ticker_List = ACTIVE_COINS
    logger.info(f"거래 대상: {Coin_Ticker_List}")
    
    print("\n-- START ------------------------------------------------------------------------------------------\n")
    
    try:
        # 잔고 데이터 가져오기
        balance = binanceX.fetch_balance(params={"type": "future"})
        time.sleep(0.1)
        logger.info(f"초기 잔고: {balance['USDT']['total']} USDT")
        print("balance['USDT'] : ", balance['USDT'])
    except Exception as e:
        error_msg = f"잔고 조회 실패: {e}"
        log_error(error_msg, traceback.format_exc())
        sys.exit(1)

    # 설정 파일 경로
    info_file_path = os.path.join(os.path.dirname(__file__), "MA_Martingale_v1.json")
    os.makedirs(os.path.dirname(info_file_path), exist_ok=True)

    # 설정 파일 로드 또는 생성
    try:
        with open(info_file_path, 'r') as json_file:
            dic = json.load(json_file)
        
        # start_money가 0이거나 없으면 현재 잔고로 업데이트
        if dic.get('start_money', 0) == 0:
            current_balance = float(balance['USDT']['total'])
            dic['start_money'] = current_balance
            dic['my_money'] = current_balance
            logger.info(f"start_money가 0이므로 현재 잔고로 업데이트: {current_balance:.2f} USDT")
            
            # 설정 파일 업데이트
            try:
                with open(info_file_path, 'w') as outfile:
                    json.dump(dic, outfile, indent=4, ensure_ascii=False)
                logger.info("잔고 업데이트 후 설정 파일 저장 완료")
            except Exception as write_error:
                log_error(f"잔고 업데이트 후 설정 파일 저장 실패: {write_error}")
        
        logger.info(f"설정 파일 로드 성공: 시작자본: {dic['start_money']:.2f} USDT")

    except Exception as e:
        logger.info("설정 파일이 없어 새로 생성합니다.")
        print("Exception by First")
        dic = {
            "yesterday": 0,
            "today": 0,
            "start_money": float(balance['USDT']['total']),
            "my_money": float(balance['USDT']['total']),
            "coins": {
                "BTC/USDT": {
                    "long": {
                        "position": 0,        # 0: 없음, 1: 보유
                        "entry_price": 0,     # 진입 가격
                        "entry_time": None,   # 진입 시간
                        "slices_count": 0,    # 슬라이스 개수
                        "total_trades": 0,    # 총 거래 횟수
                        "success_trades": 0,  # 성공 거래 횟수
                        "failed_trades": 0,   # 실패 거래 횟수
                        "success_rate": 0.0,  # 성공률 (%)
                        "total_profit": 0,    # 총 수익
                        "position_size": 0,   # 진입 시 수량 저장
                    },
                    "short": {
                        "position": 0,        # 0: 없음, 1: 보유
                        "entry_price": 0,     # 진입 가격
                        "entry_time": None,   # 진입 시간
                        "slices_count": 0,    # 슬라이스 개수
                        "total_trades": 0,    # 총 거래 횟수
                        "success_trades": 0,  # 성공 거래 횟수
                        "failed_trades": 0,   # 실패 거래 횟수
                        "success_rate": 0.0,  # 성공률 (%)
                        "total_profit": 0,    # 총 수익
                    },
                    "no": 0,                  # 거래번호
                    "total_trades": 0,        # 총 거래 횟수 (롱+숏)
                    "success_trades": 0,      # 총 성공 거래 횟수 (롱+숏)
                    "failed_trades": 0,       # 총 실패 거래 횟수 (롱+숏)
                    "success_rate": 0.0,      # 총 성공률 (%)
                    "total_profit": 0,        # 총 수익 (롱+숏)
                    "last_trade_time": None   # 마지막 거래 시간
                }
            },
            "settings": {
                "investment_ratio": INVESTMENT_RATIO,
                "divide": DIVIDE,
                "last_update": dt.datetime.now().isoformat()
            }
        }
        try:
            with open(info_file_path, 'w') as outfile:
                json.dump(dic, outfile, indent=4, ensure_ascii=False)
            logger.info("새 설정 파일 생성 완료")
        except Exception as write_error:
            log_error(f"설정 파일 저장 실패: {write_error}")

    # 한국 시간 기준으로 어제와 오늘 날짜 계산
    yesterday = dt.datetime.now(dt.UTC) + dt.timedelta(hours=9) - dt.timedelta(days=1)
    today = dt.datetime.now(dt.UTC) + dt.timedelta(hours=9)

    # 24시에 수익금 처리
    if today.hour == 0 and today.minute == 0:
        balance = binanceX.fetch_balance(params={"type": "future"})
        time.sleep(0.1)
        dic["today"] = float(balance['USDT']['total'])-dic["my_money"]
        dic["my_money"] = float(balance['USDT']['total'])
        dic["yesterday"] = dic["today"]
        dic["today"] = 0
        with open(info_file_path, 'w') as outfile:
            json.dump(dic, outfile, indent=4, ensure_ascii=False)
    
    # 아침 8시에 일일 리포트 텔레그램 전송
    if today.hour == 8 and today.minute == 0:
        try:
            # 일일 리포트 생성
            report_msg = create_daily_report(dic, balance)
            line_alert.SendMessage(report_msg)
            logger.info("아침 8시 일일 리포트 텔레그램 전송 완료")
        except Exception as e:
            log_error(f"일일 리포트 전송 실패: {e}")
            logger.error(f"일일 리포트 전송 실패: {e}")

    # 메인 거래 루프
    for Target_Coin_Ticker in Coin_Ticker_List:
        logger.info(f"=== {Target_Coin_Ticker} 거래 시작 ===")
        
        # 거래할 코인 티커와 심볼
        Target_Coin_Symbol = Target_Coin_Ticker.replace("/", "").replace(":USDT", "")
        logger.info(f"거래 심볼: {Target_Coin_Symbol}")
        
        # 기본 설정값 사용
        coin_leverage = DEFAULT_LEVERAGE
        coin_charge = DEFAULT_CHARGE
        
        # 레버리지 설정
        try:
            leverage_result = binanceX.fapiPrivate_post_leverage({'symbol': Target_Coin_Symbol, 'leverage': coin_leverage})
            logger.info(f"{Target_Coin_Symbol} 레버리지 설정 성공: {coin_leverage}배")
        except Exception as e:
            try:
                leverage_result = binanceX.fapiprivate_post_leverage({'symbol': Target_Coin_Symbol, 'leverage': coin_leverage})
                logger.info(f"{Target_Coin_Symbol} 레버리지 설정 성공 (대체): {coin_leverage}배")
            except Exception as e2:
                error_msg = f"{Target_Coin_Symbol} 레버리지 설정 실패: {e2}"
                log_error(error_msg)
                continue

        # 격리모드 설정
        # try:
        #     binanceX.fapiPrivate_post_margintype({'symbol': Target_Coin_Symbol, 'marginType': 'ISOLATED'})
        #     logger.info(f"{Target_Coin_Symbol} 격리모드 설정 완료")
        # except Exception as e:
        #     logger.warning(f"{Target_Coin_Symbol} 격리모드 설정 실패: {e}")

        # 캔들 정보 가져오기
        df = myBinance.GetOhlcv(binanceX, Target_Coin_Ticker, '1m')
        
        # 해당 코인 가격을 가져온다
        coin_price = myBinance.GetCoinNowPrice(binanceX, Target_Coin_Ticker)
        
        # 현재 포지션 상태 확인
        long_data = dic.get('coins', {}).get(Target_Coin_Ticker, {}).get('long', {})
        short_data = dic.get('coins', {}).get(Target_Coin_Ticker, {}).get('short', {})
        long_position = long_data.get('position', 0)
        short_position = short_data.get('position', 0)
        # 전략 계산과 청산 조건은 평균단가 기준으로 진행
        long_entry_price = long_data.get('avg_entry_price', long_data.get('entry_price', 0))
        short_entry_price = short_data.get('avg_entry_price', short_data.get('entry_price', 0))
        long_slices_count = long_data.get('slices_count', 0)
        short_slices_count = short_data.get('slices_count', 0)
        
        # 포지션 상태 로깅
        if long_position == 1:
            log_position_status(long_position, long_entry_price, coin_price, f"{Target_Coin_Symbol}(롱)", long_slices_count)
        if short_position == 1:
            log_position_status(short_position, short_entry_price, coin_price, f"{Target_Coin_Symbol}(숏)", short_slices_count)
        if long_position == 0 and short_position == 0:
            log_position_status(0, 0, coin_price, Target_Coin_Symbol, 0)
        
        # 전략 실행
        action, reason = execute_ma_trend_strategy(binanceX, Target_Coin_Ticker, df, long_position, short_position, long_entry_price, short_entry_price, dic)
        
        logger.info(f"전략 신호: {action} - {reason}")
        
        # {DIVIDE}분할 자산으로 거래 금액 계산 (한 번만)
        investment_amount = dic['my_money'] * INVESTMENT_RATIO / DIVIDE
        
        # 실제 계산된 투자금액 로깅
        logger.info(f"{DIVIDE}분할 투자금액: {INVESTMENT_RATIO*100}% ÷ {DIVIDE} = {INVESTMENT_RATIO/DIVIDE*100:.3f}% (1슬라이스당)")
        logger.info(f"1슬라이스 투자금액: {investment_amount:.4f} USDT = {INVESTMENT_RATIO/DIVIDE*100:.3f}%")
        
        # 최소 분할 시 몇 개가 나오는지 계산 및 로깅
        if Target_Coin_Ticker == 'BTC/USDT':
            # BTC 최소 수량 0.001 기준으로 계산
            min_btc = 0.001
            min_investment_needed = (min_btc * coin_price) / coin_leverage
            min_divide_possible = int(dic['my_money'] * INVESTMENT_RATIO / min_investment_needed)
            
            logger.info(f"=== 최소 분할 분석 ===")
            logger.info(f"BTC 최소 수량: {min_btc}")
            logger.info(f"현재 BTC 가격: {coin_price:.2f} USDT")
            logger.info(f"20배 레버리지 적용 시 최소 투자금: {min_investment_needed:.4f} USDT")
            logger.info(f"현재 분할 수: {min_divide_possible}/{DIVIDE}개")
            logger.info(f"========================")
        
        position_size = (investment_amount * coin_leverage) / coin_price

        logger.info(f"{Target_Coin_Ticker} 1슬라이스 갯수: {position_size}")
        position_size = round(position_size, 3)  # 소수점 3자리로 반올림
        
        # 최소 수량 확인 및 설정
        minimum_amount = myBinance.GetMinimumAmount(binanceX, Target_Coin_Ticker)
        if position_size < minimum_amount:
            position_size = minimum_amount
            logger.info(f"{Target_Coin_Ticker} 최소수량 적용: {minimum_amount}")
        
        # 거래 실행 또는 물타기/손절
        # --- 물타기(롱) ---
        if long_position == 1 and action != 'SELL':
            try:
                # 다음 단계 판단 (최대 5단계: 1,3,9,27,81)
                next_stage_index = long_slices_count + 1  # 초기 1 -> 다음 2 (1차 물타기)
                if 1 <= long_slices_count <= 4:
                    # 트리거: 평균단가 기준 -1%/-2%/-3%/-4%
                    avg_price = dic['coins'][Target_Coin_Ticker]['long'].get('avg_entry_price', long_entry_price)
                    drop_rate = (coin_price - avg_price) / avg_price * 100.0
                    threshold = -float(long_slices_count)  # -1, -2, -3, -4
                    # 추세 신호 재확인 (롱)
                    trend_ok = check_trend_signals(df, len(df)-1, 'LONG')
                    if drop_rate <= threshold and trend_ok:
                        # 추가 유닛 수 계산
                        delta_units = get_martingale_delta_units(long_slices_count)
                        if delta_units > 0:
                            add_qty = (investment_amount * coin_leverage * delta_units) / coin_price
                            add_qty = round(add_qty, 3)
                            # 최소 수량 보정
                            minimum_amount = myBinance.GetMinimumAmount(binanceX, Target_Coin_Ticker)
                            if add_qty < minimum_amount:
                                add_qty = minimum_amount
                            # 주문 실행 (롱 추가 매수)
                            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', add_qty, None, {'positionSide': 'LONG'})
                            exec_price = float(data.get('average', coin_price))
                            # 기존 수량/평단 갱신
                            current_qty = dic['coins'][Target_Coin_Ticker]['long'].get('position_qty', 0)
                            new_qty_total = round(current_qty + add_qty, 6)
                            if new_qty_total > 0:
                                new_avg = (avg_price * current_qty + exec_price * add_qty) / new_qty_total
                            else:
                                new_avg = exec_price
                            dic['coins'][Target_Coin_Ticker]['long']['avg_entry_price'] = new_avg
                            dic['coins'][Target_Coin_Ticker]['long']['position_qty'] = new_qty_total
                            dic['coins'][Target_Coin_Ticker]['long']['slices_count'] = long_slices_count + 1
                            dic['coins'][Target_Coin_Ticker]['long']['position_size'] = add_qty
                            # 저장
                            with open(info_file_path, 'w') as outfile:
                                json.dump(dic, outfile, indent=4, ensure_ascii=False)
                            # 로깅
                            log_trade_action('MARTINGALE', Target_Coin_Ticker, 'LONG', exec_price, add_qty, f"롱 {long_slices_count}차 물타기 실행(-{long_slices_count}% 트리거)")
                            logger.info(f"롱 물타기 체결: 단계 {long_slices_count}-> {long_slices_count+1}, 가격 {exec_price:.2f}, 추가수량 {add_qty}")
                            # 물타기 시에는 이후 일반 액션은 다음 루프로 넘김
                            continue
                # 손절: 4차 물타기 완료 후(=단계 5) 1배 기준 -1%
                if long_slices_count >= 5:
                    initial_price = dic['coins'][Target_Coin_Ticker]['long'].get('initial_entry_price', long_entry_price)
                    return_1x = (coin_price - initial_price) / initial_price * 100.0
                    if return_1x <= -1.0:
                        # 전량 청산
                        pos_qty = dic['coins'][Target_Coin_Ticker]['long'].get('position_qty', dic['coins'][Target_Coin_Ticker]['long'].get('position_size', 0))
                        if pos_qty > 0:
                            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', round(pos_qty,3), None, {'positionSide': 'LONG'})
                            exec_price = float(data.get('average', coin_price))
                            # 정리 후 기존 SELL 로직에서 마무리되도록 신호 오버라이드
                            action = 'SELL'
                            reason = f"롱 손절(-1%): 초기진입 {initial_price:.2f} → {coin_price:.2f}"
            except Exception as e:
                logger.warning(f"롱 물타기/손절 처리 중 오류: {e}")

        # --- 물타기(숏) ---
        if short_position == 1 and action != 'SELL_SHORT':
            try:
                next_stage_index = short_slices_count + 1
                if 1 <= short_slices_count <= 4:
                    avg_price = dic['coins'][Target_Coin_Ticker]['short'].get('avg_entry_price', short_entry_price)
                    raise_rate = (coin_price - avg_price) / avg_price * 100.0
                    threshold = float(short_slices_count)  # +1, +2, +3, +4
                    trend_ok = check_trend_signals(df, len(df)-1, 'SHORT')
                    if raise_rate >= threshold and trend_ok:
                        delta_units = get_martingale_delta_units(short_slices_count)
                        if delta_units > 0:
                            add_qty = (investment_amount * coin_leverage * delta_units) / coin_price
                            add_qty = round(add_qty, 3)
                            minimum_amount = myBinance.GetMinimumAmount(binanceX, Target_Coin_Ticker)
                            if add_qty < minimum_amount:
                                add_qty = minimum_amount
                            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', add_qty, None, {'positionSide': 'SHORT'})
                            exec_price = float(data.get('average', coin_price))
                            current_qty = dic['coins'][Target_Coin_Ticker]['short'].get('position_qty', 0)
                            new_qty_total = round(current_qty + add_qty, 6)
                            if new_qty_total > 0:
                                new_avg = (avg_price * current_qty + exec_price * add_qty) / new_qty_total
                            else:
                                new_avg = exec_price
                            dic['coins'][Target_Coin_Ticker]['short']['avg_entry_price'] = new_avg
                            dic['coins'][Target_Coin_Ticker]['short']['position_qty'] = new_qty_total
                            dic['coins'][Target_Coin_Ticker]['short']['slices_count'] = short_slices_count + 1
                            dic['coins'][Target_Coin_Ticker]['short']['position_size'] = add_qty
                            with open(info_file_path, 'w') as outfile:
                                json.dump(dic, outfile, indent=4, ensure_ascii=False)
                            log_trade_action('MARTINGALE', Target_Coin_Ticker, 'SHORT', exec_price, add_qty, f"숏 {short_slices_count}차 물타기 실행(+{short_slices_count}% 트리거)")
                            logger.info(f"숏 물타기 체결: 단계 {short_slices_count}-> {short_slices_count+1}, 가격 {exec_price:.2f}, 추가수량 {add_qty}")
                            continue
                if short_slices_count >= 5:
                    initial_price = dic['coins'][Target_Coin_Ticker]['short'].get('initial_entry_price', short_entry_price)
                    return_1x = (initial_price - coin_price) / initial_price * 100.0
                    if return_1x <= -1.0:  # 숏 손절: 초기 대비 +1% 역방향
                        pos_qty = dic['coins'][Target_Coin_Ticker]['short'].get('position_qty', dic['coins'][Target_Coin_Ticker]['short'].get('position_size', 0))
                        if pos_qty > 0:
                            data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', round(pos_qty,3), None, {'positionSide': 'SHORT'})
                            exec_price = float(data.get('average', coin_price))
                            action = 'SELL_SHORT'
                            reason = f"숏 손절(-1%): 초기진입 {initial_price:.2f} → {coin_price:.2f}"
            except Exception as e:
                logger.warning(f"숏 물타기/손절 처리 중 오류: {e}")

        # 거래 실행
        if action == 'BUY' and long_position == 0:
            try:
                # 162분할 자산으로 거래 (position_size는 위에서 이미 계산됨)
                # 주문 실행
                data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', position_size, None, {'positionSide': 'LONG'})
                buy_price = float(data['average'])
                
                # 포지션 정보 업데이트 (초기 진입)
                dic['coins'][Target_Coin_Ticker]['long']['position'] = 1
                dic['coins'][Target_Coin_Ticker]['long']['entry_price'] = buy_price
                dic['coins'][Target_Coin_Ticker]['long']['initial_entry_price'] = buy_price
                dic['coins'][Target_Coin_Ticker]['long']['avg_entry_price'] = buy_price
                dic['coins'][Target_Coin_Ticker]['long']['entry_time'] = dt.datetime.now().isoformat()
                dic['coins'][Target_Coin_Ticker]['long']['slices_count'] = 1  # 초기 단계
                dic['coins'][Target_Coin_Ticker]['long']['position_size'] = position_size  # 마지막 주문 수량 저장
                dic['coins'][Target_Coin_Ticker]['long']['position_qty'] = position_size   # 총 보유 수량 저장
                dic['coins'][Target_Coin_Ticker]['long']['base_usdt_per_slice'] = investment_amount
                dic['coins'][Target_Coin_Ticker]['no'] += 1
                
                # 설정 파일 저장
                with open(info_file_path, 'w') as outfile:
                    json.dump(dic, outfile, indent=4, ensure_ascii=False)
                
                msg = f"\n{Target_Coin_Symbol} 롱 포지션 진입 성공!\n진입가: {buy_price:.2f}\n수량: {position_size:.3f}\n사유: {reason}"
                logger.info(f"롱 포지션 진입 성공: {Target_Coin_Symbol}, 가격: {buy_price:.2f}, 수량: {position_size:.3f}")
                
                # 거래 로그 기록
                log_trade_action('BUY', Target_Coin_Ticker, 'LONG', buy_price, position_size, reason)
                
                line_alert.SendMessage(msg)
                
            except Exception as e:
                error_msg = f"롱 포지션 진입 실패: {e}"
                log_error(error_msg, traceback.format_exc())
                
        elif action == 'SELL' and long_position == 1:
            try:
                # JSON에서 저장된 총 보유 수량으로 전량 청산
                position_size = dic['coins'][Target_Coin_Ticker]['long'].get('position_qty', dic['coins'][Target_Coin_Ticker]['long'].get('position_size', 0))
                logger.info(f"{Target_Coin_Ticker} 롱 청산 시 저장된 수량: {position_size}")
                
                # 주문 실행
                data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', position_size, None, {'positionSide': 'LONG'})
                sell_price = float(data['average'])
                
                # 수익률 계산
                # 평단 기준 수익률
                avg_price = dic['coins'][Target_Coin_Ticker]['long'].get('avg_entry_price', long_entry_price)
                revenue_rate = (sell_price - avg_price) / avg_price * 100.0
                roi = revenue_rate * coin_leverage
                revenue_amount = (sell_price - avg_price) * position_size
                total_fee = (avg_price + sell_price) * position_size * coin_charge
                net_revenue = revenue_amount - total_fee
                
                # 포지션 정보 초기화
                dic['coins'][Target_Coin_Ticker]['long']['position'] = 0
                dic['coins'][Target_Coin_Ticker]['long']['entry_price'] = 0
                dic['coins'][Target_Coin_Ticker]['long']['avg_entry_price'] = 0
                dic['coins'][Target_Coin_Ticker]['long']['initial_entry_price'] = 0
                dic['coins'][Target_Coin_Ticker]['long']['entry_time'] = None
                dic['coins'][Target_Coin_Ticker]['long']['slices_count'] = 0  # 슬라이스 개수 초기화
                dic['coins'][Target_Coin_Ticker]['long']['position_size'] = 0  # 구매 수량 초기화
                dic['coins'][Target_Coin_Ticker]['long']['position_qty'] = 0
                
                # 롱 포지션 승률 업데이트
                dic['coins'][Target_Coin_Ticker]['long']['total_trades'] += 1
                if net_revenue > 0:
                    dic['coins'][Target_Coin_Ticker]['long']['success_trades'] += 1
                else:
                    dic['coins'][Target_Coin_Ticker]['long']['failed_trades'] += 1
                
                # 롱 포지션 성공률 계산
                long_total_trades = dic['coins'][Target_Coin_Ticker]['long']['total_trades']
                long_success_trades = dic['coins'][Target_Coin_Ticker]['long']['success_trades']
                dic['coins'][Target_Coin_Ticker]['long']['success_rate'] = (long_success_trades / long_total_trades) * 100.0
                
                # 전체 승률 업데이트
                dic['coins'][Target_Coin_Ticker]['total_trades'] += 1
                if net_revenue > 0:
                    dic['coins'][Target_Coin_Ticker]['success_trades'] += 1
                else:
                    dic['coins'][Target_Coin_Ticker]['failed_trades'] += 1
                
                # 전체 성공률 계산
                total_trades = dic['coins'][Target_Coin_Ticker]['total_trades']
                success_trades = dic['coins'][Target_Coin_Ticker]['success_trades']
                dic['coins'][Target_Coin_Ticker]['success_rate'] = (success_trades / total_trades) * 100.0
                
                # 수익 업데이트
                dic['coins'][Target_Coin_Ticker]['long']['total_profit'] += net_revenue
                dic['coins'][Target_Coin_Ticker]['total_profit'] += net_revenue
                dic['today'] += net_revenue
                dic['my_money'] += net_revenue
                
                # 설정 파일 저장
                with open(info_file_path, 'w') as outfile:
                    json.dump(dic, outfile, indent=4, ensure_ascii=False)
                
                msg = f"\n{Target_Coin_Symbol} 롱 포지션 청산 성공!\n진입가: {long_entry_price:.2f}\n청산가: {sell_price:.2f}\n수익률: {revenue_rate:+.2f}%\nROI({coin_leverage}배): {roi:+.2f}%\n순수익: {net_revenue:+.2f}$\n사유: {reason}"
                logger.info(f"롱 포지션 청산 성공: {Target_Coin_Symbol}, 수익률: {revenue_rate:+.2f}%, 순수익: {net_revenue:+.2f}$")
                line_alert.SendMessage(msg)
                
            except Exception as e:
                error_msg = f"롱 포지션 청산 실패: {e}"
                log_error(error_msg, traceback.format_exc())
        
        elif action == 'BUY_SHORT' and short_position == 0:
            try:
                # 162분할 자산으로 거래 (position_size는 위에서 이미 계산됨)
                # 주문 실행
                data = binanceX.create_order(Target_Coin_Ticker, 'market', 'sell', position_size, None, {'positionSide': 'SHORT'})
                sell_price = float(data['average'])
                
                # 포지션 정보 업데이트 (초기 진입)
                dic['coins'][Target_Coin_Ticker]['short']['position'] = 1
                dic['coins'][Target_Coin_Ticker]['short']['entry_price'] = sell_price
                dic['coins'][Target_Coin_Ticker]['short']['initial_entry_price'] = sell_price
                dic['coins'][Target_Coin_Ticker]['short']['avg_entry_price'] = sell_price
                dic['coins'][Target_Coin_Ticker]['short']['entry_time'] = dt.datetime.now().isoformat()
                dic['coins'][Target_Coin_Ticker]['short']['slices_count'] = 1
                dic['coins'][Target_Coin_Ticker]['short']['position_size'] = position_size
                dic['coins'][Target_Coin_Ticker]['short']['position_qty'] = position_size
                dic['coins'][Target_Coin_Ticker]['short']['base_usdt_per_slice'] = investment_amount
                dic['coins'][Target_Coin_Ticker]['no'] += 1
                
                # 설정 파일 저장
                with open(info_file_path, 'w') as outfile:
                    json.dump(dic, outfile, indent=4, ensure_ascii=False)
                
                msg = f"\n{Target_Coin_Symbol} 숏 포지션 진입 성공!\n진입가: {sell_price:.2f}\n수량: {position_size:.3f}\n사유: {reason}"
                logger.info(f"숏 포지션 진입 성공: {Target_Coin_Symbol}, 가격: {sell_price:.2f}, 수량: {position_size:.3f}")
                line_alert.SendMessage(msg)
                
            except Exception as e:
                error_msg = f"숏 포지션 진입 실패: {e}"
                log_error(error_msg, traceback.format_exc())
                
        elif action == 'SELL_SHORT' and short_position == 1:
            try:
                # JSON에서 저장된 총 보유 수량으로 전량 청산
                position_size = dic['coins'][Target_Coin_Ticker]['short'].get('position_qty', dic['coins'][Target_Coin_Ticker]['short'].get('position_size', 0))
                logger.info(f"{Target_Coin_Ticker} 숏 청산 시 저장된 수량: {position_size}")
                
                # 주문 실행
                data = binanceX.create_order(Target_Coin_Ticker, 'market', 'buy', position_size, None, {'positionSide': 'SHORT'})
                buy_price = float(data['average'])
                
                # 평단 기준 수익률 (숏은 내려갈 때 수익)
                avg_price = dic['coins'][Target_Coin_Ticker]['short'].get('avg_entry_price', short_entry_price)
                revenue_rate = (avg_price - buy_price) / avg_price * 100.0
                roi = revenue_rate * coin_leverage
                revenue_amount = (avg_price - buy_price) * position_size
                total_fee = (avg_price + buy_price) * position_size * coin_charge
                net_revenue = revenue_amount - total_fee
                
                # 포지션 정보 초기화
                dic['coins'][Target_Coin_Ticker]['short']['position'] = 0
                dic['coins'][Target_Coin_Ticker]['short']['entry_price'] = 0
                dic['coins'][Target_Coin_Ticker]['short']['avg_entry_price'] = 0
                dic['coins'][Target_Coin_Ticker]['short']['initial_entry_price'] = 0
                dic['coins'][Target_Coin_Ticker]['short']['entry_time'] = None
                dic['coins'][Target_Coin_Ticker]['short']['slices_count'] = 0  # 슬라이스 개수 초기화
                dic['coins'][Target_Coin_Ticker]['short']['position_size'] = 0  # 구매 수량 초기화
                dic['coins'][Target_Coin_Ticker]['short']['position_qty'] = 0
                
                # 숏 포지션 승률 업데이트
                dic['coins'][Target_Coin_Ticker]['short']['total_trades'] += 1
                if net_revenue > 0:
                    dic['coins'][Target_Coin_Ticker]['short']['success_trades'] += 1
                else:
                    dic['coins'][Target_Coin_Ticker]['short']['failed_trades'] += 1
                
                # 숏 포지션 성공률 계산
                short_total_trades = dic['coins'][Target_Coin_Ticker]['short']['total_trades']
                short_success_trades = dic['coins'][Target_Coin_Ticker]['short']['success_trades']
                dic['coins'][Target_Coin_Ticker]['short']['success_rate'] = (short_success_trades / short_total_trades) * 100.0
                
                # 전체 승률 업데이트
                dic['coins'][Target_Coin_Ticker]['total_trades'] += 1
                if net_revenue > 0:
                    dic['coins'][Target_Coin_Ticker]['success_trades'] += 1
                else:
                    dic['coins'][Target_Coin_Ticker]['failed_trades'] += 1
                
                # 전체 성공률 계산
                total_trades = dic['coins'][Target_Coin_Ticker]['total_trades']
                success_trades = dic['coins'][Target_Coin_Ticker]['success_trades']
                dic['coins'][Target_Coin_Ticker]['success_rate'] = (success_trades / total_trades) * 100.0
                
                # 수익 업데이트
                dic['coins'][Target_Coin_Ticker]['short']['total_profit'] += net_revenue
                dic['coins'][Target_Coin_Ticker]['total_profit'] += net_revenue
                dic['today'] += net_revenue
                dic['my_money'] += net_revenue
                
                # 설정 파일 저장
                with open(info_file_path, 'w') as outfile:
                    json.dump(dic, outfile, indent=4, ensure_ascii=False)
                
                msg = f"\n{Target_Coin_Symbol} 숏 포지션 청산 성공!\n진입가: {short_entry_price:.2f}\n청산가: {buy_price:.2f}\n수익률: {revenue_rate:+.2f}%\nROI({coin_leverage}배): {roi:+.2f}%\n순수익: {net_revenue:+.2f}$\n사유: {reason}"
                logger.info(f"숏 포지션 청산 성공: {Target_Coin_Symbol}, 수익률: {revenue_rate:+.2f}%, 순수익: {net_revenue:+.2f}$")
                line_alert.SendMessage(msg)
                
            except Exception as e:
                error_msg = f"숏 포지션 청산 실패: {e}"
                log_error(error_msg, traceback.format_exc())
        
        logger.info(f"=== {Target_Coin_Symbol} 거래 완료 ===")
        print("\n-- END --------------------------------------------------------------------------------------------\n")
    
    # 프로그램 종료 로깅
    logger.info("=== MA + 추세 전략 봇 종료 ===")