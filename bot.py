"""
================================================================================
  ICT AI FOREX BOT — VERSI FINAL
  ✅ DeepSeek V4 Flash (analisa ICT — otak AI)
  ✅ Deriv (eksekusi order)
  ✅ Forex Factory News Filter (hindari berita besar)
  ✅ Telegram (notifikasi HP)
  ✅ Railway (server gratis 24 jam)
================================================================================
"""

import os
import time
import logging
import requests
import json
import websocket
import threading
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────────────
#  KONFIGURASI — isi di Railway Variables
# ─────────────────────────────────────────────────────
DEEPSEEK_API_KEY  = os.getenv("DEEPSEEK_API_KEY", "")   # dari platform.deepseek.com
DERIV_API_TOKEN   = os.getenv("DERIV_API_TOKEN", "")
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID", "")

# ─────────────────────────────────────────────────────
#  PENGATURAN TRADING
# ─────────────────────────────────────────────────────
# Simbol Deriv:
# Forex  : frxEURUSD, frxGBPUSD, frxUSDJPY, frxXAUUSD
# Crypto : cryBTCUSD, cryETHUSD
# Index  : R_100, R_50
ACTIVE_SYMBOL  = "frxEURUSD"
TIMEFRAME      = "3600"       # H1 = 3600 detik
TRADE_STAKE    = 10           # Modal per trade (USD)
TRADE_DURATION = 60           # Durasi kontrak (menit)
MAX_TRADES     = 1
CHECK_INTERVAL = 300          # Cek tiap 5 menit

# News Filter Settings
NEWS_PAUSE_BEFORE = 60        # Pause X menit SEBELUM berita
NEWS_PAUSE_AFTER  = 30        # Pause X menit SETELAH berita
NEWS_CURRENCIES   = ["USD", "EUR", "GBP", "JPY"]  # Mata uang yang dipantau

# ─────────────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger(__name__)

# State WebSocket Deriv
deriv_response = {}
deriv_event    = threading.Event()


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
#  📰 FOREX FACTORY NEWS FILTER
# ══════════════════════════════════════════════════════

def get_forex_factory_news() -> list:
    """
    Ambil kalender berita dari Forex Factory.
    Return list berita HIGH dan MEDIUM impact hari ini.
    """
    news_list = []

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        r   = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()

        now_utc   = datetime.now(timezone.utc)
        today_str = now_utc.strftime("%m-%d-%Y")

        for event in data:
            # Filter hanya hari ini
            if event.get("date", "") != today_str:
                continue

            impact   = event.get("impact", "").lower()
            currency = event.get("country", "").upper()

            # Hanya HIGH dan MEDIUM impact
            if impact not in ["high", "medium"]:
                continue

            # Hanya mata uang yang relevan
            if currency not in NEWS_CURRENCIES:
                continue

            # Parse waktu
            time_str = event.get("time", "")
            try:
                if time_str and time_str != "All Day" and ":" in time_str:
                    hour, minute = map(int, time_str.split(":")[:2])
                    am_pm = "am" if "am" in time_str.lower() else "pm"
                    if am_pm == "pm" and hour != 12:
                        hour += 12
                    elif am_pm == "am" and hour == 12:
                        hour = 0
                    news_time = now_utc.replace(
                        hour=hour, minute=minute, second=0, microsecond=0
                    )
                else:
                    continue
            except:
                continue

            news_list.append({
                "title":     event.get("title", "Unknown"),
                "currency":  currency,
                "impact":    impact,
                "time_utc":  news_time,
                "forecast":  event.get("forecast", "-"),
                "previous":  event.get("previous", "-"),
            })

        log.info(f"News filter: {len(news_list)} berita relevan ditemukan hari ini")

    except Exception as e:
        log.warning(f"Gagal ambil Forex Factory data: {e}")
        # Fallback: coba scraping langsung
        news_list = scrape_ff_fallback()

    return news_list


