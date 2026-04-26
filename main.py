import os
import time
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

CHECK_INTERVAL = 180
COOLDOWN = 60 * 60

QUERIES = [
    "WETH", "ETH", "USDC", "USDT", "WBTC", "BTC",
    "AAVE", "LINK", "UNI", "LDO", "ARB", "OP",
    "wstETH", "rETH", "weETH", "cbETH", "USDe", "sUSDe"
]

CHAINS = {"ethereum", "base", "arbitrum"}
LAST_ALERTS = {}

def send(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg},
            timeout=15
        )
    except Exception as e:
        print("Telegram error:", e)

def safe_get_json(url):
    try:
        r = requests.get(url, timeout=20)
        if r.status_code != 200:
            print("Bad status:", r.status_code, url)
            return {}
        return r.json()
    except Exception as e:
        print("Fetch/json error:", e, url)
        return {}

def fetch_pairs(query):
    url = f"https://api.dexscreener.com/latest/dex/search?q={query}"
    data = safe_get_json(url)
    return data.get("pairs") or []

def good_pair(p):
    dex = (p.get("dexId") or "").lower()
    chain = p.get("chainId")

    if "uniswap" not in dex:
        return False

    if chain not in CHAINS:
        return False

    liquidity = float((p.get("liquidity") or {}).get("usd") or 0)
    volume24 = float((p.get("volume") or {}).get("h24") or 0)
    volume1h = float((p.get("volume") or {}).get("h1") or 0)

    txns = p.get("txns") or {}
    h24 = txns.get("h24") or {}
    buys = int(h24.get("buys") or 0)
    sells = int(h24.get("sells") or 0)
    total_txns = buys + sells

    makers = int(((p.get("makers") or {}).get("h24")) or 0)

    if liquidity < 300_000:
        return False

    if liquidity > 50_000_000:
        return False

    if volume24 < 500_000:
        return False

    if volume1h < 50_000:
        return False

    if volume24 / liquidity < 0.25:
        return False

    if total_txns < 250:
        return False

    if makers < 50:
        return False

    if buys == 0 or sells == 0:
        return False

    balance = min(buys, sells) / max(buys, sells)
    if balance < 0.25:
        return False

    return True

def scan():
    found = {}

    for q in QUERIES:
        pairs = fetch_pairs(q)
        for p in pairs:
            pair_id = p.get("pairAddress")
            if pair_id:
                found[pair_id] = p

    for pair_id, p in found.items():
        try:
            if not good_pair(p):
                continue

            now = time.time()
            if pair_id in LAST_ALERTS and now - LAST_ALERTS[pair_id] < COOLDOWN:
                continue

            base = (p.get("baseToken") or {}).get("symbol", "?")
            quote = (p.get("quoteToken") or {}).get("symbol", "?")
            chain = p.get("chainId", "?")
            dex = p.get("dexId", "?")

            liquidity = float((p.get("liquidity") or {}).get("usd") or 0)
            volume24 = float((p.get("volume") or {}).get("h24") or 0)
            volume1h = float((p.get("volume") or {}).get("h1") or 0)
            vol_tvl = volume24 / liquidity if liquidity else 0

            h24 = (p.get("txns") or {}).get("h24") or {}
            buys = int(h24.get("buys") or 0)
            sells = int(h24.get("sells") or 0)
            total_txns = buys + sells

            makers = int(((p.get("makers") or {}).get("h24")) or 0)

            dex_url = p.get("url") or f"https://dexscreener.com/{chain}/{pair_id}"
            uni_url = f"https://app.uniswap.org/explore/pools/{chain}/{pair_id}"

            msg = f"""
🚨 LP KANDIDAAT

Pool: {base}/{quote}
Chain: {chain}
DEX: {dex}

💧 Liquidity: ${liquidity:,.0f}
📊 24h Volume: ${volume24:,.0f}
⚡ 1h Volume: ${volume1h:,.0f}
📈 Vol/TVL: {vol_tvl:.2f}

🔁 TXNS 24h: {total_txns}
🟢 Buys: {buys}
🔴 Sells: {sells}
👥 Makers: {makers}

Dexscreener:
{dex_url}

Uniswap:
{uni_url}

VFAT:
https://vfat.io/
"""
            send(msg)
            LAST_ALERTS[pair_id] = now

        except Exception as e:
            print("Pair error:", e)

send("✅ LP scanner stabiel gestart")

while True:
    scan()
    time.sleep(CHECK_INTERVAL)
