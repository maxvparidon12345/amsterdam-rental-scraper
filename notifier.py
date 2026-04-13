import os
import urllib.request
import urllib.parse
import json
from typing import List
from scrapers.base import Listing


def _send_message(token: str, chat_id: str, text: str) -> None:
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data,
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
        if not result.get("ok"):
            raise RuntimeError(f"Telegram fout: {result}")


MAX_MESSAGES = 10


def send_alert(listings: List[Listing]) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    to_send = listings[:MAX_MESSAGES]
    overflow = len(listings) - len(to_send)

    for l in to_send:
        price_str = f"€{l.price}/mnd" if l.price else "prijs onbekend"
        bedrooms_str = f"{l.bedrooms} kamers" if l.bedrooms else ""
        m2_str = f"{l.m2} m²" if l.m2 else ""
        details = " · ".join(filter(None, [price_str, bedrooms_str, m2_str, l.postcode]))
        title = l.title or l.source
        text = f"🏠 *Nieuwe woning*\n[{title}]({l.url})\n{details}"
        _send_message(token, chat_id, text)

    if overflow > 0:
        _send_message(token, chat_id, f"📋 En nog *{overflow}* andere nieuwe woningen — check Funda voor het volledige overzicht.")

    print(f"Telegram bericht verstuurd met {len(listings)} listing(s)")
