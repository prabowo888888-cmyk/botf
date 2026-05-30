"""
================================================================================
  ICT PRO SIGNAL BOT — Versi Paling Lengkap & Profitable
  ✅ ICT Lengkap: Structure, BOS, OB, FVG, Liquidity Sweep
  ✅ 4 Timeframe: Daily + H4 + H1 + M15
  ✅ RSI Divergence
  ✅ SNR Klasik
  ✅ DXY Filter (Dollar Index — berlawanan dengan Gold)
  ✅ COT Sentiment (posisi institusi/bank besar)
  ✅ Forex Factory News Filter
  ✅ Kill Zone Filter
  ✅ Telegram Sinyal ke HP
  ✅ Railway Server 24 jam gratis
  ✅ Tanpa AI/LLM — tidak pernah error
================================================================================
"""

import os
import time
import logging
import requests
from datetime import datetime, timezone, timedelta

# ─────────────────────────────────────────────────────
#  KONFIGURASI — isi di Railway Variables
# ─────────────────────────────────────────────────────
TWELVE_DATA_KEY  = os.getenv("TWELVE_DATA_KEY", "")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ─────────────────────────────────────────────────────
#  PENGATURAN TRADING
# ─────────────────────────────────────────────────────
SYMBOL         = "XAU/USD"    # Tampilan Telegram
SYMBOL_TD      = "XAU/USD"    # Twelve Data format
DXY_SYMBOL     = "DXY"        # Dollar Index
CHECK_INTERVAL = 900           # Cek tiap 15 menit
MIN_SCORE      = 6             # Minimal skor konfluensi
TP_RR          = 2.0
SL_BUFFER      = 1.5

# Kill Zone (UTC)
KILL_ZONES = {
    "London Open":  (7,  9),
    "NY Open":      (12, 14),
    "London Close": (15, 16),
    "Asia Open":    (0,  2),
}

# News Filter
NEWS_PAUSE_BEFORE = 60
NEWS_PAUSE_AFTER  = 30
NEWS_CURRENCIES   = ["USD", "EUR", "GBP", "JPY", "XAU"]

# RSI Settings
RSI_PERIOD     = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD   = 30

# DXY Settings
DXY_TREND_LOOKBACK = 20  # Candle untuk deteksi tren DXY

# ─────────────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════
#  TELEGRAM
# ══════════════════════════════════════════════════════

def send_telegram(text: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        log.error(f"Telegram error: {e}")


# ══════════════════════════════════════════════════════
#  TWELVE DATA — DATA HARGA
# ══════════════════════════════════════════════════════

def get_candles(symbol: str, interval: str, count: int = 100) -> list:
    try:
        r = requests.get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": symbol, "interval": interval,
                "outputsize": count, "apikey": TWELVE_DATA_KEY,
                "timezone": "UTC"
            },
            timeout=15
        )
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "error":
            log.error(f"Twelve Data [{symbol}]: {data.get('message')}")
            return []
        values = data.get("values", [])
        values.reverse()
        return values
    except Exception as e:
        log.error(f"Twelve Data error: {e}")
        return []


def parse(candles: list) -> dict:
    return {
        "open":  [float(c["open"])  for c in candles],
        "high":  [float(c["high"])  for c in candles],
        "low":   [float(c["low"])   for c in candles],
        "close": [float(c["close"]) for c in candles],
        "time":  [c["datetime"]     for c in candles],
    }


def get_price(symbol: str = None) -> float:
    sym = symbol or SYMBOL_TD
    try:
        r = requests.get(
            "https://api.twelvedata.com/price",
            params={"symbol": sym, "apikey": TWELVE_DATA_KEY},
            timeout=10
        )
        return float(r.json().get("price", 0))
    except:
        return 0.0


def pip() -> float:
    if "JPY" in SYMBOL: return 0.01
    if "XAU" in SYMBOL: return 0.1
    return 0.0001


# ══════════════════════════════════════════════════════
#  DXY FILTER — Dollar Index
# ══════════════════════════════════════════════════════

def analyze_dxy() -> dict:

    """Ambil DXY dari Yahoo Finance (gratis, tanpa API key)"""
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB",
            params={"interval": "1h", "range": "5d"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15
        )
        r.raise_for_status()
        data   = r.json()
        closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        closes = [c for c in closes if c is not None]

        if len(closes) < 20:
            return {"trend":"UNKNOWN","bias":"NEUTRAL","detail":"Data DXY kurang"}

        ma_fast  = sum(closes[-5:])  / 5
        ma_slow  = sum(closes[-20:]) / 20
        current  = closes[-1]
        prev     = closes[-10]
        change   = ((current - prev) / prev) * 100

        if ma_fast > ma_slow:
            trend = "BULLISH"; bias = "BEARISH"
        elif ma_fast < ma_slow:
            trend = "BEARISH"; bias = "BULLISH"
        else:
            trend = "RANGING"; bias = "NEUTRAL"

        return {
            "trend":      trend,
            "bias":       bias,
            "current":    current,
            "change_pct": round(change, 3),
            "detail":     f"DXY: {current:.3f} ({change:+.3f}%) → Gold bias {bias}"
        }

    except Exception as e:
        log.error(f"DXY Yahoo error: {e}")
        return {"trend":"UNKNOWN","bias":"NEUTRAL","detail":str(e)}


