"""27Huis scraper — Playwright (JS-rendered listings).

Listings page: https://www.27huis.nl/nl/aanbod/huur
The huur page renders via JS. Based on the homepage HTML, listing cards use:
  <a href="/nl/aanbod/woning/amsterdam/[street]/[uuid]">
    <span>Te huur</span>
    <h3>street address</h3>
    <p>Xm²</p>
    <p>X kamers</p>
    <p>€ X.XXX p.m. excl.</p>
  </a>

Only Amsterdam listings are kept (city in href path).
"""

import re
import time
from typing import List, Optional
from playwright.sync_api import Page
from bs4 import BeautifulSoup
from scrapers.base import Listing, parse_price, safe_int

BASE_URL = "https://www.27huis.nl"
SEARCH_URL = f"{BASE_URL}/nl/aanbod/huur"

EXCLUDE_PHRASES = [
    "geen delers", "niet geschikt voor delers", "geen woningdelers",
    "no sharers", "not suitable for sharing", "geen studenten en woningdelers",
]


def _is_excluded(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in EXCLUDE_PHRASES)


def _parse_card(a_tag) -> Optional[Listing]:
    href = a_tag.get("href", "")
    if not href or "/nl/aanbod/woning/" not in href:
        return None

    # Only Amsterdam
    if "/amsterdam/" not in href.lower():
        return None

    # Only "Te huur" (not "Te koop", "Verhuurd" or "Verkocht")
    spans = [s.get_text(strip=True).lower() for s in a_tag.find_all("span")]
    if "te huur" not in spans:
        return None

    url = BASE_URL + href if href.startswith("/") else href
    listing_id = href.strip("/").split("/")[-1]

    h3 = a_tag.find("h3")
    title = h3.get_text(strip=True) if h3 else ""

    full_text = a_tag.get_text(" ", strip=True)

    # Price: "€ X.XXX p.m. excl."
    price = None
    price_match = re.search(r"€\s*[\d.,]+", full_text)
    if price_match:
        price = parse_price(price_match.group(0))

    # m2: "185m²", "185 m²", or standalone number before "kamers"
    m2 = None
    m2_match = re.search(r"(\d+)\s*m²", full_text)
    if m2_match:
        m2 = int(m2_match.group(1))
    else:
        # Format: "110 3 kamers" — number before rooms count
        m2_kamers = re.search(r"(\d{2,4})\s+\d+\s+kamers?", full_text, re.IGNORECASE)
        if m2_kamers:
            m2 = int(m2_kamers.group(1))

    # Bedrooms from "X kamers" (total - 1)
    bedrooms = None
    kamers_match = re.search(r"(\d+)\s*kamers?", full_text, re.IGNORECASE)
    if kamers_match:
        rooms = int(kamers_match.group(1))
        bedrooms = max(rooms - 1, 1)

    # Postcode: not in card; try from title with regex
    postcode = ""
    pc_match = re.search(r"(\d{4})\s?[A-Z]{2}", title)
    if pc_match:
        postcode = pc_match.group(0)[:4]

    return Listing(
        id=listing_id,
        url=url,
        source="27Huis",
        title=title,
        price=price,
        bedrooms=bedrooms,
        m2=m2,
        postcode=postcode,
    )


def scrape(page: Page) -> List[Listing]:
    listings = []
    seen_ids: set = set()
    url = SEARCH_URL

    for _ in range(5):
        page.goto(url, timeout=30000)
        time.sleep(3)

        soup = BeautifulSoup(page.content(), "lxml")
        a_tags = soup.find_all("a", href=re.compile(r"/nl/aanbod/woning/amsterdam/"))

        page_listings = []
        for a_tag in a_tags:
            try:
                listing = _parse_card(a_tag)
                if listing and listing.id not in seen_ids:
                    if not _is_excluded(a_tag.get_text()):
                        seen_ids.add(listing.id)
                        page_listings.append(listing)
            except Exception:
                pass

        if not page_listings:
            break

        listings.extend(page_listings)

        # Next page
        next_link = soup.select_one('a[rel="next"]')
        if not next_link:
            break
        href = next_link.get("href", "")
        url = BASE_URL + href if href.startswith("/") else href
        time.sleep(2)

    return listings
