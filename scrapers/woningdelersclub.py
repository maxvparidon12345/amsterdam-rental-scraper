"""Woning Delers Club scraper.

NOTE: Woning Delers Club (woningdelersclub.nl) is a matchmaking platform
with no publicly accessible property listings. Properties are only shown
to registered users after a manual matching process by their agents.
This scraper always returns an empty list.
"""
from typing import List
from scrapers.base import Listing


def scrape() -> List[Listing]:
    return []
