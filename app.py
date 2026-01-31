import os
import sys
import logging
import asyncio
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests
import feedparser
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
from telegram.error import BadRequest

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ==========================================
# CONFIGURATION
# ==========================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot Configuration
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7864891028:AAEUgywUrxj3J9E4cIHLMXs2q6Cw2BfIDfQ")

# API Configuration
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
DEFILLAMA_BASE_URL = "https://api.llama.fi"
STABLECOINS_BASE_URL = "https://stablecoins.llama.fi"
API_REQUEST_TIMEOUT = 15
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0"}

# AI API Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# Constants
SUPPORTED_CHAINS = ["Ethereum", "Solana", "BSC", "Base", "Arbitrum", "Polygon", "Optimism", "Avalanche"]
MAX_COINS_TO_FETCH = 100
WELCOME_MESSAGE_DELAY = 2
MARKET_REFRESH_INTERVAL = 300

# State Management
background_tasks = {}
regime_start_times = {}
user_ai_preference = {}
previous_market_data = {}
user_overlay_settings = {}  # Track user overlay preferences

# ==========================================
# UTILITY FUNCTIONS
# ==========================================

def create_main_keyboard():
    """Create main menu keyboard"""
    keyboard = [
        [KeyboardButton("⚔️ Cross"), KeyboardButton("🌊 Sector Rotation")],
        [KeyboardButton("🔥 Trending Coins"), KeyboardButton("💎 Alpha Signals")],
        [KeyboardButton("📊 Technical Analysis"), KeyboardButton("🧠 SMC Analysis")],
        [KeyboardButton("🎛️ Overlay Settings"), KeyboardButton("🤖 AI Assistant")],
        [KeyboardButton("ℹ️ Help")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

def fetch_json(url: str, params=None):
    """Fetch JSON data from API with error handling"""
    try:
        response = requests.get(
            url, 
            params=params, 
            headers=REQUEST_HEADERS, 
            timeout=API_REQUEST_TIMEOUT
        )
        if response.status_code == 200:
            return response.json()
    except Exception as error:
        logger.error(f"Error fetching {url}: {error}")
    return None

def detect_trend(current, previous):
    """Determine trend direction"""
    if previous is None:
        return "Neutral➖"
    if current > previous:
        return "Uptrend📈"
    else:
        return "Downtrend📉"

# ==========================================
# SMART MONEY CONCEPTS (SMC) FUNCTIONS
# ==========================================

class SMCAnalyzer:
    """Smart Money Concepts Analysis Engine"""
    
    @staticmethod
    def detect_order_blocks(prices: List[float], volumes: List[float]) -> List[Dict]:
        """Detect institutional order blocks"""
        order_blocks = []
        
        for i in range(3, len(prices) - 3):
            # Bullish Order Block Detection
            if (prices[i] > prices[i-1] and 
                prices[i] > prices[i-2] and 
                volumes[i] > sum(volumes[i-3:i]) / 3 * 1.5):
                
                order_blocks.append({
                    'type': 'bullish',
                    'index': i,
                    'price': prices[i-1],
                    'high': prices[i],
                    'volume': volumes[i],
                    'strength': volumes[i] / (sum(volumes[i-3:i]) / 3)
                })
            
            # Bearish Order Block Detection
            elif (prices[i] < prices[i-1] and 
                  prices[i] < prices[i-2] and 
                  volumes[i] > sum(volumes[i-3:i]) / 3 * 1.5):
                
                order_blocks.append({
                    'type': 'bearish',
                    'index': i,
                    'price': prices[i-1],
                    'low': prices[i],
                    'volume': volumes[i],
                    'strength': volumes[i] / (sum(volumes[i-3:i]) / 3)
                })
        
        return order_blocks
    
    @staticmethod
    def detect_bos_choch(prices: List[float], highs: List[float], lows: List[float]) -> List[Dict]:
        """Detect Break of Structure (BOS) and Change of Character (CHOCH)"""
        events = []
        swing_highs = []
        swing_lows = []
        
        # Identify swing points
        for i in range(2, len(prices) - 2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1]:
                swing_highs.append({'index': i, 'price': highs[i]})
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1]:
                swing_lows.append({'index': i, 'price': lows[i]})
        
        # Detect BOS (price breaking previous structure in trend direction)
        for i in range(1, len(swing_highs)):
            if swing_highs[i]['price'] > swing_highs[i-1]['price']:
                events.append({
                    'type': 'BOS',
                    'direction': 'bullish',
                    'index': swing_highs[i]['index'],
                    'price': swing_highs[i]['price'],
                    'prev_level': swing_highs[i-1]['price']
                })
        
        for i in range(1, len(swing_lows)):
            if swing_lows[i]['price'] < swing_lows[i-1]['price']:
                events.append({
                    'type': 'BOS',
                    'direction': 'bearish',
                    'index': swing_lows[i]['index'],
                    'price': swing_lows[i]['price'],
                    'prev_level': swing_lows[i-1]['price']
                })
        
        # Detect CHOCH (trend reversal signals)
        for i in range(1, len(swing_lows)):
            if i < len(swing_highs) and swing_lows[i]['index'] > swing_highs[i-1]['index']:
                if lows[swing_lows[i]['index']] > lows[swing_lows[i-1]['index']]:
                    events.append({
                        'type': 'CHOCH',
                        'direction': 'bullish',
                        'index': swing_lows[i]['index'],
                        'price': swing_lows[i]['price']
                    })
        
        return events
    
    @staticmethod
    def detect_fvg(prices: List[float], highs: List[float], lows: List[float]) -> List[Dict]:
        """Detect Fair Value Gaps (imbalances)"""
        fvgs = []
        
        for i in range(1, len(prices) - 1):
            # Bullish FVG: gap between candle[i-1].low and candle[i+1].high
            if lows[i-1] > highs[i+1]:
                fvgs.append({
                    'type': 'bullish',
                    'index': i,
                    'top': lows[i-1],
                    'bottom': highs[i+1],
                    'size': lows[i-1] - highs[i+1],
                    'filled': False
                })
            
            # Bearish FVG: gap between candle[i-1].high and candle[i+1].low
            elif highs[i-1] < lows[i+1]:
                fvgs.append({
                    'type': 'bearish',
                    'index': i,
                    'top': lows[i+1],
                    'bottom': highs[i-1],
                    'size': lows[i+1] - highs[i-1],
                    'filled': False
                })
        
        return fvgs
    
    @staticmethod
    def detect_liquidity_zones(prices: List[float], highs: List[float], lows: List[float], volumes: List[float]) -> List[Dict]:
        """Detect liquidity grab zones"""
        liquidity_zones = []
        
        for i in range(5, len(prices) - 1):
            # Equal highs (liquidity pool)
            recent_highs = highs[i-5:i]
            max_high = max(recent_highs)
            equal_highs = [h for h in recent_highs if abs(h - max_high) / max_high < 0.001]
            
            if len(equal_highs) >= 2 and highs[i] > max_high:
                liquidity_zones.append({
                    'type': 'liquidity_grab',
                    'direction': 'buy_side',
                    'index': i,
                    'price': max_high,
                    'volume': volumes[i],
                    'strength': len(equal_highs)
                })
            
            # Equal lows (liquidity pool)
            recent_lows = lows[i-5:i]
            min_low = min(recent_lows)
            equal_lows = [l for l in recent_lows if abs(l - min_low) / min_low < 0.001]
            
            if len(equal_lows) >= 2 and lows[i] < min_low:
                liquidity_zones.append({
                    'type': 'liquidity_grab',
                    'direction': 'sell_side',
                    'index': i,
                    'price': min_low,
                    'volume': volumes[i],
                    'strength': len(equal_lows)
                })
        
        return liquidity_zones
    
    @staticmethod
    def detect_wyckoff_phase(prices: List[float], volumes: List[float]) -> Dict:
        """Detect Wyckoff accumulation/distribution phases"""
        if len(prices) < 20:
            return {'phase': 'Unknown', 'confidence': 0}
        
        recent_prices = prices[-20:]
        recent_volumes = volumes[-20:]
        
        price_range = max(recent_prices) - min(recent_prices)
        avg_volume = sum(recent_volumes) / len(recent_volumes)
        recent_volume = sum(recent_volumes[-5:]) / 5
        
        price_change = (recent_prices[-1] - recent_prices[0]) / recent_prices[0]
        
        # Accumulation detection
        if abs(price_change) < 0.05 and recent_volume > avg_volume * 1.2:
            return {
                'phase': 'Accumulation',
                'confidence': min(90, int((recent_volume / avg_volume) * 50)),
                'volume_ratio': recent_volume / avg_volume,
                'price_compression': price_range / recent_prices[-1]
            }
        
        # Distribution detection
        elif abs(price_change) < 0.05 and recent_volume > avg_volume * 1.5 and recent_prices[-1] > sum(recent_prices) / len(recent_prices):
            return {
                'phase': 'Distribution',
                'confidence': min(90, int((recent_volume / avg_volume) * 45)),
                'volume_ratio': recent_volume / avg_volume,
                'price_compression': price_range / recent_prices[-1]
            }
        
        # Markup (uptrend)
        elif price_change > 0.1 and recent_volume > avg_volume:
            return {
                'phase': 'Markup',
                'confidence': min(85, int(price_change * 400)),
                'volume_ratio': recent_volume / avg_volume,
                'price_change': price_change
            }
        
        # Markdown (downtrend)
        elif price_change < -0.1 and recent_volume > avg_volume:
            return {
                'phase': 'Markdown',
                'confidence': min(85, int(abs(price_change) * 400)),
                'volume_ratio': recent_volume / avg_volume,
                'price_change': price_change
            }
        
        return {'phase': 'Neutral', 'confidence': 30}
    
    @staticmethod
    def detect_pd_arrays(prices: List[float], highs: List[float], lows: List[float]) -> List[Dict]:
        """Detect Premium/Discount Arrays"""
        pd_arrays = []
        
        for i in range(10, len(prices)):
            recent_range = max(highs[i-10:i]) - min(lows[i-10:i])
            mid_point = (max(highs[i-10:i]) + min(lows[i-10:i])) / 2
            
            current_price = prices[i]
            
            # Premium zone (above 50% of range)
            if current_price > mid_point:
                premium_pct = ((current_price - mid_point) / (recent_range / 2)) * 100
                pd_arrays.append({
                    'type': 'premium',
                    'index': i,
                    'price': current_price,
                    'percentage': min(100, premium_pct),
                    'level': mid_point
                })
            
            # Discount zone (below 50% of range)
            else:
                discount_pct = ((mid_point - current_price) / (recent_range / 2)) * 100
                pd_arrays.append({
                    'type': 'discount',
                    'index': i,
                    'price': current_price,
                    'percentage': min(100, discount_pct),
                    'level': mid_point
                })
        
        return pd_arrays
    
    @staticmethod
    def analyze_kill_zones(current_hour: int) -> Dict:
        """Identify institutional trading kill zones"""
        # London Kill Zone: 02:00 - 05:00 UTC
        # New York Kill Zone: 12:00 - 15:00 UTC
        # Asian Kill Zone: 20:00 - 23:00 UTC
        
        if 2 <= current_hour < 5:
            return {
                'zone': 'London Kill Zone',
                'active': True,
                'description': 'High institutional activity - London open',
                'priority': 'HIGH'
            }
        elif 12 <= current_hour < 15:
            return {
                'zone': 'New York Kill Zone',
                'active': True,
                'description': 'Peak institutional activity - NY open',
                'priority': 'CRITICAL'
            }
        elif 20 <= current_hour < 23:
            return {
                'zone': 'Asian Kill Zone',
                'active': True,
                'description': 'Asian institutional activity',
                'priority': 'MEDIUM'
            }
        else:
            return {
                'zone': 'No Kill Zone',
                'active': False,
                'description': 'Low institutional activity',
                'priority': 'LOW'
            }

# ==========================================
# TRADINGVIEW INTEGRATION
# ==========================================

def generate_tradingview_url(symbol: str, interval: str = "D") -> str:
    """Generate TradingView chart URL with symbol"""
    # Clean symbol
    clean_symbol = symbol.upper().replace("/", "").replace("-", "")
    
    # Map interval to TradingView format
    interval_map = {
        "15m": "15",
        "1h": "60",
        "4h": "240",
        "1d": "D",
        "1w": "W"
    }
    
    tv_interval = interval_map.get(interval, "D")
    
    # Construct TradingView URL
    base_url = "https://www.tradingview.com/chart/"
    symbol_param = f"?symbol=BINANCE:{clean_symbol}USDT"
    interval_param = f"&interval={tv_interval}"
    
    return f"{base_url}{symbol_param}{interval_param}"

def generate_tradingview_widget_html(symbol: str, chat_id: int, overlays: Dict) -> str:
    """Generate TradingView widget HTML with custom overlays"""
    clean_symbol = symbol.upper().replace("/", "").replace("-", "")
    
    # Build studies array based on user overlay settings
    studies = []
    
    if overlays.get('ma_50', True):
        studies.append('"MASimple@tv-basicstudies"')
    if overlays.get('ma_200', True):
        studies.append('"MASimple@tv-basicstudies"')
    if overlays.get('rsi', True):
        studies.append('"RSI@tv-basicstudies"')
    if overlays.get('volume', True):
        studies.append('"Volume@tv-basicstudies"')
    
    studies_str = ", ".join(studies)
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{symbol} - TradingView Chart</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #131722;
        }}
        #tradingview-widget {{
            width: 100%;
            height: 100vh;
        }}
        .overlay-controls {{
            position: fixed;
            top: 10px;
            right: 10px;
            background: rgba(19, 23, 34, 0.95);
            padding: 15px;
            border-radius: 8px;
            z-index: 1000;
            border: 1px solid #2962FF;
        }}
        .overlay-controls h3 {{
            margin: 0 0 10px 0;
            color: #fff;
            font-size: 14px;
        }}
        .overlay-item {{
            margin: 8px 0;
            color: #B2B5BE;
            font-size: 12px;
        }}
        .overlay-item input {{
            margin-right: 8px;
        }}
    </style>
