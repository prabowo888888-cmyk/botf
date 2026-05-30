"""
================================================================================
  ICT PURE SIGNAL BOT — Tanpa AI/LLM
  ✅ Algoritma ICT matematis murni
  ✅ Twelve Data (data harga realtime)
  ✅ Forex Factory News Filter
  ✅ Telegram (sinyal ke HP)
  ✅ Railway (server gratis 24 jam)
  ✅ Tidak pernah error 429, tidak butuh API AI
================================================================================
  Konsep ICT yang dideteksi:
  - Market Structure (HH, HL, LH, LL)
  - Break of Structure (BOS)
  - Order Block (OB)
  - Fair Value Gap (FVG)
  - Liquidity Sweep
  - Kill Zone (London & NY Open)
================================================================================
"""

import os
import time
import logging
import requests
import json
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────────────
#  KONFIGURASI — isi di Railway Variables
# ─────────────────────────────────────────────────────
TWELVE_DATA_KEY  = os.getenv("TWELVE_DATA_KEY", "")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ─────────────────────────────────────────────────────
#  PENGATURAN TRADING
# ─────────────────────────────────────────────────────
SYMBOL          = "XAU/USD"     # Ganti: EUR/USD, GBP/USD, XAU/USD
SYMBOL_TD       = "XAU/USD"     # Format Twelve Data
CHECK_INTERVAL  = 900           # Cek tiap 15 menit (detik)
MIN_CONFLUENCE  = 3             # Minimal konfluensi ICT untuk sinyal
SL_MULTIPLIER   = 1.5           # SL = jarak swing * multiplier
TP_RR           = 2.0           # Risk:Reward ratio

# Kill Zone (UTC) — waktu terbaik trading ICT
KILL_ZONES = {
    "London Open": (7, 9),
    "NY Open":     (12, 14),
    "London Close":(15, 16),
    "Asia Open":   (0, 2),
}

# News Filter
NEWS_PAUSE_BEFORE = 60
NEWS_PAUSE_AFTER  = 30
NEWS_CURRENCIES   = ["USD", "EUR", "GBP", "JPY", "XAU"]

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
#  TWELVE DATA
# ══════════════════════════════════════════════════════

def get_candles(symbol: str, interval: str, count: int = 100) -> list:
    """Ambil data candle dari Twelve Data"""
    try:
        r = requests.get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol":     symbol,
                "interval":   interval,
                "outputsize": count,
                "apikey":     TWELVE_DATA_KEY,
                "timezone":   "UTC"
            },
            timeout=15
        )
        r.raise_for_status()
        data = r.json()

        if data.get("status") == "error":
            log.error(f"Twelve Data: {data.get('message')}")
            return []

        values = data.get("values", [])
        values.reverse()  # Urut dari lama ke baru
        return values

    except Exception as e:
        log.error(f"Error Twelve Data: {e}")
        return []


def parse_candles(candles: list) -> dict:
    """Parse candle ke dict array"""
    return {
        "open":  [float(c["open"])  for c in candles],
        "high":  [float(c["high"])  for c in candles],
        "low":   [float(c["low"])   for c in candles],
        "close": [float(c["close"]) for c in candles],
        "time":  [c["datetime"]     for c in candles],
    }


def get_price() -> float:
    """Ambil harga terkini"""
    try:
        r = requests.get(
            "https://api.twelvedata.com/price",
            params={"symbol": SYMBOL_TD, "apikey": TWELVE_DATA_KEY},
            timeout=10
        )
        return float(r.json().get("price", 0))
    except:
        return 0.0


# ══════════════════════════════════════════════════════
#  ICT ANALYSIS ENGINE — Algoritma Matematis Murni
# ══════════════════════════════════════════════════════

def get_pip_size() -> float:
    """Pip size berdasarkan symbol"""
    if "JPY" in SYMBOL:
        return 0.01
    elif "XAU" in SYMBOL or "GOLD" in SYMBOL:
        return 0.1
    else:
        return 0.0001


