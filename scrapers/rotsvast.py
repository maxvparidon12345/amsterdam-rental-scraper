"""Rotsvast Amsterdam scraper — requests + BeautifulSoup.

Listings page: https://www.rotsvast.nl/huis-huren-amsterdam/
The page is mostly server-side rendered; text content is present in raw HTML.
Listing cards are <a href="/huren/..."> elements containing city, street,
m², rooms and price as child div text nodes.
"""

import re
import time
import random
from typing import List, Optional
import requests
from bs4 import BeautifulSoup
from scrapers.base import Listing, parse_price, safe_int, random_headers

BASE_URL = "https://www.rotsvast.nl"
SEARCH_URL = f"{BASE_URL}/huis-huren-amsterdam/"

EXCLUDE_PHRASES = [
    "geen delers", "niet geschikt voor delers", "geen woningdelers",
    "no sharers", "not suitable for sharing", "geen studenten en woningdelers",
]

_STATUS_WORDS = {"beschikbaar", "verhuurd", "new", "nieuw"}


def _is_excluded(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in EXCLUDE_PHRASES)


def _parse_listing(a_tag) -> Optional[Listing]:
    href = a_tag.get("href", "")
    if not href:
        return None

    url = BASE_URL + href if href.startswith("/") else href
    listing_id = href.strip("/").split("/")[-1]

    # Use full text of the card for extraction
    full_text = a_tag.get_text(" ", strip=True)

    # Price: "€2.400 p.m." — Dutch dot = thousands separator, so 2.400 = 2400
    price = None
    price_match = re.search(r"€\s*([\d.]+)", full_text)
    if price_match:
        raw = price_match.group(1).replace(".", "")
        price = int(raw) if raw.isdigit() else None

    # m2: "79 m²"
    m2 = None
    m2_match = re.search(r"(\d+)\s*m²", full_text)
    if m2_match:
        m2 = int(m2_match.group(1))

    # Rooms: standalone number between m² and price
    rooms = None
    rooms_match = re.search(r"m²\s*(\d{1,2})\s*€", full_text)
    if rooms_match:
        rooms = int(rooms_match.group(1))

    # Title from named div (street name is the 4th non-empty div text)
    divs = [d.get_text(strip=True) for d in a_tag.find_all("div") if d.get_text(strip=True)]
    # Filter out status words and the parent combined-text div
    meaningful = [
        p for p in divs
        if p.lower() not in _STATUS_WORDS
        and "m²" not in p
        and "€" not in p
        and not re.search(r"Amsterdam.+m²", p)  # skip combined text
    ]
    # meaningful: [city, street] — use street as title
    title = meaningful[1] if len(meaningful) >= 2 else (meaningful[0] if meaningful else "")

    bedrooms = max(rooms - 1, 1) if rooms else None

    return Listing(
        id=listing_id,
        url=url,
        source="Rotsvast Amsterdam",
        title=title,
        price=price,
        bedrooms=bedrooms,
        m2=m2,
    )


def scrape() -> List[Listing]:
    listings = []
    seen_ids: set = set()

    for page_num in range(1, 6):
        url = SEARCH_URL if page_num == 1 else f"{SEARCH_URL}?p={page_num}"
        try:
            resp = requests.get(url, headers=random_headers(), timeout=15)
            resp.raise_for_status()
        except Exception:
            break

        soup = BeautifulSoup(resp.text, "lxml")
        # Match only Amsterdam listings (city is embedded in the URL slug)
        a_tags = soup.find_all("a", href=re.compile(r"/huren/[a-z0-9-]+-amsterdam-"))

        page_listings = []
        for a_tag in a_tags:
            try:
                listing = _parse_listing(a_tag)
                if listing and listing.id not in seen_ids:
                    if not _is_excluded(a_tag.get_text()):
                        seen_ids.add(listing.id)
                        page_listings.append(listing)
            except Exception:
                pass

        if not page_listings:
            break

        listings.extend(page_listings)
        time.sleep(random.uniform(1, 2))

    return listings