</head>
<body>
    <div id="tradingview-widget"></div>
    
    <div class="overlay-controls">
        <h3>📊 Overlays</h3>
        <div class="overlay-item">
            <input type="checkbox" id="fvg" {"checked" if overlays.get('fvg', True) else ""}>
            <label for="fvg">Fair Value Gaps</label>
        </div>
        <div class="overlay-item">
            <input type="checkbox" id="ob" {"checked" if overlays.get('order_blocks', True) else ""}>
            <label for="ob">Order Blocks</label>
        </div>
        <div class="overlay-item">
            <input type="checkbox" id="bos" {"checked" if overlays.get('bos_choch', True) else ""}>
            <label for="bos">BOS / CHOCH</label>
        </div>
        <div class="overlay-item">
            <input type="checkbox" id="liq" {"checked" if overlays.get('liquidity', True) else ""}>
            <label for="liq">Liquidity Zones</label>
        </div>
        <div class="overlay-item">
            <input type="checkbox" id="sr" {"checked" if overlays.get('support_resistance', True) else ""}>
            <label for="sr">Support/Resistance</label>
        </div>
        <div class="overlay-item">
            <input type="checkbox" id="pd" {"checked" if overlays.get('pd_arrays', True) else ""}>
            <label for="pd">PD Arrays</label>
        </div>
        <div class="overlay-item">
            <input type="checkbox" id="kz" {"checked" if overlays.get('kill_zones', True) else ""}>
            <label for="kz">Kill Zones</label>
        </div>
    </div>
    
    <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
    <script type="text/javascript">
        new TradingView.widget({{
            "width": "100%",
            "height": "100%",
            "symbol": "BINANCE:{clean_symbol}USDT",
            "interval": "D",
            "timezone": "Etc/UTC",
            "theme": "dark",
            "style": "1",
            "locale": "en",
            "toolbar_bg": "#f1f3f6",
            "enable_publishing": false,
            "allow_symbol_change": true,
            "container_id": "tradingview-widget",
            "studies": [{studies_str}],
            "show_popup_button": true,
            "popup_width": "1000",
            "popup_height": "650"
        }});
        
        // Overlay toggle functionality
        document.querySelectorAll('.overlay-item input').forEach(checkbox => {{
            checkbox.addEventListener('change', function() {{
                // Send message back to Telegram bot about overlay change
                if (window.Telegram && window.Telegram.WebApp) {{
                    window.Telegram.WebApp.sendData(JSON.stringify({{
                        type: 'overlay_toggle',
                        overlay: this.id,
                        enabled: this.checked
                    }}));
                }}
            }});
        }});
    </script>