def detect_market_structure(data: dict, lookback: int = 20) -> str:
    """
    Deteksi struktur pasar berdasarkan swing high/low
    Return: BULLISH, BEARISH, atau RANGING
    """
    highs  = data["high"][-lookback:]
    lows   = data["low"][-lookback:]
    closes = data["close"][-lookback:]
    n      = len(closes)

    if n < 6:
        return "RANGING"

    # Cari swing points
    swing_highs = []
    swing_lows  = []

    for i in range(2, n - 2):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
           highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            swing_highs.append(highs[i])

        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
           lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            swing_lows.append(lows[i])

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return "RANGING"

    # Cek Higher High + Higher Low = Bullish
    hh = swing_highs[-1] > swing_highs[-2]
    hl = swing_lows[-1]  > swing_lows[-2]

    # Cek Lower High + Lower Low = Bearish
    lh = swing_highs[-1] < swing_highs[-2]
    ll = swing_lows[-1]  < swing_lows[-2]

    if hh and hl:
        return "BULLISH"
    elif lh and ll:
        return "BEARISH"
    else:
        return "RANGING"


def detect_bos(data: dict, lookback: int = 30) -> str:
    """
    Break of Structure — harga close menembus swing high/low terakhir
    Return: BOS_BULLISH, BOS_BEARISH, atau NONE
    """
    highs  = data["high"][-lookback:]
    lows   = data["low"][-lookback:]
    closes = data["close"][-lookback:]
    n      = len(closes)

    if n < 10:
        return "NONE"

    # Swing high/low dari 5-30 candle lalu (bukan 2 terakhir)
    prev_swing_high = max(highs[:-5])
    prev_swing_low  = min(lows[:-5])
    last_close      = closes[-1]
    prev_close      = closes[-2]

    # BOS Bullish — close baru pertama kali tembus swing high
    if last_close > prev_swing_high and prev_close <= prev_swing_high:
        return "BOS_BULLISH"

    # BOS Bearish — close baru pertama kali tembus swing low
    if last_close < prev_swing_low and prev_close >= prev_swing_low:
        return "BOS_BEARISH"

    return "NONE"


def detect_liquidity_sweep(data: dict, lookback: int = 20) -> str:
    """
    Liquidity Sweep — spike tembus swing lalu close berbalik
    Ini sinyal kuat smart money sudah ambil likuiditas
    Return: SWEEP_HIGH (bearish), SWEEP_LOW (bullish), NONE
    """
    highs  = data["high"][-lookback:]
    lows   = data["low"][-lookback:]
    closes = data["close"][-lookback:]
    n      = len(closes)

    if n < 5:
        return "NONE"

    prev_high  = max(highs[-lookback:-2])
    prev_low   = min(lows[-lookback:-2])
    last_high  = highs[-1]
    last_low   = lows[-1]
    last_close = closes[-1]
    pip        = get_pip_size()

    # Sweep high — wick tembus high lalu close di bawahnya (bearish reversal)
    if last_high > prev_high and last_close < prev_high - (pip * 3):
        return "SWEEP_HIGH"

    # Sweep low — wick tembus low lalu close di atasnya (bullish reversal)
    if last_low < prev_low and last_close > prev_low + (pip * 3):
        return "SWEEP_LOW"

    return "NONE"


