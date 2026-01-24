import math
import json
import urllib.request
import urllib.parse
import os
import time
import logging
import telebot
from typing import Dict, Optional
from telebot import util as tb_util

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN env var is missing. Set BOT_TOKEN in your environment.")

# ADMIN_IDS can be a comma-separated list in env, e.g. "12345,67890"
_admin_env = os.getenv("ADMIN_IDS", "")
if _admin_env:
    try:
        ADMIN_IDS = set(int(x.strip()) for x in _admin_env.split(",") if x.strip())
    except ValueError:
        ADMIN_IDS = {956046532}
else:
    ADMIN_IDS = {956046532}

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="MarkdownV2")

# ================= API CONFIG =================
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
DEFILLAMA_BASE_URL = "https://api.llama.fi"

MAX_COINS = int(os.getenv("MAX_COINS", "50"))
TIMEOUT = 20
HEADERS = {"User-Agent": "Mozilla/5.0"}

# basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nansenprobot")

# ================= HTTP =================
def fetch_json(url: str, params: Optional[Dict] = None, retries: int = 3, backoff: float = 1.0):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    attempt = 0
    while attempt < retries:
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            attempt += 1
            logger.warning("HTTP error on %s (attempt %d/%d): %s", url, attempt, retries, e)
            if attempt >= retries:
                logger.error("Failed to fetch %s after %d attempts", url, retries)
                return None
            time.sleep(backoff * (2 ** (attempt - 1)))
    return None

# ================= MARKET =================
def global_metrics():
    g = fetch_json(f"{COINGECKO_BASE_URL}/global")
    if not g:
        return {"btc_dom": 0.0, "btc_change": 0.0}
    try:
        btc_dom = float(g["data"]["market_cap_percentage"].get("btc", 0) or 0)
    except Exception:
        btc_dom = 0.0

    btc_price = fetch_json(
        f"{COINGECKO_BASE_URL}/simple/price",
        {"ids": "bitcoin", "vs_currencies": "usd", "include_24hr_change": "true"}
    )

    try:
        btc_change = float(btc_price["bitcoin"].get("usd_24h_change", 0) or 0) if btc_price else 0.0
    except Exception:
        btc_change = 0.0

    return {"btc_dom": btc_dom, "btc_change": btc_change}


def market_regime(btc_dom, btc_change):
    if btc_change < -2:
        return "RISK OFF"
    if btc_dom > 52 and btc_change > 0:
        return "BTC SEASON"
    return "ALT SEASON"

# ================= ANALYSIS =================
def fdv_risk(mcap, fdv):
    try:
        mcap = float(mcap or 0)
        fdv = float(fdv or mcap or 0)
        if fdv == 0:
            return 0.0
        r = mcap / fdv
        return 100 * (1 - (1 / (1 + math.exp(-10 * (r - 0.3)))))
    except Exception:
        return 0.0


def analyze_coin(c, regime):
    volume = (c.get("total_volume") or 0) or 0
    mcap = (c.get("market_cap") or 0) or 0
    fdv = c.get("fully_diluted_valuation") or mcap or 0
    change = (c.get("price_change_percentage_24h") or 0) or 0

    # guard numeric coercion
    try:
        volume = float(volume)
    except Exception:
        volume = 0.0
    try:
        mcap = float(mcap)
    except Exception:
        mcap = 0.0
    try:
        fdv = float(fdv)
    except Exception:
        fdv = mcap
    try:
        change = float(change)
    except Exception:
        change = 0.0

    efficiency = (math.log10(volume + 1) if volume >= 0 else 0) / (abs(change) + 0.5)
    risk = fdv_risk(mcap, fdv)

    score = efficiency * 4 + (100 - risk) * 0.3
    if regime != "ALT SEASON":
        score *= 0.6

    score = max(0, min(100, score))
    return {
        "symbol": (c.get("symbol") or "").upper(),
        "score": int(round(score)),
        "change": change,
        "mcap": mcap
    }

# ================= FORMAT =================
def money(v):
    try:
        v = float(v or 0)
    except Exception:
        v = 0.0
    if v >= 1e9:
        return f"${v/1e9:.2f}B"
    if v >= 1e6:
        return f"${v/1e6:.0f}M"
    return f"${v:,.0f}"

def pct(v):
    try:
        v = float(v or 0)
    except Exception:
        v = 0.0
    return f"{v:+.2f}%"

# ================= ACCESS =================
def is_admin(uid):
    return uid in ADMIN_IDS

# ================= COMMANDS =================
@bot.message_handler(commands=["start"])
def start(m):
    bot.send_message(
        m.chat.id,
        "🤖 *Nansen Pro Intelligence*\n\n"
        "/run — Full market scan (admin)\n"
        "/help — Commands"
    )

@bot.message_handler(commands=["help"])
def help_cmd(m):
    bot.send_message(
        m.chat.id,
        "*Commands:*\n\n"
        "/run — Execute full analysis\n"
        "Admin only"
    )

@bot.message_handler(commands=["run"])
def run(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "⛔ Unauthorized")
        return

    bot.send_message(m.chat.id, "🔄 Running analysis…")
    try:
        metrics = global_metrics()
        regime = market_regime(metrics["btc_dom"], metrics["btc_change"])

        coins = fetch_json(
            f"{COINGECKO_BASE_URL}/coins/markets",
            {
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": MAX_COINS,
                "price_change_percentage": "24h"
            }
        )

        analyzed = [analyze_coin(c, regime) for c in (coins or [])]
        analyzed.sort(key=lambda x: x["score"], reverse=True)

        msg = f"*🧭 MARKET REGIME*\n{tb_util.escape_markdown(regime, version=2)}\n\n*🚀 TOP ALPHA*\n\n"

        for c in analyzed[:10]:
            sym = tb_util.escape_markdown(c["symbol"], version=2)
            score = c["score"]
            change = tb_util.escape_markdown(pct(c["change"]), version=2)
            mcap = tb_util.escape_markdown(money(c["mcap"]), version=2)
            msg += f"*{sym}* — Score `{score}`\n24h {change} | {mcap}\n\n"

        bot.send_message(m.chat.id, msg)
    except Exception as ex:
        logger.exception("Unhandled error during /run")
        bot.send_message(m.chat.id, "❌ An error occurred while running analysis.")
        # notify admins
        for aid in ADMIN_IDS:
            try:
                bot.send_message(aid, f"Error in bot /run: {ex}")
            except Exception:
                logger.exception("Failed to notify admin %s", aid)

# ================= RUN =================
if __name__ == "__main__":
    logger.info("🚀 Nansen Pro Bot — starting")
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