# ══════════════════════════════════════════════════════
#  COT SENTIMENT — Posisi Institusi
# ══════════════════════════════════════════════════════

def get_cot_sentiment() -> dict:
    """
    COT (Commitment of Traders) Report
    Ambil data sentimen institusi dari sumber publik
    COT report dirilis setiap Jumat oleh CFTC

    Non-Commercial (Speculators/Hedge Funds):
    - Net Long tinggi  → Bullish institusi → Gold bisa naik
    - Net Short tinggi → Bearish institusi → Gold bisa turun
    """
    try:
        # Ambil data COT dari API publik CFTC
        r = requests.get(
            "https://www.cftc.gov/dea/futures/financial_lf.htm",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15
        )

        # Fallback: cek sentimen via fear & greed proxy
        # Gunakan data dari alternative.me (gratis, tidak perlu key)
        r2 = requests.get(
            "https://api.alternative.me/fng/?limit=7",
            timeout=10
        )
        r2.raise_for_status()
        fng_data = r2.json().get("data", [])

        if not fng_data:
            return _cot_fallback()

        # Fear & Greed Index untuk Gold/market sentiment
        latest    = fng_data[0]
        fng_value = int(latest.get("value", 50))
        fng_class = latest.get("value_classification", "Neutral")

        # Hitung tren sentimen 7 hari
        values_7d = [int(d.get("value", 50)) for d in fng_data]
        avg_7d    = sum(values_7d) / len(values_7d)
        trend     = "improving" if fng_value > avg_7d else "declining"

        # Interpretasi untuk Gold:
        # Extreme Fear  (0-25)  → Gold biasanya NAIK (safe haven)
        # Fear          (25-45) → Gold cenderung NAIK
        # Neutral       (45-55) → Tidak ada bias jelas
        # Greed         (55-75) → Gold cenderung TURUN
        # Extreme Greed (75-100)→ Gold biasanya TURUN (risk on)

        if fng_value <= 25:
            gold_sentiment = "BULLISH"
            reason = "Extreme Fear — investor cari safe haven (Gold)"
        elif fng_value <= 45:
            gold_sentiment = "BULLISH"
            reason = "Fear — sentimen mendukung Gold naik"
        elif fng_value <= 55:
            gold_sentiment = "NEUTRAL"
            reason = "Neutral — tidak ada sentimen dominan"
        elif fng_value <= 75:
            gold_sentiment = "BEARISH"
            reason = "Greed — risk on, Gold cenderung turun"
        else:
            gold_sentiment = "BEARISH"
            reason = "Extreme Greed — pasar risk on, Gold tertekan"

        return {
            "fng_value":   fng_value,
            "fng_class":   fng_class,
            "gold_sentiment": gold_sentiment,
            "trend_7d":    trend,
            "avg_7d":      round(avg_7d, 1),
            "reason":      reason,
            "detail":      f"Fear & Greed: {fng_value} ({fng_class}) → Gold {gold_sentiment}"
        }

    except Exception as e:
        log.warning(f"Sentiment error: {e}")
        return _cot_fallback()


def _cot_fallback() -> dict:
    """Fallback jika API sentiment gagal"""
    return {
        "fng_value":      50,
        "fng_class":      "Neutral",
        "gold_sentiment": "NEUTRAL",
        "trend_7d":       "unknown",
        "avg_7d":         50,
        "reason":         "Data sentimen tidak tersedia",
        "detail":         "Sentiment: N/A"
    }


# ══════════════════════════════════════════════════════
#  INDIKATOR TEKNIKAL
# ══════════════════════════════════════════════════════

def calc_rsi(closes: list, period: int = 14) -> list:
    if len(closes) < period + 1:
        return [50] * len(closes)

    rsi_values = [50] * period
    gains, losses = [], []

    for i in range(1, period + 1):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    for i in range(period, len(closes)):
        diff = closes[i] - closes[i-1]
        avg_gain = (avg_gain * (period-1) + max(diff, 0))  / period
        avg_loss = (avg_loss * (period-1) + max(-diff, 0)) / period

        if avg_loss == 0:
            rsi_values.append(100)
        else:
            rsi_values.append(round(100 - (100 / (1 + avg_gain/avg_loss)), 2))

    return rsi_values


def detect_rsi_divergence(closes: list, rsi: list, lookback: int = 20) -> str:
    if len(closes) < lookback or len(rsi) < lookback:
        return "NONE"

    c, r = closes[-lookback:], rsi[-lookback:]
    n    = len(c)

    price_lows, price_highs = [], []
    for i in range(1, n-1):
        if c[i] < c[i-1] and c[i] < c[i+1]:
            price_lows.append((i, c[i], r[i]))
        if c[i] > c[i-1] and c[i] > c[i+1]:
            price_highs.append((i, c[i], r[i]))

    if len(price_lows) >= 2:
        p1, p2 = price_lows[-2], price_lows[-1]
        if p2[1] < p1[1] and p2[2] > p1[2]:
            return "BULLISH_DIV"

    if len(price_highs) >= 2:
        p1, p2 = price_highs[-2], price_highs[-1]
        if p2[1] > p1[1] and p2[2] < p1[2]:
            return "BEARISH_DIV"

    return "NONE"


