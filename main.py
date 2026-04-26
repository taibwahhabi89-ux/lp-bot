import os
import time
import requests

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

LAST_VOLUMES = {}
LAST_ALERTS = {}
COOLDOWN_SECONDS = 900  # 15 min cooldown

def send(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        pass

def score_pair(p):
    score = 0
    reasons = []

    volume = p.get("volume", {}).get("h24", 0)
    liquidity = p.get("liquidity", {}).get("usd", 0)
    txns = p.get("txns", {}).get("h24", {}).get("buys", 0)

    if volume > 100000:
        score += 1
        reasons.append("volume")

    if liquidity > 50000:
        score += 1
        reasons.append("liquidity")

    if txns > 100:
        score += 1
        reasons.append("activity")

    return score, reasons

def scan():
    url = "https://api.dexscreener.com/latest/dex/pairs/ethereum"
    data = requests.get(url).json()

    found = {}

    for pair in data["pairs"]:
        pair_id = pair["pairAddress"]
        found[pair_id] = pair

    for pair_id, p in found.items():
        try:
            score, reason = score_pair(p)

            # 🔥 EARLY + MOMENTUM
            pair_created = p.get("pairCreatedAt", 0)
            age_minutes = (time.time() - pair_created/1000) / 60 if pair_created else 99999

            if age_minutes < 120:
                score += 2

            if age_minutes < 30:
                score += 3

            if score < 5:
                continue

            volume = p["volume"]["h24"]
            liquidity = p["liquidity"]["usd"]

            # 🔥 FILTERS (no garbage)
            if liquidity < 30000:
                continue

            base = p["baseToken"]["symbol"]
            quote = p["quoteToken"]["symbol"]

            if quote not in ["USDC", "USDT", "WETH"]:
                continue

            old_volume = LAST_VOLUMES.get(pair_id, volume)
            change = volume - old_volume

            now = time.time()
            if pair_id in LAST_ALERTS and now - LAST_ALERTS[pair_id] < COOLDOWN_SECONDS:
                continue

            # 🔥 SPIKE DETECTIE
            if change > 50000 and volume > 100000:
                msg = f"""
🚀 VOLUME SPIKE

{base}/{quote}

💧 Liquidity: ${liquidity:,.0f}
📊 Volume: ${volume:,.0f}
📈 Spike: +${change:,.0f}

https://dexscreener.com/ethereum/{pair_id}
"""

                send(msg)
                LAST_ALERTS[pair_id] = now

            LAST_VOLUMES[pair_id] = volume

        except:
            continue

send("🔥 LP scanner volledig gestart!!")

while True:
    scan()
    time.sleep(60)