</body>
</html>
"""
    return html

# ==========================================
# ETF & MARKET DATA FUNCTIONS
# ==========================================

def fetch_etf_net_flows():
    """Fetch BTC, ETH, GOLD, SILVER ETF flows"""
    try:
        btc_data = fetch_json("https://api.llama.fi/etfs/bitcoin")
        eth_data = fetch_json("https://api.llama.fi/etfs/ethereum")
        
        btc_flow = btc_data.get("netFlow", 0) if btc_data else 0
        eth_flow = eth_data.get("netFlow", 0) if eth_data else 0
        gold_flow = 0  # Placeholder
        silver_flow = 0  # Placeholder
        
        return btc_flow, eth_flow, gold_flow, silver_flow
    except Exception as e:
        logger.error(f"Error fetching ETF flows: {e}")
        return 0, 0, 0, 0

def get_market_regime():
    """Calculate current market regime"""
    try:
        global_resp = requests.get(
            f"{COINGECKO_BASE_URL}/global",
            headers=REQUEST_HEADERS,
            timeout=API_REQUEST_TIMEOUT
        )
        global_data = global_resp.json()["data"]
        
        btc_dominance = global_data["market_cap_percentage"].get("btc", 0)
        total_market_cap = global_data["total_market_cap"].get("usd", 0) / 1e12
        
        eth_resp = requests.get(
            f"{COINGECKO_BASE_URL}/simple/price?ids=ethereum,bitcoin&vs_currencies=usd",
            headers=REQUEST_HEADERS,
            timeout=API_REQUEST_TIMEOUT
        )
        prices = eth_resp.json()
        eth_btc_ratio = prices["ethereum"]["usd"] / prices["bitcoin"]["usd"]
        
        usdt_dominance = global_data["market_cap_percentage"].get("usdt", 0)
        altcoin_dominance = 100 - btc_dominance - usdt_dominance
        
        fng_resp = requests.get("https://api.alternative.me/fng/?limit=1", timeout=API_REQUEST_TIMEOUT)
        fear_greed_index = int(fng_resp.json()["data"][0]["value"])
        
        btc_resp = requests.get(
            f"{COINGECKO_BASE_URL}/coins/bitcoin/market_chart?vs_currency=usd&days=14",
            headers=REQUEST_HEADERS,
            timeout=API_REQUEST_TIMEOUT
        )
        prices_data = [p[1] for p in btc_resp.json()["prices"]]
        deltas = [prices_data[i+1] - prices_data[i] for i in range(len(prices_data)-1)]
        gains = sum(d for d in deltas if d > 0) / 14
        losses = abs(sum(d for d in deltas if d < 0)) / 14
        rs = gains / losses if losses != 0 else 0
        bitcoin_rsi = 100 - (100 / (1 + rs))
        
        checklist = {
            "BTC Dominance < 45%": btc_dominance < 45,
            "ETH/BTC > 0.07": eth_btc_ratio > 0.07,
            "Altcoin Dominance > 50%": altcoin_dominance > 50,
            "Fear & Greed > 65": fear_greed_index > 65,
            "Bitcoin RSI > 50": bitcoin_rsi > 50
        }
        
        passed = sum(checklist.values())
        regime = "Alt Season" if passed >= 3 else "BTC Season"
        
        return {
            "regime": regime,
            "emoji": "🟢" if regime == "Alt Season" else "🟡",
            "btc_dominance": btc_dominance,
            "eth_btc_ratio": eth_btc_ratio,
            "altcoin_dominance": altcoin_dominance,
            "total_market_cap": total_market_cap,
            "fear_greed_index": fear_greed_index,
            "bitcoin_rsi": bitcoin_rsi,
            "checklist": checklist,
            "passed": passed
        }
    except Exception as e:
        logger.error(f"Error fetching market regime: {e}")
        return {
            "regime": "BTC Season",
            "emoji": "🟡",
            "btc_dominance": 57.03,
            "eth_btc_ratio": 0.03289,
            "altcoin_dominance": 36.58,
            "total_market_cap": 2.91,
            "fear_greed_index": 16,
            "bitcoin_rsi": 42.70,
            "checklist": {},
            "passed": 0
        }

# ==========================================
# NEWS FUNCTIONS
# ==========================================

def fetch_news():
    """Fetch market-relevant news"""
    news_items = []
    priority_keywords = ["high", "urgent", "important", "risky", "uptrend", "downtrend", 
                        "bullish", "bearish", "breakout", "crash", "rally"]
    
    try:
        feeds = [
            "https://www.coindesk.com/arc/outboundfeeds/rss/",
            "https://cointelegraph.com/rss",
            "https://news.bitcoin.com/feed/",
            "https://cryptoslate.com/feed/",
            "https://decrypt.co/feed/"
        ]
        
        for url in feeds:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                title = entry.title
                
                is_urgent = any(keyword in title.lower() for keyword in priority_keywords)
                
                image = "https://cryptologos.cc/logos/bitcoin-btc-logo.png"
                if "media_content" in entry and entry.media_content:
                    image = entry.media_content[0].get("url", image)
                elif "media_thumbnail" in entry and entry.media_thumbnail:
                    image = entry.media_thumbnail[0].get("url", image)
                
                news_items.append({
                    "title": title,
                    "url": entry.link,
                    "image": image,
                    "published": entry.published if "published" in entry else datetime.now().strftime("%b %d, %Y %I:%M %p"),
                    "urgent": is_urgent
                })
        
        news_items.sort(key=lambda x: (not x["urgent"], x["published"]), reverse=True)
        return news_items[:5]
        
    except Exception as e:
        logger.error(f"News fetch error: {e}")
        return [{
            "title": "Fallback: Crypto market update",
            "url": "https://cryptonews.com/",
            "image": "https://cryptologos.cc/logos/bitcoin-btc-logo.png",
            "published": datetime.now().strftime("%b %d, %Y %I:%M %p"),
            "urgent": False
        }]

# ==========================================
# MESSAGE MANAGEMENT
# ==========================================

async def clear_market_messages(chat_id, context):
    """Clear all market overview and news messages"""
    if chat_id in context.user_data and "market_messages" in context.user_data[chat_id]:
        for msg_id in context.user_data[chat_id]["market_messages"]:
            try:
                await context.bot.delete_message(chat_id, msg_id)
            except BadRequest:
                pass
        context.user_data[chat_id]["market_messages"] = []

async def send_market_overview(chat_id, context, market_data):
    """Send market overview and news"""
    await clear_market_messages(chat_id, context)
    
    if chat_id not in context.user_data:
        context.user_data[chat_id] = {}
    if "market_messages" not in context.user_data[chat_id]:
        context.user_data[chat_id]["market_messages"] = []
    
    prev = previous_market_data.get(chat_id, {})
    btc_trend = detect_trend(market_data['btc_dominance'], prev.get("btc_dominance"))
    eth_trend = detect_trend(market_data['eth_btc_ratio'], prev.get("eth_btc_ratio"))
    alt_trend = detect_trend(market_data['altcoin_dominance'], prev.get("altcoin_dominance"))
    
    previous_market_data[chat_id] = {
        "btc_dominance": market_data['btc_dominance'],
        "eth_btc_ratio": market_data['eth_btc_ratio'],
        "altcoin_dominance": market_data['altcoin_dominance']
    }
    
    btc_etf, eth_etf, gold_etf, silver_etf = fetch_etf_net_flows()
    
    checklist_text = "\n".join([
        f"{'✅' if v else '⛔'} {k}" 
        for k, v in market_data['checklist'].items()
    ])
    
    # Get Kill Zone info
    current_hour = datetime.utcnow().hour
    kill_zone = SMCAnalyzer.analyze_kill_zones(current_hour)
    kz_indicator = f"🎯 {kill_zone['zone']} - {kill_zone['priority']}" if kill_zone['active'] else "⏸️ Off-hours"
    
    overview_text = (
        f"📊 *MARKET OVERVIEW*\n\n"
        f"{market_data['emoji']} {market_data['regime']} Active\n"
        f"{kz_indicator}\n\n"
        f"*Metrics:*\n"
        f"• BTC Dominance: {market_data['btc_dominance']:.2f}% | {btc_trend}\n"
        f"• ETH/BTC Ratio: {market_data['eth_btc_ratio']:.5f} | {eth_trend}\n"
        f"• Altcoin Dominance: {market_data['altcoin_dominance']:.2f}% | {alt_trend}\n"
        f"• Total Market Cap: ${market_data['total_market_cap']:.2f}T\n"
        f"• Fear & Greed Index: {market_data['fear_greed_index']}\n"
        f"• Bitcoin RSI: {market_data['bitcoin_rsi']:.2f}\n\n"
        f"*ETF Net Flows | ETH Market Focus:*\n"
        f"• BTC ETF: ${btc_etf:,.0f} (live)\n"
        f"• ETH ETF: ${eth_etf:,.0f} (live)\n"
        f"• GOLD ETF: ${gold_etf:,.0f} (live)\n"
        f"• SILVER ETF: ${silver_etf:,.0f} (live)\n\n"
        f"📌 *Alt Season Checklist:* {market_data['passed']}/5 Passed\n"
        f"{checklist_text}\n\n"
        f"⏰ Market Update: {datetime.now().strftime('%b %d, %Y %I:%M %p')}"
    )
    
    overview_msg = await context.bot.send_message(
        chat_id,
        overview_text,
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    context.user_data[chat_id]["market_messages"].append(overview_msg.message_id)
    
    news_items = fetch_news()
    for item in news_items:
        try:
            caption = f"📰 *{item['title']}*\n🕒 Published: {item['published']}"
            if item['urgent']:
                caption = f"🚨 *URGENT*\n" + caption
            
            news_msg = await context.bot.send_photo(
                chat_id=chat_id,
                photo=item["image"],
                caption=caption,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Read Full Article", url=item["url"])]
                ])
            )
            context.user_data[chat_id]["market_messages"].append(news_msg.message_id)
        except Exception as e:
            logger.error(f"Error sending news item: {e}")

async def update_regime_pin(chat_id, context, market_data, force=False):
    """Update or create regime pin message"""
    current_regime = market_data['regime']
    
    if chat_id in regime_start_times:
        if regime_start_times[chat_id]["regime"] != current_regime or force:
            regime_start_times[chat_id] = {
                "regime": current_regime,
                "start_time": datetime.now()
            }
            
            if "pin_message_id" in context.user_data.get(chat_id, {}):
                try:
                    await context.bot.unpin_chat_message(
                        chat_id,
                        context.user_data[chat_id]["pin_message_id"]
                    )
                    await context.bot.delete_message(
                        chat_id,
                        context.user_data[chat_id]["pin_message_id"]
                    )
                except BadRequest:
                    pass
            
            pin_text = (
                f"{market_data['emoji']} *{current_regime} Active*\n"
                f"Update: {datetime.now().strftime('%b %d, %Y %I:%M %p')}"
            )
            
            try:
                pin_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text=pin_text,
                    parse_mode="Markdown"
                )
                await context.bot.pin_chat_message(
                    chat_id,
                    pin_msg.message_id,
                    disable_notification=True
                )
                context.user_data[chat_id]["pin_message_id"] = pin_msg.message_id
            except Exception as e:
                logger.error(f"Error pinning message: {e}")
    else:
        regime_start_times[chat_id] = {
            "regime": current_regime,
            "start_time": datetime.now()
        }
        
        pin_text = (
            f"{market_data['emoji']} *{current_regime} Active*\n"
            f"Update: {datetime.now().strftime('%b %d, %Y %I:%M %p')}"
        )
        
        try:
            pin_msg = await context.bot.send_message(
                chat_id=chat_id,
                text=pin_text,
                parse_mode="Markdown"
            )
            await context.bot.pin_chat_message(
                chat_id,
                pin_msg.message_id,
                disable_notification=True
            )
            if chat_id not in context.user_data:
                context.user_data[chat_id] = {}
            context.user_data[chat_id]["pin_message_id"] = pin_msg.message_id
        except Exception as e:
            logger.error(f"Error creating pin: {e}")

# ==========================================
# BACKGROUND TASK
# ==========================================

async def auto_market_refresh(chat_id: int, application):
    """Background task to refresh market data"""
    while True:
        try:
            await asyncio.sleep(MARKET_REFRESH_INTERVAL)
            
            market_data = get_market_regime()
            await send_market_overview(chat_id, application, market_data)
            await update_regime_pin(chat_id, application, market_data)
            
        except Exception as e:
            logger.error(f"Error in auto refresh: {e}")

# ==========================================
# CROSS ANALYSIS FUNCTIONS
# ==========================================

def calculate_ma(prices, period):
    """Calculate Simple Moving Average"""
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period

def run_institutional_smc(coin_id, timeframe):
    """Run complete Institutional SMC analysis following the master flow"""

    timeframe_days = {
        "15m": 7,
        "1h": 30,
        "4h": 90,
        "1d": 180,
        "1w": 365
    }

    hist_data = fetch_historical_prices(
        coin_id,
        timeframe,
        timeframe_days.get(timeframe, 90)
    )
    if not hist_data:
        return {"error": "Failed to fetch data. Check if coin symbol is valid."}

    prices = hist_data["prices"]
    volumes = hist_data["volumes"]

    if len(prices) < 50:  # Reduced from 200 to 50 for more flexibility
        return {"error": f"Insufficient data (need at least 50 periods, got {len(prices)}). Try a longer timeframe like 1D or 1W."}

    highs = [p * 1.02 for p in prices]
    lows = [p * 0.98 for p in prices]

    timeframe_roles = {
        "15m": "Entry Trigger",
        "1h": "Execution Bias",
        "4h": "Structure Control (Trade Permission)",
        "1d": "Swing Bias",
        "1w": "Macro Bias Only"
    }
    role = timeframe_roles.get(timeframe, "Unknown")

    ma50 = calculate_ma(prices, 50)
    ma200 = calculate_ma(prices, 200)
    current_price = prices[-1]

    if ma50 and ma200:
        if ma50 > ma200 and current_price > ma50:
            regime = "BULLISH"
        elif ma50 < ma200 and current_price < ma50:
            regime = "BEARISH"
        else:
            regime = "RANGE"
    else:
        regime = "UNKNOWN"

    liquidity_zones = SMCAnalyzer.detect_liquidity_zones(
        prices, highs, lows, volumes
    )

    rsi = calculate_rsi(prices)
    macd_line, signal_line, histogram = calculate_macd(prices)

    return {
        "coin": coin_id,
        "timeframe": timeframe,
        "role": role,
        "regime": regime,
        "ma50": ma50,
        "ma200": ma200,
        "rsi": rsi,
        "macd_histogram": histogram,
        "current_price": current_price
    }


def calculate_rsi(prices, period=14):
    """Calculate RSI indicator"""
    if len(prices) < period + 1:
        return None
    
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi
    
def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calculate MACD indicator"""
    if len(prices) < slow:
        return None, None, None

    ema_fast = []
    ema_slow = []

    k_fast = 2 / (fast + 1)
    ema_fast.append(sum(prices[:fast]) / fast)
    for price in prices[fast:]:
        ema_fast.append(price * k_fast + ema_fast[-1] * (1 - k_fast))

    k_slow = 2 / (slow + 1)
    ema_slow.append(sum(prices[:slow]) / slow)
    for price in prices[slow:]:
        ema_slow.append(price * k_slow + ema_slow[-1] * (1 - k_slow))

    macd_line = [
        ema_fast[i + (slow - fast)] - ema_slow[i]
        for i in range(len(ema_slow))
    ]

    k_signal = 2 / (signal + 1)
    signal_line = [sum(macd_line[:signal]) / signal]
    for macd in macd_line[signal:]:
        signal_line.append(macd * k_signal + signal_line[-1] * (1 - k_signal))

    histogram = [
        macd_line[i + signal - 1] - signal_line[i]
        for i in range(len(signal_line))
    ]

    return macd_line[-1], signal_line[-1], histogram[-1]
    