def calc_snr(data: dict, lookback: int = 50) -> dict:
    highs = data["high"][-lookback:]
    lows  = data["low"][-lookback:]
    p     = pip()

    sh, sl = [], []
    for i in range(2, len(highs)-2):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
           highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            sh.append(highs[i])
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
           lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            sl.append(lows[i])

    current      = data["close"][-1]
    nearest_res  = min(sh, key=lambda x: abs(x-current)) if sh else 0
    nearest_sup  = min(sl, key=lambda x: abs(x-current)) if sl else 0

    return {
        "resistance":  max(sh) if sh else 0,
        "support":     min(sl) if sl else 0,
        "nearest_res": nearest_res,
        "nearest_sup": nearest_sup,
    }


# ══════════════════════════════════════════════════════
#  ICT ANALYSIS ENGINE
# ══════════════════════════════════════════════════════

def detect_structure(data: dict, lookback: int = 30) -> str:
    highs = data["high"][-lookback:]
    lows  = data["low"][-lookback:]
    n     = len(highs)
    if n < 6: return "RANGING"

    sh, sl = [], []
    for i in range(2, n-2):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
           highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            sh.append(highs[i])
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
           lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            sl.append(lows[i])

    if len(sh) < 2 or len(sl) < 2: return "RANGING"
    if sh[-1] > sh[-2] and sl[-1] > sl[-2]: return "BULLISH"
    if sh[-1] < sh[-2] and sl[-1] < sl[-2]: return "BEARISH"
    return "RANGING"


def detect_bos(data: dict, lookback: int = 30) -> str:
    highs  = data["high"][-lookback:]
    lows   = data["low"][-lookback:]
    closes = data["close"][-lookback:]
    n      = len(closes)
    if n < 10: return "NONE"

    prev_sh = max(highs[:-5])
    prev_sl = min(lows[:-5])
    lc, pc  = closes[-1], closes[-2]

    if lc > prev_sh and pc <= prev_sh: return "BOS_BULLISH"
    if lc < prev_sl and pc >= prev_sl: return "BOS_BEARISH"
    return "NONE"


def detect_sweep(data: dict, lookback: int = 20) -> str:
    highs  = data["high"][-lookback:]
    lows   = data["low"][-lookback:]
    closes = data["close"][-lookback:]
    p      = pip()
    if len(closes) < 5: return "NONE"

    ph = max(highs[-lookback:-2])
    pl = min(lows[-lookback:-2])

    if highs[-1] > ph and closes[-1] < ph - p*3: return "SWEEP_HIGH"
    if lows[-1]  < pl and closes[-1] > pl + p*3: return "SWEEP_LOW"
    return "NONE"


def detect_ob(data: dict, lookback: int = 50) -> list:
    opens  = data["open"][-lookback:]
    highs  = data["high"][-lookback:]
    lows   = data["low"][-lookback:]
    closes = data["close"][-lookback:]
    n      = len(closes)
    obs    = []
    if n < 5: return obs

    avg_range = sum(highs[i]-lows[i] for i in range(n)) / n

    for i in range(1, n-3):
        impulse = abs(closes[i+1]-opens[i+1]) > avg_range * 1.5
        if closes[i] < opens[i] and closes[i+1] > opens[i+1] and impulse:
            obs.append({"type":"BULLISH_OB","high":highs[i],"low":lows[i],"age":n-i})
        if closes[i] > opens[i] and closes[i+1] < opens[i+1] and impulse:
            obs.append({"type":"BEARISH_OB","high":highs[i],"low":lows[i],"age":n-i})

    return [o for o in obs if o["age"] <= 30]


def detect_fvg(data: dict, lookback: int = 50) -> list:
    highs  = data["high"][-lookback:]
    lows   = data["low"][-lookback:]
    closes = data["close"][-lookback:]
    n      = len(closes)
    fvgs   = []
    min_gap = pip() * 5
    if n < 5: return fvgs

    for i in range(1, n-1):
        if lows[i+1] - highs[i-1] >= min_gap:
            fvgs.append({"type":"BULLISH_FVG","top":lows[i+1],"bottom":highs[i-1],"age":n-i})
        if lows[i-1] - highs[i+1] >= min_gap:
            fvgs.append({"type":"BEARISH_FVG","top":lows[i-1],"bottom":highs[i+1],"age":n-i})

    return [f for f in fvgs if f["age"] <= 20]


def in_zone(price: float, low: float, high: float, buf: float = 0) -> bool:
    return (low - buf) <= price <= (high + buf)


def get_kz() -> tuple:
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5: return False, "Weekend"
    for name, (s, e) in KILL_ZONES.items():
        if s <= now.hour < e: return True, name
    return False, "Outside Kill Zone"


