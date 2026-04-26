import os, time, requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "180"))
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "21600"))

MIN_LIQUIDITY = float(os.getenv("MIN_LIQUIDITY", "300000"))
MAX_LIQUIDITY = float(os.getenv("MAX_LIQUIDITY", "50000000"))
MIN_VOLUME_24H = float(os.getenv("MIN_VOLUME_24H", "500000"))
MIN_VOL_TVL = float(os.getenv("MIN_VOL_TVL", "0.25"))
MIN_TXNS_24H = int(os.getenv("MIN_TXNS_24H", "300"))
MIN_MAKERS = int(os.getenv("MIN_MAKERS", "80"))
MIN_SPIKE_1H = float(os.getenv("MIN_SPIKE_1H", "100000"))

CHAINS = {"ethereum", "base", "arbitrum"}
QUERIES = [
    "WETH", "ETH", "USDC", "USDT", "WBTC", "BTC",
    "LINK", "AAVE", "UNI", "LDO", "ARB", "OP",
    "weETH", "wstETH", "rETH", "cbETH", "ezETH",
    "sUSDe", "USDe", "DAI", "FRAX"
]

BAD_WORDS = [
    "elon", "musk", "inu", "pepe", "dog", "cat", "shib",
    "chad", "moon", "pump", "safe", "baby", "flork",
    "asteroid", "casino", "presale"
]

last_volumes = {}
last_alerts = {}

def send(msg):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": msg},
        timeout=15
    )

def fetch(query):
    url = f"https://api.dexscreener.com/latest/dex/search?q={query}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json().get("pairs", [])

def bad_name(base, quote):
    name = f"{base} {quote}".lower()
    return any(w in name for w in BAD_WORDS)

def score_pair(p):
    score = 0

    chain = p.get("chainId", "")
    dex = p.get("dexId", "")
    base = p.get("baseToken", {}).get("symbol", "")
    quote = p.get("quoteToken", {}).get("symbol", "")

    if chain not in CHAINS:
        return -999, "wrong chain"

    if "uniswap" not in dex.lower():
        return -999, "not uniswap"

    if bad_name(base, quote):
        return -999, "meme/garbage name"

    liquidity = float(p.get("liquidity", {}).get("usd") or 0)
    volume24 = float(p.get("volume", {}).get("h24") or 0)
    volume1h = float(p.get("volume", {}).get("h1") or 0)

    txns = p.get("txns", {}).get("h24", {})
    buys = int(txns.get("buys") or 0)
    sells = int(txns.get("sells") or 0)
    total_txns = buys + sells

    makers = int(p.get("makers", {}).get("h24") or 0)

    price_change = p.get("priceChange", {})
    change_24h = float(price_change.get("h24") or 0)

    if liquidity < MIN_LIQUIDITY:
        return -999, "liquidity too low"

    if liquidity > MAX_LIQUIDITY:
        return -999, "liquidity too high"

    if volume24 < MIN_VOLUME_24H:
        return -999, "volume too low"

    vol_tvl = volume24 / liquidity if liquidity else 0

    if vol_tvl < MIN_VOL_TVL:
        return -999, "vol/tvl too low"

    if total_txns < MIN_TXNS_24H:
        return -999, "not enough txns"

    if makers < MIN_MAKERS:
        return -999, "not enough makers"

    if abs(change_24h) > 300:
        return -999, "too pumpy"

    if vol_tvl >= 0.25:
        score += 1
    if vol_tvl >= 0.5:
        score += 2
    if volume1h >= MIN_SPIKE_1H:
        score += 2
    if total_txns >= 500:
        score += 1
    if makers >= 150:
        score += 1
    if buys > 0 and sells > 0:
        balance = min(buys, sells) / max(buys, sells)
        if balance > 0.35:
            score += 1

    return score, "ok"

def scan():
    found = {}

    for q in QUERIES:
        try:
            for p in fetch(q):
                pair_id = p.get("pairAddress")
                if pair_id:
                    found[pair_id] = p
        except Exception:
            continue

    for pair_id, p in found.items():
        try:
            score, reason = score_pair(p)
            if score < 5:
                continue

            now = time.time()
            if pair_id in last_alerts and now - last_alerts[pair_id] < COOLDOWN_SECONDS:
                continue

            chain = p.get("chainId", "")
            dex = p.get("dexId", "")
            base = p.get("baseToken", {}).get("symbol", "")
            quote = p.get("quoteToken", {}).get("symbol", "")

            liquidity = float(p.get("liquidity", {}).get("usd") or 0)
            volume24 = float(p.get("volume", {}).get("h24") or 0)
            volume1h = float(p.get("volume", {}).get("h1") or 0)
            vol_tvl = volume24 / liquidity if liquidity else 0

            txns = p.get("txns", {}).get("h24", {})
            buys = int(txns.get("buys") or 0)
            sells = int(txns.get("sells") or 0)
            total_txns = buys + sells

            makers = int(p.get("makers", {}).get("h24") or 0)

            dex_link = p.get("url")
            uni_link = f"https://app.uniswap.org/explore/pools/{chain}/{pair_id}"
            vfat_link = "https://vfat.io/"

            msg = f"""
🚨 LP KANDIDAAT GEVONDEN

Pool: {base}/{quote}
Chain: {chain}
DEX: {dex}
Score: {score}/8

💧 Liquidity: ${liquidity:,.0f}
📊 24h Volume: ${volume24:,.0f}
⚡ 1h Volume: ${volume1h:,.0f}
📈 Vol/TVL: {vol_tvl:.2f}

🔁 TXNS 24h: {total_txns}
🟢 Buys: {buys}
🔴 Sells: {sells}
👥 Makers: {makers}

Dexscreener:
{dex_link}

Uniswap:
{uni_link}

VFAT:
{vfat_link}
"""
            send(msg)
            last_alerts[pair_id] = now

        except Exception:
            continue

send("🔥 LP scanner volledig gestart")

while True:
    scan()
    time.sleep(CHECK_INTERVAL)