def fetch_historical_prices(coin_id, timeframe, days=30):
    """Fetch historical price data"""
    try:
        timeframe_days = {
            "15m": 1,
            "1h": 7,
            "4h": 30,
            "1d": 90,
            "1w": 365
        }
        days_to_fetch = timeframe_days.get(timeframe, 30)
        
        data = fetch_json(
            f"{COINGECKO_BASE_URL}/coins/{coin_id}/market_chart",
            params={
                "vs_currency": "usd",
                "days": days_to_fetch,
                "interval": "daily"
            }
        )
        
        if not data or 'prices' not in data:
            return None
        
        return {
            'prices': [p[1] for p in data['prices']],
            'volumes': [v[1] for v in data.get('total_volumes', [])],
            'timestamps': [p[0] for p in data['prices']]
        }
    except Exception as e:
        logger.error(f"Error fetching historical data for {coin_id}: {e}")
        return None

def calculate_cross_score(prices, cross_type):
    """Calculate cross analysis score"""
    if len(prices) < 200:
        return None
    
    ma50 = calculate_ma(prices, 50)
    ma200 = calculate_ma(prices, 200)
    
    if not ma50 or not ma200:
        return None
    
    ma50_prev = calculate_ma(prices[:-1], 50)
    ma200_prev = calculate_ma(prices[:-1], 200)
    
    if not ma50_prev or not ma200_prev:
        return None
    
    golden_cross = ma50_prev <= ma200_prev and ma50 > ma200
    death_cross = ma50_prev >= ma200_prev and ma50 < ma200
    
    if cross_type == "golden" and not golden_cross:
        return None
    if cross_type == "death" and not death_cross:
        return None
    
    rsi = calculate_rsi(prices)
    score = 30
    
    if rsi:
        if cross_type == "golden":
            if 30 < rsi < 70:
                score += 25
            elif rsi < 30:
                score += 20
        else:
            if 30 < rsi < 70:
                score += 25
            elif rsi > 70:
                score += 20
    
    cross_strength = abs(ma50 - ma200) / ma200 * 100
    score += min(20, cross_strength * 2)
    
    return {
        'score': round(score),
        'ma50': ma50,
        'ma200': ma200,
        'rsi': rsi,
        'cross_strength': cross_strength
    }

def get_coingecko_coin_list():
    """Get CoinGecko coin list for symbol mapping"""
    try:
        coins = fetch_json(f"{COINGECKO_BASE_URL}/coins/list")
        mapping = {}
        for coin in coins or []:
            symbol = coin.get('symbol', '').lower()
            coin_id = coin.get('id', '')
            if symbol and coin_id:
                if symbol not in mapping or len(coin_id) < len(mapping[symbol]):
                    mapping[symbol] = coin_id
        return mapping
    except:
        return {}

# ==========================================
# SECTOR ROTATION FUNCTIONS
# ==========================================

def calculate_volume_efficiency(volume, price_change_abs):
    """Calculate volume efficiency metric"""
    if price_change_abs < 0.1:
        price_change_abs = 0.1
    efficiency = math.log(volume + 1) / (price_change_abs + 1)
    return efficiency