def scrape_ff_fallback() -> list:
    """Fallback scraping Forex Factory jika JSON gagal"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15"
        }
        r = requests.get(
            "https://www.forexfactory.com/calendar",
            headers=headers, timeout=15
        )
        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.find_all("tr", class_="calendar__row")
        news = []

        for row in rows:
            impact_el = row.find("td", class_="calendar__impact")
            if not impact_el:
                continue

            impact_icon = impact_el.find("span")
            if not impact_icon:
                continue

            impact_class = impact_icon.get("class", [])
            if not any("red" in c or "ora" in c for c in impact_class):
                continue

            currency_el = row.find("td", class_="calendar__currency")
            title_el    = row.find("td", class_="calendar__event")
            time_el     = row.find("td", class_="calendar__time")

            if currency_el and title_el:
                currency = currency_el.text.strip()
                if currency in NEWS_CURRENCIES:
                    news.append({
                        "title":    title_el.text.strip(),
                        "currency": currency,
                        "impact":   "high",
                        "time_utc": datetime.now(timezone.utc),
                        "forecast": "-",
                        "previous": "-",
                    })

        return news
    except Exception as e:
        log.warning(f"Fallback scraping gagal: {e}")
        return []


def check_news_filter(news_list: list) -> tuple:
    """
    Cek apakah ada berita besar dalam window waktu tertentu.

    Returns:
        (should_pause: bool, reason: str, news_info: dict or None)
    """
    now_utc       = datetime.now(timezone.utc)
    pause_before  = timedelta(minutes=NEWS_PAUSE_BEFORE)
    pause_after   = timedelta(minutes=NEWS_PAUSE_AFTER)

    for news in news_list:
        news_time = news["time_utc"]
        diff      = news_time - now_utc

        # Sebelum berita
        if timedelta(0) < diff <= pause_before:
            minutes_left = int(diff.total_seconds() / 60)
            return True, f"⏰ {minutes_left} menit lagi", news

        # Setelah berita (masih dalam window pause)
        if -pause_after <= diff <= timedelta(0):
            minutes_ago = int(abs(diff.total_seconds()) / 60)
            return True, f"🕐 {minutes_ago} menit lalu", news

    return False, "", None


def fmt_news_pause(reason: str, news: dict) -> str:
    """Format pesan pause karena berita"""
    impact_emoji = "🔴🔴🔴" if news["impact"] == "high" else "🟡🟡"
    currency_flag = {
        "USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧",
        "JPY": "🇯🇵", "AUD": "🇦🇺", "CAD": "🇨🇦"
    }.get(news["currency"], "🌍")

    news_time_wib = news["time_utc"] + timedelta(hours=7)  # Convert ke WIB

    return f"""⚠️ <b>NEWS FILTER AKTIF — Trading Dihentikan</b>

{currency_flag} <b>{news['currency']} — {news['title']}</b>
🕐 Waktu: {news_time_wib.strftime('%H:%M')} WIB ({reason})
💥 Dampak: {impact_emoji} {'HIGH' if news['impact'] == 'high' else 'MEDIUM'} IMPACT
📊 Prediksi: {news['forecast']} | Sebelumnya: {news['previous']}

⏸ Bot <b>PAUSE</b> {NEWS_PAUSE_BEFORE} menit sebelum
   dan {NEWS_PAUSE_AFTER} menit setelah berita.

