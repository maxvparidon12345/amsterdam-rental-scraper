"""Hoofdscript — scrape, filter, dedupliceer, stuur e-mail."""

import json
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

from scrapers import funda
from filters import apply_filters
from notifier import send_alert

SEEN_FILE = Path("seen.json")

# Playwright scrapers: tuples van (naam, scrape-functie)
PLAYWRIGHT_SCRAPERS = [
    ("Funda", funda.scrape),
    # Voeg hier nieuwe Playwright-scrapers toe, bijv.:
    # ("Pararius", pararius.scrape),
]

# requests+BS4 scrapers: tuples van (naam, scrape-functie)
REQUESTS_SCRAPERS = [
    # Voeg hier nieuwe requests-scrapers toe, bijv.:
    # ("Vesteda", vesteda.scrape),
]


def load_seen() -> set:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def save_seen(seen: set) -> None:
    SEEN_FILE.write_text(json.dumps(sorted(seen), indent=2))


def run_playwright_scrapers(headless: bool) -> list:
    listings = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        for name, scrape_fn in PLAYWRIGHT_SCRAPERS:
            try:
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    )
                )
                page = context.new_page()
                page.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                )
                results = scrape_fn(page)
                print(f"{name}: {len(results)} listings")
                listings.extend(results)
                context.close()
            except Exception as e:
                print(f"[FOUT] {name}: {e}", file=sys.stderr)
        browser.close()
    return listings


def run_requests_scrapers() -> list:
    listings = []
    for name, scrape_fn in REQUESTS_SCRAPERS:
        try:
            results = scrape_fn()
            print(f"{name}: {len(results)} listings")
            listings.extend(results)
        except Exception as e:
            print(f"[FOUT] {name}: {e}", file=sys.stderr)
    return listings


def main():
    seen = load_seen()

    headless = os.environ.get("PLAYWRIGHT_HEADLESS", "false").lower() == "true"

    all_listings = []
    all_listings.extend(run_playwright_scrapers(headless))
    all_listings.extend(run_requests_scrapers())

    filtered = apply_filters(all_listings)
    new_listings = [l for l in filtered if l.id not in seen]

    print(
        f"Totaal: {len(all_listings)} → {len(filtered)} na filter "
        f"→ {len(new_listings)} nieuw"
    )

    if new_listings:
        send_alert(new_listings)
        for listing in new_listings:
            seen.add(listing.id)
        save_seen(seen)
    else:
        print("Geen nieuwe listings gevonden.")


if __name__ == "__main__":
    main()