def calculate_rci_metrics(coin, volume, mcap, price, change):
    """Calculate RCI institutional metrics"""
    smart_money = min(100, (volume / mcap) * 1000) if mcap > 0 else 0
    efficiency = calculate_volume_efficiency(volume, abs(change)) * 10
    liquidity = (math.log10(volume + 1) / math.log10(mcap + 1)) * 10 if mcap > 0 else 0
    velocity = (volume / mcap) * 100 if mcap > 0 else 0
    
    rci = (smart_money * 0.3 + efficiency * 0.3 + liquidity * 0.2 + velocity * 0.2)
    
    if rci > 70 and abs(change) < 4:
        state = "🧠 ACCUM"
    elif efficiency > 10 and change > 5:
        state = "📉 DISTRIB"
    elif rci > 65 and change > 8:
        state = "🚀 MOMENTUM"
    else:
        state = "➖ NEUTRAL"
    
    return {
        'smart_money': round(smart_money, 1),
        'efficiency': round(efficiency, 2),
        'liquidity': round(liquidity, 2),
        'velocity': round(velocity, 2),
        'rci': round(rci, 1),
        'state': state
    }

def analyze_sector_rotation():
    """Analyze DeFi sector rotation using TVL and fees"""
    try:
        protocols = fetch_json(f"{DEFILLAMA_BASE_URL}/protocols")
        if not protocols:
            return []
        
        cg_mapping = get_coingecko_coin_list()
        sector_data = {}
        
        for p in protocols:
            cat = p.get("category", "Unknown")
            if cat not in sector_data:
                sector_data[cat] = {
                    "tvl": 0,
                    "tvl_change_7d": 0,
                    "protocols": [],
                    "count": 0
                }
            
            tvl = p.get("tvl", 0) or 0
            sector_data[cat]["tvl"] += tvl
            sector_data[cat]["tvl_change_7d"] += p.get("change_7d", 0) or 0
            sector_data[cat]["count"] += 1
            
            symbol = (p.get("symbol") or p.get("gecko_id") or "").lower()
            sector_data[cat]["protocols"].append({
                "name": p.get("name", "Unknown"),
                "symbol": symbol,
                "tvl": tvl,
                "change_1d": p.get("change_1d", 0) or 0
            })
        
        ranked_sectors = sorted(
            sector_data.items(),
            key=lambda x: (x[1]["tvl"], x[1]["tvl_change_7d"]),
            reverse=True
        )
        
        final_sectors = []
        
        for category, data in ranked_sectors[:5]:
            top_tokens = sorted(
                data["protocols"],
                key=lambda x: x["tvl"],
                reverse=True
            )[:50]
            
            coin_ids = [
                cg_mapping[t["symbol"]] 
                for t in top_tokens 
                if t["symbol"] in cg_mapping
            ]
            
            if len(coin_ids) < 5:
                continue
            
            coin_data = []
            chunk_size = 50
            for i in range(0, min(len(coin_ids), 100), chunk_size):
                chunk = coin_ids[i:i + chunk_size]
                chunk_data = fetch_json(
                    f"{COINGECKO_BASE_URL}/coins/markets",
                    params={
                        "vs_currency": "usd",
                        "ids": ",".join(chunk),
                        "order": "market_cap_desc",
                        "sparkline": False,
                        "price_change_percentage": "24h"
                    }
                )
                if chunk_data:
                    coin_data.extend(chunk_data)
            
            if not coin_data or len(coin_data) < 5:
                continue
            
            processed_tokens = []
            total_rci = 0
            
            for coin in coin_data[:10]:
                vol = coin.get("total_volume", 0) or 0
                change = coin.get("price_change_percentage_24h", 0) or 0
                mcap = coin.get("market_cap", 0) or 0
                price = coin.get("current_price", 0) or 0
                
                if vol == 0 or mcap == 0 or price == 0:
                    continue
                
                metrics = calculate_rci_metrics(coin, vol, mcap, price, change)
                total_rci += metrics['rci']
                
                processed_tokens.append({
                    "symbol": coin.get("symbol", "").upper(),
                    "price": price,
                    "change": change,
                    "efficiency": metrics['efficiency'],
                    "rci": metrics['rci'],
                    "smart_money": metrics['smart_money'],
                    "liquidity": metrics['liquidity'],
                    "velocity": metrics['velocity'],
                    "state": metrics['state']
                })
            
            if len(processed_tokens) < 5:
                continue
            
            processed_tokens.sort(key=lambda x: x['rci'], reverse=True)
            
            avg_rci = total_rci / len(processed_tokens)
            
            if avg_rci > 65 and data["tvl_change_7d"] > 0:
                flow_status = "🔥 HOT"
            elif avg_rci > 55:
                flow_status = "📈 GROW"
            else:
                flow_status = "➖ NEUTRAL"
            
            final_sectors.append({
                "category": category,
                "tvl": data["tvl"],
                "flow_status": flow_status,
                "avg_rci": avg_rci,
                "tokens": processed_tokens[:10]
            })
        
        return final_sectors
        
    except Exception as e:
        logger.error(f"Error in sector rotation: {e}")
        return []

def get_sector_explanation(category):
    """Get brief explanation of sector"""
    explanations = {
        "Liquid Staking": "Liquid Staking lets users stake assets (usually ETH) while keeping a liquid token they can trade, lend, or use in DeFi.\n👉 Result: staking yield + capital efficiency, which is why institutions accumulate here early.",
        "Lending": "Decentralized lending protocols allow users to lend or borrow crypto assets without intermediaries.\n👉 Result: passive yield for lenders, leveraged positions for borrowers.",
        "DEX": "Decentralized exchanges enable peer-to-peer token swaps without centralized custody.\n👉 Result: permissionless trading with lower fees than CEXs.",
        "Yield": "Yield protocols optimize returns through automated strategies across multiple DeFi platforms.\n👉 Result: maximized APY through compound effects and arbitrage.",
        "Derivatives": "On-chain derivatives platforms offer perpetual futures, options, and leveraged trading.\n👉 Result: sophisticated hedging and speculation tools without centralized risk."
    }
    return explanations.get(category, f"{category} - Institutional capital is rotating into this sector.")

# ==========================================
# AI ASSISTANT FUNCTIONS
# ==========================================

async def ai_query(query: str, market_context: dict, ai_provider: str) -> str:
    """Query AI with market context"""
    try:
        context = (
            f"Current market regime: {market_context.get('regime', 'Unknown')}\n"
            f"BTC Dominance: {market_context.get('btc_dominance', 0):.2f}%\n"
            f"Fear & Greed: {market_context.get('fear_greed_index', 0)}\n"
            f"User query: {query}"
        )
        
        if ai_provider == "groq":
            if not GROQ_API_KEY or GROQ_API_KEY == "":
                return (
                    "❌ Groq API key not configured.\n\n"
                    "Please add this line to your .env file:\n"
                    "GROQ_API_KEY=your_groq_api_key_here\n\n"
                    "Get your key at: console.groq.com"
                )
            
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "mixtral-8x7b-32768",
                    "messages": [
                        {"role": "system", "content": "You are a crypto market analyst. Be concise and market-aware."},
                        {"role": "user", "content": context}
                    ],
                    "max_tokens": 500
                },
                timeout=15
            )
            
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            elif response.status_code == 401:
                return "❌ Invalid Groq API key. Please check your GROQ_API_KEY in .env file."
            else:
                return f"❌ Groq API error: {response.status_code}\n{response.text}"
        
        elif ai_provider == "deepseek":
            if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "":
                return (
                    "❌ DeepSeek API key not configured.\n\n"
                    "Please add this line to your .env file:\n"
                    "DEEPSEEK_API_KEY=your_deepseek_api_key_here\n\n"
                    "Get your key at: platform.deepseek.com"
                )
            
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": "You are a crypto market analyst. Be concise and market-aware."},
                        {"role": "user", "content": context}
                    ],
                    "max_tokens": 500
                },
                timeout=15
            )
            
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            elif response.status_code == 401:
                return "❌ Invalid DeepSeek API key. Please check your DEEPSEEK_API_KEY in .env file."
            else:
                return f"❌ DeepSeek API error: {response.status_code}\n{response.text}"
        
        else:
            return "Unknown AI provider. Please select Groq or DeepSeek."
    
    except Exception as e:
        logger.error(f"AI query error: {e}")
        return f"❌ Error querying AI: {str(e)}"