def detect_order_blocks(data: dict, lookback: int = 50) -> list:
    """
    Order Block — candle sebelum impulse move besar
    Bullish OB: candle bearish sebelum naik kuat
    Bearish OB: candle bullish sebelum turun kuat
    """
    opens  = data["open"][-lookback:]
    highs  = data["high"][-lookback:]
    lows   = data["low"][-lookback:]
    closes = data["close"][-lookback:]
    n      = len(closes)
    obs    = []

    if n < 5:
        return obs

    avg_range = sum(highs[i] - lows[i] for i in range(n)) / n

    for i in range(1, n - 3):
        body       = abs(closes[i] - opens[i])
        next_body  = abs(closes[i+1] - opens[i+1])
        next2_body = abs(closes[i+2] - opens[i+2]) if i+2 < n else 0

        # Impulse = candle besar (> 1.5x rata-rata)
        is_impulse = next_body > avg_range * 1.5

        # Bullish OB: candle bearish + impulse naik berikutnya
        if (closes[i] < opens[i] and          # candle bearish
            closes[i+1] > opens[i+1] and      # impulse bullish
            is_impulse):
            obs.append({
                "type":  "BULLISH_OB",
                "high":  highs[i],
                "low":   lows[i],
                "index": i,
                "age":   n - i  # berapa candle lalu
            })

        # Bearish OB: candle bullish + impulse turun berikutnya
        if (closes[i] > opens[i] and          # candle bullish
            closes[i+1] < opens[i+1] and      # impulse bearish
            is_impulse):
            obs.append({
                "type":  "BEARISH_OB",
                "high":  highs[i],
                "low":   lows[i],
                "index": i,
                "age":   n - i
            })

    # Kembalikan OB yang masih relevan (< 30 candle lalu)
    return [ob for ob in obs if ob["age"] <= 30]


def detect_fvg(data: dict, lookback: int = 50) -> list:
    """
    Fair Value Gap (Imbalance) — gap antara candle 1 dan candle 3
    Harga cenderung kembali mengisi gap ini
    """
    highs  = data["high"][-lookback:]
    lows   = data["low"][-lookback:]
    closes = data["close"][-lookback:]
    n      = len(closes)
    fvgs   = []
    pip    = get_pip_size()
    min_gap = pip * 5  # Minimal 5 pip agar signifikan

    if n < 5:
        return fvgs

    for i in range(1, n - 1):
        # Bullish FVG: low[i+1] > high[i-1]
        gap = lows[i+1] - highs[i-1]
        if gap >= min_gap:
            fvgs.append({
                "type":   "BULLISH_FVG",
                "top":    lows[i+1],
                "bottom": highs[i-1],
                "mid":    (lows[i+1] + highs[i-1]) / 2,
                "index":  i,
                "age":    n - i
            })

        # Bearish FVG: high[i+1] < low[i-1]
        gap = lows[i-1] - highs[i+1]
        if gap >= min_gap:
            fvgs.append({
                "type":   "BEARISH_FVG",
                "top":    lows[i-1],
                "bottom": highs[i+1],
                "mid":    (lows[i-1] + highs[i+1]) / 2,
                "index":  i,
                "age":    n - i
            })

    return [f for f in fvgs if f["age"] <= 20]


def is_price_in_zone(price: float, zone_low: float,
                     zone_high: float, buffer: float = 0) -> bool:
    """Cek apakah harga berada di dalam zona"""
    return (zone_low - buffer) <= price <= (zone_high + buffer)


def get_kill_zone() -> tuple:
    """Cek apakah sekarang dalam Kill Zone"""
    now  = datetime.now(timezone.utc)
    hour = now.hour
    dow  = now.weekday()

    if dow >= 5:  # Weekend
        return False, "Weekend"

    for name, (start, end) in KILL_ZONES.items():
        if start <= hour < end:
            return True, name

    return False, "Outside Kill Zone"


def calculate_sl_tp(direction: str, entry: float,
                    data: dict, lookback: int = 20) -> tuple:
    """Hitung SL dan TP berdasarkan struktur"""
    pip = get_pip_size()
    highs = data["high"][-lookback:]
    lows  = data["low"][-lookback:]

    if direction == "BUY":
        swing_low = min(lows[-10:])
        sl_dist   = max((entry - swing_low) * SL_MULTIPLIER, pip * 10)
        sl        = entry - sl_dist
        tp        = entry + (sl_dist * TP_RR)
        sl_pips   = round(sl_dist / pip)
        tp_pips   = round(sl_dist * TP_RR / pip)
    else:
        swing_high = max(highs[-10:])
        sl_dist    = max((swing_high - entry) * SL_MULTIPLIER, pip * 10)
        sl         = entry + sl_dist
        tp         = entry - (sl_dist * TP_RR)
        sl_pips    = round(sl_dist / pip)
        tp_pips    = round(sl_dist * TP_RR / pip)

    return sl, tp, sl_pips, tp_pips