<i>Ini melindungi dari volatilitas ekstrem saat berita!</i>"""


def fmt_daily_news(news_list: list) -> str:
    """Format ringkasan berita hari ini"""
    if not news_list:
        return "📅 <b>Kalender Berita Hari Ini:</b>\n\n✅ Tidak ada berita HIGH/MEDIUM impact.\nBot bebas trading sepanjang hari!"

    lines = ["📅 <b>Kalender Berita Hari Ini:</b>\n"]
    for n in sorted(news_list, key=lambda x: x["time_utc"]):
        wib_time     = n["time_utc"] + timedelta(hours=7)
        impact_emoji = "🔴" if n["impact"] == "high" else "🟡"
        flag = {
            "USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧",
            "JPY": "🇯🇵", "AUD": "🇦🇺", "CAD": "🇨🇦"
        }.get(n["currency"], "🌍")
        lines.append(
            f"{impact_emoji} {wib_time.strftime('%H:%M')} WIB | "
            f"{flag} {n['currency']} | {n['title']}"
        )

    lines.append(
        f"\n⚠️ Bot otomatis PAUSE {NEWS_PAUSE_BEFORE} menit sebelum "
        f"& {NEWS_PAUSE_AFTER} menit setelah setiap berita."
    )
    return "\n".join(lines)


# ══════════════════════════════════════════════════════
#  DERIV API
# ══════════════════════════════════════════════════════

def deriv_send(request: dict, timeout: int = 15) -> dict:
    global deriv_response, deriv_event
    deriv_response = {}
    deriv_event.clear()

    def on_message(ws, message):
        global deriv_response
        deriv_response = json.loads(message)
        deriv_event.set()

    def on_error(ws, error):
        log.error(f"Deriv WS Error: {error}")
        deriv_event.set()

    def on_open(ws):
        ws.send(json.dumps(request))

    try:
        ws = websocket.WebSocketApp(
            "wss://ws.binaryws.com/websockets/v3?app_id=1089",
            on_message=on_message, on_error=on_error, on_open=on_open
        )
        t = threading.Thread(target=ws.run_forever)
        t.daemon = True
        t.start()
        deriv_event.wait(timeout=timeout)
        ws.close()
        return deriv_response
    except Exception as e:
        log.error(f"Deriv WS Exception: {e}")
        return {}


def deriv_get_candles(symbol: str, granularity: str, count: int = 50) -> list:
    r = deriv_send({
        "ticks_history": symbol,
        "adjust_start_time": 1,
        "count": count,
        "end": "latest",
        "granularity": int(granularity),
        "style": "candles"
    }, timeout=20)
    return r.get("candles", [])


def deriv_get_balance() -> float:
    auth = deriv_send({"authorize": DERIV_API_TOKEN})
    return float(auth.get("authorize", {}).get("balance", 0))


def deriv_get_open_contracts() -> list:
    deriv_send({"authorize": DERIV_API_TOKEN})
    r = deriv_send({"portfolio": 1, "contract_type": ["CALL", "PUT"]})
    return r.get("portfolio", {}).get("contracts", [])


def deriv_buy_contract(direction: str, stake: float, duration: int) -> dict:
    deriv_send({"authorize": DERIV_API_TOKEN})
    proposal = deriv_send({
        "proposal": 1,
        "amount": stake,
        "basis": "stake",
        "contract_type": direction,
        "currency": "USD",
        "duration": duration,
        "duration_unit": "m",
        "symbol": ACTIVE_SYMBOL
    })
    if "error" in proposal:
        return proposal
    pid = proposal.get("proposal", {}).get("id")
    if not pid:
        return {}
    return deriv_send({"buy": pid, "price": stake})


def format_candles_for_ai(candles: list, label: str) -> str:
    if not candles:
        return f"{label}: Tidak ada data\n"
    lines = [f"\n📊 {label}:"]
    lines.append("Waktu (UTC)  | Open      | High      | Low       | Close")
    lines.append("-" * 60)
    for c in candles[-20:]:
        dt  = datetime.fromtimestamp(c.get("epoch", 0), tz=timezone.utc).strftime("%m-%d %H:%M")
        o   = float(c.get("open", 0))
        h   = float(c.get("high", 0))
        l   = float(c.get("low", 0))
        cl  = float(c.get("close", 0))
        arr = "▲" if cl > o else "▼"
        lines.append(f"{dt}   | {o:.5f} | {h:.5f} | {l:.5f} | {cl:.5f} {arr}")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════
#  CLAUDE AI — OTAK ICT
# ══════════════════════════════════════════════════════

def ask_deepseek_ai(market_data: str, news_context: str) -> dict:
    """Kirim data pasar ke DeepSeek V4 Flash untuk analisa ICT"""

    system_prompt = """Kamu adalah trader forex profesional dengan keahlian ICT (Inner Circle Trader).
Analisa data candlestick dan buat keputusan trading berdasarkan konsep ICT:
1. Market Structure (HH, HL, LH, LL) — Bullish/Bearish/Ranging
2. Break of Structure (BOS) dan Change of Character (CHoCH)
3. Order Block — zona institusional
4. Fair Value Gap (FVG/Imbalance)
5. Liquidity Sweep — stop hunt sebelum reversal
6. Kill Zone — London Open (07-09 UTC) dan NY Open (12-14 UTC)

Aturan KETAT:
- Rekomendasikan CALL atau PUT HANYA jika ada minimal 3 konfluensi ICT yang jelas
- Keyakinan minimal 7/10 untuk eksekusi
- Jika ada berita besar dalam waktu dekat → otomatis WAIT
- Jika pasar ranging atau tidak ada setup jelas → WAIT
- Gunakan bahasa Indonesia yang mudah dipahami pemula

