import os
import time
import requests

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SEEN = set()

def send(msg):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": msg}
    )

def scan():
    url = "https://api.dexscreener.com/latest/dex/pairs/ethereum"
    data = requests.get(url).json()

    for pair in data["pairs"]:
        try:
            volume = pair["volume"]["h24"]
            liquidity = pair["liquidity"]["usd"]
            base = pair["baseToken"]["symbol"]
            quote = pair["quoteToken"]["symbol"]

            pair_id = pair["pairAddress"]

            if quote not in ["USDC", "USDT", "WETH"]:
                continue

            if liquidity < 50000:
                continue

            if volume < 200000:
                continue

            if pair_id in SEEN:
                continue

            SEEN.add(pair_id)

            msg = f"""
🚨 NEW ACTIVE POOL

{base}/{quote}
💧 Liquidity: ${liquidity:,.0f}
📊 Volume: ${volume:,.0f}

https://dexscreener.com/ethereum/{pair_id}
"""
            send(msg)

        except:
            continue

send("🔥 Scanner gestart")

while True:
    scan()
    time.sleep(120)
