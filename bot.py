"""
================================================================================
  ICT AI SIGNAL BOT — VERSI FINAL
  ✅ DeepSeek V4 Flash (analisa ICT)
  ✅ Twelve Data (data harga forex realtime)
  ✅ Forex Factory News Filter
  ✅ Telegram (kirim sinyal ke HP)
  ✅ Railway (server gratis 24 jam)
  ❌ Tidak ada eksekusi otomatis — kamu eksekusi manual di broker
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
DEEPSEEK_API_KEY  = os.getenv("DEEPSEEK_API_KEY", "")   # platform.deepseek.com
TWELVE_DATA_KEY   = os.getenv("TWELVE_DATA_KEY", "")    # twelvedata.com
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID", "")

# ─────────────────────────────────────────────────────
#  PENGATURAN TRADING
# ─────────────────────────────────────────────────────
# Pair forex yang ingin dianalisa
# Contoh: EUR/USD, GBP/USD, USD/JPY, XAU/USD (Gold)
SYMBOL          = "EUR/USD"
SYMBOL_TD       = "EUR/USD"    # Format Twelve Data
CHECK_INTERVAL  = 300          # Cek tiap 5 menit
SL_PIPS         = 15           # Info SL untuk sinyal
TP_RR           = 2.0          # Risk:Reward ratio

# News Filter
NEWS_PAUSE_BEFORE = 60         # Pause X menit sebelum berita
NEWS_PAUSE_AFTER  = 30         # Pause X menit setelah berita
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
    """Kirim pesan ke Telegram HP"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram belum dikonfigurasi")
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML"
            },
            timeout=10
        )
        r.raise_for_status()
    except Exception as e:
        log.error(f"Telegram error: {e}")


# ══════════════════════════════════════════════════════
#  TWELVE DATA — AMBIL DATA HARGA
# ══════════════════════════════════════════════════════

def get_candles_twelvedata(symbol: str, interval: str, count: int = 50) -> list:
    """
    Ambil data candlestick dari Twelve Data
    interval: 1min, 5min, 15min, 1h, 4h, 1day
    """
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
            log.error(f"Twelve Data error: {data.get('message')}")
            return []

        values = data.get("values", [])
        # Twelve Data return terbaru di atas — balik urutannya
        values.reverse()
        return values

    except Exception as e:
        log.error(f"Error ambil data Twelve Data: {e}")
        return []


def format_candles_for_ai(candles: list, label: str) -> str:
    """Format candle ke teks yang mudah dibaca AI"""
    if not candles:
        return f"{label}: Tidak ada data\n"

    lines = [f"\n📊 {label}:"]
    lines.append("Waktu (UTC)      | Open      | High      | Low       | Close")
    lines.append("-" * 65)

    for c in candles[-20:]:
        dt  = c.get("datetime", "")[:16]
        o   = float(c.get("open", 0))
        h   = float(c.get("high", 0))
        l   = float(c.get("low", 0))
        cl  = float(c.get("close", 0))
        arr = "▲" if cl > o else "▼"
        lines.append(f"{dt}  | {o:.5f} | {h:.5f} | {l:.5f} | {cl:.5f} {arr}")

    return "\n".join(lines)


def get_current_price(symbol: str) -> float:
    """Ambil harga terkini"""
    try:
        r = requests.get(
            "https://api.twelvedata.com/price",
            params={"symbol": symbol, "apikey": TWELVE_DATA_KEY},
            timeout=10
        )
        r.raise_for_status()
        return float(r.json().get("price", 0))
    except:
        return 0.0


# ══════════════════════════════════════════════════════
#  FOREX FACTORY NEWS FILTER
# ══════════════════════════════════════════════════════

def get_forex_factory_news() -> list:
    """Ambil kalender berita dari Forex Factory"""
    news_list = []
    try:
        r = requests.get(
            "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15
        )
        r.raise_for_status()
        data      = r.json()
        today_str = datetime.now(timezone.utc).strftime("%m-%d-%Y")

        for event in data:
            if event.get("date", "") != today_str:
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
                    t       = datetime.strptime(time_str.upper(), "%I:%M%p")
                    now_utc = datetime.now(timezone.utc)
                    news_time = now_utc.replace(
                        hour=t.hour, minute=t.minute,
                        second=0, microsecond=0
                    )
                else:
                    continue
            except:
                continue

            news_list.append({
                "title":    event.get("title", "Unknown"),
                "currency": currency,
                "impact":   impact,
                "time_utc": news_time,
                "forecast": event.get("forecast", "-"),
                "previous": event.get("previous", "-"),
            })

        log.info(f"News filter: {len(news_list)} berita relevan hari ini")
    except Exception as e:
        log.warning(f"Gagal ambil berita: {e}")

    return news_list