# ══════════════════════════════════════════════════════
#  SIGNAL GENERATOR — ICT Confluence Engine
# ══════════════════════════════════════════════════════

def generate_signal(htf: dict, ltf: dict) -> dict:
    """
    Generate sinyal ICT berdasarkan konfluensi:
    1. Market Structure (HTF)
    2. Kill Zone aktif
    3. Liquidity Sweep
    4. Order Block
    5. Fair Value Gap
    6. BOS/CHoCH
    """
    current_price = ltf["close"][-1]
    pip           = get_pip_size()
    buf           = pip * 3

    # ── Analisa HTF ──
    htf_structure = detect_market_structure(htf, lookback=30)
    if htf_structure == "RANGING":
        return {"sinyal": "WAIT", "alasan": "Pasar HTF sedang ranging/sideways"}

    # ── Kill Zone ──
    in_kz, kz_name = get_kill_zone()
    if not in_kz:
        return {"sinyal": "WAIT", "alasan": f"Di luar Kill Zone ({kz_name})"}

    # ── Deteksi semua elemen ICT ──
    sweep     = detect_liquidity_sweep(ltf)
    bos       = detect_bos(ltf)
    obs       = detect_order_blocks(ltf)
    fvgs      = detect_fvg(ltf)
    ltf_struct= detect_market_structure(ltf, lookback=20)

    # ══════════════════
    #  SINYAL BULLISH
    # ══════════════════
    if htf_structure == "BULLISH":
        confluences = []
        score       = 0

        # Konfluensi 1: HTF Structure
        confluences.append(f"✅ HTF Bullish Structure")
        score += 1

        # Konfluensi 2: Kill Zone
        confluences.append(f"✅ Kill Zone: {kz_name}")
        score += 1

        # Konfluensi 3: Liquidity Sweep
        if sweep == "SWEEP_LOW":
            confluences.append("✅ Liquidity Sweep Low (Stop Hunt)")
            score += 2

        # Konfluensi 4: BOS Bullish
        if bos == "BOS_BULLISH":
            confluences.append("✅ Break of Structure Bullish")
            score += 2

        # Konfluensi 5: LTF Structure konfirmasi
        if ltf_struct == "BULLISH":
            confluences.append("✅ LTF Structure Bullish")
            score += 1

        # Konfluensi 6: Harga di Bullish Order Block
        ob_match = None
        for ob in obs:
            if ob["type"] == "BULLISH_OB":
                if is_price_in_zone(current_price, ob["low"], ob["high"], buf):
                    confluences.append(f"✅ Bullish Order Block")
                    ob_match = ob
                    score += 3
                    break

        # Konfluensi 7: Harga di Bullish FVG
        fvg_match = None
        for fvg in fvgs:
            if fvg["type"] == "BULLISH_FVG":
                if is_price_in_zone(current_price, fvg["bottom"], fvg["top"], buf):
                    confluences.append(f"✅ Fair Value Gap Bullish")
                    fvg_match = fvg
                    score += 2
                    break

        if score >= MIN_CONFLUENCE + 2:
            sl, tp, sl_pips, tp_pips = calculate_sl_tp("BUY", current_price, ltf)
            return {
                "sinyal":      "BUY",
                "score":       score,
                "entry":       current_price,
                "sl":          sl,
                "tp":          tp,
                "sl_pips":     sl_pips,
                "tp_pips":     tp_pips,
                "confluences": confluences,
                "kz":          kz_name,
                "structure":   htf_structure,
                "ob":          ob_match,
                "fvg":         fvg_match,
            }

    # ══════════════════
    #  SINYAL BEARISH
    # ══════════════════
    elif htf_structure == "BEARISH":
        confluences = []
        score       = 0

        confluences.append(f"✅ HTF Bearish Structure")
        score += 1

        confluences.append(f"✅ Kill Zone: {kz_name}")
        score += 1

        if sweep == "SWEEP_HIGH":
            confluences.append("✅ Liquidity Sweep High (Stop Hunt)")
            score += 2

        if bos == "BOS_BEARISH":
            confluences.append("✅ Break of Structure Bearish")
            score += 2

        if ltf_struct == "BEARISH":
            confluences.append("✅ LTF Structure Bearish")
            score += 1

        ob_match = None
        for ob in obs:
            if ob["type"] == "BEARISH_OB":
                if is_price_in_zone(current_price, ob["low"], ob["high"], buf):
                    confluences.append(f"✅ Bearish Order Block")
                    ob_match = ob
                    score += 3
                    break

        fvg_match = None
        for fvg in fvgs:
            if fvg["type"] == "BEARISH_FVG":
                if is_price_in_zone(current_price, fvg["bottom"], fvg["top"], buf):
                    confluences.append(f"✅ Fair Value Gap Bearish")
                    fvg_match = fvg
                    score += 2
                    break

        if score >= MIN_CONFLUENCE + 2:
            sl, tp, sl_pips, tp_pips = calculate_sl_tp("SELL", current_price, ltf)
            return {
                "sinyal":      "SELL",
                "score":       score,
                "entry":       current_price,
                "sl":          sl,
                "tp":          tp,
                "sl_pips":     sl_pips,
                "tp_pips":     tp_pips,
                "confluences": confluences,
                "kz":          kz_name,
                "structure":   htf_structure,
                "ob":          ob_match,
                "fvg":         fvg_match,
            }

    return {"sinyal": "WAIT", "alasan": "Tidak ada konfluensi ICT yang cukup"}


