# signals.py
import yfinance as yf
import pandas as pd
import time
from config import (
    INTERVAL, DATA_PERIOD,
    MA_FAST, MA_SLOW, RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD,
    ADX_PERIOD, ADX_TREND_THRESHOLD,
    DAILY_FILTER, DAILY_FILTER_SELL, DAILY_MA_FAST, DAILY_MA_SLOW
)

# cache เทรนด์รายวัน: {symbol: (เวลาหมดอายุ, ผลลัพธ์)}
_daily_cache = {}
CACHE_OK_SECONDS = 6 * 3600     # ดึงสำเร็จ เก็บ 6 ชม.
CACHE_FAIL_SECONDS = 3600       # ดึงไม่สำเร็จ ลองใหม่ทุก 1 ชม.


def calculate_rsi(close_prices, period=14):
    delta = close_prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_adx(high, low, close, period=14):
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    plus_dm[(plus_dm - minus_dm) < 0] = 0
    minus_dm[(minus_dm - plus_dm) < 0] = 0

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(window=period).mean()
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    return dx.rolling(window=period).mean()


def calculate_macd(close_prices, fast=12, slow=26, signal=9):
    ema_fast = close_prices.ewm(span=fast, adjust=False).mean()
    ema_slow = close_prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line


def get_intraday_data(symbol, retries=3):
    """ดึงแท่ง 15m แล้วตัดแท่งสุดท้าย (ที่ยังไม่ปิด) ทิ้ง"""
    for attempt in range(retries):
        try:
            data = yf.download(symbol, period=DATA_PERIOD, interval=INTERVAL,
                               progress=False, timeout=15)

            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            if data.empty:
                return None

            data = data.iloc[:-1]

            if data.index.tz is not None:
                data.index = data.index.tz_convert("Asia/Bangkok")

            return data

        except Exception as e:
            print(f"[{symbol}] ดึงข้อมูลผิดพลาด (attempt {attempt+1}/{retries}): {e}")
            time.sleep(3)

    return None


def get_daily_trend(symbol):
    """
    เทรนด์รายวัน: "UP" ถ้า MA20 > MA50, "DOWN" ถ้าต่ำกว่า, "N/A" ถ้าดึงข้อมูลไม่ได้
    ใช้เฉพาะแท่งรายวันที่ปิดแล้ว (ตัดแท่งล่าสุดทิ้ง) และ cache ไว้
    """
    now = time.time()
    cached = _daily_cache.get(symbol)
    if cached and cached[0] > now:
        return cached[1]

    trend = "N/A"
    try:
        data = yf.download(symbol, period="1y", interval="1d",
                           progress=False, timeout=15)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        data = data.iloc[:-1] if not data.empty else data

        if len(data) >= DAILY_MA_SLOW + 1:
            ma_fast = data['Close'].rolling(window=DAILY_MA_FAST).mean().iloc[-1]
            ma_slow = data['Close'].rolling(window=DAILY_MA_SLOW).mean().iloc[-1]
            trend = "UP" if float(ma_fast) > float(ma_slow) else "DOWN"
    except Exception as e:
        print(f"[{symbol}] ดึงเทรนด์รายวันไม่สำเร็จ: {e}")

    ttl = CACHE_OK_SECONDS if trend != "N/A" else CACHE_FAIL_SECONDS
    _daily_cache[symbol] = (now + ttl, trend)
    return trend


def get_signal(symbol):
    """MA Crossover + ADX + MACD + RSI (15m) แล้วกรองด้วยเทรนด์รายวัน"""
    try:
        data = get_intraday_data(symbol)

        min_required = max(MA_SLOW + ADX_PERIOD, 26 + 9) + 2
        if data is None or len(data) < min_required:
            return None

        data['MA_fast'] = data['Close'].rolling(window=MA_FAST).mean()
        data['MA_slow'] = data['Close'].rolling(window=MA_SLOW).mean()
        data['RSI'] = calculate_rsi(data['Close'], RSI_PERIOD)
        data['ADX'] = calculate_adx(data['High'], data['Low'], data['Close'], ADX_PERIOD)
        macd_line, signal_line = calculate_macd(data['Close'])
        data['MACD'] = macd_line
        data['MACD_signal'] = signal_line

        latest = data.iloc[-1]
        previous = data.iloc[-2]
        bar_time = data.index[-1].strftime("%Y-%m-%d %H:%M")

        price = float(latest['Close'])
        ma_fast_now = float(latest['MA_fast'])
        ma_slow_now = float(latest['MA_slow'])
        rsi_now = float(latest['RSI'])
        adx_now = float(latest['ADX'])
        macd_now = float(latest['MACD'])
        macd_signal_now = float(latest['MACD_signal'])
        ma_fast_prev = float(previous['MA_fast'])
        ma_slow_prev = float(previous['MA_slow'])

        golden_cross = (ma_fast_prev <= ma_slow_prev) and (ma_fast_now > ma_slow_now)
        death_cross = (ma_fast_prev >= ma_slow_prev) and (ma_fast_now < ma_slow_now)
        trending = adx_now > ADX_TREND_THRESHOLD
        macd_bullish = macd_now > macd_signal_now
        macd_bearish = macd_now < macd_signal_now

        signal = "HOLD"
        if golden_cross:
            if not trending:
                signal = "SKIP_CHOPPY"
            elif not macd_bullish:
                signal = "SKIP_MACD_MISMATCH"
            elif rsi_now >= RSI_OVERBOUGHT:
                signal = "BUY_CAUTION"
            else:
                signal = "BUY"
        elif death_cross:
            if not trending:
                signal = "SKIP_CHOPPY"
            elif not macd_bearish:
                signal = "SKIP_MACD_MISMATCH"
            elif rsi_now <= RSI_OVERSOLD:
                signal = "SELL_CAUTION"
            else:
                signal = "SELL"

        # ตัวกรองเทรนด์รายวัน (เช็คเฉพาะตอนมีสัญญาณ จะได้ไม่ดึงข้อมูลโดยไม่จำเป็น)
        daily_trend = "-"
        if signal in ("BUY", "BUY_CAUTION", "SELL", "SELL_CAUTION"):
            daily_trend = get_daily_trend(symbol)
            if DAILY_FILTER:
                if signal in ("BUY", "BUY_CAUTION") and daily_trend == "DOWN":
                    signal = "SKIP_AGAINST_DAILY"
                elif signal in ("SELL", "SELL_CAUTION") and daily_trend == "UP" and DAILY_FILTER_SELL:
                    signal = "SKIP_AGAINST_DAILY"

        return {
            "symbol": symbol,
            "signal": signal,
            "bar_time": bar_time,
            "daily_trend": daily_trend,
            "price": round(price, 2),
            "rsi": round(rsi_now, 1),
            "adx": round(adx_now, 1),
            "macd": round(macd_now, 3),
            "macd_signal": round(macd_signal_now, 3),
            "ma_fast": round(ma_fast_now, 2),
            "ma_slow": round(ma_slow_now, 2),
        }

    except Exception as e:
        print(f"เกิดข้อผิดพลาดตอนคำนวณ {symbol}: {e}")
        return None