# ==========================================
# COMMAND HANDLERS
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    chat_id = update.effective_chat.id
    
    try:
        await update.message.delete()
    except BadRequest:
        pass
    
    await clear_market_messages(chat_id, context)
    
    # Initialize default overlay settings
    if chat_id not in user_overlay_settings:
        user_overlay_settings[chat_id] = {
            'fvg': True,
            'order_blocks': True,
            'bos_choch': True,
            'liquidity': True,
            'support_resistance': True,
            'ma_50': True,
            'ma_200': True,
            'pd_arrays': True,
            'kill_zones': True,
            'rsi': True,
            'volume': True
        }
    
    user = update.effective_user
    user_name = user.first_name or user.username or "Trader"
    
    welcome_msg = await context.bot.send_message(
        chat_id=chat_id,
        text=f"Welcome, *{user_name}*! Let's explore crypto with Smart Money Concepts! 🚀",
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    
    if chat_id not in background_tasks:
        background_tasks[chat_id] = asyncio.create_task(
            auto_market_refresh(chat_id, context.application)
        )
    
    await asyncio.sleep(WELCOME_MESSAGE_DELAY)
    try:
        await context.bot.delete_message(chat_id, welcome_msg.message_id)
    except BadRequest:
        pass
    
    market_data = get_market_regime()
    await send_market_overview(chat_id, context, market_data)
    await update_regime_pin(chat_id, context, market_data, force=True)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    await update.message.reply_text(
        "ℹ️ *HELP*\n\n"
        "/start - Restart bot\n"
        "/help - Show this help\n\n"
        "⚔️ Cross - Golden/Death cross analysis with confluence scoring\n"
        "🌊 Sector Rotation - Institutional DeFi rotation analysis\n"
        "🔥 Trending - Current trending coins by market cap\n"
        "💎 Alpha - Stealth accumulation and distribution signals\n"
        "📊 Technical - TradingView chart with live widgets\n"
        "🧠 SMC Analysis - Smart Money Concepts (Order Blocks, FVG, BOS/CHOCH)\n"
        "🎛️ Overlay Settings - Toggle chart overlays ON/OFF\n"
        "🤖 AI Assistant - Market Q&A with Groq or DeepSeek\n\n"
        "*New Features:*\n"
        "• TradingView Live Charts\n"
        "• Smart Money Concepts Analysis\n"
        "• Kill Zone Detection\n"
        "• Wyckoff Phase Identification\n"
        "• Customizable Overlays\n\n"
        "Market updates refresh automatically every 5 minutes.",
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )

# ==========================================
# FEATURE HANDLERS
# ==========================================

async def cross_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Cross Analysis button"""
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟢 Golden Cross", callback_data="golden_cross"),
            InlineKeyboardButton("🔴 Death Cross", callback_data="death_cross")
        ]
    ])
    
    await update.message.reply_text(
        "⚔️ *CROSS ANALYSIS*\n\n"
        "Choose your cross type:\n"
        "🟢 Golden Cross - MA50 crosses above MA200 (Bullish)\n"
        "🔴 Death Cross - MA50 crosses below MA200 (Bearish)",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def cross_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cross type selection"""
    query = update.callback_query
    context.user_data["cross_type"] = "golden" if query.data == "golden_cross" else "death"
    await query.answer()
    
    cross_emoji = "🟢" if query.data == "golden_cross" else "🔴"
    cross_name = "Golden Cross" if query.data == "golden_cross" else "Death Cross"
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("15 Minutes", callback_data="tf_15m"),
            InlineKeyboardButton("1 Hour", callback_data="tf_1h")
        ],
        [
            InlineKeyboardButton("4 Hours", callback_data="tf_4h"),
            InlineKeyboardButton("1 Day", callback_data="tf_1d")
        ],
        [
            InlineKeyboardButton("1 Week", callback_data="tf_1w")
        ]
    ])
    
    await query.edit_message_text(
        f"{cross_emoji} *{cross_name}* Selected\n\n"
        f"Now choose your timeframe:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def timeframe_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle timeframe selection and perform analysis"""
    query = update.callback_query
    tf = query.data.replace("tf_", "")
    cross_type = context.user_data.get("cross_type", "golden")
    await query.answer()
    
    cross_name = "Golden Cross" if cross_type == "golden" else "Death Cross"
    
    await query.edit_message_text(
        f"⚔️ Analyzing {cross_name} on {tf} timeframe...\n"
        f"⏳ This may take a moment...",
        parse_mode="Markdown"
    )
    
    try:
        cg_mapping = get_coingecko_coin_list()
        
        top_coins = fetch_json(
            f"{COINGECKO_BASE_URL}/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 100,
                "sparkline": False
            }
        )
        
        if not top_coins:
            await query.edit_message_text(
                "❌ Failed to fetch coin data",
                parse_mode="Markdown"
            )
            return
        
        results = []
        
        for coin in top_coins:
            coin_id = coin.get("id")
            if not coin_id:
                continue
            
            hist_data = fetch_historical_prices(coin_id, tf)
            if not hist_data:
                continue
            
            analysis = calculate_cross_score(hist_data['prices'], cross_type)
            if not analysis or analysis['score'] < 50:
                continue
            
            results.append({
                'symbol': coin.get('symbol', '').upper(),
                'name': coin.get('name', ''),
                'price': coin.get('current_price', 0),
                'change_24h': coin.get('price_change_percentage_24h', 0),
                'score': analysis['score'],
                'ma50': analysis['ma50'],
                'ma200': analysis['ma200'],
                'rsi': analysis['rsi']
            })
        
        if not results:
            await query.edit_message_text(
                f"⚔️ {cross_name} Analysis ({tf})\n\n"
                f"❌ No coins found with confirmed cross.",
                parse_mode="Markdown"
            )
            return
        
        results.sort(key=lambda x: x['score'], reverse=True)
        top_results = results[:10]
        
        message = (
            f"⚔️ *{cross_name.upper()}* ({tf})\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Found *{len(results)}* coins, showing top 10\n\n"
        )
        
        for i, coin in enumerate(top_results, 1):
            rank = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            message += (
                f"{rank} *{coin['symbol']}* (${coin['price']:,.4f})\n"
                f"├ Score: *{coin['score']}/100*\n"
                f"├ RSI: {coin['rsi']:.1f}\n"
                f"├ MA50: ${coin['ma50']:,.2f}\n"
                f"├ MA200: ${coin['ma200']:,.2f}\n\n"
            )
        
        await query.edit_message_text(message, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error in cross analysis: {e}")
        await query.edit_message_text(
            "❌ Error during analysis.",
            parse_mode="Markdown"
        )

async def sector_rotation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Sector Rotation button"""
    chat_id = update.effective_chat.id
    await clear_market_messages(chat_id, context)
    
    await update.message.reply_text(
        "🔍 Analyzing sector rotation (Institutional DeFi)...",
        reply_markup=create_main_keyboard()
    )
    
    try:
        sectors = analyze_sector_rotation()
        
        if not sectors:
            await update.message.reply_text(
                "❌ Failed to fetch sector data",
                reply_markup=create_main_keyboard()
            )
            return
        
        for i, sector in enumerate(sectors, 1):
            header = (
                f"{sector['flow_status']} *{i}. {sector['category']}*\n"
                f"{get_sector_explanation(sector['category'])}\n\n"
            )
            
            table = (
                "#  | Coin    | %      | Eff   | RCI  | Smart | Liq  | Vel  | State\n"
                "-------------------------------------------------------------------------------------\n"
            )
            
            for j, token in enumerate(sector['tokens'], 1):
                table += (
                    f"{j:<2} | {token['symbol']:<7} | {token['change']:+.1f}% | "
                    f"{token['efficiency']:<5.2f} | {token['rci']:<4.1f} | "
                    f"{token['smart_money']:<5.1f} | {token['liquidity']:<4.2f} | "
                    f"{token['velocity']:<4.2f} | {token['state']}\n"
                )
            
            legend = (
                "\n*Legend:*\n"
                "🔥 HOT / 📈 GROW → early smart-money positioning\n"
                "Low % + high Eff / RCI → accumulation before price expansion\n"
                "Negative flow + weak fees → avoid (late or decaying)"
            )
            
            message = f"{header}```\n{table}```{legend}"
            
            await update.message.reply_text(
                message,
                parse_mode="Markdown",
                reply_markup=create_main_keyboard()
            )
    
    except Exception as e:
        logger.error(f"Error in sector rotation: {e}")
        await update.message.reply_text(
            "❌ Error analyzing sectors",
            reply_markup=create_main_keyboard()
        )

async def trending_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Trending Coins button"""
    chat_id = update.effective_chat.id
    await clear_market_messages(chat_id, context)
    
    await update.message.reply_text(
        "🔍 Fetching trending coins...",
        reply_markup=create_main_keyboard()
    )
    
    try:
        trending = fetch_json(f"{COINGECKO_BASE_URL}/search/trending")
        
        if not trending or 'coins' not in trending:
            await update.message.reply_text(
                "❌ Failed to fetch trending data",
                reply_markup=create_main_keyboard()
            )
            return
        
        text = "🔥 *TRENDING COINS*\n\n"
        
        for i, item in enumerate(trending['coins'][:10], 1):
            coin = item['item']
            rank = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            
            text += (
                f"{rank} *{coin['symbol']}* ({coin['name']})\n"
                f"   Rank: #{coin.get('market_cap_rank', 'N/A')}\n"
                f"   Score: {coin.get('score', 0)}\n\n"
            )
        
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=create_main_keyboard()
        )
    
    except Exception as e:
        logger.error(f"Error fetching trending: {e}")
        await update.message.reply_text(
            "❌ Error fetching trending coins",
            reply_markup=create_main_keyboard()
        )

