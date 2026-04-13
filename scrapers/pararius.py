"""Pararius scraper — gebruikt Playwright (site blokkeert gewone requests)."""

import re
from typing import List
from playwright.sync_api import Page
from scrapers.base import Listing, parse_price, safe_int

BASE_URL = "https://www.pararius.nl"
SEARCH_URL = f"{BASE_URL}/huurwoningen/amsterdam/0-2400/2-slaapkamers"


def _parse_listing(item) -> Listing:
    """Parseer één listing-sectie (BeautifulSoup tag)."""
    title_tag = item.select_one(".listing-search-item__link--title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    href = title_tag["href"] if title_tag and title_tag.get("href") else ""
    url = BASE_URL + href if href.startswith("/") else href
    listing_id = href.strip("/").split("/")[-1] if href else url

    price_tag = item.select_one(".listing-search-item__price-main")
    price = parse_price(price_tag.get_text()) if price_tag else None

    location_tag = item.select_one(".listing-search-item__sub-title")
    location_text = location_tag.get_text(strip=True) if location_tag else ""
    # Format: "1031 JH Amsterdam (Wijk)"
    postcode = ""
    neighborhood = ""
    if location_text:
        pc_match = re.match(r"(\d{4}\s?[A-Z]{2})", location_text)
        if pc_match:
            postcode = pc_match.group(1).replace(" ", "")[:4]
        wijk_match = re.search(r"\(([^)]+)\)", location_text)
        if wijk_match:
            neighborhood = wijk_match.group(1)

    m2_tag = item.select_one(".illustrated-features__item--surface-area")
    m2 = safe_int(m2_tag.get_text()) if m2_tag else None

    rooms_tag = item.select_one(".illustrated-features__item--number-of-rooms")
    rooms_text = rooms_tag.get_text(strip=True) if rooms_tag else ""
    # "3 kamers" → 3 rooms total; bedrooms ≈ rooms - 1
    rooms_num = safe_int(rooms_text)
    bedrooms = max(rooms_num - 1, 1) if rooms_num else None

    return Listing(
        id=listing_id,
        url=url,
        source="Pararius",
        title=title,
        price=price,
        bedrooms=bedrooms,
        m2=m2,
        neighborhood=neighborhood,
        postcode=postcode,
    )


def scrape(page: Page) -> List[Listing]:
    """Scrape Pararius listings. Verwacht een open Playwright page-object."""
    from bs4 import BeautifulSoup

    listings = []
    url = SEARCH_URL

    while url:
        page.goto(url, timeout=30000)
        try:
            page.wait_for_selector("section.listing-search-item", timeout=12000)
        except Exception:
            break

        soup = BeautifulSoup(page.content(), "lxml")
        items = soup.select("section.listing-search-item")
        for item in items:
            # Sla promotie-/banner-items over
            if "listing-search-item--for-rent" not in " ".join(item.get("class", [])):
                continue
            try:
                listings.append(_parse_listing(item))
            except Exception:
                pass

        # Volgende pagina
        next_link = soup.select_one('a[rel="next"]')
        if next_link and next_link.get("href"):
            href = next_link["href"]
            url = BASE_URL + href if href.startswith("/") else href
        else:
            url = None

    return listings