def check_news_filter(news_list: list) -> tuple:
    """Cek apakah ada berita besar dalam window waktu"""
    now_utc = datetime.now(timezone.utc)

    for news in news_list:
        diff = news["time_utc"] - now_utc

        if timedelta(0) < diff <= timedelta(minutes=NEWS_PAUSE_BEFORE):
            menit = int(diff.total_seconds() / 60)
            return True, f"{menit} menit lagi", news

        if timedelta(minutes=-NEWS_PAUSE_AFTER) <= diff <= timedelta(0):
            menit = int(abs(diff.total_seconds()) / 60)
            return True, f"{menit} menit lalu", news

    return False, "", None


def fmt_daily_news(news_list: list) -> str:
    """Format kalender berita harian"""
    if not news_list:
        return "📅 <b>Kalender Berita Hari Ini:</b>\n\n✅ Tidak ada berita HIGH/MEDIUM impact.\nAman trading sepanjang hari!"

    flag_map = {
        "USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧",
        "JPY": "🇯🇵", "AUD": "🇦🇺", "CAD": "🇨🇦", "XAU": "🥇"
    }
    lines = ["📅 <b>Kalender Berita Hari Ini:</b>\n"]
    for n in sorted(news_list, key=lambda x: x["time_utc"]):
        wib  = n["time_utc"] + timedelta(hours=7)
        icon = "🔴" if n["impact"] == "high" else "🟡"
        flag = flag_map.get(n["currency"], "🌍")
        lines.append(f"{icon} {wib.strftime('%H:%M')} WIB | {flag} {n['currency']} | {n['title']}")

    lines.append(f"\n⚠️ Bot pause {NEWS_PAUSE_BEFORE} mnt sebelum & {NEWS_PAUSE_AFTER} mnt setelah berita.")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════
#  DEEPSEEK V4 FLASH — OTAK ANALISA ICT
# ══════════════════════════════════════════════════════

def ask_deepseek(market_data: str, news_context: str) -> dict:
    """Kirim data ke DeepSeek V4 Flash untuk analisa ICT"""

    system_prompt = """Kamu adalah trader forex profesional dengan keahlian mendalam di strategi ICT (Inner Circle Trader).
Tugasmu menganalisa data candlestick dan memberikan sinyal trading yang akurat.

Konsep ICT yang WAJIB dianalisa:
1. MARKET STRUCTURE — identifikasi tren (Bullish/Bearish/Ranging) dari HH, HL, LH, LL
2. BREAK OF STRUCTURE (BOS) — konfirmasi tren berlanjut
3. CHANGE OF CHARACTER (CHoCH) — potensi reversal/pembalikan
4. ORDER BLOCK — zona supply/demand institusional (candle sebelum impulse move besar)
5. FAIR VALUE GAP (FVG/Imbalance) — gap harga yang belum terisi
6. LIQUIDITY SWEEP — spike menembus swing high/low lalu berbalik (stop hunt)
7. KILL ZONE — London Open (07-09 UTC) dan NY Open (12-14 UTC) adalah waktu terbaik entry

Aturan KETAT untuk sinyal:
- Berikan sinyal BUY atau SELL HANYA jika ada MINIMAL 3 konfluensi ICT yang kuat
- Keyakinan minimal 7/10 untuk memberikan sinyal
- Jika ada berita besar dalam waktu dekat → WAIT
- Jika pasar sedang ranging/sideways → WAIT
- Jelaskan analisa dalam Bahasa Indonesia yang mudah dipahami pemula
- Berikan level entry, SL, dan TP yang spesifik berdasarkan struktur pasar

Jawab HANYA dalam format JSON berikut (tanpa teks lain, tanpa markdown backtick):
{
  "sinyal": "BUY" atau "SELL" atau "WAIT",
  "keyakinan": angka 1-10,
  "analisa": "penjelasan analisa ICT dalam bahasa Indonesia, max 4 kalimat, mudah dipahami pemula",
  "konfluensi": ["konfluensi 1", "konfluensi 2", "konfluensi 3"],
  "entry": angka harga entry yang disarankan,
  "sl": angka harga stop loss,
  "tp": angka harga take profit,
  "sl_pips": angka jarak SL dalam pip,
  "tp_pips": angka jarak TP dalam pip,
  "catatan": "tips atau peringatan penting untuk trader"
}"""

    user_msg = f"""Analisa pasar berikut menggunakan strategi ICT:

⏰ Waktu sekarang (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}
📊 Pair: {SYMBOL}

{news_context}

{market_data}

Berikan analisa ICT lengkap dan sinyal trading dalam format JSON."""

    try:
        r = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type":  "application/json"
            },
            json={
                "model":       "deepseek-v4-flash",
                "max_tokens":  1024,
                "temperature": 0.1,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_msg}
                ]
            },
            timeout=30
        )
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"].strip()

        # Bersihkan markdown jika ada
        if "```" in raw:
            parts = raw.split("```")
            raw   = parts[1] if len(parts) > 1 else parts[0]
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw.strip())
        log.info(f"DeepSeek: {result.get('sinyal')} | Keyakinan: {result.get('keyakinan')}/10")
        return result

    except json.JSONDecodeError as e:
        log.error(f"JSON parse error: {e} | Raw: {raw[:200]}")
        return {"sinyal": "WAIT", "analisa": "Error parsing respons AI", "keyakinan": 0}
    except Exception as e:
        log.error(f"DeepSeek error: {e}")
        return {"sinyal": "WAIT", "analisa": str(e), "keyakinan": 0}


