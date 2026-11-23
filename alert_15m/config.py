# config.py (เวอร์ชัน GitHub Actions) - Webhook อ่านจาก GitHub Secret ไม่ต้องใส่ในไฟล์
import os

WATCHLIST = {
    "stocks": ["AAPL", "MSFT", "NVDA"],
    "crypto": ["BTC-USD", "ETH-USD", "SUI-USD"],
    "commodities": ["GC=F", "CL=F"]
}

INTERVAL = "15m"
DATA_PERIOD = "30d"
BAR_MINUTES = 15

MA_FAST = 20
MA_SLOW = 50
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
ADX_PERIOD = 14
ADX_TREND_THRESHOLD = 20

DAILY_FILTER = True
DAILY_FILTER_SELL = True
DAILY_MA_FAST = 20
DAILY_MA_SLOW = 50

DISCORD_WEBHOOK_URL = os.environ.get("https://discord.com/api/webhooks/1574291000011132968/FXz48qe833dQgLhGzD1M_0sETWJKFHVljFDysyRaF4-Dj7rpxfQBYb7Fwi2WfFIyXriI", "")

LOG_FILE = "signal_log_15m.csv"
STATE_FILE = "last_alerted.json"
MAX_SIGNAL_AGE_MIN = 45   # แจ้งเฉพาะสัญญาณจากแท่งที่ปิดไม่เกิน 45 นาทีก่อน (กันแจ้งสัญญาณเก่า/ตลาดปิด)
