from dataclasses import dataclass, field
from typing import Optional
import re
import random

HEADERS_POOL = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
]


def random_headers() -> dict:
    return random.choice(HEADERS_POOL)


def safe_int(value: str) -> Optional[int]:
    """Extract first integer from a string, or return None."""
    if not value:
        return None
    cleaned = re.sub(r"[^\d]", "", str(value))
    return int(cleaned) if cleaned else None


def parse_price(text: str) -> Optional[int]:
    """Parse a Dutch price string like '€ 1.850 p/m' → 1850."""
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", str(text))
    return int(digits) if digits else None


@dataclass
class Listing:
    id: str
    url: str
    source: str
    title: str = ""
    price: Optional[int] = None        # per month in euros
    bedrooms: Optional[int] = None
    m2: Optional[int] = None
    neighborhood: str = ""
    postcode: str = ""
    available_from: str = ""
    extra: dict = field(default_factory=dict)

    def summary(self) -> str:
        parts = [f"[{self.source}] {self.title}"]
        if self.price:
            parts.append(f"€{self.price}/mnd")
        if self.bedrooms:
            parts.append(f"{self.bedrooms} slaapkamers")
        if self.m2:
            parts.append(f"{self.m2} m²")
        if self.neighborhood:
            parts.append(self.neighborhood)
        if self.postcode:
            parts.append(self.postcode)
        if self.available_from:
            parts.append(f"Beschikbaar: {self.available_from}")
        parts.append(self.url)
        return "\n".join(parts)