# ══════════════════════════════════════════════════════
#  FORMAT PESAN TELEGRAM
# ══════════════════════════════════════════════════════

def fmt_signal(sig: dict) -> str:
    sinyal    = sig["sinyal"]
    emoji     = "🟢" if sinyal == "BUY" else "🔴"
    score     = sig.get("score", 0)
    stars     = "⭐" * min(score, 10)
    konf_text = "\n".join(sig.get("confluences", []))
    now_wib   = datetime.now(timezone.utc) + timedelta(hours=7)

    return f"""{emoji} <b>ICT SIGNAL — {sinyal}</b>
🕐 {now_wib.strftime('%H:%M')} WIB

📊 <b>Pair:</b> {SYMBOL}
💪 <b>Kekuatan:</b> {score}/10 {stars}

📋 <b>Konfluensi ICT:</b>
{konf_text}

━━━━━━━━━━━━━━━━━━
📍 <b>Entry    :</b> {sig['entry']:.5f}
🛑 <b>Stop Loss:</b> {sig['sl']:.5f} ({sig['sl_pips']} pip)
✅ <b>Take Profit:</b> {sig['tp']:.5f} ({sig['tp_pips']} pip)
⚖️ <b>RR Ratio  :</b> 1:{TP_RR}
━━━━━━━━━━━━━━━━━━

⚠️ <i>Eksekusi manual di broker kamu.
Selalu gunakan manajemen risiko!</i>"""


def fmt_wait(alasan: str, price: float) -> str:
    now_wib = datetime.now(timezone.utc) + timedelta(hours=7)
    in_kz, kz_name = get_kill_zone()
    kz_status = f"✅ {kz_name}" if in_kz else f"⏰ {kz_name}"

    return f"""🟡 <b>ICT — WAIT / NO SIGNAL</b>
🕐 {now_wib.strftime('%H:%M')} WIB

📊 {SYMBOL} | 💹 {price:.5f}
🕐 Kill Zone: {kz_status}
💬 <i>{alasan}</i>

⏳ <i>Bot cek lagi dalam 15 menit...</i>"""