# ══════════════════════════════════════════════════════
#  FORMAT PESAN TELEGRAM
# ══════════════════════════════════════════════════════

def fmt_signal(ai: dict, current_price: float) -> str:
    sinyal    = ai.get("sinyal", "WAIT")
    emoji     = "🟢" if sinyal == "BUY" else "🔴"
    keyakinan = int(ai.get("keyakinan", 0))
    stars     = "⭐" * keyakinan
    konf      = ai.get("konfluensi", [])
    konf_text = "\n  • ".join(konf) if konf else "-"

    entry = ai.get("entry", current_price)
    sl    = ai.get("sl", 0)
    tp    = ai.get("tp", 0)

    now_wib = datetime.now(timezone.utc) + timedelta(hours=7)

    return f"""{emoji} <b>ICT SIGNAL — {sinyal}</b>
🕐 {now_wib.strftime('%H:%M')} WIB

📊 <b>Pair:</b> {SYMBOL}
🤖 <b>Keyakinan AI:</b> {keyakinan}/10
{stars}

💬 <b>Analisa DeepSeek AI:</b>
<i>{ai.get('analisa', '-')}</i>

📋 <b>Konfluensi ICT:</b>
  • {konf_text}

━━━━━━━━━━━━━━━━━━
📍 <b>Entry  :</b> {entry:.5f}
🛑 <b>Stop Loss :</b> {sl:.5f} ({ai.get('sl_pips','?')} pip)
✅ <b>Take Profit:</b> {tp:.5f} ({ai.get('tp_pips','?')} pip)
⚖️ <b>RR Ratio :</b> 1:{TP_RR}
━━━━━━━━━━━━━━━━━━

💡 <b>Catatan:</b>
<i>{ai.get('catatan', '-')}</i>

⚠️ <i>Eksekusi manual di broker kamu.
Selalu gunakan manajemen risiko!</i>"""


def fmt_news_pause(reason: str, news: dict) -> str:
    flag_map = {
        "USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧",
        "JPY": "🇯🇵", "AUD": "🇦🇺", "CAD": "🇨🇦"
    }
    wib  = news["time_utc"] + timedelta(hours=7)
    flag = flag_map.get(news["currency"], "🌍")
    icon = "🔴🔴🔴" if news["impact"] == "high" else "🟡🟡"

    return f"""⚠️ <b>NEWS FILTER — Trading Dihentikan</b>

{flag} <b>{news['currency']} — {news['title']}</b>
🕐 Waktu: {wib.strftime('%H:%M')} WIB ({reason})
💥 Dampak: {icon} {'HIGH' if news['impact']=='high' else 'MEDIUM'} IMPACT
📊 Prediksi: {news['forecast']} | Sebelumnya: {news['previous']}

⏸ <b>Bot PAUSE otomatis.</b>
Hindari entry manual saat berita besar!"""


# ══════════════════════════════════════════════════════
#  MAIN BOT LOOP
# ══════════════════════════════════════════════════════