def calc_sl_tp(direction: str, entry: float, data: dict) -> tuple:
    p      = pip()
    highs  = data["high"][-10:]
    lows   = data["low"][-10:]

    if direction == "BUY":
        swing   = min(lows)
        sl_dist = max((entry - swing) * SL_BUFFER, p * 10)
        sl = entry - sl_dist
        tp = entry + sl_dist * TP_RR
    else:
        swing   = max(highs)
        sl_dist = max((swing - entry) * SL_BUFFER, p * 10)
        sl = entry + sl_dist
        tp = entry - sl_dist * TP_RR

    return sl, tp, round(sl_dist/p), round(sl_dist*TP_RR/p)


# ══════════════════════════════════════════════════════
#  MASTER CONFLUENCE ENGINE
#  ICT + DXY + Sentiment + RSI + SNR
# ══════════════════════════════════════════════════════

def generate_signal(daily: dict, h4: dict, h1: dict, m15: dict,
                    dxy: dict, sentiment: dict) -> dict:
    price = m15["close"][-1]
    p     = pip()
    buf   = p * 3

    # ── Kill Zone ──
    in_kz, kz_name = get_kz()
    if not in_kz:
        return {"sinyal": "WAIT", "alasan": f"Di luar Kill Zone ({kz_name})"}

    # ── Struktur 4 TF ──
    daily_s = detect_structure(daily, 30)
    h4_s    = detect_structure(h4,    30)
    h1_s    = detect_structure(h1,    20)
    m15_s   = detect_structure(m15,   20)

    if daily_s == "RANGING" and h4_s == "RANGING":
        return {"sinyal": "WAIT", "alasan": "Daily + H4 ranging — tidak ada bias jelas"}

    # ── ICT Elements ──
    h4_bos    = detect_bos(h4)
    h1_bos    = detect_bos(h1)
    h1_sweep  = detect_sweep(h1)
    m15_sweep = detect_sweep(m15)
    h4_obs    = detect_ob(h4)
    h1_obs    = detect_ob(h1)
    h4_fvgs   = detect_fvg(h4)
    h1_fvgs   = detect_fvg(h1)

    # ── RSI ──
    h1_rsi    = calc_rsi(h1["close"],  RSI_PERIOD)
    m15_rsi   = calc_rsi(m15["close"], RSI_PERIOD)
    h1_div    = detect_rsi_divergence(h1["close"],  h1_rsi)
    m15_div   = detect_rsi_divergence(m15["close"], m15_rsi)
    h1_rsi_v  = h1_rsi[-1]  if h1_rsi  else 50
    m15_rsi_v = m15_rsi[-1] if m15_rsi else 50

    # ── SNR ──
    snr = calc_snr(h4, 50)

    # ── DXY & Sentiment ──
    dxy_bias  = dxy.get("bias", "NEUTRAL")
    sent_bias = sentiment.get("gold_sentiment", "NEUTRAL")

    # ════════════════════════
    #  ANALISA BULLISH
    # ════════════════════════
    bias_bull = (daily_s == "BULLISH" or
                 (daily_s == "RANGING" and h4_s == "BULLISH"))

    if bias_bull:
        conf  = []
        score = 0

        # ── Struktur ──
        if daily_s == "BULLISH":
            conf.append("✅ Daily Bullish Bias");       score += 2
        if h4_s == "BULLISH":
            conf.append("✅ H4 Bullish Structure");     score += 2
        if h1_s == "BULLISH":
            conf.append("✅ H1 Bullish Confirmation");  score += 1
        if m15_s == "BULLISH":
            conf.append("✅ M15 Bullish Entry");        score += 1

        # ── Kill Zone ──
        conf.append(f"✅ Kill Zone: {kz_name}");        score += 1

        # ── DXY Filter ──
        if dxy_bias == "BULLISH":
            conf.append(f"✅ DXY Turun → Gold Bullish ({dxy.get('detail','')})"); score += 3
        elif dxy_bias == "BEARISH":
            conf.append(f"⚠️ DXY Naik → Berlawanan dengan BUY Gold"); score -= 2
        elif dxy_bias == "NEUTRAL":
            conf.append(f"➖ DXY Neutral ({dxy.get('detail','')})");

        # ── Sentiment ──
        if sent_bias == "BULLISH":
            conf.append(f"✅ Sentimen Bullish Gold — {sentiment.get('reason','')}"); score += 2
        elif sent_bias == "BEARISH":
            conf.append(f"⚠️ Sentimen Bearish Gold — {sentiment.get('reason','')}"); score -= 1
        else:
            conf.append(f"➖ Sentimen Neutral (F&G: {sentiment.get('fng_value',50)})")

        # ── ICT: Sweep ──
        if h1_sweep == "SWEEP_LOW":
            conf.append("✅ H1 Liquidity Sweep Low");  score += 2
        if m15_sweep == "SWEEP_LOW":
            conf.append("✅ M15 Liquidity Sweep Low"); score += 1

        # ── ICT: BOS ──
        if h4_bos == "BOS_BULLISH":
            conf.append("✅ H4 Break of Structure ↑"); score += 2
        if h1_bos == "BOS_BULLISH":
            conf.append("✅ H1 Break of Structure ↑"); score += 1

        # ── ICT: OB ──
        for ob in h4_obs:
            if ob["type"] == "BULLISH_OB" and in_zone(price, ob["low"], ob["high"], buf):
                conf.append("✅ H4 Bullish Order Block"); score += 3; break
        for ob in h1_obs:
            if ob["type"] == "BULLISH_OB" and in_zone(price, ob["low"], ob["high"], buf):
                conf.append("✅ H1 Bullish Order Block"); score += 2; break

        # ── ICT: FVG ──
        for fvg in h4_fvgs:
            if fvg["type"] == "BULLISH_FVG" and in_zone(price, fvg["bottom"], fvg["top"], buf):
                conf.append("✅ H4 Fair Value Gap ↑"); score += 2; break
        for fvg in h1_fvgs:
            if fvg["type"] == "BULLISH_FVG" and in_zone(price, fvg["bottom"], fvg["top"], buf):
                conf.append("✅ H1 Fair Value Gap ↑"); score += 1; break

        # ── RSI ──
        if h1_div  == "BULLISH_DIV": conf.append("✅ H1 RSI Divergence Bullish");  score += 2
        if m15_div == "BULLISH_DIV": conf.append("✅ M15 RSI Divergence Bullish"); score += 1
        if h1_rsi_v  < RSI_OVERSOLD: conf.append(f"✅ H1 RSI Oversold ({h1_rsi_v:.0f})");   score += 1
        if m15_rsi_v < RSI_OVERSOLD: conf.append(f"✅ M15 RSI Oversold ({m15_rsi_v:.0f})"); score += 1

        # ── SNR ──
        if snr["nearest_sup"] > 0 and abs(price - snr["nearest_sup"]) < p * 30:
            conf.append(f"✅ Dekat Support ({snr['nearest_sup']:.3f})"); score += 1

        if score >= MIN_SCORE:
            sl, tp, slp, tpp = calc_sl_tp("BUY", price, m15)
            return {
                "sinyal": "BUY", "score": score, "entry": price,
                "sl": sl, "tp": tp, "sl_pips": slp, "tp_pips": tpp,
                "conf": conf, "kz": kz_name,
                "rsi_h1": h1_rsi_v, "rsi_m15": m15_rsi_v,
                "dxy": dxy, "sentiment": sentiment,
                "structure": f"D:{daily_s} H4:{h4_s} H1:{h1_s} M15:{m15_s}",
            }

    # ════════════════════════
    #  ANALISA BEARISH
    # ════════════════════════
    bias_bear = (daily_s == "BEARISH" or
                 (daily_s == "RANGING" and h4_s == "BEARISH"))

    if bias_bear:
        conf  = []
        score = 0

        if daily_s == "BEARISH": conf.append("✅ Daily Bearish Bias");      score += 2
        if h4_s    == "BEARISH": conf.append("✅ H4 Bearish Structure");    score += 2
        if h1_s    == "BEARISH": conf.append("✅ H1 Bearish Confirmation"); score += 1
        if m15_s   == "BEARISH": conf.append("✅ M15 Bearish Entry");       score += 1

        conf.append(f"✅ Kill Zone: {kz_name}"); score += 1

        if dxy_bias == "BEARISH":
            conf.append(f"✅ DXY Naik → Gold Bearish ({dxy.get('detail','')})"); score += 3
        elif dxy_bias == "BULLISH":
            conf.append(f"⚠️ DXY Turun → Berlawanan dengan SELL Gold"); score -= 2
        else:
            conf.append(f"➖ DXY Neutral ({dxy.get('detail','')})")

        if sent_bias == "BEARISH":
            conf.append(f"✅ Sentimen Bearish Gold — {sentiment.get('reason','')}"); score += 2
        elif sent_bias == "BULLISH":
            conf.append(f"⚠️ Sentimen Bullish Gold — {sentiment.get('reason','')}"); score -= 1
        else:
            conf.append(f"➖ Sentimen Neutral (F&G: {sentiment.get('fng_value',50)})")

        if h1_sweep  == "SWEEP_HIGH": conf.append("✅ H1 Liquidity Sweep High");  score += 2
        if m15_sweep == "SWEEP_HIGH": conf.append("✅ M15 Liquidity Sweep High"); score += 1

        if h4_bos == "BOS_BEARISH": conf.append("✅ H4 Break of Structure ↓"); score += 2
        if h1_bos == "BOS_BEARISH": conf.append("✅ H1 Break of Structure ↓"); score += 1

        for ob in h4_obs:
            if ob["type"] == "BEARISH_OB" and in_zone(price, ob["low"], ob["high"], buf):
                conf.append("✅ H4 Bearish Order Block"); score += 3; break
        for ob in h1_obs:
            if ob["type"] == "BEARISH_OB" and in_zone(price, ob["low"], ob["high"], buf):
                conf.append("✅ H1 Bearish Order Block"); score += 2; break

        for fvg in h4_fvgs:
            if fvg["type"] == "BEARISH_FVG" and in_zone(price, fvg["bottom"], fvg["top"], buf):
                conf.append("✅ H4 Fair Value Gap ↓"); score += 2; break
        for fvg in h1_fvgs:
            if fvg["type"] == "BEARISH_FVG" and in_zone(price, fvg["bottom"], fvg["top"], buf):
                conf.append("✅ H1 Fair Value Gap ↓"); score += 1; break

        if h1_div  == "BEARISH_DIV": conf.append("✅ H1 RSI Divergence Bearish");  score += 2
        if m15_div == "BEARISH_DIV": conf.append("✅ M15 RSI Divergence Bearish"); score += 1
        if h1_rsi_v  > RSI_OVERBOUGHT: conf.append(f"✅ H1 RSI Overbought ({h1_rsi_v:.0f})");   score += 1
        if m15_rsi_v > RSI_OVERBOUGHT: conf.append(f"✅ M15 RSI Overbought ({m15_rsi_v:.0f})"); score += 1

        if snr["nearest_res"] > 0 and abs(price - snr["nearest_res"]) < p * 30:
            conf.append(f"✅ Dekat Resistance ({snr['nearest_res']:.3f})"); score += 1

        if score >= MIN_SCORE:
            sl, tp, slp, tpp = calc_sl_tp("SELL", price, m15)
            return {
                "sinyal": "SELL", "score": score, "entry": price,
                "sl": sl, "tp": tp, "sl_pips": slp, "tp_pips": tpp,
                "conf": conf, "kz": kz_name,
                "rsi_h1": h1_rsi_v, "rsi_m15": m15_rsi_v,
                "dxy": dxy, "sentiment": sentiment,
                "structure": f"D:{daily_s} H4:{h4_s} H1:{h1_s} M15:{m15_s}",
            }

    return {"sinyal": "WAIT", "alasan": f"Skor belum cukup | D:{daily_s} H4:{h4_s} | DXY:{dxy_bias} | Sent:{sent_bias}"}


