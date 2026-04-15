"""Interhouse Amsterdam scraper — Playwright (JS-rendered listings).

Listings page: https://interhouse.nl/en/listings/?offer=huur
Listings load client-side. Each card is wrapped in an <a> linking to
  /en/vastgoed/huur/[city]/[type]/[street]
with an <h3> for the address and text nodes for size, bedrooms and price.

Field patterns in card text:
  h3  : "Appartement For rent Backershagen"
  text: "Amsterdam - Zuid"
  text: "Ca. 117 m2" or "117 m²"
  text: "3 bedrooms" or "3 slaapkamers"
  text: "€ 2.950 per month" or "€2.950/mnd"
"""

import re
import time
from typing import List, Optional
from playwright.sync_api import Page
from bs4 import BeautifulSoup
from scrapers.base import Listing, parse_price, safe_int

BASE_URL = "https://interhouse.nl"
SEARCH_URL = f"{BASE_URL}/en/listings/?offer=huur"

EXCLUDE_PHRASES = [
    "geen delers", "niet geschikt voor delers", "geen woningdelers",
    "no sharers", "not suitable for sharing", "geen studenten en woningdelers",
]


def _is_excluded(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in EXCLUDE_PHRASES)


def _parse_card(a_tag) -> Optional[Listing]:
    href = a_tag.get("href", "")
    if not href or "/vastgoed/huur/" not in href:
        return None

    # Filter to Amsterdam
    if "amsterdam" not in href.lower():
        return None

    url = BASE_URL + href if href.startswith("/") else href
    listing_id = href.strip("/").split("/")[-1]

    h3 = a_tag.find("h3")
    title = h3.get_text(" ", strip=True) if h3 else ""

    full_text = a_tag.get_text(" ", strip=True)

    # Price — "€ 2.950 per month", Dutch dot = thousands → strip to digits
    price = None
    price_match = re.search(r"€\s*([\d.]+)", full_text)
    if price_match:
        raw = price_match.group(1).replace(".", "")
        price = int(raw) if raw.isdigit() else None

    # m2: "Ca.  117 m 2" or "117 m²" (space may appear between m and 2)
    m2 = None
    m2_match = re.search(r"(?:Ca\.\s*)?(\d+)\s*m\s*[²2]", full_text, re.IGNORECASE)
    if m2_match:
        m2 = int(m2_match.group(1))

    # Bedrooms: "3 bedrooms", "Apartment 3" (total rooms; bedrooms = rooms - 1 for apartments)
    bedrooms = None
    bed_match = re.search(r"(\d+)\s*(?:bedrooms?|slaapkamers?)", full_text, re.IGNORECASE)
    if bed_match:
        bedrooms = int(bed_match.group(1))
    else:
        apt_match = re.search(r"[Aa]partment\s+(\d+)", full_text)
        if apt_match:
            rooms = int(apt_match.group(1))
            bedrooms = max(rooms - 1, 1)
        else:
            kamers_match = re.search(r"(\d+)\s*kamers?", full_text, re.IGNORECASE)
            if kamers_match:
                rooms = int(kamers_match.group(1))
                bedrooms = max(rooms - 1, 1)

    # Neighborhood from "Amsterdam - [area]"
    neighborhood = ""
    nb_match = re.search(r"Amsterdam\s*-\s*([^|€\n]+)", full_text, re.IGNORECASE)
    if nb_match:
        neighborhood = nb_match.group(1).strip()

    return Listing(
        id=listing_id,
        url=url,
        source="Interhouse Amsterdam",
        title=title,
        price=price,
        bedrooms=bedrooms,
        m2=m2,
        neighborhood=neighborhood,
    )


def scrape(page: Page) -> List[Listing]:
    listings = []
    seen_ids: set = set()
    url = SEARCH_URL

    for _ in range(5):  # max 5 pages
        page.goto(url, timeout=30000)
        try:
            page.wait_for_selector("h3", timeout=12000)
        except Exception:
            break

        time.sleep(2)
        soup = BeautifulSoup(page.content(), "lxml")

        a_tags = soup.find_all("a", href=re.compile(r"/vastgoed/huur/amsterdam"))

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

        # Next page — skip javascript: links
        next_link = soup.select_one('a[rel="next"], a[aria-label*="next" i]')
        if not next_link:
            break
        href = next_link.get("href", "")
        if not href or href.startswith("javascript"):
            break
        url = BASE_URL + href if href.startswith("/") else href
        time.sleep(2)

    return listings