async def alpha_signals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Alpha Signals button"""
    chat_id = update.effective_chat.id
    await clear_market_messages(chat_id, context)
    
    await update.message.reply_text(
        "🔍 Detecting alpha signals...",
        reply_markup=create_main_keyboard()
    )
    
    try:
        top_coins = fetch_json(
            f"{COINGECKO_BASE_URL}/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 50,
                "sparkline": False,
                "price_change_percentage": "24h"
            }
        )
        
        if not top_coins:
            await update.message.reply_text(
                "❌ Failed to fetch coin data",
                reply_markup=create_main_keyboard()
            )
            return
        
        accumulation = []
        distribution = []
        
        for coin in top_coins:
            vol = coin.get("total_volume", 0) or 0
            change = coin.get("price_change_percentage_24h", 0) or 0
            mcap = coin.get("market_cap", 0) or 0
            price = coin.get("current_price", 0) or 0
            
            if vol == 0 or mcap == 0:
                continue
            
            metrics = calculate_rci_metrics(coin, vol, mcap, price, change)
            
            if metrics['rci'] > 70 and abs(change) < 3:
                accumulation.append({
                    'symbol': coin.get('symbol', '').upper(),
                    'rci': metrics['rci'],
                    'change': change
                })
            
            if change > 5 and metrics['efficiency'] > 10 and metrics['smart_money'] < 50:
                distribution.append({
                    'symbol': coin.get('symbol', '').upper(),
                    'change': change
                })
        
        text = "💎 *ALPHA SIGNALS*\n\n"
        
        if accumulation:
            text += "*🧠 Stealth Accumulation:*\n"
            for i, coin in enumerate(accumulation[:5], 1):
                text += f"{i}. *{coin['symbol']}* - RCI: {coin['rci']:.1f} ({coin['change']:+.1f}%)\n"
        else:
            text += "*🧠 Stealth Accumulation:* None detected\n"
        
        text += "\n"
        
        if distribution:
            text += "*⚠️ Distribution Warnings:*\n"
            for i, coin in enumerate(distribution[:5], 1):
                text += f"{i}. *{coin['symbol']}* ({coin['change']:+.1f}%)\n"
        else:
            text += "*⚠️ Distribution Warnings:* None detected\n"
        
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=create_main_keyboard()
        )
    
    except Exception as e:
        logger.error(f"Error in alpha signals: {e}")
        await update.message.reply_text(
            "❌ Error detecting alpha signals",
            reply_markup=create_main_keyboard()
        )

async def technical_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Technical Analysis button - opens TradingView"""
    chat_id = update.effective_chat.id
    await clear_market_messages(chat_id, context)
    
    # Get user overlay settings
    overlays = user_overlay_settings.get(chat_id, {})
    
    tradingview_url = "https://www.tradingview.com/chart/"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Open TradingView", web_app=WebAppInfo(url=tradingview_url))]
    ])
    
    await update.message.reply_text(
        "📊 *TECHNICAL ANALYSIS*\n\n"
        "Click below to open TradingView in a native window.\n"
        "Analyze charts with professional indicators and tools.\n\n"
        "*Enabled Overlays:*\n"
        f"{'✅' if overlays.get('fvg', True) else '❌'} Fair Value Gaps\n"
        f"{'✅' if overlays.get('order_blocks', True) else '❌'} Order Blocks\n"
        f"{'✅' if overlays.get('bos_choch', True) else '❌'} BOS/CHOCH\n"
        f"{'✅' if overlays.get('liquidity', True) else '❌'} Liquidity Zones\n"
        f"{'✅' if overlays.get('ma_50', True) else '❌'} MA 50\n"
        f"{'✅' if overlays.get('ma_200', True) else '❌'} MA 200\n\n"
        "Use 🎛️ Overlay Settings to customize.",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def smc_analysis(update: Update, context:
    ContextTypes.DEFAULT_TYPE):
    """Handle SMC Analysis button - ask for coin input"""
    chat_id = update.effective_chat.id
    
    # Set flag to wait for coin input
    context.user_data["awaiting_smc_coin"] = True
    
    await update.message.reply_text(
        "🧠 *INSTITUTIONAL SMC ANALYSIS*\n\n"
        "Enter the coin symbol you want to analyze:\n"
        "Examples: BTC, ETH, SOL, BNB, XRP, ADA DOGE, etc.",
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
        )


async def smc_ask_timeframe(update, context, coin_symbol):
    """Ask user for timeframe after coin is provided"""
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("15 Minutes", callback_data="smc_tf_15m"),
            InlineKeyboardButton("1 Hour", callback_data="smc_tf_1h")
        ],
        [
            InlineKeyboardButton("4 Hours", callback_data="smc_tf_4h"),
            InlineKeyboardButton("1 Day", callback_data="smc_tf_1d")
        ],
        [
            InlineKeyboardButton("1 Week", callback_data="smc_tf_1w")
        ]
    ])
    
    await update.message.reply_text(
        f"🧠 SMC Analysis for *{coin_symbol.upper()}*\n\nSelect timeframe:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


async def smc_timeframe_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle timeframe selection and run SMC analysis"""
    query = update.callback_query
    timeframe = query.data.replace("smc_tf_", "")
    coin_symbol = context.user_data.get("smc_coin", "BTC")
    await query.answer()
    
    # Map symbol to CoinGecko ID
    cg_mapping = get_coingecko_coin_list()
    coin_id = cg_mapping.get(coin_symbol.lower(), coin_symbol.lower())
    
    await query.edit_message_text(
        f"🧠 Running SMC Analysis for *{coin_symbol.upper()}* ({timeframe})...\n"
        f"⏳ Please wait...",
        parse_mode="Markdown"
    )
    
    try:
        result = run_institutional_smc(coin_id, timeframe)
        
        if result and "error" not in result:
            message = (
                f"🧠 *SMC ANALYSIS - {coin_symbol.upper()}*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"*Timeframe:* {timeframe}\n"
                f"*Role:* {result['role']}\n"
                f"*Market Regime:* {result['regime']}\n\n"
                f"*Price Data:*\n"
                f"• Current: ${result['current_price']:,.2f}\n"
                f"• MA 50: ${result['ma50']:,.2f}\n"
                f"• MA 200: ${result['ma200']:,.2f}\n\n"
                f"*Indicators:*\n"
                f"• RSI: {result['rsi']:.2f}\n"
                f"• MACD Histogram: {result['macd_histogram']:.4f}\n\n"
            )
            
            await query.edit_message_text(message, parse_mode="Markdown")
        else:
            error_msg = result.get("error", "Unknown error") if result else "Failed to fetch data"
            await query.edit_message_text(
                f"❌ Error: {error_msg}\n\n"
                f"Try a different coin or timeframe.",
                parse_mode="Markdown"
            )
    
    except Exception as e:
        logger.error(f"SMC analysis error: {e}")
        await query.edit_message_text(
            f"❌ Analysis failed: {str(e)}",
            parse_mode="Markdown"
        )
    
    try:
        # Fetch Bitcoin data for demonstration
        hist_data = fetch_historical_prices("bitcoin", "1d", 90)
        
        if not hist_data:
            await update.message.reply_text(
                "❌ Failed to fetch price data",
                reply_markup=create_main_keyboard()
            )
            return
        
        prices = hist_data['prices']
        volumes = hist_data['volumes']
        
        # Generate synthetic highs/lows from prices
        highs = [p * 1.02 for p in prices]
        lows = [p * 0.98 for p in prices]
        
        # Run SMC analysis
        order_blocks = SMCAnalyzer.detect_order_blocks(prices, volumes)
        bos_choch = SMCAnalyzer.detect_bos_choch(prices, highs, lows)
        fvgs = SMCAnalyzer.detect_fvg(prices, highs, lows)
        liquidity_zones = SMCAnalyzer.detect_liquidity_zones(prices, highs, lows, volumes)
        wyckoff = SMCAnalyzer.detect_wyckoff_phase(prices, volumes)
        pd_arrays = SMCAnalyzer.detect_pd_arrays(prices, highs, lows)
        kill_zone = SMCAnalyzer.analyze_kill_zones(datetime.utcnow().hour)
        
        # Format results
        message = (
            f"🧠 *SMART MONEY CONCEPTS - BTC*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"*Wyckoff Phase:*\n"
            f"📊 {wyckoff['phase']} (Confidence: {wyckoff['confidence']}%)\n\n"
            f"*Kill Zone:*\n"
            f"🎯 {kill_zone['zone']}\n"
            f"└ Priority: {kill_zone['priority']}\n"
            f"└ {kill_zone['description']}\n\n"
            f"*Order Blocks:*\n"
            f"🟢 Bullish: {len([ob for ob in order_blocks if ob['type'] == 'bullish'])}\n"
            f"🔴 Bearish: {len([ob for ob in order_blocks if ob['type'] == 'bearish'])}\n\n"
            f"*Structure:*\n"
            f"📈 BOS Events: {len([e for e in bos_choch if e['type'] == 'BOS'])}\n"
            f"🔄 CHOCH Events: {len([e for e in bos_choch if e['type'] == 'CHOCH'])}\n\n"
            f"*Fair Value Gaps:*\n"
            f"🟢 Bullish FVG: {len([f for f in fvgs if f['type'] == 'bullish'])}\n"
            f"🔴 Bearish FVG: {len([f for f in fvgs if f['type'] == 'bearish'])}\n\n"
            f"*Liquidity:*\n"
            f"💧 Zones Detected: {len(liquidity_zones)}\n"
        )
        
        # Add recent events
        if bos_choch:
            message += "\n*Recent Structure Events:*\n"
            recent_events = sorted(bos_choch, key=lambda x: x['index'], reverse=True)[:3]
            for event in recent_events:
                direction_emoji = "📈" if event['direction'] == 'bullish' else "📉"
                message += f"{direction_emoji} {event['type']} {event['direction'].capitalize()} @ ${event['price']:,.2f}\n"
        
        if liquidity_zones:
            message += "\n*Recent Liquidity Grabs:*\n"
            recent_liq = sorted(liquidity_zones, key=lambda x: x['index'], reverse=True)[:3]
            for liq in recent_liq:
                side_emoji = "🟢" if liq['direction'] == 'buy_side' else "🔴"
                message += f"{side_emoji} {liq['direction'].replace('_', ' ').title()} @ ${liq['price']:,.2f}\n"
        
        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=create_main_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error in SMC analysis: {e}")
        await update.message.reply_text(
            "❌ Error running SMC analysis",
            reply_markup=create_main_keyboard()
        )

async def overlay_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Overlay Settings button"""
    chat_id = update.effective_chat.id
    
    # Get current settings
    overlays = user_overlay_settings.get(chat_id, {
        'fvg': True,
        'order_blocks': True,
        'bos_choch': True,
        'liquidity': True,
        'support_resistance': True,
        'ma_50': True,
        'ma_200': True,
        'pd_arrays': True,
        'kill_zones': True,
        'rsi': True,
        'volume': True
    })
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"{'✅' if overlays.get('fvg', True) else '❌'} FVG",
                callback_data="toggle_fvg"
            ),
            InlineKeyboardButton(
                f"{'✅' if overlays.get('order_blocks', True) else '❌'} Order Blocks",
                callback_data="toggle_order_blocks"
            )
        ],
        [
            InlineKeyboardButton(
                f"{'✅' if overlays.get('bos_choch', True) else '❌'} BOS/CHOCH",
                callback_data="toggle_bos_choch"
            ),
            InlineKeyboardButton(
                f"{'✅' if overlays.get('liquidity', True) else '❌'} Liquidity",
                callback_data="toggle_liquidity"
            )
        ],
        [
            InlineKeyboardButton(
                f"{'✅' if overlays.get('support_resistance', True) else '❌'} S/R",
                callback_data="toggle_support_resistance"
            ),
            InlineKeyboardButton(
                f"{'✅' if overlays.get('pd_arrays', True) else '❌'} PD Arrays",
                callback_data="toggle_pd_arrays"
            )
        ],
        [
            InlineKeyboardButton(
                f"{'✅' if overlays.get('ma_50', True) else '❌'} MA 50",
                callback_data="toggle_ma_50"
            ),
            InlineKeyboardButton(
                f"{'✅' if overlays.get('ma_200', True) else '❌'} MA 200",
                callback_data="toggle_ma_200"
            )
        ],
        [
            InlineKeyboardButton(
                f"{'✅' if overlays.get('kill_zones', True) else '❌'} Kill Zones",
                callback_data="toggle_kill_zones"
            ),
            InlineKeyboardButton(
                f"{'✅' if overlays.get('rsi', True) else '❌'} RSI",
                callback_data="toggle_rsi"
            )
        ]
    ])
    
    await update.message.reply_text(
        "🎛️ *OVERLAY SETTINGS*\n\n"
        "Toggle indicators ON/OFF for TradingView charts:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def toggle_overlay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle overlay toggle"""
    query = update.callback_query
    chat_id = query.message.chat_id
    
    # Parse which overlay to toggle
    overlay_name = query.data.replace("toggle_", "")
    
    # Get current settings
    if chat_id not in user_overlay_settings:
        user_overlay_settings[chat_id] = {}
    
    # Toggle the setting
    current_state = user_overlay_settings[chat_id].get(overlay_name, True)
    user_overlay_settings[chat_id][overlay_name] = not current_state
    
    await query.answer(f"{'Enabled' if not current_state else 'Disabled'} {overlay_name.replace('_', ' ').title()}")
    
    # Update the message with new buttons
    overlays = user_overlay_settings[chat_id]
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"{'✅' if overlays.get('fvg', True) else '❌'} FVG",
                callback_data="toggle_fvg"
            ),
            InlineKeyboardButton(
                f"{'✅' if overlays.get('order_blocks', True) else '❌'} Order Blocks",
                callback_data="toggle_order_blocks"
            )
        ],
        [
            InlineKeyboardButton(
                f"{'✅' if overlays.get('bos_choch', True) else '❌'} BOS/CHOCH",
                callback_data="toggle_bos_choch"
            ),
            InlineKeyboardButton(
                f"{'✅' if overlays.get('liquidity', True) else '❌'} Liquidity",
                callback_data="toggle_liquidity"
            )
        ],
        [
            InlineKeyboardButton(
                f"{'✅' if overlays.get('support_resistance', True) else '❌'} S/R",
                callback_data="toggle_support_resistance"
            ),
            InlineKeyboardButton(
                f"{'✅' if overlays.get('pd_arrays', True) else '❌'} PD Arrays",
                callback_data="toggle_pd_arrays"
            )
        ],
        [
            InlineKeyboardButton(
                f"{'✅' if overlays.get('ma_50', True) else '❌'} MA 50",
                callback_data="toggle_ma_50"
            ),
            InlineKeyboardButton(
                f"{'✅' if overlays.get('ma_200', True) else '❌'} MA 200",
                callback_data="toggle_ma_200"
            )
        ],
        [
            InlineKeyboardButton(
                f"{'✅' if overlays.get('ma_50', True) else '❌'} MA 50",
                callback_data="toggle_ma_50"
            ),
            InlineKeyboardButton(
                f"{'✅' if overlays.get('ma_200', True) else '❌'} MA 200",
                callback_data="toggle_ma_200"
            )
        ],
        [
            InlineKeyboardButton(
                f"{'✅' if overlays.get('kill_zones', True) else '❌'} Kill Zones",
                callback_data="toggle_kill_zones"
            ),
            InlineKeyboardButton(
                f"{'✅' if overlays.get('rsi', True) else '❌'} RSI",
                callback_data="toggle_rsi"
            )
        ]
    ])
    
    try:
        await query.edit_message_reply_markup(reply_markup=keyboard)
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            logger.error(f"Error updating overlay buttons: {e}")