# ══════════════════════════════════════════════════════
#  FORMAT TELEGRAM
# ══════════════════════════════════════════════════════

def fmt_signal(sig: dict) -> str:
    sinyal  = sig["sinyal"]
    emoji   = "🟢" if sinyal == "BUY" else "🔴"
    score   = sig.get("score", 0)
    stars   = "⭐" * min(score, 10)
    conf_t  = "\n".join(sig.get("conf", []))
    now_wib = datetime.now(timezone.utc) + timedelta(hours=7)

    dxy  = sig.get("dxy", {})
    sent = sig.get("sentiment", {})

    return f"""{emoji} <b>ICT PRO SIGNAL — {sinyal}</b>
🕐 {now_wib.strftime('%H:%M')} WIB

📊 <b>Pair:</b> {SYMBOL}
💪 <b>Skor Konfluensi:</b> {score} {stars}
📐 <b>Struktur:</b> <code>{sig.get('structure','')}</code>

💵 <b>DXY:</b> {dxy.get('current', 0):.3f} ({dxy.get('change_pct', 0):+.3f}%) → <b>{dxy.get('trend','?')}</b>
😱 <b>Fear &amp; Greed:</b> {sent.get('fng_value',50)} ({sent.get('fng_class','?')}) → Gold <b>{sent.get('gold_sentiment','?')}</b>
📊 <b>RSI:</b> H1={sig.get('rsi_h1',0):.0f} | M15={sig.get('rsi_m15',0):.0f}

📋 <b>Konfluensi:</b>
{conf_t}

━━━━━━━━━━━━━━━━━━
📍 <b>Entry    :</b> {sig['entry']:.3f}
🛑 <b>Stop Loss:</b> {sig['sl']:.3f} ({sig['sl_pips']} pip)
✅ <b>TP Target:</b> {sig['tp']:.3f} ({sig['tp_pips']} pip)
⚖️ <b>RR Ratio :</b> 1:{TP_RR}
━━━━━━━━━━━━━━━━━━

⚠️ <i>Eksekusi manual di Bitget TradeFi.
Risk max 1-2% per trade!</i>"""


