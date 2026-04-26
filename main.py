import os
import time
import requests

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

LAST_VOLUMES = {}

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
            pair_id = pair["pairAddress"]
            volume = pair["volume"]["h24"]
            liquidity = pair["liquidity"]["usd"]
            base = pair["baseToken"]["symbol"]
            quote = pair["quoteToken"]["symbol"]

            # alleen goede pairs
            if quote not in ["USDC", "USDT", "WETH"]:
                continue

            if liquidity < 30000:
                continue

            old_volume = LAST_VOLUMES.get(pair_id, volume)
            change = volume - old_volume

            # spike detectie
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

            LAST_VOLUMES[pair_id] = volume

        except:
            continue

send("🔥 Spike scanner gestart")

while True:
    scan()
    time.sleep(60)