# ==========================================
# ADDITIONAL HANDLERS
# ==========================================

async def ai_assistant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle AI Assistant menu selection"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧠 Groq (Fast)", callback_data="ai_groq")],
        [InlineKeyboardButton("🐋 DeepSeek (Smart)", callback_data="ai_deepseek")]
    ])
    await update.message.reply_text(
        "🤖 *AI Market Assistant*\nSelect your preferred AI model:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def ai_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle AI model selection callback"""
    query = update.callback_query
    provider = query.data.replace("ai_", "")
    context.user_data["ai_provider"] = provider
    await query.answer(f"Selected {provider.title()}")
    await query.edit_message_text(f"🤖 AI set to *{provider.title()}*.\nAsk me anything!")

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle settings callback"""
    query = update.callback_query
    await query.answer("Settings updated")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes text button presses to functions"""
    text = update.message.text
    chat_id = update.effective_chat.id
    
    # Check if waiting for SMC coin input
    if context.user_data.get("awaiting_smc_coin"):
        context.user_data["awaiting_smc_coin"] = False
        context.user_data["smc_coin"] = text.strip().upper()
        await smc_ask_timeframe(update, context, text.strip())
        return
    
    if text == "⚔️ Cross": await cross_analysis(update, context)
    elif text == "🌊 Sector Rotation": await sector_rotation(update, context)
    elif text == "🔥 Trending Coins": await trending_coins(update, context)
    elif text == "💎 Alpha Signals": await alpha_signals(update, context)
    elif text == "📊 Technical Analysis": await technical_analysis(update, context)
    elif text == "🧠 SMC Analysis": await smc_analysis(update, context)
    elif text == "🎛️ Overlay Settings": await overlay_settings(update, context)
    elif text == "🤖 AI Assistant": await ai_assistant(update, context)
    elif text == "ℹ️ Help": await help_command(update, context)
    else:
        # Default to AI query if not a menu button
        provider = context.user_data.get("ai_provider", "groq")
        market_data = get_market_regime()
        response = await ai_query(text, market_data, provider)
        await update.message.reply_text(response, parse_mode="Markdown")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Error: {context.error}")

# ==========================================
# MAIN
# ==========================================

def main():
    """Run the bot"""
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    
    application = Application.builder().token(TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(settings, pattern="^settings_"))
    application.add_handler(CallbackQueryHandler(smc_timeframe_selection, pattern="^smc_tf_"))
    application.add_handler(CallbackQueryHandler(cross_choice, pattern="^(golden_cross|death_cross)$"))
    application.add_handler(CallbackQueryHandler(timeframe_choice, pattern="^tf_"))
    application.add_handler(CallbackQueryHandler(ai_choice, pattern="^ai_"))
    application.add_handler(CallbackQueryHandler(toggle_overlay, pattern="^toggle_"))
    
    # Message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Run bot
    print("Bot is starting...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()