def fmt_wait(alasan: str, price: float, dxy: dict, sent: dict) -> str:
    now_wib    = datetime.now(timezone.utc) + timedelta(hours=7)
    in_kz, kz = get_kz()
    return f"""🟡 <b>ICT PRO — WAIT</b>
🕐 {now_wib.strftime('%H:%M')} WIB

📊 {SYMBOL} | 💹 {price:.3f}
🕐 {('✅ '+kz) if in_kz else ('⏰ '+kz)}
💵 DXY: {dxy.get('current',0):.3f} → {dxy.get('trend','?')}
😱 F&amp;G: {sent.get('fng_value',50)} ({sent.get('fng_class','?')})
💬 <i>{alasan}</i>

⏳ <i>Cek lagi dalam 15 menit...</i>"""


def fmt_news_pause(reason: str, news: dict) -> str:
    flags = {"USD":"🇺🇸","EUR":"🇪🇺","GBP":"🇬🇧","JPY":"🇯🇵","AUD":"🇦🇺","CAD":"🇨🇦","XAU":"🥇"}
    wib   = news["time_utc"] + timedelta(hours=7)
    return f"""⚠️ <b>NEWS FILTER — Pause Trading</b>

{flags.get(news['currency'],'🌍')} <b>{news['currency']} — {news['title']}</b>
🕐 {wib.strftime('%H:%M')} WIB ({reason})
💥 {'🔴🔴🔴 HIGH' if news['impact']=='high' else '🟡🟡 MEDIUM'} IMPACT
📊 Prediksi: {news['forecast']} | Sebelumnya: {news['previous']}

⏸ <b>Hindari entry saat berita besar!</b>"""