def fmt_news_pause(reason: str, news: dict) -> str:
    flag_map = {
        "USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧",
        "JPY": "🇯🇵", "AUD": "🇦🇺", "CAD": "🇨🇦", "XAU": "🥇"
    }
    wib  = news["time_utc"] + timedelta(hours=7)
    flag = flag_map.get(news["currency"], "🌍")
    icon = "🔴🔴🔴" if news["impact"] == "high" else "🟡🟡"

    return f"""⚠️ <b>NEWS FILTER — Trading Dihentikan</b>

{flag} <b>{news['currency']} — {news['title']}</b>
🕐 {wib.strftime('%H:%M')} WIB ({reason})
💥 {icon} {'HIGH' if news['impact']=='high' else 'MEDIUM'} IMPACT
📊 Prediksi: {news['forecast']} | Sebelumnya: {news['previous']}

⏸ <b>Hindari entry manual saat berita besar!</b>"""


# ══════════════════════════════════════════════════════
#  FOREX FACTORY NEWS
# ══════════════════════════════════════════════════════

def get_news() -> list:
    news_list = []
    try:
        r = requests.get(
            "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15
        )
        r.raise_for_status()
        today_str = datetime.now(timezone.utc).strftime("%m-%d-%Y")

        for event in r.json():
            if event.get("date") != today_str:
                continue
            impact   = event.get("impact", "").lower()
            currency = event.get("country", "").upper()
            if impact not in ["high", "medium"]:
                continue
            if currency not in NEWS_CURRENCIES:
                continue

            time_str = event.get("time", "")
            try:
                if time_str and ":" in time_str and "All Day" not in time_str:
                    t   = datetime.strptime(time_str.upper(), "%I:%M%p")
                    now = datetime.now(timezone.utc)
                    news_time = now.replace(
                        hour=t.hour, minute=t.minute,
                        second=0, microsecond=0
                    )
                else:
                    continue
            except:
                continue

            news_list.append({
                "title":    event.get("title", ""),
                "currency": currency,
                "impact":   impact,
                "time_utc": news_time,
                "forecast": event.get("forecast", "-"),
                "previous": event.get("previous", "-"),
            })

    except Exception as e:
        log.warning(f"Gagal ambil berita: {e}")

    return news_list


def check_news(news_list: list) -> tuple:
    now = datetime.now(timezone.utc)
    for news in news_list:
        diff = news["time_utc"] - now
        if timedelta(0) < diff <= timedelta(minutes=NEWS_PAUSE_BEFORE):
            return True, f"{int(diff.total_seconds()/60)} menit lagi", news
        if timedelta(minutes=-NEWS_PAUSE_AFTER) <= diff <= timedelta(0):
            return True, f"{int(abs(diff.total_seconds()/60))} menit lalu", news
    return False, "", None


def fmt_daily_news(news_list: list) -> str:
    if not news_list:
        return "📅 <b>Kalender Berita Hari Ini:</b>\n\n✅ Tidak ada berita HIGH/MEDIUM impact.\nAman trading sepanjang hari!"

    flag_map = {"USD":"🇺🇸","EUR":"🇪🇺","GBP":"🇬🇧","JPY":"🇯🇵","AUD":"🇦🇺","CAD":"🇨🇦","XAU":"🥇"}
    lines = ["📅 <b>Kalender Berita Hari Ini:</b>\n"]
    for n in sorted(news_list, key=lambda x: x["time_utc"]):
        wib  = n["time_utc"] + timedelta(hours=7)
        icon = "🔴" if n["impact"] == "high" else "🟡"
        flag = flag_map.get(n["currency"], "🌍")
        lines.append(f"{icon} {wib.strftime('%H:%M')} WIB | {flag} {n['currency']} | {n['title']}")
    lines.append(f"\n⚠️ Bot pause {NEWS_PAUSE_BEFORE} mnt sebelum & {NEWS_PAUSE_AFTER} mnt setelah berita.")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════
#  MAIN BOT LOOP
# ══════════════════════════════════════════════════════

