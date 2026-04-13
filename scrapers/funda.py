"""Funda scraper — gebruikt Playwright (zware JS + anti-bot beveiliging)."""

import re
import time
from typing import List
from playwright.sync_api import Page
from scrapers.base import Listing, parse_price, safe_int

BASE_URL = "https://www.funda.nl"
SEARCH_URL = (
    f"{BASE_URL}/zoeken/huur"
    "?selected_area=%5B%22amsterdam%22%5D"
    "&price=%22-2400%22"
    "&rooms=%223-%22"  # 3+ kamers = 2+ slaapkamers
)


def _parse_container(container) -> Listing:
    """Parseer één listing-container (BeautifulSoup tag)."""
    link_tag = container.select_one('a[href*="/detail/"]')
    href = link_tag["href"] if link_tag else ""
    url = BASE_URL + href if href.startswith("/") else href
    listing_id = href.strip("/").split("/")[-1] if href else url

    title_tag = container.select_one("span.truncate")
    title = title_tag.get_text(strip=True) if title_tag else ""

    # Locatie: "1034 BM Amsterdam"
    truncate_divs = container.find_all("div", class_=lambda c: c and "truncate" in c)
    postcode = ""
    price = None
    for td in truncate_divs:
        text = td.get_text(strip=True)
        if re.match(r"\d{4}\s?[A-Z]{2}", text):
            pc_match = re.match(r"(\d{4})", text)
            if pc_match:
                postcode = pc_match.group(1)
        elif "/maand" in text:
            price = parse_price(text)

    # m² en kamers uit de <li>-items
    li_items = container.select("li")
    m2 = None
    rooms = None
    for li in li_items:
        text = li.get_text(strip=True)
        if "m²" in text:
            m2 = safe_int(text)
        elif re.fullmatch(r"\d+", text):
            rooms = int(text)

    bedrooms = rooms if rooms else None

    return Listing(
        id=listing_id,
        url=url,
        source="Funda",
        title=title,
        price=price,
        bedrooms=bedrooms,
        m2=m2,
        postcode=postcode,
    )


def scrape(page: Page) -> List[Listing]:
    """Scrape Funda listings. Verwacht een open Playwright page-object."""
    from bs4 import BeautifulSoup

    all_listings = []
    seen_ids = set()

    for page_num in range(1, 11):  # max 10 pagina's (~150 listings)
        url = SEARCH_URL + f"&search_result={page_num}"
        page.goto(url, timeout=30000)
        time.sleep(7)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(3)

        soup = BeautifulSoup(page.content(), "lxml")
        containers = [
            d for d in soup.find_all("div")
            if "@container" in " ".join(d.get("class", []))
            and "border-b" in " ".join(d.get("class", []))
        ]

        page_listings = []
        for container in containers:
            link_tag = container.select_one('a[href*="/detail/"]')
            if not link_tag:
                continue
            try:
                listing = _parse_container(container)
                if listing.id not in seen_ids:
                    seen_ids.add(listing.id)
                    page_listings.append(listing)
            except Exception:
                pass

        if not page_listings:
            break  # geen nieuwe listings op deze pagina → stop

        all_listings.extend(page_listings)

    return all_listings