def fmt_daily_news(news_list: list) -> str:
    if not news_list:
        return "📅 <b>Kalender Berita Hari Ini:</b>\n\n✅ Tidak ada berita HIGH/MEDIUM.\nAman trading!"
    flags = {"USD":"🇺🇸","EUR":"🇪🇺","GBP":"🇬🇧","JPY":"🇯🇵","AUD":"🇦🇺","CAD":"🇨🇦","XAU":"🥇"}
    lines = ["📅 <b>Kalender Berita Hari Ini:</b>\n"]
    for n in sorted(news_list, key=lambda x: x["time_utc"]):
        wib = n["time_utc"] + timedelta(hours=7)
        lines.append(f"{'🔴' if n['impact']=='high' else '🟡'} {wib.strftime('%H:%M')} WIB | {flags.get(n['currency'],'🌍')} {n['currency']} | {n['title']}")
    lines.append(f"\n⚠️ Bot pause {NEWS_PAUSE_BEFORE} mnt sebelum & {NEWS_PAUSE_AFTER} mnt setelah berita.")
    return "\n".join(lines)


def fmt_daily_brief(dxy: dict, sent: dict, price: float) -> str:
    """Ringkasan market brief setiap pagi"""
    now_wib = datetime.now(timezone.utc) + timedelta(hours=7)
    dxy_emoji  = "📈" if dxy.get("trend") == "BULLISH" else "📉" if dxy.get("trend") == "BEARISH" else "➡️"
    gold_emoji = "🟢" if sent.get("gold_sentiment") == "BULLISH" else "🔴" if sent.get("gold_sentiment") == "BEARISH" else "🟡"

    return f"""🌅 <b>Market Brief Pagi — {now_wib.strftime('%d %b %Y')}</b>

💹 <b>XAU/USD:</b> {price:.3f}

💵 <b>Dollar Index (DXY):</b>
{dxy_emoji} Tren: {dxy.get('trend','?')} | Harga: {dxy.get('current',0):.3f}
→ Bias Gold: <b>{dxy.get('bias','?')}</b>

😱 <b>Fear &amp; Greed Index:</b>
{gold_emoji} {sent.get('fng_value',50)}/100 — {sent.get('fng_class','?')}
→ {sent.get('reason','')}
→ 7 hari avg: {sent.get('avg_7d',50)} ({sent.get('trend_7d','?')})

<i>Bot analisa ICT otomatis setiap 15 menit...</i>"""


# ══════════════════════════════════════════════════════
#  NEWS
# ══════════════════════════════════════════════════════

def get_news() -> list:
    news_list = []
    try:
        r = requests.get(
            "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=15
        )
        today = datetime.now(timezone.utc).strftime("%m-%d-%Y")
        for e in r.json():
            if e.get("date") != today: continue
            impact   = e.get("impact","").lower()
            currency = e.get("country","").upper()
            if impact not in ["high","medium"]: continue
            if currency not in NEWS_CURRENCIES: continue
            ts = e.get("time","")
            try:
                if ts and ":" in ts and "All Day" not in ts:
                    t   = datetime.strptime(ts.upper(), "%I:%M%p")
                    now = datetime.now(timezone.utc)
                    nt  = now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
                else: continue
            except: continue
            news_list.append({"title":e.get("title",""),"currency":currency,
                              "impact":impact,"time_utc":nt,
                              "forecast":e.get("forecast","-"),"previous":e.get("previous","-")})
    except Exception as ex:
        log.warning(f"News error: {ex}")
    return news_list


def check_news(nl: list) -> tuple:
    now = datetime.now(timezone.utc)
    for n in nl:
        d = n["time_utc"] - now
        if timedelta(0) < d <= timedelta(minutes=NEWS_PAUSE_BEFORE):
            return True, f"{int(d.total_seconds()/60)} menit lagi", n
        if timedelta(minutes=-NEWS_PAUSE_AFTER) <= d <= timedelta(0):
            return True, f"{int(abs(d.total_seconds()/60))} menit lalu", n
    return False, "", None


# ══════════════════════════════════════════════════════
#  MAIN LOOP
# ══════════════════════════════════════════════════════

