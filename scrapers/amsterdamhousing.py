"""Amsterdam Housing scraper — Playwright (JS-rendered SPA).

Listings page: https://www.amsterdamhousing.com/en/rental-listings
Listing URL pattern: /en/amsterdam/[street]/[uuid]

Each listing has multiple <a> tags pointing to the same href (image + text).
The card container holds all listing info. Data is extracted from the card.

Status: "For rent", "Under option", "Rented"
Only "For rent" and "Under option" listings are kept; "Rented" are skipped.
Price format: "€ X.XXX p.m. exclusive" — Dutch dot = thousands separator.
m² format: "69m²" (no space before symbol).
Bedrooms: "2 bedr" at the end of the card text.
"""

import re
import time
from typing import List, Optional
from playwright.sync_api import Page
from bs4 import BeautifulSoup
from scrapers.base import Listing

BASE_URL = "https://www.amsterdamhousing.com"
SEARCH_URL = f"{BASE_URL}/en/rental-listings"

EXCLUDE_PHRASES = [
    "geen delers", "niet geschikt voor delers", "geen woningdelers",
    "no sharers", "not suitable for sharing", "geen studenten en woningdelers",
]

_HREF_PATTERN = re.compile(r"/en/amsterdam/")
_SKIP_STATUSES = {"rented"}


def _is_excluded(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in EXCLUDE_PHRASES)


def _find_card(a_tag):
    """Walk up DOM to find smallest ancestor that contains price info."""
    node = a_tag
    for _ in range(8):
        node = node.parent
        if node is None:
            break
        t = node.get_text()
        if "€" in t and ("p.m." in t.lower() or "per month" in t.lower()):
            # Ensure this is not a container with multiple listings
            links = {lnk["href"] for lnk in node.find_all("a", href=_HREF_PATTERN)}
            if len(links) == 1:
                return node
    return None


def _parse_card(a_tag) -> Optional[Listing]:
    href = a_tag.get("href", "")
    if not href or "/en/amsterdam/" not in href:
        return None

    url = BASE_URL + href if href.startswith("/") else href
    listing_id = href.strip("/").split("/")[-1]

    card = _find_card(a_tag)
    if card is None:
        return None

    full_text = card.get_text(" ", strip=True)

    # Skip rented listings
    first_word = full_text.split()[0].lower() if full_text else ""
    if first_word in _SKIP_STATUSES:
        return None

    # Title: the address link text (not the status link)
    title = ""
    for lnk in card.find_all("a", href=_HREF_PATTERN):
        t = lnk.get_text(strip=True)
        if t and t.lower() not in {"rented", "under option", "for rent", "available"}:
            title = t
            break

    # Price: "€ 2.250 p.m." — Dutch dot = thousands
    price = None
    price_match = re.search(r"€\s*([\d.]+)", full_text)
    if price_match:
        raw = price_match.group(1).replace(".", "")
        price = int(raw) if raw.isdigit() else None

    # m2: "69m²"
    m2 = None
    m2_match = re.search(r"(\d+)\s*m\s*[²2]", full_text, re.IGNORECASE)
    if m2_match:
        m2 = int(m2_match.group(1))

    # Bedrooms: "2 bedr"
    bedrooms = None
    bed_match = re.search(r"(\d+)\s*bedr(?:ooms?)?", full_text, re.IGNORECASE)
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
        source="Amsterdam Housing",
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

        soup = BeautifulSoup(page.content(), "lxml")

        # Deduplicate hrefs; process each unique listing once
        seen_hrefs: set = set()
        a_tags = []
        for a in soup.find_all("a", href=_HREF_PATTERN):
            href = a.get("href", "")
            if href and href not in seen_hrefs:
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
