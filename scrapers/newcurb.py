"""NEWCURB Makelaars scraper — requests + BeautifulSoup.

Listings page: https://newcurbmakelaars.nl/woningaanbod/huur/amsterdam/
Server-side rendered. Each listing card:
  <h3><a href="/woningaanbod/huur/amsterdam/[street]/[number]">address postcode city</a></h3>
  (details and price are siblings inside h3.parent)

Price format: "€ 1.111,39 /mnd" (Dutch: dot = thousands, comma = decimal)

Note: newcurb.nl and newcurbmakelaars.nl are the same agency; the listings
live on newcurbmakelaars.nl.
"""

import re
import time
import random
from typing import List, Optional
import requests
from bs4 import BeautifulSoup
from scrapers.base import Listing, random_headers

BASE_URL = "https://newcurbmakelaars.nl"
SEARCH_URL = f"{BASE_URL}/woningaanbod/huur/amsterdam/"

EXCLUDE_PHRASES = [
    "geen delers", "niet geschikt voor delers", "geen woningdelers",
    "no sharers", "not suitable for sharing", "geen studenten en woningdelers",
]

_HREF_PATTERN = re.compile(r"/woningaanbod/huur/amsterdam/")


def _is_excluded(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in EXCLUDE_PHRASES)


def _parse_dutch_price(text: str) -> Optional[int]:
    """Parse Dutch price '€ 1.111,39 /mnd' → 1111."""
    m = re.search(r"€\s*([\d.]+)(?:[,]\d+)?", text)
    if not m:
        return None
    raw = m.group(1).replace(".", "")  # remove thousands dots
    return int(raw) if raw.isdigit() else None


def _parse_card(h3) -> Optional[Listing]:
    """Parse a listing from its h3 element (card = h3.parent)."""
    link = h3.find("a", href=_HREF_PATTERN)
    if not link:
        return None

    href = link.get("href", "").split("?")[0]
    url = BASE_URL + href if href.startswith("/") else href
    listing_id = href.strip("/").replace("/", "-")

    # Title with proper spacing
    title = link.get_text(" ", strip=True)

    card = h3.parent
    full_text = card.get_text(" ", strip=True)

    # Skip already-rented
    if "verhuurd" in full_text.lower():
        return None

    # Postcode from title: "Sierplein 68 1065LN Amsterdam"
    postcode = ""
    pc_match = re.search(r"(\d{4})\s?[A-Z]{2}", title)
    if pc_match:
        postcode = pc_match.group(0)[:4]

    # Bedrooms from "X slaapkamers"
    bedrooms = None
    slpk_match = re.search(r"(\d+)\s*slaapkamers?", full_text.lower())
    if slpk_match:
        bedrooms = int(slpk_match.group(1))
    else:
        kamers_match = re.search(r"(\d+)\s*kamers?", full_text.lower())
        if kamers_match:
            rooms = int(kamers_match.group(1))
            bedrooms = max(rooms - 1, 1)

    # m2
    m2 = None
    m2_match = re.search(r"(\d+)\s*m²", full_text)
    if m2_match:
        m2 = int(m2_match.group(1))

    # Price — Dutch format: "€ 1.111,39" → 1111
    price = _parse_dutch_price(full_text)

    return Listing(
        id=listing_id,
        url=url,
        source="NEWCURB Makelaars",
        title=title,
        price=price,
        bedrooms=bedrooms,
        m2=m2,
        postcode=postcode,
    )


def scrape() -> List[Listing]:
    listings = []
    seen_ids: set = set()

    for page_num in range(1, 6):
        params = (
            "?moveunavailablelistingstothebottom=true&orderby=10&orderdescending=true"
            f"&take=12&skip={12 * (page_num - 1)}"
        )
        url = SEARCH_URL + params
        try:
            resp = requests.get(url, headers=random_headers(), timeout=15)
            resp.raise_for_status()
        except Exception:
            break

        soup = BeautifulSoup(resp.text, "lxml")

        page_listings = []
        seen_hrefs: set = set()

        for h3 in soup.find_all("h3"):
            link = h3.find("a", href=_HREF_PATTERN)
            if not link:
                continue
            href = link.get("href", "").split("?")[0]
            if href in seen_hrefs:
                continue
            seen_hrefs.add(href)

            try:
                listing = _parse_card(h3)
                if listing and listing.id not in seen_ids:
                    if not _is_excluded(h3.parent.get_text() if h3.parent else ""):
                        seen_ids.add(listing.id)
                        page_listings.append(listing)
            except Exception:
                pass

        if not page_listings:
            break

        listings.extend(page_listings)
        time.sleep(random.uniform(1, 2))

    return listings