Jawab HANYA dalam format JSON (tanpa teks lain, tanpa markdown):
{
  "keputusan": "CALL" atau "PUT" atau "WAIT",
  "keyakinan": angka 1-10,
  "analisa": "penjelasan analisa ICT max 3 kalimat bahasa Indonesia",
  "konfluensi": ["konfluensi 1", "konfluensi 2", "konfluensi 3"],
  "sl_pips": angka,
  "tp_pips": angka,
  "catatan": "tips atau peringatan tambahan"
}"""

    user_msg = f"""Analisa pasar dengan strategi ICT:

⏰ Waktu (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}
📊 Instrumen: {ACTIVE_SYMBOL}

{news_context}

{market_data}

Buat keputusan trading ICT dalam format JSON."""

    try:
        r = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-v4-flash",
                "max_tokens": 1000,
                "temperature": 0.1,   # Rendah agar analisa konsisten
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
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw.strip())
        log.info(f"DeepSeek: {result.get('keputusan')} | Keyakinan: {result.get('keyakinan')}/10")
        return result

    except json.JSONDecodeError:
        return {"keputusan": "WAIT", "analisa": "Error parsing respons AI", "keyakinan": 0}
    except Exception as e:
        log.error(f"DeepSeek AI error: {e}")
        return {"keputusan": "WAIT", "analisa": str(e), "keyakinan": 0}


# ══════════════════════════════════════════════════════
#  FORMAT PESAN TELEGRAM
# ══════════════════════════════════════════════════════

def fmt_signal(ai: dict, price: float, direction: str) -> str:
    emoji = "🟢" if direction == "CALL" else "🔴"
    arah  = "NAIK (CALL)" if direction == "CALL" else "TURUN (PUT)"
    stars = "⭐" * min(int(ai.get("keyakinan", 0)), 10)
    konf  = "\n  • ".join(ai.get("konfluensi", ["-"]))
    return f"""{emoji} <b>ICT AI SIGNAL — {arah}</b>

📊 <b>Instrumen:</b> {ACTIVE_SYMBOL.replace('frx','').replace('cry','')}
🤖 <b>Keyakinan AI:</b> {ai.get('keyakinan',0)}/10 {stars}

💬 <b>Analisa DeepSeek AI:</b>
<i>{ai.get('analisa', '-')}</i>

📋 <b>Konfluensi ICT:</b>
  • {konf}

📈 <b>Harga:</b> {price:.5f}
💰 <b>Modal:</b> ${TRADE_STAKE} | ⏱ <b>Durasi:</b> {TRADE_DURATION} menit

💡 <b>Catatan:</b> <i>{ai.get('catatan', '-')}</i>

✅ <i>News filter aman — tidak ada berita besar!</i>"""


# ══════════════════════════════════════════════════════
#  MAIN BOT LOOP
# ══════════════════════════════════════════════════════

def run_bot():
    log.info("=" * 55)
    log.info("  🤖 ICT AI BOT FINAL — Deriv + News Filter")
    log.info(f"  Instrumen : {ACTIVE_SYMBOL} | Otak: DeepSeek V4 Flash")
    log.info("=" * 55)

    # Cek koneksi
    if not DERIV_API_TOKEN:
        send_telegram("❌ DERIV_API_TOKEN belum diisi!"); return
    if not DEEPSEEK_API_KEY:
        send_telegram("❌ DEEPSEEK_API_KEY belum diisi!"); return

    balance = deriv_get_balance()
    if balance == 0:
        send_telegram("❌ Gagal konek Deriv! Cek token."); return

    log.info(f"✅ Deriv terhubung | Balance: ${balance:,.2f}")

    # Ambil berita hari ini
    news_list = get_forex_factory_news()

    send_telegram(f"""🤖 <b>ICT AI Bot Aktif!</b>

📊 Instrumen: {ACTIVE_SYMBOL}
🧠 Otak: DeepSeek V4 Flash (ICT)
📰 News Filter: ✅ Aktif
💰 Balance: ${balance:,.2f}
💵 Modal/trade: ${TRADE_STAKE}