def run_bot():
    log.info("=" * 55)
    log.info("  📡 ICT PURE SIGNAL BOT")
    log.info(f"  Pair  : {SYMBOL} | Algoritma ICT Murni")
    log.info(f"  Tanpa LLM — Tidak pernah error 429!")
    log.info("=" * 55)

    # Cek konfigurasi
    missing = []
    if not TWELVE_DATA_KEY: missing.append("TWELVE_DATA_KEY")
    if not TELEGRAM_TOKEN:  missing.append("TELEGRAM_TOKEN")
    if not TELEGRAM_CHAT_ID:missing.append("TELEGRAM_CHAT_ID")

    if missing:
        log.error(f"Variable belum diisi: {', '.join(missing)}")
        send_telegram(f"❌ Variable belum diisi: {', '.join(missing)}")
        return

    # Test koneksi
    price = get_price()
    if price == 0:
        send_telegram("❌ Gagal konek Twelve Data! Cek TWELVE_DATA_KEY.")
        return

    log.info(f"✅ Twelve Data terhubung | {SYMBOL}: {price:.5f}")

    # Ambil berita hari ini
    news_list = get_news()

    send_telegram(f"""📡 <b>ICT Pure Signal Bot Aktif!</b>

📊 Pair: {SYMBOL}
⚙️ Engine: Algoritma ICT Matematis
📰 News Filter: ✅ Aktif
💹 Harga: {price:.5f}

✅ Tidak pakai AI — stabil 24 jam!
Bot kirim sinyal setiap ada setup ICT valid.
Kamu eksekusi manual di broker sendiri. 🎯

<i>Analisa otomatis setiap 15 menit...</i>""")

    send_telegram(fmt_daily_news(news_list))

    last_news_update = datetime.now(timezone.utc)
    last_news_sent   = None
    last_signal_key  = None
    wait_count       = 0

    while True:
        try:
            now_utc = datetime.now(timezone.utc)
            log.info(f"[{now_utc.strftime('%H:%M:%S')}] Analisa {SYMBOL}...")

            # Update berita tiap 1 jam
            if (now_utc - last_news_update).seconds >= 3600:
                news_list        = get_news()
                last_news_update = now_utc

            # ── NEWS FILTER ──
            paused, reason, news_info = check_news(news_list)
            if paused and news_info:
                news_key = f"{news_info['title']}_{reason[:5]}"
                if news_key != last_news_sent:
                    send_telegram(fmt_news_pause(reason, news_info))
                    last_news_sent = news_key
                time.sleep(60)
                continue

            last_news_sent = None

            # ── AMBIL DATA ──
            htf_raw = get_candles(SYMBOL_TD, "4h",  count=100)
            ltf_raw = get_candles(SYMBOL_TD, "1h",  count=100)

            if not htf_raw or not ltf_raw:
                log.warning("Gagal ambil candle — retry 1 menit")
                time.sleep(60)
                continue

            htf = parse_candles(htf_raw)
            ltf = parse_candles(ltf_raw)

            # ── GENERATE SINYAL ──
            sig    = generate_signal(htf, ltf)
            sinyal = sig.get("sinyal", "WAIT")

            current_price = ltf["close"][-1]

            if sinyal in ["BUY", "SELL"]:
                # Hindari kirim sinyal sama berulang
                sig_key = f"{sinyal}_{round(sig['entry'], 3)}"
                if sig_key != last_signal_key:
                    log.info(f"✅ SINYAL {sinyal} | Score: {sig.get('score')}")
                    send_telegram(fmt_signal(sig))
                    last_signal_key = sig_key
                else:
                    log.info("Sinyal sama — skip")

            else:
                last_signal_key = None
                log.info(f"WAIT | {sig.get('alasan','')}")
                # Update tiap 1 jam (4 x 15 menit)
                if wait_count % 4 == 0:
                    send_telegram(fmt_wait(sig.get("alasan", "Menunggu setup ICT..."), current_price))
                wait_count += 1

        except Exception as e:
            log.error(f"Error: {e}")
            send_telegram(f"⚠️ <b>Bot Error:</b>\n<code>{str(e)[:200]}</code>")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run_bot()
