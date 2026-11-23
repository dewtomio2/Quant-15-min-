# alert_once.py - รันครั้งเดียวแล้วจบ (ให้ GitHub Actions เรียกทุก 15 นาที)
import csv, json, os, time
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from config import (WATCHLIST, LOG_FILE, STATE_FILE, INTERVAL, DISCORD_WEBHOOK_URL,
                    MAX_SIGNAL_AGE_MIN)
from signals import get_signal

TZ = ZoneInfo("Asia/Bangkok")


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)


def format_alert(r):
    labels = {
        "BUY": "🟢 ซื้อ (ยืนยันครบ + ตรงเทรนด์รายวัน)",
        "SELL": "🔴 ขาย (ยืนยันครบ + ตรงเทรนด์รายวัน)",
        "BUY_CAUTION": "🟡 สัญญาณซื้อ (RSI สูง ระวังราคาร้อนแรง)",
        "SELL_CAUTION": "🟡 สัญญาณขาย (RSI ต่ำ ระวังราคาเย็นเกินไป)",
    }
    daily = {"UP": "ขาขึ้น", "DOWN": "ขาลง", "N/A": "ไม่มีข้อมูล (ไม่ได้กรอง)"}.get(r['daily_trend'], r['daily_trend'])
    return (f"[{r['symbol']}] {labels.get(r['signal'], r['signal'])}  (แท่ง {r['bar_time']})\n"
            f"  ราคา: {r['price']} | RSI: {r['rsi']} | ADX: {r['adx']}\n"
            f"  MACD: {r['macd']} | Signal: {r['macd_signal']}\n"
            f"  MA_fast: {r['ma_fast']} | MA_slow: {r['ma_slow']}\n"
            f"  เทรนด์รายวัน: {daily}")


def send_discord(r, text):
    if not DISCORD_WEBHOOK_URL:
        print("ยังไม่ได้ตั้ง DISCORD_WEBHOOK_URL (Secret) ข้ามการส่ง")
        return
    color = {"BUY": 3066993, "SELL": 15158332}.get(r['signal'], 15844367)
    payload = {"embeds": [{"title": f"📊 สัญญาณ {INTERVAL}: {r['symbol']}",
                           "description": f"```\n{text}\n```", "color": color}]}
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        if resp.status_code not in (200, 204):
            print(f"ส่ง Discord ไม่สำเร็จ: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"ส่ง Discord ไม่สำเร็จ: {e}")


def log_signal(r):
    exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["timestamp", "timeframe", "bar_time", "symbol", "signal", "daily_trend",
                        "price", "rsi", "adx", "macd", "macd_signal", "ma_fast", "ma_slow",
                        "action_taken", "notes"])
        w.writerow([datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"), INTERVAL, r['bar_time'],
                    r['symbol'], r['signal'], r['daily_trend'], r['price'], r['rsi'], r['adx'],
                    r['macd'], r['macd_signal'], r['ma_fast'], r['ma_slow'], "", ""])


def main():
    state = load_state()
    now = datetime.now(TZ)
    print(f"เช็คสัญญาณ {INTERVAL} ณ {now:%Y-%m-%d %H:%M:%S}")
    symbols = WATCHLIST["stocks"] + WATCHLIST["crypto"] + WATCHLIST["commodities"]
    found = 0

    for sym in symbols:
        r = get_signal(sym)
        time.sleep(1)
        if r is None:
            print(f"[{sym}] ข้อมูลไม่พอ/ดึงไม่สำเร็จ")
            continue
        sig = r['signal']
        if sig not in ("BUY", "SELL", "BUY_CAUTION", "SELL_CAUTION"):
            print(f"[{sym}] {sig} | ราคา {r['price']}")
            continue

        bar_dt = datetime.strptime(r['bar_time'], "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
        age_min = (now - bar_dt).total_seconds() / 60
        key = f"{sig}|{r['bar_time']}"
        if age_min > MAX_SIGNAL_AGE_MIN:
            print(f"[{sym}] {sig} แต่เก่าเกินไป ({age_min:.0f} นาที) ข้าม")
            continue
        if state.get(sym) == key:
            print(f"[{sym}] แจ้งไปแล้ว ข้าม")
            continue

        text = format_alert(r)
        print("\n🔔 พบสัญญาณ!\n" + text + "\n")
        send_discord(r, text)
        log_signal(r)
        state[sym] = key
        found += 1

    save_state(state)
    print(f"พบสัญญาณใหม่ {found} รายการ")


if __name__ == "__main__":
    main()