def run_bot():
    log.info("=" * 55)
    log.info("  📡 ICT AI SIGNAL BOT")
    log.info(f"  Pair  : {SYMBOL} | Otak: DeepSeek V4 Flash")
    log.info(f"  Data  : Twelve Data | Sinyal → Telegram")
    log.info("=" * 55)

    # Cek konfigurasi
    missing = []
    if not DEEPSEEK_API_KEY: missing.append("DEEPSEEK_API_KEY")
    if not TWELVE_DATA_KEY:  missing.append("TWELVE_DATA_KEY")
    if not TELEGRAM_TOKEN:   missing.append("TELEGRAM_TOKEN")
    if not TELEGRAM_CHAT_ID: missing.append("TELEGRAM_CHAT_ID")

    if missing:
        msg = f"❌ Variable belum diisi: {', '.join(missing)}"
        log.error(msg)
        send_telegram(msg)
        return

    # Test koneksi Twelve Data
    test_price = get_current_price(SYMBOL_TD)
    if test_price == 0:
        send_telegram("❌ Gagal konek Twelve Data! Cek TWELVE_DATA_KEY.")
        return

    log.info(f"✅ Twelve Data terhubung | {SYMBOL}: {test_price:.5f}")

    # Ambil berita hari ini
    news_list = get_forex_factory_news()

    send_telegram(f"""📡 <b>ICT AI Signal Bot Aktif!</b>

📊 Pair: {SYMBOL}
🧠 Otak: DeepSeek V4 Flash (ICT)
📰 News Filter: ✅ Aktif
💹 Harga saat ini: {test_price:.5f}

Bot kirim sinyal ICT setiap ada setup valid.
Kamu eksekusi manual di broker sendiri. 🎯

<i>Analisa otomatis setiap 5 menit...</i>""")

    # Kirim kalender berita hari ini
    send_telegram(fmt_daily_news(news_list))

    last_news_update = datetime.now(timezone.utc)
    last_news_sent   = None
    last_signal      = None
    wait_count       = 0

    while True:
        try:
            now_utc = datetime.now(timezone.utc)
            log.info(f"[{now_utc.strftime('%H:%M:%S')}] Menganalisa {SYMBOL}...")

            # Update berita setiap 1 jam
            if (now_utc - last_news_update).seconds >= 3600:
                news_list        = get_forex_factory_news()
                last_news_update = now_utc

            # ── NEWS FILTER ──
            paused, reason, news_info = check_news_filter(news_list)
            if paused and news_info:
                news_key = f"{news_info['title']}_{reason[:5]}"
                if news_key != last_news_sent:
                    send_telegram(fmt_news_pause(reason, news_info))
                    last_news_sent = news_key
                log.info(f"⏸ PAUSE: {news_info['title']} ({reason})")
                time.sleep(60)
                continue

            last_news_sent = None

            # ── AMBIL DATA CANDLE ──
            htf_candles = get_candles_twelvedata(SYMBOL_TD, "4h",  count=30)
            ltf_candles = get_candles_twelvedata(SYMBOL_TD, "1h",  count=50)
            m15_candles = get_candles_twelvedata(SYMBOL_TD, "15min", count=30)

            if not htf_candles or not ltf_candles:
                log.warning("Gagal ambil data — retry 1 menit")
                time.sleep(60)
                continue

            # Format data untuk AI
            market_data = (
                format_candles_for_ai(htf_candles, "H4 — Struktur Pasar (HTF)") +
                "\n" +
                format_candles_for_ai(ltf_candles, "H1 — Konfirmasi Entry") +
                "\n" +
                format_candles_for_ai(m15_candles, "M15 — Timing Entry Presisi")
            )

            # Konteks berita untuk AI
            if news_list:
                upcoming = [
                    f"- {n['currency']} '{n['title']}' pukul "
                    f"{(n['time_utc']+timedelta(hours=7)).strftime('%H:%M')} WIB "
                    f"({'HIGH' if n['impact']=='high' else 'MEDIUM'} impact)"
                    for n in sorted(news_list, key=lambda x: x["time_utc"])
                ]
                news_context = "📰 BERITA HARI INI (pertimbangkan dalam analisa):\n" + "\n".join(upcoming)
            else:
                news_context = "📰 Tidak ada berita HIGH/MEDIUM impact hari ini. Kondisi aman."

            # ── TANYA DEEPSEEK AI ──
            ai        = ask_deepseek(market_data, news_context)
            sinyal    = ai.get("sinyal", "WAIT")
            keyakinan = int(ai.get("keyakinan", 0))

            current_price = float(ltf_candles[-1].get("close", 0))

            if sinyal in ["BUY", "SELL"] and keyakinan >= 7:
                # Hindari kirim sinyal sama berulang kali
                signal_key = f"{sinyal}_{current_price:.3f}"
                if signal_key != last_signal:
                    log.info(f"✅ SINYAL {sinyal} | Keyakinan: {keyakinan}/10")
                    send_telegram(fmt_signal(ai, current_price))
                    last_signal = signal_key
                else:
                    log.info(f"Sinyal sama seperti sebelumnya — skip")

            else:
                last_signal = None
                log.info(f"WAIT | {ai.get('analisa','')[:80]}")
                # Update tiap 30 menit agar tidak spam
                if wait_count % 6 == 0:
                    now_wib = now_utc + timedelta(hours=7)
                    send_telegram(f"""🟡 <b>ICT AI — WAIT / NO SIGNAL</b>
🕐 {now_wib.strftime('%H:%M')} WIB

📊 {SYMBOL} | Keyakinan: {keyakinan}/10
💬 <i>{ai.get('analisa', 'Tidak ada setup ICT valid saat ini.')}</i>

⏳ <i>Bot cek lagi dalam 5 menit...</i>""")
                wait_count += 1

        except Exception as e:
            log.error(f"Error loop: {e}")
            send_telegram(f"⚠️ <b>Bot Error:</b>\n<code>{str(e)[:200]}</code>")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run_bot()