Bot analisa otomatis setiap 5 menit! 🚀""")

    # Kirim kalender berita hari ini
    send_telegram(fmt_daily_news(news_list))

    wait_count       = 0
    last_news_update = datetime.now(timezone.utc)
    last_news_sent   = None

    while True:
        try:
            now_utc = datetime.now(timezone.utc)
            log.info(f"[{now_utc.strftime('%H:%M:%S')}] Siklus analisa...")

            # Update berita setiap 1 jam
            if (now_utc - last_news_update).seconds >= 3600:
                news_list        = get_forex_factory_news()
                last_news_update = now_utc
                log.info("Berita diperbarui")

            # ── NEWS FILTER ──
            paused, reason, news_info = check_news_filter(news_list)
            if paused and news_info:
                news_key = f"{news_info['title']}_{reason}"
                if news_key != last_news_sent:
                    send_telegram(fmt_news_pause(reason, news_info))
                    last_news_sent = news_key
                log.info(f"⏸ PAUSE karena berita: {news_info['title']} ({reason})")
                time.sleep(60)
                continue

            last_news_sent = None

            # ── CEK POSISI AKTIF ──
            open_contracts = deriv_get_open_contracts()
            if len(open_contracts) >= MAX_TRADES:
                log.info(f"{len(open_contracts)} kontrak aktif — skip")
                if wait_count % 6 == 0:
                    send_telegram(f"📊 <b>Update:</b> {len(open_contracts)} kontrak berjalan.\n⏳ Menunggu hasil...")
                wait_count += 1
                time.sleep(CHECK_INTERVAL)
                continue

            wait_count = 0

            # ── AMBIL DATA CANDLE ──
            htf_candles = deriv_get_candles(ACTIVE_SYMBOL, "14400", count=30)  # H4
            ltf_candles = deriv_get_candles(ACTIVE_SYMBOL, TIMEFRAME, count=50) # H1

            if not htf_candles or not ltf_candles:
                log.warning("Gagal ambil candle — retry 1 menit")
                time.sleep(60)
                continue

            # Format data + konteks berita untuk AI
            market_data  = (
                format_candles_for_ai(htf_candles, f"H4 — Struktur Pasar") + "\n" +
                format_candles_for_ai(ltf_candles, f"H1 — Timing Entry")
            )

            # Beri AI info berita hari ini
            if news_list:
                upcoming = [
                    f"- {n['currency']} {n['title']} pukul "
                    f"{(n['time_utc']+timedelta(hours=7)).strftime('%H:%M')} WIB "
                    f"({'HIGH' if n['impact']=='high' else 'MEDIUM'} impact)"
                    for n in sorted(news_list, key=lambda x: x["time_utc"])
                ]
                news_context = (
                    "📰 BERITA HARI INI (sudah difilter, tapi pertimbangkan):\n" +
                    "\n".join(upcoming)
                )
            else:
                news_context = "📰 Tidak ada berita HIGH/MEDIUM impact hari ini. Kondisi aman untuk trading."

            # ── TANYA CLAUDE AI ──
            ai        = ask_deepseek_ai(market_data, news_context)
            keputusan = ai.get("keputusan", "WAIT")
            keyakinan = int(ai.get("keyakinan", 0))

            current_price = float(ltf_candles[-1].get("close", 0))

            if keputusan in ["CALL", "PUT"] and keyakinan >= 7:
                log.info(f"✅ Sinyal {keputusan} | Keyakinan: {keyakinan}/10")

                # Kirim sinyal ke Telegram
                send_telegram(fmt_signal(ai, current_price, keputusan))

                # Eksekusi order di Deriv
                result = deriv_buy_contract(keputusan, TRADE_STAKE, TRADE_DURATION)

                if result.get("buy"):
                    buy = result["buy"]
                    send_telegram(f"""✅ <b>KONTRAK DIBELI!</b>

📋 ID: {buy.get('contract_id', '-')}
💰 Modal: ${buy.get('buy_price', TRADE_STAKE)}
📈 Potensi Profit: ${buy.get('payout', '-')}
⏱ Durasi: {TRADE_DURATION} menit

Bot memantau hasilnya secara otomatis...""")
                else:
                    err = result.get("error", {}).get("message", "Unknown")
                    send_telegram(f"⚠️ Sinyal ada tapi order gagal:\n<i>{err}</i>")

            else:
                log.info(f"AI: WAIT | {ai.get('analisa','')[:80]}")
                # Update ke Telegram tiap 30 menit agar tidak spam
                if wait_count % 6 == 0:
                    send_telegram(f"""🟡 <b>ICT AI — WAIT</b>

📊 {ACTIVE_SYMBOL} | Keyakinan: {keyakinan}/10
💬 <i>{ai.get('analisa', 'Tidak ada setup ICT valid.')}</i>

⏳ Bot cek lagi dalam 5 menit...""")
                wait_count += 1

        except Exception as e:
            log.error(f"Error loop: {e}")
            send_telegram(f"⚠️ <b>Bot Error:</b>\n{str(e)[:200]}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run_bot()
