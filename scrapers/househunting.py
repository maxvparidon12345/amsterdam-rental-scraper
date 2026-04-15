"""HouseHunting Amsterdam scraper — Playwright (JS-rendered listings).

Listings page: https://househunting.nl/en/housing-offer/
Individual listing URLs follow: /en/woningaanbod/[uuid]-[street]-[city]-[n]/
Only listings with "amsterdam" in the href are returned.

NOTE: The ?vestiging=amsterdam filter showed 0 results in testing. This scraper
instead loads the base housing-offer page (all offices) and filters to Amsterdam
by checking the city in the listing URL. It may return 0 if Amsterdam listings
happen to be absent at a given run.
"""

import re
import time
from typing import List, Optional
from playwright.sync_api import Page
from bs4 import BeautifulSoup
from scrapers.base import Listing, parse_price, safe_int

BASE_URL = "https://househunting.nl"
SEARCH_URL = f"{BASE_URL}/en/housing-offer/"

EXCLUDE_PHRASES = [
    "geen delers", "niet geschikt voor delers", "geen woningdelers",
    "no sharers", "not suitable for sharing", "geen studenten en woningdelers",
]


def _is_excluded(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in EXCLUDE_PHRASES)


def _parse_card(a_tag) -> Optional[Listing]:
    href = a_tag.get("href", "")
    if not href or "/woningaanbod/" not in href:
        return None

    # Filter to Amsterdam listings
    if "-amsterdam-" not in href.lower() and not href.lower().endswith("-amsterdam"):
        return None

    url = BASE_URL + href if href.startswith("/") else href
    listing_id = href.strip("/").split("/")[-1]

    full_text = a_tag.get_text(" ", strip=True)
    if not full_text:
        return None

    h_tag = a_tag.find(re.compile(r"^h[1-4]$"))
    title = h_tag.get_text(strip=True) if h_tag else ""

    # Price
    price = None
    price_match = re.search(r"€\s*[\d.,]+", full_text)
    if price_match:
        price = parse_price(price_match.group(0))

    # m2
    m2 = None
    m2_match = re.search(r"(\d+)\s*m[²2]", full_text, re.IGNORECASE)
    if m2_match:
        m2 = int(m2_match.group(1))

    # Bedrooms
    bedrooms = None
    bed_match = re.search(r"(\d+)\s*(?:bedrooms?|slaapkamers?)", full_text, re.IGNORECASE)
    if bed_match:
        bedrooms = int(bed_match.group(1))
    else:
        kamers_match = re.search(r"(\d+)\s*kamers?", full_text, re.IGNORECASE)
        if kamers_match:
            rooms = int(kamers_match.group(1))
            bedrooms = max(rooms - 1, 1)

    # Postcode
    postcode = ""
    pc_match = re.search(r"(\d{4})\s?[A-Z]{2}", full_text)
    if pc_match:
        postcode = pc_match.group(0)[:4]

    return Listing(
        id=listing_id,
        url=url,
        source="HouseHunting Amsterdam",
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
        time.sleep(4)

        # Try to click "Show more" if present to load additional results
        try:
            show_more = page.locator('button:has-text("Show more"), button:has-text("Meer tonen")')
            if show_more.count() > 0:
                show_more.first.click()
                time.sleep(2)
        except Exception:
            pass

        soup = BeautifulSoup(page.content(), "lxml")
        a_tags = soup.find_all("a", href=re.compile(r"/woningaanbod/"))

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
        next_link = soup.select_one('a[rel="next"], a[aria-label*="next" i]')
        if not next_link:
            break
        href = next_link.get("href", "")
        url = BASE_URL + href if href.startswith("/") else href
        time.sleep(2)

    return listings
