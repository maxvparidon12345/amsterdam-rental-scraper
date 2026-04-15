"""MVA Makelaars scraper — Playwright (JS-rendered listings).

Listings page: https://mva.nl/en/huur/woningen
Listing URL pattern: /en/huur/woningen/[street-city]
Each listing has two <a> tags with the same href:
  1. Empty one (wraps the image)
  2. Text one: "Street Nr POSTCODE, CITY € X.XXX p/m AREA"

Only Amsterdam listings are kept (postcode starts with 10XX or "AMSTERDAM" in text).
m² is a trailing number after the price (no explicit unit on overview page).
Price format: "€ 2.650 p/m" — Dutch dot = thousands separator.
"""

import re
import time
from typing import List, Optional
from playwright.sync_api import Page
from bs4 import BeautifulSoup
from scrapers.base import Listing, random_headers

BASE_URL = "https://mva.nl"
SEARCH_URL = f"{BASE_URL}/en/huur/woningen"

EXCLUDE_PHRASES = [
    "geen delers", "niet geschikt voor delers", "geen woningdelers",
    "no sharers", "not suitable for sharing", "geen studenten en woningdelers",
]

_HREF_PATTERN = re.compile(r"/en/huur/woningen/[a-z0-9-]+", re.IGNORECASE)


def _is_excluded(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in EXCLUDE_PHRASES)


def _parse_card(a_tag) -> Optional[Listing]:
    href = a_tag.get("href", "")
    if not href or not re.search(r"/en/huur/woningen/[a-z]", href, re.I):
        return None

    full_text = a_tag.get_text(" ", strip=True)
    if not full_text:
        return None  # skip the empty image-wrapper link

    # Only Amsterdam listings
    if "AMSTERDAM" not in full_text.upper() and not re.search(r"\b10\d{2}\b", full_text):
        return None

    url = BASE_URL + href if href.startswith("/") else href
    listing_id = href.strip("/").split("/")[-1]

    # Postcode: "1012 EG, AMSTERDAM" or "1012EG, AMSTERDAM"
    postcode = ""
    pc_match = re.search(r"(\d{4})\s?[A-Z]{2}", full_text)
    if pc_match:
        postcode = pc_match.group(0)[:4]

    # Title: text before the postcode
    title = re.split(r"\d{4}\s?[A-Z]{2}", full_text)[0].strip() if pc_match else full_text.split("€")[0].strip()

    # Price: "€ 2.650 p/m" — Dutch dot = thousands
    price = None
    price_match = re.search(r"€\s*([\d.]+)", full_text)
    if price_match:
        raw = price_match.group(1).replace(".", "")
        price = int(raw) if raw.isdigit() else None

    # m2: trailing number after "p/m" or "p.m."
    m2 = None
    m2_match = re.search(r"p/m\s+(\d+)", full_text, re.IGNORECASE)
    if m2_match:
        m2 = int(m2_match.group(1))
    else:
        m2_explicit = re.search(r"(\d+)\s*m[²2]", full_text, re.IGNORECASE)
        if m2_explicit:
            m2 = int(m2_explicit.group(1))

    # Bedrooms: not shown on overview page — left as None
    return Listing(
        id=listing_id,
        url=url,
        source="MVA Makelaars",
        title=title,
        price=price,
        bedrooms=None,
        m2=m2,
        postcode=postcode,
    )


def scrape(page: Page) -> List[Listing]:
    listings = []
    seen_ids: set = set()
    url = SEARCH_URL

    for _ in range(5):
        page.goto(url, timeout=30000)
        try:
            page.wait_for_selector("a[href*='/huur/woningen/']", timeout=12000)
        except Exception:
            break

        time.sleep(2)
        soup = BeautifulSoup(page.content(), "lxml")

        # Deduplicate by href; use the text-bearing link (non-empty)
        seen_hrefs: set = set()
        a_tags = []
        for a in soup.find_all("a", href=_HREF_PATTERN):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            if href and text and href not in seen_hrefs:
                seen_hrefs.add(href)
                a_tags.append(a)

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
        if not href or href.startswith("javascript"):
            break
        url = BASE_URL + href if href.startswith("/") else href
        time.sleep(2)

    return listings