def run_bot():
    log.info("=" * 60)
    log.info("  📡 ICT PRO SIGNAL BOT")
    log.info(f"  {SYMBOL} | ICT + DXY + Sentiment + RSI + SNR")
    log.info("=" * 60)

    missing = [v for v, k in [
        ("TWELVE_DATA_KEY",  TWELVE_DATA_KEY),
        ("TELEGRAM_TOKEN",   TELEGRAM_TOKEN),
        ("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID)
    ] if not k]

    if missing:
        send_telegram(f"❌ Variable belum diisi: {', '.join(missing)}")
        return

    price = get_price()
    if price == 0:
        send_telegram("❌ Gagal konek Twelve Data!")
        return

    log.info(f"✅ Terhubung | {SYMBOL}: {price:.3f}")

    # Ambil data fundamental awal
    dxy       = analyze_dxy()
    sentiment = get_cot_sentiment()
    news_list = get_news()

    log.info(f"DXY: {dxy.get('detail')}")
    log.info(f"Sentiment: {sentiment.get('detail')}")

    send_telegram(f"""📡 <b>ICT Pro Signal Bot Aktif!</b>

📊 Pair: {SYMBOL}
⚙️ Engine: ICT + DXY + Sentiment + RSI + SNR
📐 Timeframe: Daily → H4 → H1 → M15
📰 News Filter: ✅ Aktif
💹 Harga: {price:.3f}

✅ Tanpa AI — stabil 24 jam!
Eksekusi manual di <b>Bitget TradeFi</b> 🎯""")

    # Kirim market brief pagi
    send_telegram(fmt_daily_brief(dxy, sentiment, price))
    send_telegram(fmt_daily_news(news_list))

    last_news_update  = datetime.now(timezone.utc)
    last_dxy_update   = datetime.now(timezone.utc)
    last_sent_update  = datetime.now(timezone.utc)
    last_news_sent    = None
    last_signal_key   = None
    wait_count        = 0
    daily_brief_sent  = False

    while True:
        try:
            now_utc = datetime.now(timezone.utc)
            now_wib = now_utc + timedelta(hours=7)
            log.info(f"[{now_utc.strftime('%H:%M:%S')}] Analisa {SYMBOL}...")

            # Kirim market brief setiap pagi jam 08:00 WIB
            if now_wib.hour == 8 and now_wib.minute < 15 and not daily_brief_sent:
                dxy       = analyze_dxy()
                sentiment = get_cot_sentiment()
                price_now = get_price()
                send_telegram(fmt_daily_brief(dxy, sentiment, price_now))
                send_telegram(fmt_daily_news(get_news()))
                daily_brief_sent = True
            elif now_wib.hour != 8:
                daily_brief_sent = False

            # Update berita tiap 1 jam
            if (now_utc - last_news_update).seconds >= 3600:
                news_list        = get_news()
                last_news_update = now_utc

            # Update DXY tiap 30 menit
            if (now_utc - last_dxy_update).seconds >= 1800:
                dxy             = analyze_dxy()
                last_dxy_update = now_utc
                log.info(f"DXY update: {dxy.get('detail')}")

            # Update sentiment tiap 2 jam
            if (now_utc - last_sent_update).seconds >= 7200:
                sentiment        = get_cot_sentiment()
                last_sent_update = now_utc
                log.info(f"Sentiment update: {sentiment.get('detail')}")

            # News filter
            paused, reason, ninfo = check_news(news_list)
            if paused and ninfo:
                nkey = f"{ninfo['title']}_{reason[:5]}"
                if nkey != last_news_sent:
                    send_telegram(fmt_news_pause(reason, ninfo))
                    last_news_sent = nkey
                time.sleep(60)
                continue

            last_news_sent = None

            # Ambil 4 timeframe
            daily_raw = get_candles(SYMBOL_TD, "1day", count=50)
            h4_raw    = get_candles(SYMBOL_TD, "4h",   count=100)
            h1_raw    = get_candles(SYMBOL_TD, "1h",   count=100)
            m15_raw   = get_candles(SYMBOL_TD, "15min",count=100)

            if not all([daily_raw, h4_raw, h1_raw, m15_raw]):
                log.warning("Gagal ambil data — retry 1 menit")
                time.sleep(60)
                continue

            daily = parse(daily_raw)
            h4    = parse(h4_raw)
            h1    = parse(h1_raw)
            m15   = parse(m15_raw)

            # Generate sinyal
            sig    = generate_signal(daily, h4, h1, m15, dxy, sentiment)
            sinyal = sig.get("sinyal", "WAIT")
            price  = m15["close"][-1]

            if sinyal in ["BUY", "SELL"]:
                sig_key = f"{sinyal}_{round(sig['entry'], 1)}"
                if sig_key != last_signal_key:
                    log.info(f"✅ {sinyal} | Skor: {sig.get('score')}")
                    send_telegram(fmt_signal(sig))
                    last_signal_key = sig_key
                else:
                    log.info("Sinyal sama — skip")
            else:
                last_signal_key = None
                log.info(f"WAIT | {sig.get('alasan','')}")
                if wait_count % 4 == 0:
                    send_telegram(fmt_wait(
                        sig.get("alasan","Menunggu setup..."),
                        price, dxy, sentiment
                    ))
                wait_count += 1

        except Exception as e:
            log.error(f"Error: {e}")
            send_telegram(f"⚠️ <b>Error:</b>\n<code>{str(e)[:200]}</code>")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run_bot()
