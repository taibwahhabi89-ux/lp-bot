import os
import time
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

CHECK_INTERVAL = 180
COOLDOWN = 60 * 60

CHAINS = {"ethereum", "base", "arbitrum"}

QUERIES = [
    "WETH", "ETH", "USDC", "USDT", "WBTC", "BTC",
    "AAVE", "LINK", "UNI", "LDO", "ARB", "OP",
    "wstETH", "rETH", "weETH", "cbETH",
    "USDe", "sUSDe", "DAI", "FRAX"
]

BAD_WORDS = [
    "elon", "musk", "inu", "pepe", "dog", "cat", "shib",
    "baby", "moon", "pump", "safe", "chad", "flork",
    "casino", "presale", "frog", "ape", "trump"
]

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
            print("Bad status", r.status_code)
            return {}
        return r.json()
    except Exception as e:
        print("JSON/fetch error:", e)
        return {}

def fetch_pairs(query):
    url = f"https://api.dexscreener.com/latest/dex/search?q={query}"
    data = safe_get_json(url)
    return data.get("pairs") or []

def has_bad_name(base, quote):
    text = f"{base} {quote}".lower()
    return any(w in text for w in BAD_WORDS)

def score_pair(p):
    score = 0
    reasons = []

    dex = (p.get("dexId") or "").lower()
    chain = p.get("chainId")

    base = (p.get("baseToken") or {}).get("symbol", "?")
    quote = (p.get("quoteToken") or {}).get("symbol", "?")

    if "uniswap" not in dex:
        return -999, ["not uniswap"]

    if chain not in CHAINS:
        return -999, ["wrong chain"]

    if has_bad_name(base, quote):
        return -999, ["bad name"]

    liquidity = float((p.get("liquidity") or {}).get("usd") or 0)
    volume24 = float((p.get("volume") or {}).get("h24") or 0)
    volume1h = float((p.get("volume") or {}).get("h1") or 0)
    volume5m = float((p.get("volume") or {}).get("m5") or 0)

    txns = p.get("txns") or {}
    h24 = txns.get("h24") or {}
    buys = int(h24.get("buys") or 0)
    sells = int(h24.get("sells") or 0)
    total_txns = buys + sells

    makers = int(((p.get("makers") or {}).get("h24")) or 0)

    price_change = p.get("priceChange") or {}
    change_24h = float(price_change.get("h24") or 0)
    change_6h = float(price_change.get("h6") or 0)
    change_1h = float(price_change.get("h1") or 0)

    pair_created = p.get("pairCreatedAt", 0)
    age_minutes = (time.time() - pair_created / 1000) / 60 if pair_created else 99999

    if liquidity < 200_000:
        return -999, ["liquidity too low"]

    if liquidity > 30_000_000:
        return -999, ["too crowded"]

    if volume24 < 500_000:
        return -999, ["volume too low"]

    if volume1h < 50_000:
        return -999, ["1h volume too low"]

    if total_txns < 200:
        return -999, ["txns too low"]

    if makers < 50:
        return -999, ["makers too low"]

    if buys == 0 or sells == 0:
        return -999, ["one sided"]

    balance = min(buys, sells) / max(buys, sells)
    if balance < 0.30:
        return -999, ["buy/sell imbalance"]

    vol_tvl = volume24 / liquidity if liquidity else 0

    if vol_tvl >= 0.25:
        score += 1
        reasons.append("good vol/tvl")

    if vol_tvl >= 0.50:
        score += 2
        reasons.append("strong vol/tvl")

    if vol_tvl >= 1.00:
        score += 2
        reasons.append("very strong vol/tvl")

    if volume1h >= 100_000:
        score += 1
        reasons.append("1h volume")

    if volume5m >= 10_000:
        score += 1
        reasons.append("5m activity")

    if total_txns >= 500:
        score += 1
        reasons.append("many txns")

    if makers >= 150:
        score += 1
        reasons.append("many makers")

    if balance >= 0.45:
        score += 1
        reasons.append("balanced flow")

    if age_minutes < 1440:
        score += 1
        reasons.append("fresh <24h")

    if age_minutes < 360:
        score += 2
        reasons.append("early <6h")

    if age_minutes < 120:
        score += 2
        reasons.append("very early <2h")

    if abs(change_24h) > 300:
        score -= 3
        reasons.append("too pumpy 24h")

    if abs(change_6h) > 200:
        score -= 2
        reasons.append("too pumpy 6h")

    if change_1h < -20:
        score -= 2
        reasons.append("dumping 1h")

    return score, reasons

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
            score, reasons = score_pair(p)

            if score < 5:
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
            volume5m = float((p.get("volume") or {}).get("m5") or 0)
            vol_tvl = volume24 / liquidity if liquidity else 0

            h24 = (p.get("txns") or {}).get("h24") or {}
            buys = int(h24.get("buys") or 0)
            sells = int(h24.get("sells") or 0)
            total_txns = buys + sells

            makers = int(((p.get("makers") or {}).get("h24")) or 0)

            price_change = p.get("priceChange") or {}
            change_1h = float(price_change.get("h1") or 0)
            change_6h = float(price_change.get("h6") or 0)
            change_24h = float(price_change.get("h24") or 0)

            pair_created = p.get("pairCreatedAt", 0)
            age_minutes = (time.time() - pair_created / 1000) / 60 if pair_created else 99999

            dex_url = p.get("url") or f"https://dexscreener.com/{chain}/{pair_id}"
            uni_url = f"https://app.uniswap.org/explore/pools/{chain}/{pair_id}"

            msg = f"""
🎯 SNIPER LP ALERT

Pool: {base}/{quote}
Chain: {chain}
DEX: {dex}
Score: {score}

💧 Liquidity: ${liquidity:,.0f}
📊 24h Volume: ${volume24:,.0f}
⚡ 1h Volume: ${volume1h:,.0f}
🔥 5m Volume: ${volume5m:,.0f}
📈 Vol/TVL: {vol_tvl:.2f}

🔁 TXNS 24h: {total_txns}
🟢 Buys: {buys}
🔴 Sells: {sells}
👥 Makers: {makers}

⏱️ Age: {age_minutes:.0f} min
📉 1h change: {change_1h:.2f}%
📉 6h change: {change_6h:.2f}%
📉 24h change: {change_24h:.2f}%

Reasons:
{", ".join(reasons)}

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

while True:
    scan()
    time.sleep(CHECK_INTERVAL)
