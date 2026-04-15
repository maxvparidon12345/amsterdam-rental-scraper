"""Amstelland Makelaars scraper — requests + BeautifulSoup.

Listings page: https://www.amstellandmakelaars.nl/woningaanbod/huur
Server-side rendered. Listing cards contain an <a href="/woningaanbod/huur/...">
with an h3 (address + postcode) and text elements for price and property details.

Detail format: "Appartement <rooms> <bedrooms> <bathrooms> <area> m²"
Price format:  "€ 2.450,- /mnd"
"""

import re
import time
import random
from typing import List, Optional
import requests
from bs4 import BeautifulSoup
from scrapers.base import Listing, parse_price, safe_int, random_headers

BASE_URL = "https://www.amstellandmakelaars.nl"
SEARCH_URL = f"{BASE_URL}/woningaanbod/huur"

EXCLUDE_PHRASES = [
    "geen delers", "niet geschikt voor delers", "geen woningdelers",
    "no sharers", "not suitable for sharing", "geen studenten en woningdelers",
]


def _is_excluded(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in EXCLUDE_PHRASES)


def _find_card(a_tag, href_pattern: re.Pattern):
    """Walk up the DOM tree to find the smallest ancestor that contains
    exactly one unique listing link, plus price and m² info."""
    node = a_tag
    for _ in range(8):
        node = node.parent
        if node is None:
            break
        t = node.get_text()
        if "€" in t and "m²" in t:
            unique = {
                lnk["href"].split("?")[0]
                for lnk in node.find_all("a", href=href_pattern)
            }
            if len(unique) == 1:
                return node
    return None


def _parse_listing(a_tag, href_pattern: re.Pattern) -> Optional[Listing]:
    href = a_tag.get("href", "").split("?")[0]
    if "/woningaanbod/huur/" not in href:
        return None

    card = _find_card(a_tag, href_pattern)
    if card is None:
        return None

    url = BASE_URL + href if href.startswith("/") else href
    listing_id = href.strip("/").split("/")[-1]

    full_text = card.get_text(" ", strip=True)

    # Skip already-rented listings
    if "verhuurd" in full_text.lower():
        return None

    # Skip listings that explicitly exclude delers/sharers
    if _is_excluded(full_text):
        return None

    # h3 contains: "Street Nr PostcodeCity€ Price/mnd"
    h3 = card.find("h3")
    h3_text = h3.get_text(" ", strip=True) if h3 else full_text

    # Postcode
    postcode = ""
    pc_match = re.search(r"(\d{4})\s?[A-Z]{2}", h3_text)
    if pc_match:
        postcode = pc_match.group(0)[:4]

    # Title: address portion before the postcode
    title = re.split(r"\d{4}\s?[A-Z]{2}", h3_text)[0].strip() if pc_match else ""

    # Price — Dutch format: "€ 2.450,- /mnd" → 2450
    price = None
    price_match = re.search(r"€\s*([\d.]+)[,\-]", h3_text)
    if price_match:
        raw = price_match.group(1).replace(".", "")
        price = int(raw) if raw.isdigit() else None

    # Area
    m2 = None
    m2_match = re.search(r"(\d+)\s*m²", full_text)
    if m2_match:
        m2 = int(m2_match.group(1))

    # Bedrooms: "Appartement <rooms> <bedrooms> <bathrooms> <m²>"
    bedrooms = None
    detail_match = re.search(
        r"(?:Appartement|Woning|Studio|Penthouse|Huis)\s+(\d+)\s+(\d+)",
        full_text, re.IGNORECASE,
    )
    if detail_match:
        bedrooms = int(detail_match.group(2))
    else:
        kamers_match = re.search(r"(\d+)\s*kamers?", full_text.lower())
        if kamers_match:
            rooms = int(kamers_match.group(1))
            bedrooms = max(rooms - 1, 1)

    return Listing(
        id=listing_id,
        url=url,
        source="Amstelland Makelaars",
        title=title,
        price=price,
        bedrooms=bedrooms,
        m2=m2,
        postcode=postcode,
    )


def scrape() -> List[Listing]:
    listings = []
    seen_ids: set = set()
    href_pattern = re.compile(r"/woningaanbod/huur/")

    for page_num in range(1, 6):
        url = SEARCH_URL if page_num == 1 else f"{SEARCH_URL}?p={page_num}"
        try:
            resp = requests.get(url, headers=random_headers(), timeout=15)
            resp.raise_for_status()
        except Exception:
            break

        soup = BeautifulSoup(resp.text, "lxml")

        # Deduplicate links first, then parse each unique listing
        seen_hrefs: set = set()
        a_tags = []
        for a in soup.find_all("a", href=href_pattern):
            href = a.get("href", "").split("?")[0]
            if href and href not in seen_hrefs:
                seen_hrefs.add(href)
                a_tags.append(a)

        page_listings = []
        for a_tag in a_tags:
            try:
                listing = _parse_listing(a_tag, href_pattern)
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
